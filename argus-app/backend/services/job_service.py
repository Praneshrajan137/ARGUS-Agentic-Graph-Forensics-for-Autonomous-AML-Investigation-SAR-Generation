"""Durable PostgreSQL job queue, global 5-slot leasing, heartbeats, cancellation & fenced publication.

Invariants:
  - Case/Job QUEUED + AuditEvent commit BEFORE returning HTTP 202.
  - Idempotency binds (requested_by, case_id, kind, idempotency_key) + canonical request_digest -> 409 on conflict.
  - At most 5 concurrent jobs globally across all worker instances (worker_slot 1..5).
  - Lease/heartbeat transactions release job locks BEFORE entering the 4-level publication lock order.
  - Worker publication relies on worker service authority & current case/data policy, NOT analyst browser session.
  - Stale fence token or terminal state can NEVER publish or revive a job.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import (
    AuditEvent, AuthGuard, CaseAssignment, CaseRecord, Dataset, DatasetGrant,
    Job, Snapshot, User, WorkerSlot, set_transaction_identity, utcnow,
)
from .intake_service import Conflict, Forbidden, IntakeError, row_hash

MAX_JOB_ATTEMPTS = 3


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    case_id: str
    dataset_id: str
    snapshot_id: str
    subject_id: str
    kind: str
    fence: int
    attempt: int
    slot_id: int
    parameters: dict[str, Any]
    deadline_epoch: float
    queue_wait_ms: int


def enqueue_analysis_job(
    session: Session,
    case_id: str,
    actor_id: str,
    idempotency_key: str,
    parameters: dict[str, Any] | None = None,
) -> tuple[Job, bool]:
    """Durably enqueue an ANALYZE job under strict 4-level lock order.

    Returns (job, created_new). Caller commits BEFORE returning HTTP 202.
    """
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise IntakeError("A bounded idempotency key is required")

    params = dict(parameters or {})
    hop_depth = int(params.get("hop_depth", 3))
    if not 1 <= hop_depth <= 6:
        raise IntakeError("hop_depth must be between 1 and 6")
    normalized_params = {
        "hop_depth": hop_depth,
        "interval_start": params.get("interval_start"),
        "interval_end": params.get("interval_end"),
        "window_mode": params.get("window_mode", "ROLLING_SECONDS"),
    }

    # Lock order 1 -> 2 -> 3
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    actor = session.get(User, actor_id, populate_existing=True)
    if not actor or not actor.enabled or not {"analyst", "administrator"}.intersection(actor.roles):
        raise Forbidden("Analyst or administrator role required to enqueue analysis")
    set_transaction_identity(session, actor.id, actor.roles)

    ds_id = session.scalar(select(CaseRecord.dataset_id).where(CaseRecord.id == case_id))
    if ds_id is None:
        raise IntakeError("Case not found")

    dataset = session.scalar(
        select(Dataset).where(Dataset.id == ds_id).with_for_update(read=True).execution_options(populate_existing=True)
    )
    is_privileged = bool({"administrator", "auditor"}.intersection(actor.roles))
    if not is_privileged and session.get(DatasetGrant, (actor.id, dataset.id), populate_existing=True) is None:
        raise Forbidden("Dataset entitlement required")

    case = session.scalar(
        select(CaseRecord).where(CaseRecord.id == case_id).with_for_update().execution_options(populate_existing=True)
    )
    if case is None:
        raise IntakeError("Case not found")
    if not is_privileged and session.get(CaseAssignment, (case.id, actor.id), populate_existing=True) is None:
        raise Forbidden("Case assignment required")

    request_digest = row_hash({
        "case_id": case.id,
        "snapshot_id": case.snapshot_id,
        "kind": "ANALYZE",
        "parameters": normalized_params,
    })

    existing = session.scalar(
        select(Job).where(
            Job.requested_by == actor.id,
            Job.case_id == case.id,
            Job.kind == "ANALYZE",
            Job.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_digest != request_digest:
            raise Conflict("Idempotency key reused with different analysis parameters")
        return existing, False

    now = utcnow()
    job = Job(
        case_id=case.id,
        snapshot_id=case.snapshot_id,
        kind="ANALYZE",
        request_digest=request_digest,
        idempotency_key=idempotency_key,
        requested_by=actor.id,
        status="QUEUED",
        attempt=0,
        fence=0,
        parameters=normalized_params,
        progress={"stage": "QUEUED", "updated_at": now.isoformat()},
        created_at=now,
    )
    session.add(job)
    session.flush()
    case.active_job_id = job.id
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="JOB_QUEUED",
        resource_id=job.id,
        detail={"case_id": case.id, "snapshot_id": case.snapshot_id, "kind": "ANALYZE"},
        created_at=now,
    ))
    session.flush()
    return job, True


def request_cancel_job(session: Session, job_id: str, actor_id: str) -> Job:
    """Request cancellation of a queued or running job under strict lock order."""
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    actor = session.get(User, actor_id, populate_existing=True)
    if not actor or not actor.enabled or not {"analyst", "administrator"}.intersection(actor.roles):
        raise Forbidden("Authorized role required to cancel jobs")
    set_transaction_identity(session, actor.id, actor.roles)

    job_case_id = session.scalar(select(Job.case_id).where(Job.id == job_id))
    if job_case_id is None:
        raise IntakeError("Job not found")
    ds_id = session.scalar(select(CaseRecord.dataset_id).where(CaseRecord.id == job_case_id))
    session.scalar(select(Dataset).where(Dataset.id == ds_id).with_for_update(read=True))
    case = session.scalar(select(CaseRecord).where(CaseRecord.id == job_case_id).with_for_update())
    is_privileged = "administrator" in (actor.roles or [])
    if not is_privileged and session.get(CaseAssignment, (case.id, actor.id)) is None:
        raise Forbidden("Case assignment required")

    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True))
    if job.status in ("COMPLETE", "FAILED", "CANCELLED"):
        return job
    now = utcnow()
    if job.status == "QUEUED":
        job.status = "CANCELLED"
        job.finished_at = now
        job.error_code = "CANCELLED_BEFORE_START"
    else:
        job.status = "CANCEL_REQUESTED"
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="JOB_CANCEL_REQUESTED",
        resource_id=job.id,
        detail={"case_id": case.id, "status": job.status},
        created_at=now,
    ))
    session.flush()
    return job


def reclaim_expired_leases(session: Session, *, max_attempts: int = MAX_JOB_ATTEMPTS) -> int:
    """Reclaim expired worker slots and requeue or fail orphaned jobs (short standalone tx)."""
    set_transaction_identity(session, None, is_worker=True)
    now = utcnow()
    reclaimed = 0
    expired_slots = session.scalars(
        select(WorkerSlot)
        .where(WorkerSlot.job_id.is_not(None), WorkerSlot.lease_until < now)
        .order_by(WorkerSlot.id)
        .with_for_update(skip_locked=True)
    ).all()

    for slot in expired_slots:
        job = session.scalar(
            select(Job).where(Job.id == slot.job_id).with_for_update(skip_locked=True)
        )
        slot.job_id = None
        slot.lease_until = None
        if job is not None and job.status in ("RUNNING", "CANCEL_REQUESTED"):
            if job.status == "CANCEL_REQUESTED":
                job.status = "CANCELLED"
                job.finished_at = now
                job.error_code = "CANCELLED"
            elif job.attempt >= max_attempts:
                job.status = "FAILED"
                job.finished_at = now
                job.error_code = "LEASE_EXPIRED_MAX_ATTEMPTS"
            else:
                job.status = "QUEUED"
                job.owner = None
                job.lease_until = None
            job.fence += 1  # Invalidate any slow zombie worker attempting late publication
            reclaimed += 1
    session.flush()
    return reclaimed


def claim_next_job(
    session: Session,
    worker_id: str,
    *,
    lease_seconds: int = 30,
    job_timeout_seconds: int = 120,
    max_attempts: int = MAX_JOB_ATTEMPTS,
) -> ClaimedJob | None:
    """Atomically claim one of the 5 global worker slots and one QUEUED job."""
    set_transaction_identity(session, None, is_worker=True)
    reclaim_expired_leases(session, max_attempts=max_attempts)

    slot = session.scalar(
        select(WorkerSlot)
        .where(WorkerSlot.job_id.is_(None))
        .order_by(WorkerSlot.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if slot is None:
        return None

    job = session.scalar(
        select(Job)
        .where(Job.status == "QUEUED", Job.attempt < max_attempts)
        .order_by(Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None

    case = session.get(CaseRecord, job.case_id)
    if case is None:
        job.status = "FAILED"
        job.error_code = "CASE_MISSING"
        job.finished_at = utcnow()
        session.flush()
        return None

    now = utcnow()
    lease_until = now + timedelta(seconds=lease_seconds)
    deadline = now + timedelta(seconds=job_timeout_seconds)

    job.status = "RUNNING"
    job.attempt += 1
    job.fence += 1
    job.owner = worker_id
    job.lease_until = lease_until
    job.deadline = deadline
    job.started_at = now
    job.progress = {"stage": "RUNNING", "attempt": job.attempt, "updated_at": now.isoformat()}

    slot.job_id = job.id
    slot.lease_until = lease_until

    wait_ms = max(0, int((now - job.created_at).total_seconds() * 1000))
    session.add(AuditEvent(
        actor_id=None,
        event_type="JOB_CLAIMED",
        resource_id=job.id,
        detail={"worker_id": worker_id, "slot_id": slot.id, "attempt": job.attempt, "fence": job.fence},
        created_at=now,
    ))
    session.flush()
    return ClaimedJob(
        job_id=job.id,
        case_id=case.id,
        dataset_id=case.dataset_id,
        snapshot_id=job.snapshot_id,
        subject_id=case.subject_id,
        kind=job.kind,
        fence=job.fence,
        attempt=job.attempt,
        slot_id=slot.id,
        parameters=dict(job.parameters or {}),
        deadline_epoch=deadline.timestamp(),
        queue_wait_ms=wait_ms,
    )


def heartbeat_job(session: Session, job_id: str, fence: int, *, lease_seconds: int = 30) -> bool:
    """Short standalone lease heartbeat. Returns False if job lost lease, was cancelled, or timed out."""
    set_transaction_identity(session, None, is_worker=True)
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True))
    now = utcnow()
    if job is None or job.fence != fence or job.status != "RUNNING":
        return False
    if job.deadline and now >= job.deadline:
        return False

    new_lease = now + timedelta(seconds=lease_seconds)
    job.lease_until = new_lease
    job.progress = {**(job.progress or {}), "heartbeat_at": now.isoformat()}
    slot = session.scalar(select(WorkerSlot).where(WorkerSlot.job_id == job.id).with_for_update())
    if slot is not None:
        slot.lease_until = new_lease
    session.flush()
    return True


def publish_job_outcome(
    session: Session,
    job_id: str,
    fence: int,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    retryable: bool = False,
    max_attempts: int = MAX_JOB_ATTEMPTS,
) -> bool:
    """Fenced result publication under strict 4-level lock order (1. AuthGuard -> 2. Dataset -> 3. Case -> 4. Job).

    Uses worker service authority (NOT the analyst's browser session).
    Never revives terminal jobs or accepts stale fence tokens.
    """
    set_transaction_identity(session, None, is_worker=True)

    # Peek routing IDs before acquiring ordered locks
    job_meta = session.execute(select(Job.case_id, Job.snapshot_id).where(Job.id == job_id)).first()
    if job_meta is None:
        return False
    case_id, snapshot_id = job_meta
    ds_id = session.scalar(select(CaseRecord.dataset_id).where(CaseRecord.id == case_id))
    if ds_id is None:
        return False

    # Strict 4-level lock order
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    dataset = session.scalar(
        select(Dataset).where(Dataset.id == ds_id).with_for_update(read=True).execution_options(populate_existing=True)
    )
    case = session.scalar(
        select(CaseRecord).where(CaseRecord.id == case_id).with_for_update().execution_options(populate_existing=True)
    )
    job = session.scalar(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )

    if job is None or job.fence != fence or job.status in ("COMPLETE", "FAILED", "CANCELLED"):
        return False

    now = utcnow()
    slot = session.scalar(select(WorkerSlot).where(WorkerSlot.job_id == job.id).with_for_update())
    if slot is not None:
        slot.job_id = None
        slot.lease_until = None

    if job.status == "CANCEL_REQUESTED" or status == "CANCELLED":
        job.status = "CANCELLED"
        job.finished_at = now
        job.error_code = error_code or "CANCELLED"
        job.progress = {"stage": "CANCELLED", "updated_at": now.isoformat()}
    elif status == "FAILED" and retryable and job.attempt < max_attempts:
        job.status = "QUEUED"
        job.owner = None
        job.lease_until = None
        job.error_code = error_code or "TRANSIENT_RETRY"
        job.progress = {"stage": "REQUEUED", "attempt": job.attempt, "updated_at": now.isoformat()}
    elif status == "COMPLETE":
        snapshot = session.get(Snapshot, snapshot_id, populate_existing=True)
        payload = dict(result or {})
        if snapshot is not None and dataset is not None:
            is_hist = dataset.generation > snapshot.generation
            payload["freshness_at_publish"] = {
                "status": "HISTORICAL_SNAPSHOT" if is_hist else "CURRENT_SNAPSHOT",
                "snapshot_generation": snapshot.generation,
                "dataset_generation_at_publish": dataset.generation,
            }
        job.status = "COMPLETE"
        job.result = payload
        job.finished_at = now
        job.error_code = None
        job.progress = {"stage": "COMPLETE", "updated_at": now.isoformat()}
        case.version += 1
    else:
        job.status = "FAILED"
        job.finished_at = now
        job.error_code = error_code or "EXECUTION_FAILED"
        job.progress = {"stage": "FAILED", "error_code": job.error_code, "updated_at": now.isoformat()}

    session.add(AuditEvent(
        actor_id=None,
        event_type="JOB_PUBLISHED",
        resource_id=job.id,
        detail={
            "case_id": case.id,
            "final_status": job.status,
            "attempt": job.attempt,
            "fence": fence,
            "error_code": job.error_code,
        },
        created_at=now,
    ))
    session.flush()
    return True
