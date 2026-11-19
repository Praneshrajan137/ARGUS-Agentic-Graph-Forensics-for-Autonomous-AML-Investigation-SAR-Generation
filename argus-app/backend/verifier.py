"""Standalone offline verifier for ARGUS reviewed narrative + manifest + approval packages.

Usage:
    python -m backend.verifier --package <package_dir> [--source-dir <original_csv_dir>]

Verifies:
  1. Exact UTF-8 narrative SHA-256, RFC-8785 canonical manifest SHA-256, and domain-separated payload_digest.
  2. Approval envelope digest, payload_digest binding, and reviewer independence against material contributors.
  3. All factual claim citations and exact Decimal calculations against embedded cited records.
  4. Optional original source-file provenance (when --source-dir is supplied); explicitly reports
     NOT_CHECKED_ORIGINAL_FILES_NOT_SUPPLIED when original files are absent.

Integrity hashes verify tamper-evidence of supplied bytes, not real-world truth or trusted authorship.
"""
import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

from .models.ledger import INPUT_MODELS
from .services.drafting_service import (
    compute_envelope_digest,
    compute_payload_digest,
    sha256_hex,
    validate_draft_package,
)
from .services.intake_service import row_hash


def verify_package_bytes(
    narrative_bytes: bytes,
    manifest_bytes: bytes,
    approval_envelope: dict[str, Any] | None = None,
    *,
    expected_payload_digest: str | None = None,
    expected_envelope_digest: str | None = None,
    source_files_by_id: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Verify package integrity, citations, exact calculations, approval, and optional provenance."""
    errors: list[str] = []
    narrative_hash = sha256_hex(narrative_bytes)
    manifest_hash = sha256_hex(manifest_bytes)
    computed_payload_digest = compute_payload_digest(narrative_hash, manifest_hash)

    validation = validate_draft_package(
        narrative_bytes,
        manifest_bytes,
        expected_payload_digest=expected_payload_digest or computed_payload_digest,
    )
    if not validation["passed"]:
        errors.extend(validation["errors"])

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception:
        manifest = {}

    # Approval envelope verification
    approval_status = "NOT_SUPPLIED"
    if approval_envelope is not None:
        approval_status = "VERIFIED"
        computed_env_digest = compute_envelope_digest(approval_envelope)
        if expected_envelope_digest and computed_env_digest != expected_envelope_digest:
            errors.append("Approval envelope digest mismatch")
            approval_status = "FAILED"
        if approval_envelope.get("payload_digest") != computed_payload_digest:
            errors.append("Approval envelope payload_digest does not match package payload_digest")
            approval_status = "FAILED"
        reviewer_id = approval_envelope.get("reviewer_id")
        manifest_contributors = set((manifest.get("case") or {}).get("material_contributors") or [])
        envelope_contributors = set(approval_envelope.get("material_contributors") or [])
        all_contributors = manifest_contributors | envelope_contributors
        if not reviewer_id or reviewer_id in all_contributors:
            errors.append("Reviewer independence violated: reviewer is listed as a material contributor")
            approval_status = "FAILED"
        if approval_envelope.get("decision") != "APPROVED":
            errors.append(f"Approval envelope decision is {approval_envelope.get('decision')!r}, not APPROVED")
            approval_status = "FAILED"

    # Original file provenance verification (explicitly reports limit if files not supplied)
    if source_files_by_id is None:
        provenance_status = "NOT_CHECKED_ORIGINAL_FILES_NOT_SUPPLIED"
        provenance_checked = 0
    else:
        provenance_status = "VERIFIED"
        provenance_checked = 0
        manifest_sfs = {sf["source_file_id"]: sf for sf in (manifest.get("source_files") or [])}
        parsed_rows_cache: dict[str, dict[int, dict]] = {}

        for sf_id, sf_meta in manifest_sfs.items():
            raw = source_files_by_id.get(sf_id)
            if raw is None:
                errors.append(f"Original source file missing for source_file_id={sf_id}")
                provenance_status = "FAILED"
                continue
            actual_hash = sha256_hex(raw)
            if actual_hash != sf_meta["sha256"] or len(raw) != sf_meta["size"]:
                errors.append(f"Original source file hash/size mismatch for {sf_id}")
                provenance_status = "FAILED"
                continue
            provenance_checked += 1
            kind = sf_meta["kind"]
            model = INPUT_MODELS[kind]
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
            row_map: dict[int, dict] = {}
            for ordinal, row in enumerate(reader, 1):
                validated = model.model_validate(row)
                payload = validated.model_dump(exclude={"supersedes_hash"})
                row_map[ordinal] = payload
            parsed_rows_cache[sf_id] = row_map

        for rec in (manifest.get("cited_records") or []):
            sf_id = rec["source_file_id"]
            if sf_id not in parsed_rows_cache:
                continue
            raw_row = parsed_rows_cache[sf_id].get(rec["row_number"])
            if raw_row is None:
                errors.append(f"Cited row ordinal {rec['row_number']} missing in source file {sf_id}")
                provenance_status = "FAILED"
                continue
            # Paired double-posting events normalize id -> posting_group_id and posting_leg -> PAIRED
            if raw_row.get("posting_group_id"):
                raw_row = {**raw_row, "id": raw_row["posting_group_id"], "posting_leg": "PAIRED"}
            if row_hash(raw_row) != rec["digest"]:
                errors.append(
                    f"Cited record {rec['kind']}/{rec['external_id']} digest does not match original CSV row {rec['row_number']}"
                )
                provenance_status = "FAILED"

    return {
        "verified": len(errors) == 0,
        "payload_digest": computed_payload_digest,
        "narrative_sha256": narrative_hash,
        "manifest_sha256": manifest_hash,
        "validation_status": validation["status"],
        "claims_checked": validation["checked_count"],
        "approval_status": approval_status,
        "provenance_status": provenance_status,
        "provenance_files_checked": provenance_checked,
        "errors": errors,
        "verification_limits": (
            "Cryptographic hashes verify integrity of supplied bytes and mathematical consistency "
            "with embedded records. They do not independently establish real-world truth or trusted authorship; "
            "independent audit custody and original source verification are operational requirements."
        ),
    }


def verify_package_directory(package_dir: Path, source_dir: Path | None = None) -> dict[str, Any]:
    narrative_bytes = (package_dir / "narrative.txt").read_bytes()
    manifest_bytes = (package_dir / "manifest.json").read_bytes()
    approval_path = package_dir / "approval.json"
    approval_envelope = json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.exists() else None
    meta_path = package_dir / "digests.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    source_map: dict[str, bytes] | None = None
    if source_dir is not None:
        source_map = {}
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        for sf in (manifest.get("source_files") or []):
            candidate = source_dir / f"{sf['source_file_id']}.csv"
            if not candidate.exists() and sf.get("filename"):
                candidate = source_dir / sf["filename"]
            if candidate.exists():
                source_map[sf["source_file_id"]] = candidate.read_bytes()

    return verify_package_bytes(
        narrative_bytes,
        manifest_bytes,
        approval_envelope,
        expected_payload_digest=meta.get("payload_digest"),
        expected_envelope_digest=meta.get("envelope_digest"),
        source_files_by_id=source_map,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline verifier for ARGUS review packages")
    parser.add_argument("--package", required=True, type=Path, help="Path to exported package directory")
    parser.add_argument("--source-dir", required=False, type=Path, help="Optional directory containing authorized original source CSV files")
    args = parser.parse_args(argv)
    report = verify_package_directory(args.package, args.source_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
