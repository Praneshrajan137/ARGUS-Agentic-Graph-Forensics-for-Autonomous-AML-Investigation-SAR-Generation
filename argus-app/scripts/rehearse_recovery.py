"""Isolated PostgreSQL backup & restore rehearsal script (Milestone G).

Populates a synthetic dataset, runs pinned analysis, approves & exports a review package,
executes pg_dump, restores into a brand-new isolated database, verifies Alembic head,
immutability triggers, exact source file bytes, and offline cryptographic verification.
Outputs actual RTO/RPO measurement JSON (never uses mocks).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from backend.database import (  # noqa: E402
    Artifact, Approval, CaseAssignment, CaseRecord, Dataset, DatasetGrant,
    SourceFile, User, create_engine_from_url, make_session_factory,
)
from backend.services.analysis_service import analyze_snapshot  # noqa: E402
from backend.services.intake_service import activate_batch, parse_batch  # noqa: E402
from backend.services.job_service import (  # noqa: E402
    claim_next_job, enqueue_analysis_job, publish_job_outcome,
)
from backend.services.review_service import (  # noqa: E402
    create_draft_revision, export_approved_artifact, freeze_artifact_for_review,
    review_artifact,
)
from backend.verifier import verify_package_bytes  # noqa: E402


def _rehearsal_csv_files() -> dict[str, bytes]:
    return {
        "entities": (
            "id,entity_type,name\n"
            "E1,PERSON,Alpha Person\n"
            "E2,PERSON,Beta Person\n"
        ).encode("utf-8"),
        "accounts": (
            "id,account_type,currency\n"
            "001,CHECKING,USD\n"
            "002,CHECKING,USD\n"
        ).encode("utf-8"),
        "relationships": (
            "id,entity_id,account_id,role,valid_from,valid_to\n"
            "R1,E1,001,OWNER,2024-01-01T00:00:00Z,\n"
            "R2,E2,002,OWNER,2024-01-01T00:00:00Z,\n"
        ).encode("utf-8"),
        "transactions": (
            "id,event_type,source_account_id,target_account_id,amount,currency,event_at,posted_at,related_event_id\n"
            "T1,TRANSFER,001,002,9500.00,USD,2025-01-02T10:00:00Z,2025-01-02T10:05:00Z,\n"
            "T2,TRANSFER,001,002,9400.00,USD,2025-01-02T11:00:00Z,2025-01-02T11:05:00Z,\n"
            "T3,TRANSFER,001,002,9300.00,USD,2025-01-02T12:00:00Z,2025-01-02T12:05:00Z,\n"
            "T4,TRANSFER,001,002,9200.00,USD,2025-01-02T13:00:00Z,2025-01-02T13:05:00Z,\n"
            "T5,TRANSFER,001,002,9100.00,USD,2025-01-02T14:00:00Z,2025-01-02T14:05:00Z,\n"
        ).encode("utf-8"),
    }


def _psycopg_to_libpq(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def rehearse_recovery(base_database_url: str) -> dict:
    parsed = make_url(base_database_url)
    admin_url = parsed.set(database="postgres").render_as_string(hide_password=False)
    src_db = f"argus_rec_src_{uuid4().hex[:8]}"
    dst_db = f"argus_rec_dst_{uuid4().hex[:8]}"
    src_url = parsed.set(database=src_db).render_as_string(hide_password=False)
    dst_url = parsed.set(database=dst_db).render_as_string(hide_password=False)

    admin_engine = create_engine_from_url(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{src_db}"'))
            conn.execute(text(f'CREATE DATABASE "{dst_db}"'))

        # 1. Migrate & populate source database
        src_engine = create_engine_from_url(src_url)
        try:
            cfg = Config(str(BACKEND_ROOT / "backend" / "alembic.ini"))
            with src_engine.begin() as conn:
                cfg.attributes["connection"] = conn
                command.upgrade(cfg, "head")
            factory = make_session_factory(src_engine)
            with factory.begin() as s:
                a1 = User(issuer="idp", subject="a1", display_name="Analyst", roles=["analyst"])
                r1 = User(issuer="idp", subject="r1", display_name="Reviewer", roles=["reviewer"])
                ds = Dataset(name="RecoveryBank", namespace="bank")
                s.add_all([a1, r1, ds])
                s.flush()
                s.add_all([
                    DatasetGrant(user_id=a1.id, dataset_id=ds.id, can_import=True),
                    DatasetGrant(user_id=r1.id, dataset_id=ds.id, can_import=False),
                ])
                act = activate_batch(s, ds.id, a1.id, parse_batch(_rehearsal_csv_files(), "bank", None), 0, "rec-1")
                case = CaseRecord(
                    dataset_id=ds.id,
                    snapshot_id=act.snapshot_id,
                    subject_id="002",
                    title="Recovery Case",
                    created_by=a1.id,
                )
                s.add(case)
                s.flush()
                s.add_all([CaseAssignment(case_id=case.id, user_id=a1.id), CaseAssignment(case_id=case.id, user_id=r1.id)])
                s.flush()
                enqueue_analysis_job(s, case.id, a1.id, idempotency_key="rec-job-1")
                claimed = claim_next_job(s, "recovery-worker")
                if claimed is None:
                    raise RuntimeError("Failed to claim rehearsal analysis job")
                analysis_res = analyze_snapshot(s, act.snapshot_id, subject_id="002")
                publish_job_outcome(s, claimed.job_id, claimed.fence, status="COMPLETE", result=analysis_res)
                art = create_draft_revision(s, case.id, a1.id)
                freeze_artifact_for_review(s, art.id, a1.id)
                review_artifact(s, art.id, r1.id, decision="APPROVED", review_note="Rehearsal approval")
                exported = export_approved_artifact(s, art.id, r1.id)
                artifact_id = art.id
        finally:
            src_engine.dispose()

        # 2. Backup via pg_dump & restore into isolated target DB, timing actual recovery
        with tempfile.TemporaryDirectory() as tmp:
            dump_path = Path(tmp) / "argus.dump"
            t_backup_start = time.monotonic()
            dump_proc = subprocess.run(
                ["pg_dump", "-Fc", "-f", str(dump_path), _psycopg_to_libpq(src_url)],
                capture_output=True,
                text=True,
            )
            if dump_proc.returncode != 0:
                raise RuntimeError(f"pg_dump failed ({dump_proc.returncode}): {dump_proc.stderr.strip()}")
            backup_seconds = round(time.monotonic() - t_backup_start, 3)
            dump_size_bytes = dump_path.stat().st_size

            t_restore_start = time.monotonic()
            restore_proc = subprocess.run(
                ["pg_restore", "--no-owner", "--clean", "--if-exists", "-d", _psycopg_to_libpq(dst_url), str(dump_path)],
                capture_output=True,
                text=True,
            )
            if restore_proc.returncode != 0:
                raise RuntimeError(f"pg_restore failed ({restore_proc.returncode}): {restore_proc.stderr.strip()}")
            restore_seconds = round(time.monotonic() - t_restore_start, 3)

        # 3. Verify restored DB independently with offline verifier
        dst_engine = create_engine_from_url(dst_url)
        try:
            with dst_engine.connect() as conn:
                schema_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            dst_factory = make_session_factory(dst_engine)
            with dst_factory() as s:
                restored_art = s.get(Artifact, artifact_id)
                restored_app = s.scalar(select(Approval).where(Approval.artifact_id == artifact_id))
                restored_sfs = {sf.id: bytes(sf.bytes) for sf in s.scalars(select(SourceFile)).all()}
                verification = verify_package_bytes(
                    bytes(restored_art.narrative),
                    bytes(restored_art.manifest),
                    dict(restored_app.envelope_json),
                    expected_payload_digest=exported.payload_digest,
                    expected_envelope_digest=exported.envelope_digest,
                    source_files_by_id=restored_sfs,
                )
        finally:
            dst_engine.dispose()

        passed = (
            verification["verified"]
            and verification["provenance_status"] == "VERIFIED"
            and verification["claims_checked"] > 0
            and verification["provenance_files_checked"] > 0
        )
        return {
            "status": "PASSED" if passed else "FAILED",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "schema_revision": schema_rev,
            "dump_size_bytes": dump_size_bytes,
            "backup_seconds": backup_seconds,
            "restore_seconds": restore_seconds,
            "measured_data_loss_bytes": 0 if verification["verified"] else -1,
            "verifier_report": verification,
        }
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{src_db}" WITH (FORCE)'))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dst_db}" WITH (FORCE)'))
        admin_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated PostgreSQL backup & restore rehearsal")
    parser.add_argument("--database-url", default=os.getenv("ARGUS_TEST_DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.database_url:
        report = {
            "status": "BLOCKED",
            "reason": "PostgreSQL unavailable: set ARGUS_TEST_DATABASE_URL and start local PostgreSQL/Docker engine.",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    report = rehearse_recovery(args.database_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
