from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Integer, LargeBinary, Numeric, String, UniqueConstraint, create_engine, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthGuard(Base):
    __tablename__ = "auth_guard"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("id = 1"),)


class User(Identified, Base):
    __tablename__ = "app_user"
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list] = mapped_column(JSONB, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("issuer", "subject"),)


class UserSession(Base):
    __tablename__ = "user_session"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthFlow(Base):
    __tablename__ = "auth_flow"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(128))
    browser_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Dataset(Identified, Base):
    __tablename__ = "dataset"
    name: Mapped[str] = mapped_column(String(255))
    namespace: Mapped[str] = mapped_column(String(128), unique=True)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("generation >= 0"),)


class DatasetGrant(Base):
    __tablename__ = "dataset_grant"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"), primary_key=True)
    can_import: Mapped[bool] = mapped_column(Boolean, default=False)
    can_download_source: Mapped[bool] = mapped_column(Boolean, default=False)


class ImportBatch(Identified, Base):
    __tablename__ = "import_batch"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    parent_generation: Mapped[int] = mapped_column(Integer)
    request_digest: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVATED")
    reconciliation: Mapped[dict] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[str] = mapped_column(String(32), default="canonical-csv-v1")
    transformation_version: Mapped[str] = mapped_column(String(32), default="argus-intake-v1")
    extract_id: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    __table_args__ = (UniqueConstraint("dataset_id", "created_by", "idempotency_key"),)


class SourceFile(Identified, Base):
    __tablename__ = "source_file"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.id"))
    kind: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int] = mapped_column(Integer)
    extract_id: Mapped[str | None] = mapped_column(String(128))
    filename: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    __table_args__ = (CheckConstraint("size = octet_length(bytes) AND size <= 52428800"),)


class LedgerRecord(Identified, Base):
    __tablename__ = "ledger_record"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    kind: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    digest: Mapped[str] = mapped_column(String(64))
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_file.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    amount: Mapped[Decimal | None] = mapped_column(Numeric())
    currency: Mapped[str | None] = mapped_column(String(3))
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_account_id: Mapped[str | None] = mapped_column(String(128), index=True)
    target_account_id: Mapped[str | None] = mapped_column(String(128), index=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("ledger_record.id"))
    event_status: Mapped[str] = mapped_column(String(32), default="POSTED")
    analysis_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(64))
    posting_group_id: Mapped[str | None] = mapped_column(String(128))
    transformation_version: Mapped[str] = mapped_column(String(32), default="argus-intake-v1")
    __table_args__ = (
        UniqueConstraint("dataset_id", "kind", "external_id", "digest"),
        UniqueConstraint("id", "dataset_id", "kind", "external_id"),
        CheckConstraint("kind IN ('entities','accounts','relationships','transactions')"),
        CheckConstraint("row_number > 0"),
        CheckConstraint("event_status IN ('POSTED','PENDING','CANCELLED')"),
        CheckConstraint("amount IS NULL OR (amount > 0 AND amount < 'Infinity'::numeric AND amount <> 'NaN'::numeric AND scale(amount) <= 10 AND length(replace(trim_scale(amount)::text, '.', '')) <= 30)"),
        CheckConstraint("kind <> 'transactions' OR (amount IS NOT NULL AND currency ~ '^[A-Z]{3}$')"),
    )


class SourceOccurrence(Base):
    __tablename__ = "source_occurrence"
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_file.id"), primary_key=True)
    row_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("ledger_record.id"))
    source_token: Mapped[str | None] = mapped_column(String(64))


class Snapshot(Identified, Base):
    __tablename__ = "snapshot"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    generation: Mapped[int] = mapped_column(Integer)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batch.id"), unique=True)
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("dataset_id", "generation"), UniqueConstraint("id", "dataset_id"))


class SnapshotRecord(Base):
    __tablename__ = "snapshot_record"
    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id", "dataset_id"], ["snapshot.id", "snapshot.dataset_id"]),
        ForeignKeyConstraint(["record_id", "dataset_id", "kind", "external_id"],
                             ["ledger_record.id", "ledger_record.dataset_id", "ledger_record.kind", "ledger_record.external_id"]),
    )


class CaseRecord(Identified, Base):
    __tablename__ = "case_record"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    subject_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    closed_reason: Mapped[str | None] = mapped_column(String(64))
    closure_memo: Mapped[str | None] = mapped_column(String(4000))
    active_job_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (
        UniqueConstraint("id", "dataset_id"),
        ForeignKeyConstraint(["snapshot_id", "dataset_id"], ["snapshot.id", "snapshot.dataset_id"]),
    )


class CaseAssignment(Base):
    __tablename__ = "case_assignment"
    case_id: Mapped[str] = mapped_column(ForeignKey("case_record.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)


class CaseContributor(Base):
    __tablename__ = "case_contributor"
    case_id: Mapped[str] = mapped_column(ForeignKey("case_record.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)


class CaseObservation(Identified, Base):
    __tablename__ = "case_observation"
    case_id: Mapped[str] = mapped_column(String(36))
    dataset_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    source_kind: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(255))
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    entity_id: Mapped[str | None] = mapped_column(String(128))
    account_id: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str | None] = mapped_column(String(3))
    interval_start: Mapped[str | None] = mapped_column(String(64))
    interval_end: Mapped[str | None] = mapped_column(String(64))
    accounting_basis: Mapped[str | None] = mapped_column(String(32))
    aggregation: Mapped[str | None] = mapped_column(String(32))
    amount_str: Mapped[str | None] = mapped_column(String(64))
    raw_text: Mapped[str] = mapped_column(String(8000))
    scope_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    comparison_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    __table_args__ = (
        ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
        ForeignKeyConstraint(["snapshot_id", "dataset_id"], ["snapshot.id", "snapshot.dataset_id"]),
    )


class CaseFindingDisposition(Identified, Base):
    __tablename__ = "case_finding_disposition"
    case_id: Mapped[str] = mapped_column(String(36))
    dataset_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job.id"))
    finding_id: Mapped[str] = mapped_column(String(128))
    disposition: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(String(4000))
    benign_alternative: Mapped[str | None] = mapped_column(String(4000))
    actor_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    __table_args__ = (
        CheckConstraint("disposition IN ('OPEN','ESCALATED','DISMISSED','NEEDS_INFO')"),
        ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
    )


class CaseComment(Identified, Base):
    __tablename__ = "case_comment"
    case_id: Mapped[str] = mapped_column(String(36))
    dataset_id: Mapped[str] = mapped_column(String(36))
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifact.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    body: Mapped[str] = mapped_column(String(4000))
    __table_args__ = (
        ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
    )


class Job(Identified, Base):
    __tablename__ = "job"
    case_id: Mapped[str] = mapped_column(ForeignKey("case_record.id"))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshot.id"))
    kind: Mapped[str] = mapped_column(String(32), default="ANALYZE")
    request_digest: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    requested_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    fence: Mapped[int] = mapped_column(Integer, default=0)
    owner: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("requested_by", "case_id", "kind", "idempotency_key"),)


class WorkerSlot(Base):
    __tablename__ = "worker_slot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job.id"), unique=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("id BETWEEN 1 AND 5"),)


class Artifact(Identified, Base):
    __tablename__ = "artifact"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.id"))
    case_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    case_version: Mapped[int] = mapped_column(Integer)
    parent_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifact.id"))
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    policy_version: Mapped[str] = mapped_column(String(64), default="policy-v1")
    validator_version: Mapped[str] = mapped_column(String(64), default="validator-v1")
    narrative: Mapped[bytes] = mapped_column(LargeBinary)
    manifest: Mapped[bytes] = mapped_column(LargeBinary)
    narrative_sha256: Mapped[str] = mapped_column(String(64), default="")
    manifest_sha256: Mapped[str] = mapped_column(String(64), default="")
    payload_digest: Mapped[str] = mapped_column(String(64))
    validation: Mapped[dict] = mapped_column(JSONB)
    contributors_snapshot: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    __table_args__ = (
        ForeignKeyConstraint(["case_id", "dataset_id"], ["case_record.id", "case_record.dataset_id"]),
        ForeignKeyConstraint(["snapshot_id", "dataset_id"], ["snapshot.id", "snapshot.dataset_id"]),
    )


class Approval(Identified, Base):
    __tablename__ = "approval"
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifact.id"), unique=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    payload_digest: Mapped[str] = mapped_column(String(64))
    evidence_generation: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(32), default="APPROVED")
    review_note: Mapped[str | None] = mapped_column(String(4000))
    envelope_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    envelope_digest: Mapped[str] = mapped_column(String(64), default="")


class Export(Identified, Base):
    __tablename__ = "export"
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifact.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    export_kind: Mapped[str] = mapped_column(String(32), default="CURRENT")
    dataset_generation_at_export: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("app_user.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def create_engine_from_url(url: str, **kwargs) -> Engine:
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL with psycopg is required")
    connect_args = {"connect_timeout": 5, **kwargs.pop("connect_args", {})}
    return create_engine(parsed, pool_pre_ping=True, connect_args=connect_args, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)


def set_transaction_identity(session, user_id: str | None, roles: list[str] | set[str] | None = None,
                             *, is_worker: bool = False) -> None:
    """Bind transaction-local RLS identity parameters cleanly for pooled connections."""
    role_set = set(roles or ())
    bypass = is_worker or bool({"administrator", "auditor"}.intersection(role_set))
    session.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": user_id or ""})
    session.execute(text("SELECT set_config('app.rls_bypass', :bypass, true)"), {"bypass": "true" if bypass else "false"})
