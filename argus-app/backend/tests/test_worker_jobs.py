"""Milestone C worker & durable job queue tests: 5-slot cap, fencing, idempotency, cancellation & restart."""
import os
import sys
from datetime import timedelta
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
    CaseAssignment, CaseRecord, Dataset, DatasetGrant, Job, User, WorkerSlot,
    create_engine_from_url, make_session_factory, utcnow,
)
from backend.services.intake_service import Conflict, activate_batch, parse_batch  # noqa: E402
from backend.services.job_service import (  # noqa: E402
    claim_next_job, enqueue_analysis_job, heartbeat_job, publish_job_outcome,
    reclaim_expired_leases, request_cancel_job,
)
from backend.tests.test_intake import files  # noqa: E402
from backend.worker import run_worker_once  # noqa: E402


@pytest.fixture
def pg_worker_env():
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
    schema = "worker_test_" + uuid4().hex
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
            analyst = User(issuer="idp", subject="an", display_name="Analyst", roles=["analyst"])
            ds = Dataset(name="Bank", namespace="bank")
            s.add_all([analyst, ds])
            s.flush()
            s.add(DatasetGrant(user_id=analyst.id, dataset_id=ds.id, can_import=True))
            act = activate_batch(s, ds.id, analyst.id, parse_batch(files(), "bank", None), 0, "b1")
            case = CaseRecord(dataset_id=ds.id, snapshot_id=act.snapshot_id, subject_id="002", title="Worker Case", created_by=analyst.id)
            s.add(case)
            s.flush()
            s.add(CaseAssignment(case_id=case.id, user_id=analyst.id))
            ids = {"analyst": analyst.id, "ds": ds.id, "case": case.id}
        yield url, engine, factory, ids, schema
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_pg_idempotency_conflict_and_global_five_slot_cap(pg_worker_env):
    _, _, factory, ids, _ = pg_worker_env
    with factory.begin() as s:
        j1, created1 = enqueue_analysis_job(s, ids["case"], ids["analyst"], "idem-1", {"hop_depth": 3})
        j1_again, created2 = enqueue_analysis_job(s, ids["case"], ids["analyst"], "idem-1", {"hop_depth": 3})
        assert created1 is True and created2 is False and j1.id == j1_again.id

    with pytest.raises(Conflict), factory.begin() as s:
        enqueue_analysis_job(s, ids["case"], ids["analyst"], "idem-1", {"hop_depth": 4})

    # Queue 6 distinct jobs -> only 5 slots can be claimed simultaneously across all workers!
    with factory.begin() as s:
        for i in range(2, 7):
            enqueue_analysis_job(s, ids["case"], ids["analyst"], f"idem-{i}", {"hop_depth": 3})

    claimed = []
    for w in range(6):
        with factory.begin() as s:
            c = claim_next_job(s, f"worker-{w}")
            if c is not None:
                claimed.append(c)
    assert len(claimed) == 5
    assert len({c.slot_id for c in claimed}) == 5
    assert len({c.job_id for c in claimed}) == 5


def test_pg_fencing_lease_expiry_and_terminal_immutability(pg_worker_env):
    _, _, factory, ids, _ = pg_worker_env
    with factory.begin() as s:
        job, _ = enqueue_analysis_job(s, ids["case"], ids["analyst"], "fence-1", {"hop_depth": 3})
        job_id = job.id

    with factory.begin() as s:
        first_claim = claim_next_job(s, "worker-A", lease_seconds=1)
        assert first_claim is not None and first_claim.fence == 1

    # Simulate worker-A stalling past lease expiry
    with factory.begin() as s:
        slot = s.get(WorkerSlot, first_claim.slot_id)
        slot.lease_until = utcnow() - timedelta(seconds=5)
        reclaimed = reclaim_expired_leases(s)
        assert reclaimed == 1

    # worker-B reclaims with higher fence token (fence=3: +1 on reclaim, +1 on new claim)
    with factory.begin() as s:
        second_claim = claim_next_job(s, "worker-B", lease_seconds=30)
        assert second_claim is not None and second_claim.job_id == job_id
        assert second_claim.fence > first_claim.fence

    # Stale worker-A heartbeat & publication MUST be rejected
    with factory.begin() as s:
        assert heartbeat_job(s, job_id, first_claim.fence) is False
        assert publish_job_outcome(s, job_id, first_claim.fence, status="COMPLETE", result={"stale": True}) is False

    # Current worker-B publishes cleanly; subsequent late write cannot revive terminal job
    with factory.begin() as s:
        assert publish_job_outcome(s, job_id, second_claim.fence, status="COMPLETE", result={"ok": True}) is True
        assert publish_job_outcome(s, job_id, second_claim.fence, status="FAILED", error_code="LATE") is False
        final_job = s.get(Job, job_id)
        assert final_job.status == "COMPLETE"
        assert final_job.result["ok"] is True


def test_pg_supervised_spawn_worker_runs_pinned_analysis_without_analyst_session(pg_worker_env):
    url, _, factory, ids, schema = pg_worker_env
    with factory.begin() as s:
        job, _ = enqueue_analysis_job(s, ids["case"], ids["analyst"], "exec-1", {"hop_depth": 3})
        job_id = job.id

    # Analyst has NO active browser session; worker still executes & publishes under service authority
    status = run_worker_once(factory, url, "worker-spawn-1", schema=schema)
    assert status == "COMPLETE"
    with factory() as s:
        done = s.get(Job, job_id)
        assert done.status == "COMPLETE"
        assert done.result["analysis_code_version"] == "argus-analysis-v1"
        assert done.result["freshness_at_publish"]["status"] == "CURRENT_SNAPSHOT"

    # Cancellation of a queued job transitions cleanly before execution
    with factory.begin() as s:
        j2, _ = enqueue_analysis_job(s, ids["case"], ids["analyst"], "cancel-1", {"hop_depth": 2})
        cancelled = request_cancel_job(s, j2.id, ids["analyst"])
        assert cancelled.status == "CANCELLED"
