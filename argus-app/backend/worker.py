"""Bounded supervised Python worker process for ARGUS production analysis.

Uses multiprocessing(spawn) child isolation so cancellation, deadline expiry, and
lease loss terminate actual OS execution rather than stranding Python threads.
All operational logs/metrics contain opaque IDs only (zero financial content).
"""
import logging
import multiprocessing as mp
import os
import queue as queue_mod
import signal
import socket
import time
from dataclasses import replace
from typing import Any

from sqlalchemy.exc import OperationalError

from .database import create_engine_from_url, make_session_factory, set_transaction_identity
from .models.policy import DEFAULT_PRODUCTION_POLICY
from .services.analysis_service import analyze_snapshot
from .services.job_service import (
    ClaimedJob, claim_next_job, heartbeat_job, publish_job_outcome,
)
from .settings import ProductionSettings

logger = logging.getLogger("argus.worker")


def _child_execute_analysis(
    database_url: str,
    snapshot_id: str,
    subject_id: str,
    parameters: dict[str, Any],
    max_events: int,
    max_accounts: int,
    deadline_seconds: float,
    result_queue: mp.Queue,
    schema: str | None = None,
) -> None:
    """Isolated child-process target: executes pinned snapshot analysis and returns result via IPC."""
    engine = None
    try:
        connect_args = {"options": f"-csearch_path={schema}"} if schema else {}
        engine = create_engine_from_url(database_url, connect_args=connect_args)
        factory = make_session_factory(engine)
        policy = DEFAULT_PRODUCTION_POLICY
        if parameters.get("window_mode") == "INSTITUTION_BUSINESS_DAY":
            policy = replace(
                policy,
                business_day=replace(policy.business_day, mode="INSTITUTION_BUSINESS_DAY"),
            )
        with factory() as session:
            set_transaction_identity(session, None, is_worker=True)
            result = analyze_snapshot(
                session,
                snapshot_id,
                subject_id,
                hop_depth=int(parameters.get("hop_depth", 3)),
                policy=policy,
                interval_start=parameters.get("interval_start"),
                interval_end=parameters.get("interval_end"),
                max_events=max_events,
                max_accounts=max_accounts,
                deadline_seconds=deadline_seconds,
            )
        result_queue.put({"ok": True, "result": result})
    except OperationalError:
        result_queue.put({"ok": False, "retryable": True, "error_code": "DB_OPERATIONAL_ERROR"})
    except ValueError:
        result_queue.put({"ok": False, "retryable": False, "error_code": "INVALID_ANALYSIS_SCOPE"})
    except Exception:
        result_queue.put({"ok": False, "retryable": False, "error_code": "UNEXPECTED_ANALYSIS_ERROR"})
    finally:
        if engine is not None:
            engine.dispose()


def _terminate_process(proc: mp.Process) -> None:
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(timeout=2.0)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=2.0)


def execute_claimed_job(
    factory,
    database_url: str,
    claimed: ClaimedJob,
    *,
    max_events: int = 20_000,
    max_accounts: int = 5_000,
    lease_seconds: int = 30,
    heartbeat_interval: float = 5.0,
    schema: str | None = None,
) -> str:
    """Supervise one claimed job inside an isolated spawned child process."""
    t0 = time.monotonic()
    ctx = mp.get_context("spawn")
    result_queue: mp.Queue = ctx.Queue(maxsize=1)
    remaining = max(1.0, claimed.deadline_epoch - time.time())

    proc = ctx.Process(
        target=_child_execute_analysis,
        args=(
            database_url,
            claimed.snapshot_id,
            claimed.subject_id,
            claimed.parameters,
            max_events,
            max_accounts,
            remaining,
            result_queue,
            schema,
        ),
        daemon=True,
    )
    proc.start()

    last_hb = time.monotonic()
    aborted_reason: str | None = None

    while proc.is_alive():
        proc.join(timeout=0.25)
        if not proc.is_alive():
            break
        now_wall = time.time()
        if now_wall >= claimed.deadline_epoch:
            aborted_reason = "DEADLINE_EXCEEDED"
            _terminate_process(proc)
            break
        if (time.monotonic() - last_hb) >= heartbeat_interval:
            with factory.begin() as s:
                still_owned = heartbeat_job(s, claimed.job_id, claimed.fence, lease_seconds=lease_seconds)
            last_hb = time.monotonic()
            if not still_owned:
                aborted_reason = "LEASE_OR_CANCEL_ABORT"
                _terminate_process(proc)
                break

    duration_ms = int((time.monotonic() - t0) * 1000)
    outcome_status = "FAILED"
    result_payload = None
    error_code = None
    retryable = False

    if aborted_reason == "DEADLINE_EXCEEDED":
        outcome_status = "FAILED"
        error_code = "DEADLINE_EXCEEDED"
    elif aborted_reason == "LEASE_OR_CANCEL_ABORT":
        outcome_status = "CANCELLED"
        error_code = "CANCELLED_OR_FENCED"
    else:
        try:
            msg = result_queue.get_nowait()
            if msg.get("ok"):
                outcome_status = "COMPLETE"
                result_payload = msg["result"]
            else:
                outcome_status = "FAILED"
                error_code = msg.get("error_code", "EXECUTION_FAILED")
                retryable = bool(msg.get("retryable", False))
        except queue_mod.Empty:
            outcome_status = "FAILED"
            error_code = f"CHILD_EXIT_{proc.exitcode}"
            retryable = True

    with factory.begin() as s:
        published = publish_job_outcome(
            s,
            claimed.job_id,
            claimed.fence,
            status=outcome_status,
            result=result_payload,
            error_code=error_code,
            retryable=retryable,
        )

    logger.info(
        "worker_job_finished job_id=%s case_id=%s slot=%d attempt=%d fence=%d status=%s published=%s queue_wait_ms=%d duration_ms=%d",
        claimed.job_id, claimed.case_id, claimed.slot_id, claimed.attempt, claimed.fence,
        outcome_status, published, claimed.queue_wait_ms, duration_ms,
    )
    return outcome_status


def run_worker_once(
    factory,
    database_url: str,
    worker_id: str,
    *,
    max_events: int = 20_000,
    max_accounts: int = 5_000,
    lease_seconds: int = 30,
    job_timeout_seconds: int = 120,
    schema: str | None = None,
) -> str | None:
    """Attempt to claim and run a single queued job. Returns final status or None if idle."""
    with factory.begin() as s:
        claimed = claim_next_job(
            s,
            worker_id,
            lease_seconds=lease_seconds,
            job_timeout_seconds=job_timeout_seconds,
        )
    if claimed is None:
        return None
    return execute_claimed_job(
        factory,
        database_url,
        claimed,
        max_events=max_events,
        max_accounts=max_accounts,
        lease_seconds=lease_seconds,
        schema=schema,
    )


def run_worker_loop(settings: ProductionSettings, *, poll_interval: float = 0.5) -> None:
    """Long-running supervised worker daemon."""
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    engine = create_engine_from_url(settings.database_url)
    factory = make_session_factory(engine)
    stop = False

    def _handle_stop(signum, _frame):
        nonlocal stop
        logger.info("worker_shutdown_signal worker_id=%s signal=%s", worker_id, signum)
        stop = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    logger.info("worker_started worker_id=%s", worker_id)

    try:
        while not stop:
            try:
                status = run_worker_once(
                    factory,
                    settings.database_url,
                    worker_id,
                    max_events=settings.max_graph_events,
                    max_accounts=settings.max_graph_accounts,
                    job_timeout_seconds=settings.job_seconds,
                )
                if status is None:
                    time.sleep(poll_interval)
            except OperationalError:
                logger.warning("worker_db_transient_error worker_id=%s", worker_id)
                time.sleep(min(5.0, poll_interval * 4))
    finally:
        engine.dispose()
        logger.info("worker_stopped worker_id=%s", worker_id)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    run_worker_loop(ProductionSettings.from_environment())
