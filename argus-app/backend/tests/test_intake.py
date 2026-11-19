"""Synthetic intake contract tests; PostgreSQL tests never use public application tables."""
import csv
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, OperationalError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND.parent))

from backend.database import (  # noqa: E402
    Artifact, AuditEvent, CaseContributor, CaseRecord, Dataset,
    DatasetGrant, ImportBatch, LedgerRecord, Snapshot, SnapshotRecord,
    SourceFile, SourceOccurrence, User, create_engine_from_url, make_session_factory,
)
from backend.models.ledger import REQUIRED_HEADERS, TransactionInput  # noqa: E402
from backend.services.intake_service import (  # noqa: E402
    Conflict, Forbidden, IntakeError, activate_batch, canonical_payload, parse_batch, row_hash,
)


def csv_bytes(kind, rows, extra=()):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=[*REQUIRED_HEADERS[kind], *extra])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def tx(id="0001", amount="10.00", **changes):
    row = dict(id=id, event_type="TRANSFER", source_account_id="001", target_account_id="002",
               amount=amount, currency="USD", event_at="2025-01-02T12:00:00Z",
               posted_at="2025-01-03T00:00:00Z", related_event_id="")
    row.update(changes)
    return row


def files(transactions=None):
    return {
        "entities": csv_bytes("entities", [{"id": "E1", "entity_type": "PERSON", "name": "A\nB"}]),
        "accounts": csv_bytes("accounts", [dict(id=a, account_type="CHECKING", currency="USD") for a in ("001", "002")]),
        "relationships": csv_bytes("relationships", [dict(id="R" + a, entity_id="E1", account_id=a,
            role="OWNER", valid_from="2024-01-01T00:00:00Z", valid_to="") for a in ("001", "002")]),
        "transactions": csv_bytes("transactions", transactions if transactions is not None else [tx()]),
    }


def control(count=1, total="10", origin="INDEPENDENT_UPSTREAM"):
    scope = dict(namespace="bank", kind="transactions", interval_start="2025-01-01T00:00:00Z",
                 interval_end="2025-02-01T00:00:00Z", timezone="UTC", accounting_basis="EVENT",
                 account_ids=[], population="ALL", filters={})
    return {"declaration": scope, "upstream": {"scope": dict(scope), "origin": origin,
            "system": "synthetic-core", "extract_id": "independent-counter-1", "sha256": "a" * 64,
            "row_count": count, "gross_totals": {"USD": total}}}


def test_canonical_duplicates_preserve_raw_occurrences_and_money():
    parsed = parse_batch(files([tx(), tx(amount="10.0")]), "bank", control(2, "20.00"))
    source = parsed.files["transactions"]
    assert source.raw_row_count == 2 and source.normalized_count == 1
    assert [r.row_number for r in source.occurrences] == [1, 2]
    assert parsed.records["transactions"]["0001"].payload["amount"] == "10"
    assert parsed.reconciliation["status"] == "RECONCILED"
    assert parsed.reconciliation["observed"]["gross_totals"] == {"USD": "20"}
    assert parsed.eligible_counts["transactions"] == 1
    record = parsed.records["transactions"]["0001"]
    assert row_hash(record.payload) == record.digest
    assert canonical_payload({"z": "10", "a": "é"}) == b'{"a":"\xc3\xa9","z":"10"}'
    with pytest.raises(IntakeError):
        canonical_payload({"amount": 1.1})


@pytest.mark.parametrize("amount", ["0", "-1", "1e2", "NaN", "Infinity", "1.00000000001", "9" * 31, " 1", "+1"])
def test_reject_invalid_money(amount):
    with pytest.raises(IntakeError):
        parse_batch(files([tx(amount=amount)]), "bank", None)


def test_exact_totals_do_not_depend_on_global_decimal_context():
    amount = "99999999999999999999.1234567890"
    p = parse_batch(files([tx("1", amount), tx("2", amount)]), "bank", control(2, "199999999999999999998.246913578"))
    assert p.reconciliation["status"] == "RECONCILED"
    assert p.reconciliation["observed"]["gross_totals"]["USD"] == "199999999999999999998.246913578"


@pytest.mark.parametrize("body", [b"id,id\na,b\n", b"id,entity_type,name,unknown\na,PERSON,A,x\n",
    b"id,entity_type,name\na,PERSON,\xff\n", b"id,entity_type,name\na,PERSON,A\x00\n",
    b'id,entity_type,name\na,PERSON,"unclosed', b"id,entity_type,name\na,PERSON,A,extra\n"])
def test_malformed_csv_rejected(body):
    with pytest.raises(IntakeError):
        parse_batch({"entities": body}, "bank", None)


def test_multiline_uses_record_ordinal_and_conflicting_duplicates_fail():
    p = parse_batch({"entities": csv_bytes("entities", [dict(id="1", entity_type="PERSON", name="A\nB"),
        dict(id="2", entity_type="PERSON", name="C")])}, "bank", None)
    assert [o.row_number for o in p.files["entities"].occurrences] == [1, 2]
    with pytest.raises(IntakeError):
        parse_batch(files([tx(), tx(amount="11")]), "bank", None)


@pytest.mark.parametrize("field,value", [("event_at", "2025-01-02T00:00:00"), ("currency", "usd"),
    ("source_account_id", ""), ("id", "x" * 129), ("posted_at", "2025-01-02")])
def test_strict_transaction_fields(field, value):
    row = tx()
    row[field] = value
    with pytest.raises(IntakeError):
        parse_batch(files([row]), "bank", None)


def test_typed_schema_cash_reversal_and_joint_owners():
    assert TransactionInput.model_json_schema()["properties"]["amount"]["type"] == "string"
    cash = tx()
    cash.update(event_type="CASH_DEPOSIT", source_account_id="")
    p = parse_batch(files([cash]), "bank", None)
    assert p.records["transactions"]["0001"].payload["source_account_id"] is None
    cash["source_account_id"] = "001"
    with pytest.raises(IntakeError):
        parse_batch(files([cash]), "bank", None)
    rev = tx()
    rev["event_type"] = "REVERSAL"
    with pytest.raises(IntakeError):
        parse_batch(files([rev]), "bank", None)


def test_reconciliation_never_infers_completeness():
    assert parse_batch(files(), "bank", None).reconciliation["status"] == "UNVERIFIED"
    assert parse_batch(files(), "bank", control(2, "20")).reconciliation["status"] == "MISMATCH"
    assert parse_batch(files(), "bank", control(origin="UPLOADED_FILE")).reconciliation["status"] == "UNVERIFIED"
    c = control()
    c["upstream"]["scope"]["namespace"] = "other"
    assert parse_batch(files(), "bank", c).reconciliation["status"] == "UNVERIFIED"
    c = control()
    c["upstream"]["scope"]["accounting_basis"] = "POSTING"
    assert parse_batch(files(), "bank", c).reconciliation["status"] == "UNVERIFIED"


def test_bounds_and_file_kind(monkeypatch):
    import backend.services.intake_service as intake
    monkeypatch.setattr(intake, "MAX_BATCH_BYTES", 5)
    with pytest.raises(IntakeError):
        parse_batch(files(), "bank", None)
    with pytest.raises(IntakeError):
        parse_batch({"input.zip": b"zip"}, "bank", None)
    monkeypatch.setattr(intake, "MAX_BATCH_BYTES", 50 * 1024 * 1024)
    monkeypatch.setattr(intake, "MAX_EVENTS", 1)
    with pytest.raises(IntakeError):
        parse_batch(files([tx(), tx()]), "bank", None)


@pytest.fixture
def db():
    url = os.getenv("ARGUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL unavailable: set ARGUS_TEST_DATABASE_URL to a synthetic test database")
    admin = create_engine_from_url(url)
    try:
        with admin.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        admin.dispose()
        pytest.fail(f"Configured synthetic PostgreSQL unreachable ({type(exc).__name__})")
    schema = "intake_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine_from_url(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        factory = make_session_factory(engine)
        with factory.begin() as session:
            user = User(issuer="synthetic", subject="analyst", display_name="Analyst", roles=["analyst"])
            dataset = Dataset(name="Synthetic", namespace="bank")
            session.add_all([user, dataset])
            session.flush()
            session.add(DatasetGrant(user_id=user.id, dataset_id=dataset.id, can_import=True))
            ids = user.id, dataset.id
        yield engine, factory, ids
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def activate(db, p=None, generation=0, key="first"):
    _, factory, (actor, dataset) = db
    with factory.begin() as s:
        return activate_batch(s, dataset, actor, p or parse_batch(files(), "bank", None), generation, key)


def test_postgres_only():
    with pytest.raises(ValueError):
        create_engine_from_url("sqlite://")


def test_pg_migration_and_cumulative_overlap_correction_idempotency(db):
    first = activate(db)
    assert first.generation == 1
    p = parse_batch({"transactions": csv_bytes("transactions", [tx(), tx("0002", "5")])}, "bank", None)
    second = activate(db, p, 1, "second")
    assert second.generation == 2
    assert activate(db, p, 1, "second").snapshot_id == second.snapshot_id
    old_hash = p.records["transactions"]["0001"].digest
    correction = tx(amount="12", supersedes_hash=old_hash)
    corrected = parse_batch({"transactions": csv_bytes("transactions", [correction], ("supersedes_hash",))}, "bank", None)
    third = activate(db, corrected, 2, "correction")
    _, factory, (_, dataset) = db
    with factory() as s:
        assert s.get(Dataset, dataset).generation == 3
        assert s.scalar(select(func.count()).select_from(LedgerRecord).where(LedgerRecord.kind == "transactions")) == 3
        assert s.scalar(select(func.count()).select_from(SnapshotRecord).where(SnapshotRecord.snapshot_id == third.snapshot_id)) == 7
        assert s.scalar(select(func.count()).select_from(SourceOccurrence).where(SourceOccurrence.record_id.in_(
            select(LedgerRecord.id).where(LedgerRecord.kind == "transactions")))) == 4
        old = s.scalar(select(LedgerRecord).join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id).where(
            SnapshotRecord.snapshot_id == first.snapshot_id, LedgerRecord.kind == "transactions"))
        assert old.amount == Decimal("10")
        assert s.scalar(select(func.count()).select_from(AuditEvent)) == 3


def test_pg_failures_leave_no_partial_batches_and_caller_rollback(db):
    activate(db)
    with pytest.raises(Conflict):
        activate(db, generation=0, key="stale")
    with pytest.raises(Conflict):
        activate(db, parse_batch(files([tx(amount="12")]), "bank", None), 1, "first")
    with pytest.raises(Conflict):
        activate(db, parse_batch(files([tx(amount="12")]), "bank", None), 1, "silent")
    bad = tx()
    bad["target_account_id"] = "missing"
    with pytest.raises(IntakeError):
        activate(db, parse_batch(files([bad]), "bank", None), 1, "bad")
    _, factory, (actor, dataset) = db
    with pytest.raises(RuntimeError):
        with factory.begin() as s:
            activate_batch(s, dataset, actor, parse_batch(files(), "bank", None), 1, "rollback")
            raise RuntimeError("interrupt before commit")
    with factory() as s:
        assert s.get(Dataset, dataset).generation == 1
        assert s.scalar(select(func.count()).select_from(ImportBatch)) == 1


def test_pg_simultaneous_head_advance_has_one_winner(db):
    activate(db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(activate, db, parse_batch({"transactions": csv_bytes("transactions", [tx(str(i))])}, "bank", None), 1, str(i)) for i in (2, 3)]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Conflict:
                results.append("conflict")
    assert sum(r == "conflict" for r in results) == 1


def test_pg_authorization_and_effective_relationships(db):
    _, factory, (actor, _) = db
    with factory.begin() as s:
        s.get(User, actor).enabled = False
    with pytest.raises(Forbidden):
        activate(db)
    with factory.begin() as s:
        s.get(User, actor).enabled = True
    f = files()
    f["relationships"] = csv_bytes("relationships", [dict(id="R" + a, entity_id="E1", account_id=a,
        role="OWNER", valid_from="2026-01-01T00:00:00Z", valid_to="") for a in ("001", "002")])
    with pytest.raises(IntakeError):
        activate(db, parse_batch(f, "bank", None))


def test_pg_constraints_immutability_and_snapshot_isolation(db):
    result = activate(db)
    engine, factory, (actor, dataset) = db
    with factory() as s:
        record = s.scalar(select(LedgerRecord).where(LedgerRecord.kind == "transactions"))
        record_id = record.id
    for sql in ["UPDATE ledger_record SET amount=11 WHERE id=:record", "DELETE FROM ledger_record WHERE id=:record",
                "UPDATE audit_event SET event_type='changed'", "DELETE FROM snapshot_record WHERE snapshot_id=:snapshot",
                "UPDATE source_file SET bytes='changed'::bytea", "DELETE FROM import_batch", "DELETE FROM source_occurrence"]:
        with pytest.raises(DBAPIError), engine.begin() as c:
            c.execute(text(sql), {"record": record_id, "snapshot": result.snapshot_id})
    with pytest.raises(DBAPIError), factory.begin() as s:
        other = Dataset(name="Other", namespace="other")
        s.add(other)
        s.flush()
        snap = Snapshot(dataset_id=other.id, generation=1)
        s.add(snap)
        s.flush()
        s.add(SnapshotRecord(snapshot_id=snap.id, dataset_id=other.id, kind="transactions", external_id="0001", record_id=record_id))
    with pytest.raises(DBAPIError), factory.begin() as s:
        s.add(SnapshotRecord(snapshot_id=result.snapshot_id, dataset_id=dataset, kind="transactions", external_id="0001", record_id=record_id))
    with factory.begin() as s:
        case = CaseRecord(dataset_id=dataset, snapshot_id=result.snapshot_id, subject_id="E1", title="Review", created_by=actor)
        s.add(case)
        s.flush()
        artifact = Artifact(dataset_id=dataset, case_id=case.id, snapshot_id=result.snapshot_id, case_version=1,
            narrative=b"exact", manifest=b"{}", payload_digest="b" * 64, validation={}, created_by=actor)
        s.add_all([artifact, CaseContributor(case_id=case.id, user_id=actor)])
        s.flush()
        artifact_id = artifact.id
    with factory.begin() as s:
        s.get(Artifact, artifact_id).status = "IN_REVIEW"
    for sql in ["UPDATE artifact SET narrative='changed'::bytea", "DELETE FROM artifact", "DELETE FROM case_contributor"]:
        with pytest.raises(DBAPIError), engine.begin() as c:
            c.execute(text(sql))


def test_double_posting_debit_credit_collapses_to_single_economic_event():
    debit = tx(id="LEG-1", amount="500.00", posting_group_id="EVT-0001", posting_leg="DEBIT")
    credit = tx(id="LEG-2", amount="500.00", posting_group_id="EVT-0001", posting_leg="CREDIT")
    tx_csv = csv_bytes("transactions", [debit, credit], extra=("posting_group_id", "posting_leg"))
    batch_files = {**files(), "transactions": tx_csv}
    parsed = parse_batch(batch_files, "bank", control(2, "1000.00"))
    src = parsed.files["transactions"]
    assert src.raw_row_count == 2
    assert src.normalized_count == 1
    assert list(parsed.records["transactions"].keys()) == ["EVT-0001"]
    assert parsed.records["transactions"]["EVT-0001"].payload["posting_leg"] == "PAIRED"
    assert parsed.reconciliation["status"] == "RECONCILED"
    assert parsed.reconciliation["observed"]["raw_row_count"] == 2
    assert parsed.reconciliation["observed"]["normalized_event_count"] == 1
    assert parsed.reconciliation["observed"]["gross_totals"] == {"USD": "1000"}
    assert parsed.reconciliation["observed"]["normalized_gross_totals"] == {"USD": "500"}

    # Unpaired leg or mismatched amount between legs must fail
    with pytest.raises(IntakeError):
        parse_batch({**files(), "transactions": csv_bytes("transactions", [debit], extra=("posting_group_id", "posting_leg"))}, "bank")
    bad_credit = tx(id="LEG-2", amount="501.00", posting_group_id="EVT-0001", posting_leg="CREDIT")
    with pytest.raises(IntakeError):
        parse_batch({**files(), "transactions": csv_bytes("transactions", [debit, bad_credit], extra=("posting_group_id", "posting_leg"))}, "bank")


def test_pending_fx_and_unsupported_events_remain_visible_with_exclusions():
    from backend.models.ledger import analysis_eligibility
    posted = tx(id="0001", status="POSTED")
    pending = tx(id="0002", status="PENDING")
    fx = tx(id="0003", event_type="FX_CONVERSION", status="POSTED", fx_counter_currency="EUR", fx_rate="0.92")
    unsup = tx(id="0004", event_type="UNSUPPORTED", status="POSTED")
    tx_csv = csv_bytes("transactions", [posted, pending, fx, unsup], extra=("status", "fx_counter_currency", "fx_rate"))
    parsed = parse_batch({**files(), "transactions": tx_csv}, "bank", None)
    assert parsed.reconciliation["observed"]["normalized_event_count"] == 4
    assert parsed.reconciliation["observed"]["analysis_eligible_count"] == 1
    assert parsed.reconciliation["observed"]["excluded_count"] == 3
    assert analysis_eligibility(parsed.records["transactions"]["0001"].payload) == (True, None)
    assert analysis_eligibility(parsed.records["transactions"]["0002"].payload) == (False, "PENDING_EVENT")
    assert analysis_eligibility(parsed.records["transactions"]["0003"].payload) == (False, "FX_EVENT_UNSUPPORTED")
    assert analysis_eligibility(parsed.records["transactions"]["0004"].payload) == (False, "UNSUPPORTED_EVENT_TYPE")


def test_truncated_but_freshly_hashed_file_fails_independent_controls():
    # Upstream control declares 2 rows totaling 20 USD; a truncated file with 1 row
    # has a valid SHA-256 of its own bytes but must report MISMATCH against upstream controls.
    truncated = files([tx("0001", "10.00")])
    parsed = parse_batch(truncated, "bank", control(2, "20.00"))
    assert len(parsed.files["transactions"].sha256) == 64
    assert parsed.reconciliation["status"] == "MISMATCH"
    assert parsed.reconciliation["reason"] == "count_or_total_mismatch"


def test_temporal_ownership_change_validates_without_retrospective_rewrite():
    from backend.services.intake_service import _validate_references
    f = {
        "entities": csv_bytes("entities", [
            {"id": "E1", "entity_type": "PERSON", "name": "Owner One"},
            {"id": "E2", "entity_type": "PERSON", "name": "Owner Two"},
        ]),
        "accounts": csv_bytes("accounts", [
            {"id": "001", "account_type": "CHECKING", "currency": "USD"},
            {"id": "002", "account_type": "CHECKING", "currency": "USD"},
        ]),
        "relationships": csv_bytes("relationships", [
            {"id": "R1", "entity_id": "E1", "account_id": "001", "role": "OWNER",
             "valid_from": "2024-01-01T00:00:00Z", "valid_to": "2025-01-01T00:00:00Z"},
            {"id": "R2", "entity_id": "E2", "account_id": "001", "role": "OWNER",
             "valid_from": "2025-01-01T00:00:00Z", "valid_to": ""},
            {"id": "R3", "entity_id": "E1", "account_id": "002", "role": "OWNER",
             "valid_from": "2024-01-01T00:00:00Z", "valid_to": ""},
        ]),
        "transactions": csv_bytes("transactions", [
            tx("0001", "100.00", event_at="2024-06-01T12:00:00Z", posted_at="2024-06-01T13:00:00Z"),
            tx("0002", "200.00", event_at="2025-06-01T12:00:00Z", posted_at="2025-06-01T13:00:00Z"),
        ]),
    }
    parsed = parse_batch(f, "bank", None)
    combined = {(kind, ext_id): rec.payload for kind, recs in parsed.records.items() for ext_id, rec in recs.items()}
    _validate_references(combined)
    assert "0001" in parsed.records["transactions"]
    assert "001" in parsed.records["accounts"]


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity", "0", "-1", "1.00000000001", "1" + "0" * 30])
def test_pg_numeric_check_on_direct_insert(db, amount):
    activate(db)
    _, factory, (_, dataset) = db
    with pytest.raises(DBAPIError), factory.begin() as s:
        source = s.scalar(select(SourceFile).where(SourceFile.kind == "transactions"))
        s.add(LedgerRecord(dataset_id=dataset, kind="transactions", external_id="bad", digest="f" * 64,
            source_file_id=source.id, row_number=1, payload={}, amount=Decimal(amount), currency="USD"))
