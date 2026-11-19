"""Deterministic production drafting, canonical RFC-8785 manifests, and factual validation.

Zero external AI or LLM calls — even when OPENAI_API_KEY exists in the environment.
All source text and human interpretations are treated as inert literal data.
"""
import hashlib
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any

from ..models.ledger import decimal_string
from .intake_service import canonical_payload

MANIFEST_VERSION = "argus-manifest-v1"
DRAFTING_CODE_VERSION = "argus-drafter-v1"
VALIDATOR_VERSION = "argus-factual-validator-v1"
PAYLOAD_DOMAIN_PREFIX = b"argus.review_package.v1\x00"
ENVELOPE_DOMAIN_PREFIX = b"argus.approval_envelope.v1\x00"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_payload_digest(narrative_sha256: str, manifest_sha256: str) -> str:
    """Domain-separated payload digest over ordered component SHA-256 hex digests."""
    blob = (
        PAYLOAD_DOMAIN_PREFIX
        + narrative_sha256.encode("ascii")
        + b"\x00"
        + manifest_sha256.encode("ascii")
    )
    return sha256_hex(blob)


def compute_envelope_digest(envelope: dict[str, Any]) -> str:
    """Domain-separated digest over canonical RFC-8785 approval envelope."""
    return sha256_hex(ENVELOPE_DOMAIN_PREFIX + canonical_payload(envelope))


def _exact_sum_strings(amount_strings: list[str]) -> str:
    if not amount_strings:
        return "0"
    values = [Decimal(s) for s in amount_strings]
    lowest_exp = min(v.as_tuple().exponent for v in values)
    highest_digit = max(v.adjusted() for v in values)
    with localcontext() as ctx:
        ctx.prec = max(48, highest_digit - lowest_exp + len(str(len(values))) + 8)
        total = sum(values, Decimal("0"))
    return decimal_string(total)


@dataclass(frozen=True)
class DraftPackage:
    narrative_bytes: bytes
    manifest_bytes: bytes
    narrative_sha256: str
    manifest_sha256: str
    payload_digest: str
    manifest: dict[str, Any]
    validation: dict[str, Any]


def build_draft_package(
    *,
    case_meta: dict[str, Any],
    dataset_meta: dict[str, Any],
    snapshot_meta: dict[str, Any],
    reconciliation: dict[str, Any],
    analysis_result: dict[str, Any],
    cited_records: list[dict[str, Any]],
    source_files: list[dict[str, Any]],
    observations: list[dict[str, Any]] | None = None,
    dispositions: list[dict[str, Any]] | None = None,
    analyst_interpretations: list[dict[str, Any]] | None = None,
    material_contributors: list[str] | None = None,
    parent_artifact_id: str | None = None,
    revision_number: int = 1,
) -> DraftPackage:
    """Build deterministic Five Ws + How narrative + canonical RFC-8785 manifest."""
    observations = list(observations or [])
    dispositions = list(dispositions or [])
    analyst_interpretations = list(analyst_interpretations or [])
    contributors = sorted(set(material_contributors or []))

    records_by_ext: dict[tuple[str, str], dict[str, Any]] = {
        (rec["kind"], rec["external_id"]): rec for rec in cited_records
    }
    tx_records = [rec for rec in cited_records if rec["kind"] == "transactions"]
    entity_records = sorted(
        [rec for rec in cited_records if rec["kind"] == "entities"],
        key=lambda r: r["external_id"],
    )
    account_records = sorted(
        [rec for rec in cited_records if rec["kind"] == "accounts"],
        key=lambda r: r["external_id"],
    )

    findings = analysis_result.get("findings") or []
    coverage = analysis_result.get("coverage") or {}

    # Collect cited event IDs from findings (or all cited tx records if manual scope)
    cited_event_ids = sorted({
        eid
        for f in findings
        for eid in f.get("cited_event_ids", [])
        if ("transactions", eid) in records_by_ext
    })
    if not cited_event_ids and tx_records:
        cited_event_ids = sorted(r["external_id"] for r in tx_records)

    cited_txs = [records_by_ext[("transactions", eid)] for eid in cited_event_ids]

    # Exact totals grouped by currency from cited events only
    amounts_by_currency: dict[str, list[str]] = {}
    event_ids_by_currency: dict[str, list[str]] = {}
    event_times: list[str] = []
    for rec in cited_txs:
        p = rec["payload"]
        cur = p["currency"]
        amounts_by_currency.setdefault(cur, []).append(p["amount"])
        event_ids_by_currency.setdefault(cur, []).append(rec["external_id"])
        event_times.append(p["event_at"])

    totals_by_currency = {
        cur: _exact_sum_strings(vals) for cur, vals in sorted(amounts_by_currency.items())
    }
    sorted_times = sorted(event_times)

    # Source-derived geographic indicators ONLY — never fabricate jurisdiction/country
    countries = sorted({
        rec["payload"]["country"].strip()
        for rec in entity_records
        if isinstance(rec["payload"].get("country"), str) and rec["payload"]["country"].strip()
    })

    # Five Ws + How sections (pure literal data — no template interpolation of untrusted text)
    entity_labels = [f"{r['external_id']} ({r['payload'].get('name', 'unnamed')})" for r in entity_records]
    account_labels = [f"{r['external_id']} [{r['payload'].get('account_type', 'UNKNOWN')}/{r['payload'].get('currency', '?')}]" for r in account_records]
    who_text = (
        f"Subject: {case_meta['subject_id']}. "
        f"Entities: {', '.join(entity_labels) if entity_labels else 'None cited'}. "
        f"Accounts: {', '.join(account_labels) if account_labels else 'None cited'}."
    )

    if totals_by_currency:
        totals_desc = "; ".join(
            f"{cur} {total} across {len(event_ids_by_currency[cur])} cited event(s)"
            for cur, total in totals_by_currency.items()
        )
    else:
        totals_desc = "No cited transaction events in current draft scope"

    finding_types = sorted({f.get("typology", "UNKNOWN") for f in findings})
    what_text = (
        f"Observed patterns within declared scope: {', '.join(finding_types) if finding_types else 'None qualifying'}. "
        f"Cited volume: {totals_desc}."
    )

    where_text = (
        f"Source-recorded country indicators: {', '.join(countries)}."
        if countries
        else "Not provided in source records."
    )

    when_text = (
        f"{sorted_times[0]} to {sorted_times[-1]} (UTC, derived strictly from {len(cited_txs)} cited event(s))."
        if sorted_times
        else "No cited event timestamps available."
    )

    why_lines: list[str] = []
    if findings:
        for f in findings:
            why_lines.append(
                f"- Finding {f['finding_id']} [{f['typology']}/{f.get('channel', 'TRANSFER')}/{f.get('mode', '')}]: "
                f"{f['event_count']} event(s) totaling {f['currency']} {f['total_amount']} "
                f"(uncalibrated priority score: {f['uncalibrated_priority_score']})."
            )
    else:
        why_lines.append(
            "- No qualifying heuristic pattern found within the declared scope "
            "(this does not clear a customer)."
        )
    if dispositions:
        for d in dispositions:
            why_lines.append(
                f"- Human disposition on {d['finding_id']}: {d['disposition']} — {d['rationale']}"
                + (f" | Benign alternative: {d['benign_alternative']}" if d.get("benign_alternative") else "")
            )
    if observations:
        for obs in observations:
            verdict = (obs.get("comparison_json") or {}).get("verdict", "UNSCOPED")
            why_lines.append(
                f"- Scoped observation {obs['source_ref']} ({obs['source_kind']}): comparison status {verdict}."
            )
    why_text = "\n".join(why_lines)

    how_lines = [
        f"Analysis code: {analysis_result.get('analysis_code_version', 'unknown')}; "
        f"policy: {(analysis_result.get('policy') or {}).get('policy_id', 'unknown')}@"
        f"{(analysis_result.get('policy') or {}).get('policy_version', 'unknown')}.",
        f"Source reconciliation status: {reconciliation.get('status', 'UNVERIFIED')} "
        f"({reconciliation.get('reason', 'not_specified')}).",
        f"Analysis coverage: {coverage.get('status', 'NOT_REPORTED')} "
        f"(considered={coverage.get('considered_events', 0)}, "
        f"excluded={coverage.get('excluded_events_count', 0)}, "
        f"limitations={len(coverage.get('limitations') or [])}).",
        "Note: Graph paths and transaction windows represent observed record relationships only; "
        "they do not establish identity of fungible funds, criminal intent, or an official regulatory filing.",
    ]
    how_text = "\n".join(how_lines)

    # Typed factual claims with direct record citations & verifiable derivations
    factual_claims: list[dict[str, Any]] = []
    claim_seq = 1
    for cur, total in totals_by_currency.items():
        cur_eids = sorted(event_ids_by_currency[cur])
        factual_claims.append({
            "claim_id": f"CLM-{claim_seq:03d}",
            "claim_type": "OBSERVED_FACT",
            "section": "WHAT",
            "statement": f"Cited {cur} events total {total} across {len(cur_eids)} event(s).",
            "cited_event_ids": cur_eids,
            "cited_record_ids": [records_by_ext[("transactions", e)]["record_id"] for e in cur_eids],
            "derivation": {
                "operation": "SUM_BY_CURRENCY",
                "currency": cur,
                "expected_total": total,
                "expected_count": len(cur_eids),
            },
        })
        claim_seq += 1

    for f in findings:
        f_eids = sorted(e for e in f.get("cited_event_ids", []) if ("transactions", e) in records_by_ext)
        if not f_eids:
            continue
        factual_claims.append({
            "claim_id": f"CLM-{claim_seq:03d}",
            "claim_type": "OBSERVED_FACT",
            "section": "WHY",
            "statement": (
                f"Finding {f['finding_id']} ({f['typology']} {f.get('mode', '')}) cites {len(f_eids)} "
                f"{f['currency']} event(s)."
            ),
            "cited_event_ids": f_eids,
            "cited_record_ids": [records_by_ext[("transactions", e)]["record_id"] for e in f_eids],
            "derivation": {
                "operation": "COUNT",
                "expected_count": len(f_eids),
            },
        })
        claim_seq += 1

    # Explicitly separate analyst interpretations (labelled human judgment)
    labelled_interpretations = [
        {
            "interpretation_id": item.get("interpretation_id") or f"INT-{idx:03d}",
            "claim_type": "ANALYST_INTERPRETATION",
            "author_id": item.get("author_id", "unknown"),
            "text": str(item.get("text", "")),
        }
        for idx, item in enumerate(analyst_interpretations, 1)
        if str(item.get("text", "")).strip()
    ]

    interp_block = (
        "\n".join(f"- [{i['interpretation_id']} | Author: {i['author_id']}] {i['text']}" for i in labelled_interpretations)
        if labelled_interpretations
        else "None recorded."
    )

    narrative_text = "\n\n".join([
        "=== ARGUS INVESTIGATION REVIEW PACKAGE — NOT FILED ===",
        "Status: REVIEWED / DRAFT PACKAGE — NOT SUBMITTED TO FINCEN OR ANY REGULATOR",
        f"Case ID: {case_meta['id']} | Revision: {revision_number} | Dataset Generation: {snapshot_meta['generation']}",
        f"WHO (Observed Facts):\n{who_text}",
        f"WHAT (Observed Facts):\n{what_text}",
        f"WHERE (Source-Derived Geography):\n{where_text}",
        f"WHEN (Cited Event Timeframe):\n{when_text}",
        f"WHY (Indicators, Dispositions & Scoped Observations):\n{why_text}",
        f"HOW (Scope, Mechanics, Coverage & Reconciliation):\n{how_text}",
        f"ANALYST INTERPRETATION (Human Judgment — Not Machine-Verified Fact):\n{interp_block}",
        f"CITED EVENT IDS ({len(cited_event_ids)}):\n{', '.join(cited_event_ids) if cited_event_ids else 'None'}",
        "=== END REVIEW PACKAGE — NOT FILED ===",
    ]) + "\n"
    narrative_bytes = narrative_text.encode("utf-8")
    narrative_hash = sha256_hex(narrative_bytes)

    canonical_cited_records = sorted(
        [
            {
                "record_id": r["record_id"],
                "kind": r["kind"],
                "external_id": r["external_id"],
                "digest": r["digest"],
                "source_file_id": r["source_file_id"],
                "row_number": r["row_number"],
                "payload": r["payload"],
            }
            for r in cited_records
        ],
        key=lambda r: (r["kind"], r["external_id"], r["record_id"]),
    )
    canonical_source_files = sorted(
        [
            {
                "source_file_id": sf["id"],
                "kind": sf["kind"],
                "sha256": sf["sha256"],
                "size": sf["size"],
                "extract_id": sf.get("extract_id"),
                "filename": sf.get("filename"),
            }
            for sf in source_files
        ],
        key=lambda sf: (sf["kind"], sf["source_file_id"]),
    )

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "filing_status": "REVIEW_PACKAGE_NOT_FILED",
        "versions": {
            "drafter_version": DRAFTING_CODE_VERSION,
            "validator_version": VALIDATOR_VERSION,
            "analysis_code_version": analysis_result.get("analysis_code_version"),
            "policy": analysis_result.get("policy"),
        },
        "case": {
            "case_id": case_meta["id"],
            "title": case_meta["title"],
            "subject_id": case_meta["subject_id"],
            "case_version": case_meta["version"],
            "revision_number": revision_number,
            "parent_artifact_id": parent_artifact_id,
            "material_contributors": contributors,
        },
        "evidence_scope": {
            "dataset_id": dataset_meta["id"],
            "dataset_namespace": dataset_meta["namespace"],
            "snapshot_id": snapshot_meta["id"],
            "snapshot_generation": snapshot_meta["generation"],
            "reconciliation": reconciliation,
            "analysis_scope": analysis_result.get("scope"),
            "coverage": coverage,
        },
        "sections": {
            "who": who_text,
            "what": what_text,
            "where": where_text,
            "when": when_text,
            "why": why_text,
            "how": how_text,
        },
        "totals_by_currency": totals_by_currency,
        "findings": findings,
        "dispositions": dispositions,
        "observations": observations,
        "factual_claims": factual_claims,
        "analyst_interpretations": labelled_interpretations,
        "cited_records": canonical_cited_records,
        "source_files": canonical_source_files,
        "narrative_sha256": narrative_hash,
    }

    manifest_bytes = canonical_payload(manifest)
    manifest_hash = sha256_hex(manifest_bytes)
    payload_digest = compute_payload_digest(narrative_hash, manifest_hash)
    validation = validate_draft_package(narrative_bytes, manifest_bytes, expected_payload_digest=payload_digest)

    return DraftPackage(
        narrative_bytes=narrative_bytes,
        manifest_bytes=manifest_bytes,
        narrative_sha256=narrative_hash,
        manifest_sha256=manifest_hash,
        payload_digest=payload_digest,
        manifest=manifest,
        validation=validation,
    )


def validate_draft_package(
    narrative_bytes: bytes,
    manifest_bytes: bytes,
    *,
    expected_payload_digest: str | None = None,
) -> dict[str, Any]:
    """Deterministic validator verifying citations, exact Decimal math, and non-filing integrity."""
    import json

    errors: list[str] = []
    narrative_hash = sha256_hex(narrative_bytes)
    manifest_hash = sha256_hex(manifest_bytes)
    payload_digest = compute_payload_digest(narrative_hash, manifest_hash)

    if expected_payload_digest and payload_digest != expected_payload_digest:
        errors.append("Payload digest mismatch against narrative and manifest components")

    try:
        narrative_text = narrative_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "status": "FAILED",
            "passed": False,
            "checked_count": 0,
            "eligible_count": 0,
            "validator_version": VALIDATOR_VERSION,
            "artifact_digest": payload_digest,
            "errors": ["Narrative bytes are not valid UTF-8"],
        }

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {
            "status": "FAILED",
            "passed": False,
            "checked_count": 0,
            "eligible_count": 0,
            "validator_version": VALIDATOR_VERSION,
            "artifact_digest": payload_digest,
            "errors": ["Manifest bytes are not valid JSON"],
        }

    # Verify RFC-8785 canonical byte stability
    try:
        recanon = canonical_payload(manifest)
        if recanon != manifest_bytes:
            errors.append("Manifest bytes are not canonical RFC-8785")
    except Exception:
        errors.append("Manifest contains non-canonical or float values")

    if manifest.get("narrative_sha256") != narrative_hash:
        errors.append("Manifest narrative_sha256 does not match narrative bytes")

    if manifest.get("filing_status") != "REVIEW_PACKAGE_NOT_FILED":
        errors.append("Manifest must explicitly declare REVIEW_PACKAGE_NOT_FILED")

    if "NOT FILED" not in narrative_text or "Filed pursuant to" in narrative_text:
        errors.append("Narrative missing non-filing disclosure or contains false filing claim")

    sections = manifest.get("sections") or {}
    for key in ("who", "what", "where", "when", "why", "how"):
        val = sections.get(key)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"Missing required section: {key.upper()}")

    # Verify every factual claim against embedded cited_records with exact Decimal arithmetic
    cited_map: dict[tuple[str, str], dict] = {
        (rec["kind"], rec["external_id"]): rec
        for rec in (manifest.get("cited_records") or [])
    }
    claims = manifest.get("factual_claims") or []
    checked = 0
    for claim in claims:
        checked += 1
        cid = claim.get("claim_id", "unknown")
        eids = claim.get("cited_event_ids") or []
        missing = [e for e in eids if ("transactions", e) not in cited_map]
        if missing:
            errors.append(f"Claim {cid} references uncited event(s): {missing}")
            continue
        deriv = claim.get("derivation") or {}
        op = deriv.get("operation")
        if op == "SUM_BY_CURRENCY":
            cur = deriv.get("currency")
            amounts = []
            for e in eids:
                payload = cited_map[("transactions", e)]["payload"]
                if payload.get("currency") != cur:
                    errors.append(f"Claim {cid} mixes currency {payload.get('currency')} into {cur} sum")
                else:
                    amounts.append(payload["amount"])
            recomputed = _exact_sum_strings(amounts)
            if recomputed != deriv.get("expected_total"):
                errors.append(f"Claim {cid} total mismatch: claimed {deriv.get('expected_total')}, computed {recomputed}")
            if len(amounts) != deriv.get("expected_count"):
                errors.append(f"Claim {cid} count mismatch: claimed {deriv.get('expected_count')}, computed {len(amounts)}")
        elif op == "COUNT":
            if len(eids) != deriv.get("expected_count"):
                errors.append(f"Claim {cid} count mismatch: claimed {deriv.get('expected_count')}, computed {len(eids)}")

    passed = len(errors) == 0
    return {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "checked_count": checked,
        "eligible_count": len(claims),
        "validator_version": VALIDATOR_VERSION,
        "artifact_digest": payload_digest,
        "errors": errors,
    }
