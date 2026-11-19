import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

import rfc8785
from pydantic import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..database import (
    AuditEvent, AuthGuard, Dataset, DatasetGrant, ImportBatch, LedgerRecord,
    Snapshot, SnapshotRecord, SourceFile, SourceOccurrence, User, new_id, utcnow,
)
from ..models.ledger import (
    INPUT_MODELS, REQUIRED_HEADERS, SCHEMA_VERSION, TRANSFORMATION_VERSION,
    analysis_eligibility, decimal_string, timestamp,
)

MAX_BATCH_BYTES = 50 * 1024 * 1024
MAX_EVENTS = 100_000
MAX_AUXILIARY_ROWS = 100_000
BULK_CHUNK_SIZE = 5_000


class IntakeError(ValueError):
    pass


class Conflict(IntakeError):
    pass


class Forbidden(IntakeError):
    pass


def canonical_payload(payload) -> bytes:
    def reject_floats(value):
        if isinstance(value, (float, Decimal)):
            raise IntakeError("Authoritative decimal values must be strings")
        if isinstance(value, dict):
            for item in value.values():
                reject_floats(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                reject_floats(item)
    reject_floats(payload)
    return rfc8785.dumps(payload)


def row_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


def _sum_precision(item_count: int) -> int:
    """Compute exact local Decimal precision from admitted digit limit (30) + cardinality."""
    return max(48, 30 + len(str(max(1, item_count))) + 8)


@dataclass
class ParsedRecord:
    payload: dict
    digest: str
    row_number: int
    supersedes_hash: str | None
    source_token: str | None = None
    canonical_id: str | None = None

    @property
    def record_id(self) -> str:
        return self.canonical_id or self.payload["id"]


@dataclass
class ParsedFile:
    content: bytes
    sha256: str
    occurrences: list[ParsedRecord] = field(default_factory=list)
    normalized_count: int = 0

    @property
    def raw_row_count(self) -> int:
        return len(self.occurrences)


@dataclass
class ParsedBatch:
    namespace: str
    files: dict[str, ParsedFile]
    records: dict[str, dict[str, ParsedRecord]]
    reconciliation: dict
    eligible_counts: dict[str, int]
    request_digest: str
    schema_version: str = SCHEMA_VERSION
    transformation_version: str = TRANSFORMATION_VERSION
    extract_id: str | None = None


@dataclass(frozen=True)
class Activation:
    batch_id: str
    snapshot_id: str
    generation: int
    reconciliation: dict


def _reconcile(
    parsed: dict[str, ParsedFile],
    records: dict[str, dict[str, ParsedRecord]],
    namespace: str,
    controls: dict | None,
) -> dict:
    transactions = parsed.get("transactions")
    normalized_txs = records.get("transactions", {})
    raw_amounts: dict[str, Decimal] = {}
    norm_amounts: dict[str, Decimal] = {}
    eligible_count = 0
    excluded_count = 0

    raw_rows = transactions.occurrences if transactions else []
    with localcontext() as context:
        context.prec = _sum_precision(len(raw_rows))
        for row in raw_rows:
            currency = row.payload["currency"]
            raw_amounts[currency] = raw_amounts.get(currency, Decimal(0)) + Decimal(row.payload["amount"])
    with localcontext() as context:
        context.prec = _sum_precision(len(normalized_txs))
        for rec in normalized_txs.values():
            currency = rec.payload["currency"]
            norm_amounts[currency] = norm_amounts.get(currency, Decimal(0)) + Decimal(rec.payload["amount"])
            eligible, _ = analysis_eligibility(rec.payload)
            if eligible:
                eligible_count += 1
            else:
                excluded_count += 1

    observed = {
        "row_count": transactions.raw_row_count if transactions else 0,
        "raw_row_count": transactions.raw_row_count if transactions else 0,
        "normalized_event_count": len(normalized_txs),
        "analysis_eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "gross_totals": {key: decimal_string(value) for key, value in sorted(raw_amounts.items())},
        "normalized_gross_totals": {key: decimal_string(value) for key, value in sorted(norm_amounts.items())},
    }
    result = {
        "status": "UNVERIFIED",
        "reason": "no_independent_controls_supplied",
        "observed": observed,
        "controls": controls,
        "scope": "agreement_with_declared_controls_only",
    }
    if not controls:
        return result
    if not isinstance(controls, dict):
        raise IntakeError("Control metadata must be an object")
    declaration, upstream = controls.get("declaration"), controls.get("upstream")
    if not isinstance(declaration, dict) or not isinstance(upstream, dict):
        result["reason"] = "incomplete_control_structure"
        return result
    required = {
        "namespace", "kind", "interval_start", "interval_end", "timezone",
        "accounting_basis", "account_ids", "population", "filters",
    }
    if not required.issubset(declaration) or upstream.get("scope") != declaration:
        result["reason"] = "incompatible_control_scope"
        return result
    if (
        declaration["namespace"] != namespace
        or declaration["kind"] != "transactions"
        or declaration["accounting_basis"] != "EVENT"
        or declaration["filters"] != {}
        or declaration["population"] != "ALL"
        or declaration["account_ids"] != []
    ):
        result["reason"] = "unsupported_or_mismatched_control_declaration"
        return result
    if (
        upstream.get("origin") != "INDEPENDENT_UPSTREAM"
        or not upstream.get("system")
        or not upstream.get("extract_id")
        or not re.fullmatch(r"[a-f0-9]{64}", upstream.get("sha256", ""))
    ):
        result["reason"] = "non_independent_or_incomplete_upstream_provenance"
        return result
    start, end = timestamp(declaration["interval_start"]), timestamp(declaration["interval_end"])
    if start >= end:
        raise IntakeError("Invalid control interval")
    if transactions and any(not start <= timestamp(row.payload["event_at"]) < end for row in transactions.occurrences):
        result["status"] = "MISMATCH"
        result["reason"] = "event_outside_declared_interval"
        return result
    try:
        expected = upstream["gross_totals"]
        if not isinstance(expected, dict) or type(upstream["row_count"]) is not int or upstream["row_count"] < 0:
            raise ValueError
        totals = {}
        for currency, value in expected.items():
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,10})?", value) or len(value) > 50:
                raise ValueError
            totals[currency] = decimal_string(Decimal(value))
    except (KeyError, ValueError, TypeError):
        raise IntakeError("Invalid independent control values") from None
    matched = upstream["row_count"] == observed["row_count"] and totals == observed["gross_totals"]
    result["status"] = "RECONCILED" if matched else "MISMATCH"
    result["reason"] = "matched_declared_independent_controls" if matched else "count_or_total_mismatch"
    return result


def _collapse_double_postings(
    source: ParsedFile,
    grouped_legs: dict[str, list[tuple[ParsedRecord, str]]],
    tx_records: dict[str, ParsedRecord],
) -> None:
    """Collapse paired DEBIT+CREDIT rows sharing posting_group_id into one economic event."""
    compare_fields = (
        "event_type", "source_account_id", "target_account_id", "amount",
        "currency", "event_at", "posted_at", "status", "related_event_id",
        "fx_counter_currency", "fx_rate",
    )
    for group_id, legs in sorted(grouped_legs.items()):
        if len(legs) != 2:
            raise IntakeError(f"Double-posting group '{group_id}' requires exactly two complementary legs")
        leg_names = {leg_name for _, leg_name in legs}
        if leg_names != {"DEBIT", "CREDIT"}:
            raise IntakeError(f"Double-posting group '{group_id}' must contain one DEBIT and one CREDIT leg")
        first_rec, _ = legs[0]
        second_rec, _ = legs[1]
        if any(first_rec.payload.get(f) != second_rec.payload.get(f) for f in compare_fields):
            raise IntakeError(f"Conflicting double-posting legs for group '{group_id}'")
        if first_rec.supersedes_hash != second_rec.supersedes_hash:
            raise IntakeError(f"Conflicting correction reference in double-posting group '{group_id}'")
        canonical_payload_dict = {
            **first_rec.payload,
            "id": group_id,
            "posting_group_id": group_id,
            "posting_leg": "PAIRED",
        }
        canonical_digest = row_hash(canonical_payload_dict)
        canonical_rec = ParsedRecord(
            payload=canonical_payload_dict,
            digest=canonical_digest,
            row_number=min(first_rec.row_number, second_rec.row_number),
            supersedes_hash=first_rec.supersedes_hash,
            source_token=first_rec.source_token,
            canonical_id=group_id,
        )
        previous = tx_records.get(group_id)
        if previous and (previous.digest != canonical_rec.digest or previous.supersedes_hash != canonical_rec.supersedes_hash):
            raise IntakeError(f"Conflicting identifier '{group_id}' with existing transaction")
        tx_records[group_id] = previous or canonical_rec
        for raw_rec, _ in legs:
            raw_rec.canonical_id = group_id
    source.normalized_count = len(tx_records)


def parse_batch(
    files: dict[str, bytes],
    namespace: str,
    controls: dict | None = None,
    *,
    extract_id: str | None = None,
) -> ParsedBatch:
    if not files or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", namespace):
        raise IntakeError("An explicit source namespace and CSV files are required")
    if set(files) - set(REQUIRED_HEADERS) or any(not isinstance(value, bytes) for value in files.values()):
        raise IntakeError("Only canonical CSV file kinds are accepted")
    if sum(len(value) for value in files.values()) > MAX_BATCH_BYTES:
        raise IntakeError("Batch exceeds byte budget")
    parsed: dict[str, ParsedFile] = {}
    records: dict[str, dict[str, ParsedRecord]] = {}
    for kind, content in sorted(files.items()):
        if b"\x00" in content:
            raise IntakeError("NUL bytes are not permitted")
        source = ParsedFile(content, hashlib.sha256(content).hexdigest())
        parsed[kind], records[kind] = source, {}
        grouped_legs: dict[str, list[tuple[ParsedRecord, str]]] = {}
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
            headers = reader.fieldnames or []
            model = INPUT_MODELS[kind]
            if len(headers) != len(set(headers)) or not set(REQUIRED_HEADERS[kind]).issubset(headers) or set(headers) - set(model.model_fields):
                raise IntakeError(f"Invalid {kind} CSV headers")
            limit = MAX_EVENTS if kind == "transactions" else MAX_AUXILIARY_ROWS
            for ordinal, raw in enumerate(reader, 1):
                if ordinal > limit:
                    raise IntakeError(f"{kind} exceeds row budget")
                if None in raw or any(value is None or len(value) > 4096 for value in raw.values()):
                    raise IntakeError(f"Invalid {kind} record {ordinal}")
                validated = model.model_validate(raw)
                payload = validated.model_dump(exclude={"supersedes_hash"})
                record = ParsedRecord(payload, row_hash(payload), ordinal, validated.supersedes_hash, raw.get("amount"))
                if kind == "transactions" and payload.get("posting_group_id"):
                    grouped_legs.setdefault(payload["posting_group_id"], []).append((record, payload["posting_leg"]))
                    source.occurrences.append(record)
                    continue
                previous = records[kind].get(validated.id)
                if previous and (previous.digest != record.digest or previous.supersedes_hash != record.supersedes_hash):
                    raise IntakeError(f"Conflicting duplicate {kind} identifier at record {ordinal}")
                records[kind][validated.id] = previous or record
                source.occurrences.append(record)
            if kind == "transactions" and grouped_legs:
                _collapse_double_postings(source, grouped_legs, records[kind])
            else:
                source.normalized_count = len(records[kind])
        except (csv.Error, UnicodeError, ValidationError, ValueError) as exc:
            if isinstance(exc, IntakeError):
                raise
            raise IntakeError(f"Invalid {kind} CSV record") from None
    reconciliation = _reconcile(parsed, records, namespace, controls)
    resolved_extract = extract_id or (
        controls.get("upstream", {}).get("extract_id")
        if isinstance(controls, dict) and isinstance(controls.get("upstream"), dict)
        else None
    )
    digest = row_hash({
        "namespace": namespace,
        "schema_version": SCHEMA_VERSION,
        "files": {kind: source.sha256 for kind, source in parsed.items()},
        "controls": controls,
    })
    return ParsedBatch(
        namespace=namespace,
        files=parsed,
        records=records,
        reconciliation=reconciliation,
        eligible_counts={kind: len(rows) for kind, rows in records.items()},
        request_digest=digest,
        schema_version=SCHEMA_VERSION,
        transformation_version=TRANSFORMATION_VERSION,
        extract_id=resolved_extract,
    )


def _validate_references(records: dict[tuple[str, str], dict]) -> None:
    accounts = {key[1] for key in records if key[0] == "accounts"}
    entities = {key[1] for key in records if key[0] == "entities"}
    relationships: dict[str, list[dict]] = {}
    for (kind, _), row in records.items():
        if kind == "relationships":
            if row["account_id"] not in accounts or row["entity_id"] not in entities:
                raise IntakeError("Relationship references an unknown party or account")
            relationships.setdefault(row["account_id"], []).append(row)
    for (kind, identity), row in records.items():
        if kind != "transactions":
            continue
        event_time = timestamp(row["event_at"])
        for account in (row["source_account_id"], row["target_account_id"]):
            if account is None:
                continue
            if account not in accounts:
                raise IntakeError("Transaction references an unknown account")
            links = relationships.get(account, [])
            if links and not any(
                timestamp(link["valid_from"]) <= event_time
                and (not link["valid_to"] or event_time < timestamp(link["valid_to"]))
                for link in links
            ):
                raise IntakeError("Account relationship does not cover transaction time")
        if row["event_type"] == "REVERSAL":
            related = records.get(("transactions", row["related_event_id"]))
            if not related or row["related_event_id"] == identity or related["event_type"] == "REVERSAL":
                raise IntakeError("Reversal references an invalid economic event")
            if related["currency"] != row["currency"] or timestamp(related["event_at"]) > event_time:
                raise IntakeError("Reversal currency or chronology is incompatible")


def _bulk_insert_chunks(session: Session, model, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(model)
    for idx in range(0, len(rows), BULK_CHUNK_SIZE):
        session.execute(stmt, rows[idx:idx + BULK_CHUNK_SIZE])


def activate_batch(
    session: Session,
    dataset_id: str,
    actor_id: str,
    parsed: ParsedBatch,
    expected_generation: int,
    idempotency_key: str,
) -> Activation:
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise IntakeError("A bounded idempotency key is required")
    # Strict Lock Order: 1. AuthGuard (FOR SHARE) -> 2. Dataset (FOR UPDATE)
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    actor = session.get(User, actor_id, populate_existing=True)
    grant = session.get(DatasetGrant, (actor_id, dataset_id), populate_existing=True)
    if not actor or not actor.enabled or not {"analyst", "administrator"}.intersection(actor.roles) or not grant or not grant.can_import:
        raise Forbidden("Import permission required")
    dataset = session.scalar(select(Dataset).where(Dataset.id == dataset_id).with_for_update().execution_options(populate_existing=True))
    if dataset is None or dataset.namespace != parsed.namespace:
        raise IntakeError("Unknown dataset or incompatible namespace")
    previous = session.scalar(select(ImportBatch).where(
        ImportBatch.dataset_id == dataset_id,
        ImportBatch.created_by == actor_id,
        ImportBatch.idempotency_key == idempotency_key,
    ))
    if previous:
        if previous.request_digest != parsed.request_digest:
            raise Conflict("Idempotency key was used for different input")
        snapshot = session.scalar(select(Snapshot).where(Snapshot.batch_id == previous.id))
        return Activation(previous.id, snapshot.id, snapshot.generation, previous.reconciliation)
    if dataset.generation != expected_generation:
        raise Conflict("Dataset changed; validate against the current generation")

    current = session.scalar(select(Snapshot).where(Snapshot.dataset_id == dataset_id, Snapshot.generation == dataset.generation))
    existing: dict[tuple[str, str], tuple[str, str, dict]] = {}
    if current:
        for rec_id, kind, ext_id, digest, payload in session.execute(
            select(
                LedgerRecord.id, LedgerRecord.kind, LedgerRecord.external_id,
                LedgerRecord.digest, LedgerRecord.payload,
            )
            .join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id)
            .where(SnapshotRecord.snapshot_id == current.id)
        ):
            existing[(kind, ext_id)] = (rec_id, digest, payload)

    combined = {key: payload for key, (_, _, payload) in existing.items()}
    for kind, incoming in parsed.records.items():
        for identity, record in incoming.items():
            old = existing.get((kind, identity))
            if old and old[1] != record.digest and record.supersedes_hash != old[1]:
                raise Conflict("Changing an existing event requires its previous digest")
            if record.supersedes_hash and (not old or old[1] != record.supersedes_hash):
                raise Conflict("Correction does not reference the current revision")
            combined[(kind, identity)] = record.payload
    _validate_references(combined)

    now = utcnow()
    batch = ImportBatch(
        dataset_id=dataset_id,
        parent_generation=dataset.generation,
        request_digest=parsed.request_digest,
        idempotency_key=idempotency_key,
        reconciliation=parsed.reconciliation,
        schema_version=parsed.schema_version,
        transformation_version=parsed.transformation_version,
        extract_id=parsed.extract_id,
        created_by=actor_id,
        created_at=now,
    )
    session.add(batch)
    session.flush()

    chosen_ids: dict[tuple[str, str], str] = {key: rec_id for key, (rec_id, _, _) in existing.items()}
    ledger_rows: list[dict] = []
    occurrence_rows: list[dict] = []

    for kind, source in parsed.files.items():
        stored = SourceFile(
            dataset_id=dataset_id,
            batch_id=batch.id,
            kind=kind,
            sha256=source.sha256,
            bytes=source.content,
            size=len(source.content),
            extract_id=parsed.extract_id,
            filename=f"{kind}.csv",
            created_by=actor_id,
            created_at=now,
        )
        session.add(stored)
        session.flush()

        for identity, incoming in parsed.records[kind].items():
            key = (kind, identity)
            old = existing.get(key)
            if old and old[1] == incoming.digest:
                continue
            rec_id = new_id()
            row_dict = {
                "id": rec_id,
                "created_at": now,
                "dataset_id": dataset_id,
                "kind": kind,
                "external_id": identity,
                "digest": incoming.digest,
                "source_file_id": stored.id,
                "row_number": incoming.row_number,
                "payload": incoming.payload,
                "amount": None,
                "currency": None,
                "event_at": None,
                "source_account_id": None,
                "target_account_id": None,
                "supersedes_id": old[0] if old else None,
                "event_status": "POSTED",
                "analysis_eligible": True,
                "exclusion_reason": None,
                "posting_group_id": None,
                "transformation_version": parsed.transformation_version,
            }
            if kind == "transactions":
                eligible, reason = analysis_eligibility(incoming.payload)
                row_dict.update(
                    amount=Decimal(incoming.payload["amount"]),
                    currency=incoming.payload["currency"],
                    event_at=timestamp(incoming.payload["event_at"]),
                    source_account_id=incoming.payload["source_account_id"],
                    target_account_id=incoming.payload["target_account_id"],
                    event_status=incoming.payload.get("status", "POSTED"),
                    analysis_eligible=eligible,
                    exclusion_reason=reason,
                    posting_group_id=incoming.payload.get("posting_group_id"),
                )
            ledger_rows.append(row_dict)
            chosen_ids[key] = rec_id

        for occurrence in source.occurrences:
            occurrence_rows.append({
                "source_file_id": stored.id,
                "row_number": occurrence.row_number,
                "record_id": chosen_ids[(kind, occurrence.record_id)],
                "source_token": occurrence.source_token,
            })

    _bulk_insert_chunks(session, LedgerRecord, ledger_rows)
    _bulk_insert_chunks(session, SourceOccurrence, occurrence_rows)

    snapshot = Snapshot(
        dataset_id=dataset_id,
        generation=dataset.generation + 1,
        batch_id=batch.id,
        sealed=False,
        created_at=now,
    )
    session.add(snapshot)
    session.flush()

    snapshot_rows = [
        {
            "snapshot_id": snapshot.id,
            "dataset_id": dataset_id,
            "kind": kind,
            "external_id": identity,
            "record_id": rec_id,
        }
        for (kind, identity), rec_id in sorted(chosen_ids.items())
    ]
    _bulk_insert_chunks(session, SnapshotRecord, snapshot_rows)
    snapshot.sealed = True
    dataset.generation = snapshot.generation
    session.add(AuditEvent(
        actor_id=actor_id,
        event_type="DATASET_ACTIVATED",
        resource_id=dataset_id,
        detail={
            "batch_id": batch.id,
            "snapshot_id": snapshot.id,
            "generation": snapshot.generation,
            "schema_version": parsed.schema_version,
            "transformation_version": parsed.transformation_version,
            "reconciliation_status": parsed.reconciliation.get("status"),
        },
        created_at=now,
    ))
    session.flush()
    return Activation(batch.id, snapshot.id, snapshot.generation, parsed.reconciliation)
