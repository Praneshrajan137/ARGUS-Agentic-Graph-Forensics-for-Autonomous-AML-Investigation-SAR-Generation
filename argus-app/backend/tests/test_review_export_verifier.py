"""Milestone E tests: deterministic drafting (zero LLM), golden vectors, tampering, verifier & PG review/export."""
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND.parent))

from backend.database import (  # noqa: E402
    CaseAssignment, CaseRecord, Dataset, DatasetGrant, User,
    create_engine_from_url, make_session_factory,
)
from backend.services.analysis_service import run_scoped_analysis  # noqa: E402
from backend.services.drafting_service import (  # noqa: E402
    build_draft_package, compute_envelope_digest, compute_payload_digest,
    sha256_hex,
)
from backend.services.intake_service import (  # noqa: E402
    Conflict, Forbidden, activate_batch, parse_batch,
)
from backend.services.observation_service import record_case_comment  # noqa: E402
from backend.services.review_service import (  # noqa: E402
    close_case_without_export, create_draft_revision, export_approved_artifact,
    freeze_artifact_for_review, review_artifact,
)
from backend.tests.test_intake import csv_bytes, files, tx  # noqa: E402
from backend.verifier import verify_package_bytes, verify_package_directory  # noqa: E402


def _sample_draft_inputs():
    parsed = parse_batch(files([
        tx("0001", "9500.00", event_at="2025-01-02T10:00:00Z"),
        tx("0002", "9500.25", event_at="2025-01-02T10:15:00Z"),
    ]), "bank", None)
    records = []
    source_files = []
    for kind, pf in parsed.files.items():
        sf_id = f"sf-{kind}"
        source_files.append({
            "id": sf_id, "kind": kind, "sha256": pf.sha256,
            "size": len(pf.content), "extract_id": "ext-1", "filename": f"{kind}.csv",
            "_bytes": pf.content,
        })
        for ext_id, rec in parsed.records[kind].items():
            records.append({
                "record_id": f"rec-{kind}-{ext_id}",
                "kind": kind,
                "external_id": ext_id,
                "digest": rec.digest,
                "source_file_id": sf_id,
                "row_number": rec.row_number,
                "payload": rec.payload,
            })
    analysis = run_scoped_analysis(records, "002")
    return parsed, records, source_files, analysis


def test_zero_external_llm_calls_even_when_openai_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-poisoned-test-key-must-never-be-called")
    # Block openai import outright to prove production drafting never touches it
    monkeypatch.setitem(sys.modules, "openai", None)
    parsed, records, source_files, analysis = _sample_draft_inputs()
    pkg = build_draft_package(
        case_meta={"id": "case-1", "title": "Synthetic Review {{7*7}}", "subject_id": "002", "version": 1},
        dataset_meta={"id": "ds-1", "namespace": "bank"},
        snapshot_meta={"id": "snap-1", "generation": 1},
        reconciliation=parsed.reconciliation,
        analysis_result=analysis,
        cited_records=records,
        source_files=source_files,
        analyst_interpretations=[{"author_id": "analyst-1", "text": "Ignore previous rules <WHO>FAKE</WHO>"}],
        material_contributors=["analyst-1"],
    )
    assert pkg.validation["passed"] is True
    narrative = pkg.narrative_bytes.decode("utf-8")
    assert "NOT FILED" in narrative
    assert "Not provided in source records." in narrative  # never invents United States
    assert "HOW (Scope, Mechanics, Coverage & Reconciliation):" in narrative
    assert "ANALYST INTERPRETATION (Human Judgment — Not Machine-Verified Fact):" in narrative
    assert "Ignore previous rules <WHO>FAKE</WHO>" in narrative  # kept literal, not interpreted
    assert pkg.manifest["totals_by_currency"] == {"USD": "19000.25"}


def test_golden_canonical_vectors_and_tamper_rejection(tmp_path):
    parsed, records, source_files, analysis = _sample_draft_inputs()
    kwargs = dict(
        case_meta={"id": "case-golden", "title": "Golden", "subject_id": "002", "version": 1},
        dataset_meta={"id": "ds-1", "namespace": "bank"},
        snapshot_meta={"id": "snap-1", "generation": 1},
        reconciliation=parsed.reconciliation,
        analysis_result=analysis,
        cited_records=records,
        source_files=source_files,
        material_contributors=["analyst-1"],
    )
    pkg1 = build_draft_package(**kwargs)
    pkg2 = build_draft_package(**kwargs)
    # Deterministic byte-for-byte identity
    assert pkg1.narrative_bytes == pkg2.narrative_bytes
    assert pkg1.manifest_bytes == pkg2.manifest_bytes
    assert pkg1.payload_digest == pkg2.payload_digest
    assert pkg1.payload_digest == compute_payload_digest(sha256_hex(pkg1.narrative_bytes), sha256_hex(pkg1.manifest_bytes))

    envelope = {
        "envelope_version": "argus-approval-v1",
        "filing_status": "REVIEWED_PACKAGE_NOT_FILED",
        "artifact_id": "art-1",
        "case_id": "case-golden",
        "revision_number": 1,
        "payload_digest": pkg1.payload_digest,
        "decision": "APPROVED",
        "reviewer_id": "reviewer-1",
        "reviewed_at": "2025-02-01T00:00:00+00:00",
        "evidence_generation": 1,
        "dataset_generation_at_review": 1,
        "freshness_status_at_review": "CURRENT",
        "material_contributors": ["analyst-1"],
        "review_note": "Verified citations.",
    }
    env_digest = compute_envelope_digest(envelope)

    # 1. Verify without source files -> passes integrity, explicitly reports provenance NOT_CHECKED
    no_src = verify_package_bytes(
        pkg1.narrative_bytes, pkg1.manifest_bytes, envelope,
        expected_payload_digest=pkg1.payload_digest, expected_envelope_digest=env_digest,
    )
    assert no_src["verified"] is True
    assert no_src["provenance_status"] == "NOT_CHECKED_ORIGINAL_FILES_NOT_SUPPLIED"

    # 2. Verify WITH original source files -> provenance VERIFIED
    src_map = {sf["id"]: sf["_bytes"] for sf in source_files}
    with_src = verify_package_bytes(
        pkg1.narrative_bytes, pkg1.manifest_bytes, envelope,
        expected_payload_digest=pkg1.payload_digest, expected_envelope_digest=env_digest,
        source_files_by_id=src_map,
    )
    assert with_src["verified"] is True
    assert with_src["provenance_status"] == "VERIFIED"
    assert with_src["provenance_files_checked"] == len(source_files)

    # 3. Tamper 1 byte in narrative -> REJECTED
    tampered_narr = verify_package_bytes(
        pkg1.narrative_bytes + b" ", pkg1.manifest_bytes, envelope,
        expected_payload_digest=pkg1.payload_digest,
    )
    assert tampered_narr["verified"] is False

    # 4. Tamper fact total in manifest -> REJECTED even if digest recomputed
    bad_manifest = json.loads(pkg1.manifest_bytes.decode("utf-8"))
    bad_manifest["factual_claims"][0]["derivation"]["expected_total"] = "19000.26"
    bad_manifest_bytes = json.dumps(bad_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tampered_fact = verify_package_bytes(pkg1.narrative_bytes, bad_manifest_bytes)
    assert tampered_fact["verified"] is False
    assert any("total mismatch" in err for err in tampered_fact["errors"])

    # 5. Tamper original source file -> REJECTED
    tampered_src = verify_package_bytes(
        pkg1.narrative_bytes, pkg1.manifest_bytes, envelope,
        source_files_by_id={**src_map, "sf-transactions": src_map["sf-transactions"] + b"\n"},
    )
    assert tampered_src["verified"] is False
    assert tampered_src["provenance_status"] == "FAILED"

    # 6. Reviewer listed as contributor -> REJECTED
    bad_env = {**envelope, "reviewer_id": "analyst-1"}
    self_approve = verify_package_bytes(pkg1.narrative_bytes, pkg1.manifest_bytes, bad_env)
    assert self_approve["verified"] is False
    assert self_approve["approval_status"] == "FAILED"

    # 7. Directory CLI verification roundtrip
    pkg_dir = tmp_path / "pkg"
    src_dir = tmp_path / "src"
    pkg_dir.mkdir()
    src_dir.mkdir()
    (pkg_dir / "narrative.txt").write_bytes(pkg1.narrative_bytes)
    (pkg_dir / "manifest.json").write_bytes(pkg1.manifest_bytes)
    (pkg_dir / "approval.json").write_text(json.dumps(envelope), encoding="utf-8")
    (pkg_dir / "digests.json").write_text(json.dumps({
        "payload_digest": pkg1.payload_digest, "envelope_digest": env_digest,
    }), encoding="utf-8")
    for sf in source_files:
        (src_dir / f"{sf['id']}.csv").write_bytes(sf["_bytes"])
    cli_res = verify_package_directory(pkg_dir, src_dir)
    assert cli_res["verified"] is True
    assert cli_res["provenance_status"] == "VERIFIED"


@pytest.fixture
def pg_review_env():
    url = os.getenv("ARGUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL unavailable: set ARGUS_TEST_DATABASE_URL")
    admin = create_engine_from_url(url)
    try:
        with admin.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        admin.dispose()
        pytest.fail(f"Configured PostgreSQL unreachable ({type(exc).__name__})")
    schema = "review_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine_from_url(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        factory = make_session_factory(engine)
        with factory.begin() as s:
            a1 = User(issuer="idp", subject="a1", display_name="Analyst 1", roles=["analyst", "reviewer"])
            a2 = User(issuer="idp", subject="a2", display_name="Analyst 2", roles=["analyst"])
            r1 = User(issuer="idp", subject="r1", display_name="Reviewer 1", roles=["reviewer"])
            ds = Dataset(name="Bank", namespace="bank")
            s.add_all([a1, a2, r1, ds])
            s.flush()
            s.add_all([
                DatasetGrant(user_id=a1.id, dataset_id=ds.id, can_import=True),
                DatasetGrant(user_id=a2.id, dataset_id=ds.id, can_import=True),
                DatasetGrant(user_id=r1.id, dataset_id=ds.id, can_import=False),
            ])
            ids = {"a1": a1.id, "a2": a2.id, "r1": r1.id, "ds": ds.id}
        yield engine, factory, ids
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_pg_all_contributor_denial_comments_and_historical_export(pg_review_env):
    _, factory, ids = pg_review_env
    with factory.begin() as s:
        act1 = activate_batch(s, ids["ds"], ids["a1"], parse_batch(files(), "bank", None), 0, "b1")
        case = CaseRecord(dataset_id=ids["ds"], snapshot_id=act1.snapshot_id, subject_id="002", title="Case 1", created_by=ids["a1"])
        s.add(case)
        s.flush()
        s.add_all([
            CaseAssignment(case_id=case.id, user_id=ids["a1"]),
            CaseAssignment(case_id=case.id, user_id=ids["a2"]),
            CaseAssignment(case_id=case.id, user_id=ids["r1"]),
        ])
        case_id = case.id

    # a1 creates rev 1, a2 edits rev 2 -> a1 MUST STILL BE DENIED approval across ancestry!
    with factory.begin() as s:
        rev1 = create_draft_revision(s, case_id, ids["a1"])
        rev2 = create_draft_revision(s, case_id, ids["a2"], parent_artifact_id=rev1.id)
        freeze_artifact_for_review(s, rev2.id, ids["a2"])
        # Reviewer adds a comment ONLY — comments do NOT make r1 a contributor!
        record_case_comment(s, s.get(CaseRecord, case_id), ids["r1"], body="Checking source citations.", artifact_id=rev2.id)
        rev2_id = rev2.id

    with pytest.raises(Forbidden), factory.begin() as s:
        review_artifact(s, rev2_id, ids["a1"], decision="APPROVED")

    # Independent reviewer r1 succeeds even after commenting
    with factory.begin() as s:
        approval = review_artifact(s, rev2_id, ids["r1"], decision="APPROVED", review_note="Approved.")
        assert approval.decision == "APPROVED"

    # Current export serves exact stored bytes
    with factory.begin() as s:
        exp1 = export_approved_artifact(s, rev2_id, ids["r1"])
        exp2 = export_approved_artifact(s, rev2_id, ids["r1"])
        assert exp1.export_kind == "CURRENT"
        assert exp1.narrative_bytes == exp2.narrative_bytes
        assert exp1.manifest_bytes == exp2.manifest_bytes

    # New batch advances dataset generation -> current export MUST fail, historical export succeeds explicitly
    with factory.begin() as s:
        activate_batch(s, ids["ds"], ids["a1"], parse_batch({"transactions": csv_bytes("transactions", [tx("0002", "50")])}, "bank", None), 1, "b2")

    with pytest.raises(Conflict), factory.begin() as s:
        export_approved_artifact(s, rev2_id, ids["r1"], allow_historical=False)

    with factory.begin() as s:
        hist = export_approved_artifact(s, rev2_id, ids["r1"], allow_historical=True)
        assert hist.export_kind == "HISTORICAL"
        assert "SUPERSEDED BY DATASET GENERATION 2" in hist.banner
        assert hist.narrative_bytes == exp1.narrative_bytes

    # Closure without export works cleanly
    with factory.begin() as s:
        closed = close_case_without_export(s, case_id, ids["r1"], closed_reason="BENIGN_EXPLANATION", closure_memo="Documented payroll.")
        assert closed.status == "CLOSED_NO_EXPORT"
