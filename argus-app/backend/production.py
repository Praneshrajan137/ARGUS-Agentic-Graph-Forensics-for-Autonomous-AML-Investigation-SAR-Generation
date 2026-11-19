"""ARGUS Production FastAPI Application — completely isolated from research/synthetic runtime.

Never registers /api/generate, /api/reset, /api/ground-truth, /api/benchmark, /api/assess, or /api/agent.
Never imports openai, langgraph, spacy, or synthetic world generators.
Fails closed on missing security or PostgreSQL configuration.
"""
import collections
import json
import logging
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from .auth import (
    AUTH_BIND_COOKIE, CSRF_HEADER, SESSION_COOKIE, AuthError, OIDCClient,
    authenticate_session, logout_session, revoke_principal_access,
    verify_csrf_token,
)
from .database import (
    Approval, Artifact, AuditEvent, AuthGuard, CaseAssignment, CaseComment,
    CaseFindingDisposition, CaseObservation, CaseRecord, Dataset, DatasetGrant,
    ImportBatch, Job, LedgerRecord, Snapshot, SnapshotRecord, SourceFile, WorkerSlot, create_engine_from_url, make_session_factory,
    set_transaction_identity, utcnow,
)
from .services.intake_service import (
    Conflict, Forbidden, IntakeError, activate_batch, parse_batch,
)
from .services.job_service import enqueue_analysis_job, request_cancel_job
from .services.observation_service import (
    compute_scoped_ledger_total, record_case_comment,
    record_case_observation, record_finding_disposition,
)
from .services.review_service import (
    close_case_without_export, create_draft_revision, export_approved_artifact,
    freeze_artifact_for_review, review_artifact,
)
from .settings import ProductionSettings

_REDACT_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer|cookie|authorization)\s*[=:]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
]


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pat in _REDACT_PATTERNS:
            msg = pat.sub("[REDACTED]", msg)
        return msg


logger = logging.getLogger("argus.production")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSP_HEADER = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


# ── Strict Request Schemas ──

class DatasetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    namespace: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=36)
    subject_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hop_depth: int = Field(default=3, ge=1, le=6)
    interval_start: str | None = None
    interval_end: str | None = None
    window_mode: str = Field(default="ROLLING_SECONDS")


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: str = Field(min_length=1, max_length=32)
    source_ref: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=1, max_length=8000)
    scope: dict[str, Any] | None = None


class DispositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str = Field(min_length=1, max_length=128)
    disposition: str = Field(pattern=r"^(OPEN|ESCALATED|DISMISSED|NEEDS_INFO)$")
    rationale: str = Field(min_length=1, max_length=4000)
    benign_alternative: str | None = Field(default=None, max_length=4000)
    job_id: str | None = None


class CommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)
    artifact_id: str | None = None


class DraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analyst_interpretations: list[dict[str, Any]] = Field(default_factory=list)
    parent_artifact_id: str | None = None


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(APPROVED|CHANGES_REQUESTED)$")
    review_note: str | None = Field(default=None, max_length=4000)


class CloseCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    closed_reason: str = Field(default="NO_FILING_WARRANTED", min_length=1, max_length=64)
    closure_memo: str | None = Field(default=None, max_length=4000)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_historical: bool = False


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disable_user: bool = True
    revoke_sessions: bool = True
    revoke_dataset_id: str | None = None
    revoke_case_id: str | None = None


def _map_domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthError):
        return HTTPException(status_code=401, detail="Authentication required")
    if isinstance(exc, Forbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, Conflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, IntakeError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="Internal server error")


def create_production_app(
    settings: ProductionSettings | None = None,
    *,
    engine=None,
    oidc_client: OIDCClient | None = None,
    rate_limit_rpm: int = 120,
) -> FastAPI:
    """Create the isolated production FastAPI application. Fails closed if config missing."""
    cfg = settings if settings is not None else ProductionSettings.from_environment()
    owns_engine = engine is None
    db_engine = engine if engine is not None else create_engine_from_url(cfg.database_url)
    session_factory = make_session_factory(db_engine)
    oidc = oidc_client if oidc_client is not None else OIDCClient(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if owns_engine:
            db_engine.dispose()

    app = FastAPI(
        title="ARGUS Production Workbench",
        version="1.0.0",
        docs_url=None if cfg.deployment == "production" else "/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.engine = db_engine
    app.state.session_factory = session_factory
    app.state.oidc = oidc

    # Per-principal sliding window rate limiter
    rate_windows: dict[str, collections.deque] = {}

    @app.middleware("http")
    async def security_and_admission_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = _CSP_HEADER
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.exception_handler(Exception)
    async def redacted_exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        logger.error("Unhandled production error type=%s", type(exc).__name__)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    def _enforce_rate_limit(key: str) -> None:
        now = time.monotonic()
        win = rate_windows.setdefault(key, collections.deque())
        while win and win[0] < now - 60:
            win.popleft()
        if len(win) >= rate_limit_rpm:
            raise HTTPException(status_code=429, detail="Admission rate limit exceeded")
        win.append(now)

    def require_principal(request: Request) -> tuple[str, list[str], str]:
        """Validate session cookie + CSRF header on unsafe methods + per-principal rate limit."""
        raw_cookie = request.cookies.get(SESSION_COOKIE)
        try:
            with session_factory.begin() as s:
                user, sess = authenticate_session(s, raw_cookie)
                if request.method in _UNSAFE_METHODS:
                    verify_csrf_token(sess, request.headers.get(CSRF_HEADER))
                principal = (user.id, list(user.roles or []), user.display_name)
        except Exception as exc:
            raise _map_domain_error(exc) from None
        _enforce_rate_limit(f"user:{principal[0]}")
        return principal

    # ── Runtime & Health (separated liveness / readiness / worker health) ──

    @app.get("/api/runtime")
    def runtime_info():
        return {"mode": "production", "version": "1.0.0", "deployment": cfg.deployment}

    @app.get("/api/health/live")
    def health_live():
        return {"status": "alive"}

    @app.get("/api/health/ready")
    def health_ready():
        try:
            with db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            return {"status": "ready", "schema_revision": rev}
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    @app.get("/api/health/workers")
    def health_workers():
        try:
            with session_factory() as s:
                set_transaction_identity(s, None, is_worker=True)
                slots = s.scalars(select(WorkerSlot).order_by(WorkerSlot.id)).all()
                now = utcnow()
                active = sum(1 for sl in slots if sl.job_id is not None and (sl.lease_until is None or sl.lease_until >= now))
                expired = sum(1 for sl in slots if sl.job_id is not None and sl.lease_until is not None and sl.lease_until < now)
                queued = s.scalar(select(func.count()).select_from(Job).where(Job.status == "QUEUED")) or 0
            return {
                "status": "ok",
                "total_slots": len(slots),
                "active_slots": active,
                "expired_slots": expired,
                "queued_jobs": queued,
            }
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    # ── Auth (OIDC Authorization Code + PKCE, Rotating Sessions, CSRF) ──

    @app.get("/api/auth/login")
    def auth_login(persona: str | None = Query(None)):
        try:
            with session_factory.begin() as s:
                url, browser_bind = oidc.start_login(s)
        except Exception as exc:
            raise _map_domain_error(exc) from None
        if persona and cfg.deployment == "local":
            url = f"{url}&persona={persona}"
        resp = RedirectResponse(url, status_code=302)
        resp.set_cookie(
            AUTH_BIND_COOKIE, browser_bind, httponly=True,
            secure=cfg.secure_cookies, samesite="lax", max_age=300, path="/api/auth",
        )
        return resp

    @app.get("/api/auth/callback")
    def auth_callback(request: Request, code: str = Query(...), state: str = Query(...)):
        browser_bind = request.cookies.get(AUTH_BIND_COOKIE)
        try:
            with session_factory.begin() as s:
                user, raw_session, raw_csrf = oidc.exchange_and_verify(
                    s, code=code, state=state, browser_bind=browser_bind,
                )
        except Exception as exc:
            raise _map_domain_error(exc) from None
        resp = JSONResponse({
            "user_id": user.id,
            "display_name": user.display_name,
            "roles": user.roles,
            "csrf_token": raw_csrf,
        })
        resp.delete_cookie(AUTH_BIND_COOKIE, path="/api/auth")
        resp.set_cookie(
            SESSION_COOKIE, raw_session, httponly=True,
            secure=cfg.secure_cookies, samesite="lax", max_age=cfg.session_seconds, path="/",
        )
        return resp

    @app.get("/api/auth/me")
    def auth_me(request: Request):
        raw_cookie = request.cookies.get(SESSION_COOKIE)
        try:
            with session_factory.begin() as s:
                user, sess = authenticate_session(s, raw_cookie)
                # Issue a fresh rotated session + CSRF token on explicit /me bootstrap if requested
                return {
                    "authenticated": True,
                    "user_id": user.id,
                    "display_name": user.display_name,
                    "roles": list(user.roles or []),
                    "expires_at": sess.expires_at.isoformat(),
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/auth/logout")
    def auth_logout(request: Request, _principal=Depends(require_principal)):
        raw_cookie = request.cookies.get(SESSION_COOKIE)
        with session_factory.begin() as s:
            logout_session(s, raw_cookie)
        resp = JSONResponse({"status": "signed_out"})
        resp.delete_cookie(SESSION_COOKIE, path="/")
        return resp

    # ── Datasets & Cumulative Source Intake ──

    @app.get("/api/datasets")
    def list_datasets(principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            if is_priv:
                rows = s.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()
            else:
                rows = s.scalars(
                    select(Dataset)
                    .join(DatasetGrant, DatasetGrant.dataset_id == Dataset.id)
                    .where(DatasetGrant.user_id == user_id)
                    .order_by(Dataset.created_at.desc())
                ).all()
            return {"datasets": [
                {"id": d.id, "name": d.name, "namespace": d.namespace, "generation": d.generation}
                for d in rows
            ]}

    @app.post("/api/datasets", status_code=201)
    def create_dataset(body: DatasetCreateRequest, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        if not {"administrator", "analyst"}.intersection(roles):
            raise HTTPException(status_code=403, detail="Dataset creation permission required")
        with session_factory.begin() as s:
            s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
            set_transaction_identity(s, user_id, roles)
            if s.scalar(select(Dataset).where(Dataset.namespace == body.namespace)):
                raise HTTPException(status_code=409, detail="Dataset namespace already exists")
            ds = Dataset(name=body.name, namespace=body.namespace, generation=0)
            s.add(ds)
            s.flush()
            s.add(DatasetGrant(user_id=user_id, dataset_id=ds.id, can_import=True, can_download_source="administrator" in roles))
            s.add(AuditEvent(actor_id=user_id, event_type="DATASET_CREATED", resource_id=ds.id, detail={"namespace": ds.namespace}))
            return {"id": ds.id, "name": ds.name, "namespace": ds.namespace, "generation": ds.generation}

    @app.post("/api/datasets/{dataset_id}/imports", status_code=201)
    async def import_batch(
        dataset_id: str,
        expected_generation: int = Form(...),
        controls_json: str | None = Form(None),
        entities: UploadFile | None = File(None),
        accounts: UploadFile | None = File(None),
        relationships: UploadFile | None = File(None),
        transactions: UploadFile | None = File(None),
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        principal=Depends(require_principal),
    ):
        user_id, roles, _ = principal
        file_map: dict[str, bytes] = {}
        for kind, upload in (("entities", entities), ("accounts", accounts),
                             ("relationships", relationships), ("transactions", transactions)):
            if upload is not None:
                file_map[kind] = await upload.read()
        controls = None
        if controls_json:
            try:
                controls = json.loads(controls_json)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid controls_json payload") from None

        try:
            with session_factory.begin() as s:
                set_transaction_identity(s, user_id, roles)
                ds = s.get(Dataset, dataset_id)
                if ds is None:
                    raise IntakeError("Dataset not found")
                parsed = parse_batch(file_map, ds.namespace, controls)
                act = activate_batch(s, dataset_id, user_id, parsed, expected_generation, idempotency_key)
                return {
                    "batch_id": act.batch_id,
                    "snapshot_id": act.snapshot_id,
                    "generation": act.generation,
                    "reconciliation": act.reconciliation,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.get("/api/datasets/{dataset_id}/imports")
    def list_imports(dataset_id: str, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            if not is_priv and s.get(DatasetGrant, (user_id, dataset_id)) is None:
                raise HTTPException(status_code=403, detail="Dataset entitlement required")
            batches = s.scalars(
                select(ImportBatch).where(ImportBatch.dataset_id == dataset_id).order_by(ImportBatch.created_at.desc())
            ).all()
            return {"imports": [
                {
                    "id": b.id, "parent_generation": b.parent_generation, "status": b.status,
                    "schema_version": b.schema_version, "transformation_version": b.transformation_version,
                    "extract_id": b.extract_id, "reconciliation": b.reconciliation,
                    "created_at": b.created_at.isoformat(),
                }
                for b in batches
            ]}

    @app.get("/api/datasets/{dataset_id}/files/{file_id}")
    def download_source_file(dataset_id: str, file_id: str, principal=Depends(require_principal)):
        """Full raw source downloads require explicit can_download_source bulk-source entitlement."""
        user_id, roles, _ = principal
        with session_factory.begin() as s:
            s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
            set_transaction_identity(s, user_id, roles)
            grant = s.get(DatasetGrant, (user_id, dataset_id), populate_existing=True)
            if "administrator" not in roles and (grant is None or not grant.can_download_source):
                raise HTTPException(status_code=403, detail="Bulk source download permission required")
            sf = s.scalar(select(SourceFile).where(SourceFile.id == file_id, SourceFile.dataset_id == dataset_id))
            if sf is None:
                raise HTTPException(status_code=404, detail="Source file not found")
            s.add(AuditEvent(actor_id=user_id, event_type="SOURCE_FILE_DOWNLOADED", resource_id=sf.id, detail={"dataset_id": dataset_id}))
            return Response(
                content=bytes(sf.bytes),
                media_type="text/csv; charset=utf-8",
                headers={"X-Source-SHA256": sf.sha256},
            )

    # ── Cases, Durable Analysis Jobs, Observations & Dispositions ──

    @app.get("/api/cases")
    def list_cases(principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            stmt = select(CaseRecord, Dataset.generation, Snapshot.generation).join(
                Dataset, Dataset.id == CaseRecord.dataset_id
            ).join(Snapshot, Snapshot.id == CaseRecord.snapshot_id)
            if not is_priv:
                stmt = stmt.join(CaseAssignment, CaseAssignment.case_id == CaseRecord.id).where(
                    CaseAssignment.user_id == user_id
                )
            rows = s.execute(stmt.order_by(CaseRecord.created_at.desc())).all()
            return {"cases": [
                {
                    "id": c.id, "dataset_id": c.dataset_id, "snapshot_id": c.snapshot_id,
                    "subject_id": c.subject_id, "title": c.title, "status": c.status,
                    "version": c.version, "active_job_id": c.active_job_id,
                    "snapshot_generation": snap_gen, "current_dataset_generation": ds_gen,
                    "evidence_stale": ds_gen > snap_gen,
                    "created_at": c.created_at.isoformat(),
                }
                for c, ds_gen, snap_gen in rows
            ]}

    @app.post("/api/cases", status_code=201)
    def create_case(body: CaseCreateRequest, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        if not {"analyst", "administrator"}.intersection(roles):
            raise HTTPException(status_code=403, detail="Analyst role required to create cases")
        try:
            with session_factory.begin() as s:
                s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
                set_transaction_identity(s, user_id, roles)
                ds = s.scalar(select(Dataset).where(Dataset.id == body.dataset_id).with_for_update(read=True))
                if ds is None:
                    raise IntakeError("Dataset not found")
                if "administrator" not in roles and s.get(DatasetGrant, (user_id, ds.id)) is None:
                    raise Forbidden("Case creation grants no new data rights: dataset entitlement required")
                snap = s.scalar(select(Snapshot).where(Snapshot.dataset_id == ds.id, Snapshot.generation == ds.generation))
                if snap is None:
                    raise IntakeError("Dataset has no activated snapshot")
                case = CaseRecord(
                    dataset_id=ds.id, snapshot_id=snap.id, subject_id=body.subject_id,
                    title=body.title, created_by=user_id,
                )
                s.add(case)
                s.flush()
                s.add(CaseAssignment(case_id=case.id, user_id=user_id))
                s.add(AuditEvent(actor_id=user_id, event_type="CASE_CREATED", resource_id=case.id,
                                 detail={"dataset_id": ds.id, "snapshot_id": snap.id}))
                return {
                    "id": case.id, "dataset_id": case.dataset_id, "snapshot_id": case.snapshot_id,
                    "subject_id": case.subject_id, "title": case.title, "status": case.status,
                    "version": case.version, "snapshot_generation": snap.generation,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            case = s.get(CaseRecord, case_id)
            if case is None:
                raise HTTPException(status_code=404, detail="Case not found")
            if not is_priv:
                if s.get(DatasetGrant, (user_id, case.dataset_id)) is None or s.get(CaseAssignment, (case.id, user_id)) is None:
                    raise HTTPException(status_code=403, detail="Case authorization required")
            ds = s.get(Dataset, case.dataset_id)
            snap = s.get(Snapshot, case.snapshot_id)
            batch = s.get(ImportBatch, snap.batch_id) if snap and snap.batch_id else None
            jobs = s.scalars(select(Job).where(Job.case_id == case.id).order_by(Job.created_at.desc())).all()
            observations = s.scalars(select(CaseObservation).where(CaseObservation.case_id == case.id).order_by(CaseObservation.created_at.desc())).all()
            dispositions = s.scalars(select(CaseFindingDisposition).where(CaseFindingDisposition.case_id == case.id).order_by(CaseFindingDisposition.created_at.desc())).all()
            comments = s.scalars(select(CaseComment).where(CaseComment.case_id == case.id).order_by(CaseComment.created_at.asc())).all()
            artifacts = s.scalars(select(Artifact).where(Artifact.case_id == case.id).order_by(Artifact.revision_number.desc())).all()
            return {
                "id": case.id, "dataset_id": case.dataset_id, "snapshot_id": case.snapshot_id,
                "subject_id": case.subject_id, "title": case.title, "status": case.status,
                "version": case.version, "active_job_id": case.active_job_id,
                "closed_reason": case.closed_reason, "closure_memo": case.closure_memo,
                "snapshot_generation": snap.generation if snap else 0,
                "current_dataset_generation": ds.generation if ds else 0,
                "evidence_stale": bool(ds and snap and ds.generation > snap.generation),
                "reconciliation": batch.reconciliation if batch else {"status": "UNVERIFIED"},
                "jobs": [
                    {"id": j.id, "status": j.status, "attempt": j.attempt, "error_code": j.error_code,
                     "progress": j.progress, "result": j.result, "created_at": j.created_at.isoformat()}
                    for j in jobs
                ],
                "observations": [
                    {"id": o.id, "source_kind": o.source_kind, "source_ref": o.source_ref,
                     "raw_text": o.raw_text, "scope": o.scope_json, "comparison": o.comparison_json,
                     "created_by": o.created_by, "created_at": o.created_at.isoformat()}
                    for o in observations
                ],
                "dispositions": [
                    {"id": d.id, "finding_id": d.finding_id, "disposition": d.disposition,
                     "rationale": d.rationale, "benign_alternative": d.benign_alternative,
                     "actor_id": d.actor_id, "created_at": d.created_at.isoformat()}
                    for d in dispositions
                ],
                "comments": [
                    {"id": cm.id, "artifact_id": cm.artifact_id, "author_id": cm.author_id,
                     "body": cm.body, "created_at": cm.created_at.isoformat()}
                    for cm in comments
                ],
                "artifacts": [
                    {"id": a.id, "revision_number": a.revision_number, "parent_artifact_id": a.parent_artifact_id,
                     "status": a.status, "payload_digest": a.payload_digest, "validation": a.validation,
                     "contributors": a.contributors_snapshot, "created_by": a.created_by,
                     "created_at": a.created_at.isoformat()}
                    for a in artifacts
                ],
            }

    @app.get("/api/cases/{case_id}/records")
    def get_cited_case_records(case_id: str, event_ids: str | None = Query(None), principal=Depends(require_principal)):
        """Case readers receive cited pinned rows only (not bulk source files)."""
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            case = s.get(CaseRecord, case_id)
            if case is None:
                raise HTTPException(status_code=404, detail="Case not found")
            if not is_priv and (s.get(DatasetGrant, (user_id, case.dataset_id)) is None or s.get(CaseAssignment, (case.id, user_id)) is None):
                raise HTTPException(status_code=403, detail="Case authorization required")
            requested = {item.strip() for item in (event_ids or "").split(",") if item.strip()}
            stmt = (
                select(LedgerRecord, SourceFile.sha256, SourceFile.filename)
                .join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id)
                .join(SourceFile, SourceFile.id == LedgerRecord.source_file_id)
                .where(SnapshotRecord.snapshot_id == case.snapshot_id, LedgerRecord.kind == "transactions")
            )
            if requested:
                stmt = stmt.where(LedgerRecord.external_id.in_(requested))
            else:
                stmt = stmt.limit(200)
            rows = s.execute(stmt).all()
            return {"records": [
                {
                    "record_id": r.id, "external_id": r.external_id, "digest": r.digest,
                    "source_file_id": r.source_file_id, "source_file_sha256": sf_sha,
                    "source_filename": sf_name, "row_number": r.row_number,
                    "analysis_eligible": r.analysis_eligible, "exclusion_reason": r.exclusion_reason,
                    "payload": r.payload,
                }
                for r, sf_sha, sf_name in rows
            ]}

    @app.post("/api/cases/{case_id}/analyze", status_code=202)
    def submit_analysis(
        case_id: str,
        body: AnalyzeRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        principal=Depends(require_principal),
    ):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                job, created = enqueue_analysis_job(s, case_id, user_id, idempotency_key, body.model_dump())
                return {
                    "job_id": job.id, "case_id": job.case_id, "snapshot_id": job.snapshot_id,
                    "status": job.status, "created": created,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            job = s.get(Job, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            case = s.get(CaseRecord, job.case_id)
            if case is None:
                raise HTTPException(status_code=404, detail="Case not found")
            if not is_priv and (s.get(DatasetGrant, (user_id, case.dataset_id)) is None or s.get(CaseAssignment, (case.id, user_id)) is None):
                raise HTTPException(status_code=403, detail="Case authorization required")
            return {
                "job_id": job.id, "case_id": job.case_id, "snapshot_id": job.snapshot_id,
                "status": job.status, "attempt": job.attempt, "error_code": job.error_code,
                "progress": job.progress, "result": job.result,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                job = request_cancel_job(s, job_id, user_id)
                return {"job_id": job.id, "status": job.status}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/cases/{case_id}/observations", status_code=201)
    def add_observation(case_id: str, body: ObservationRequest, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        try:
            with session_factory.begin() as s:
                s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
                set_transaction_identity(s, user_id, roles)
                case = s.scalar(select(CaseRecord).where(CaseRecord.id == case_id).with_for_update())
                if case is None:
                    raise IntakeError("Case not found")
                if "administrator" not in roles and s.get(CaseAssignment, (case.id, user_id)) is None:
                    raise Forbidden("Case assignment required")
                ledger_total = None
                if body.scope and all(body.scope.get(k) for k in ("entity_id", "currency", "period_start", "period_end", "basis")):
                    ledger_total = compute_scoped_ledger_total(
                        s, case.snapshot_id, body.scope["entity_id"], body.scope["currency"],
                        body.scope["period_start"], body.scope["period_end"], body.scope["basis"],
                    )
                obs = record_case_observation(
                    s, case, user_id, source_kind=body.source_kind, source_ref=body.source_ref,
                    raw_text=body.raw_text, scope=body.scope, ledger_total=ledger_total,
                )
                return {"id": obs.id, "comparison": obs.comparison_json}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/cases/{case_id}/dispositions", status_code=201)
    def add_disposition(case_id: str, body: DispositionRequest, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        try:
            with session_factory.begin() as s:
                s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
                set_transaction_identity(s, user_id, roles)
                case = s.scalar(select(CaseRecord).where(CaseRecord.id == case_id).with_for_update())
                if case is None:
                    raise IntakeError("Case not found")
                if "administrator" not in roles and s.get(CaseAssignment, (case.id, user_id)) is None:
                    raise Forbidden("Case assignment required")
                entry = record_finding_disposition(
                    s, case, user_id, finding_id=body.finding_id, disposition=body.disposition,
                    rationale=body.rationale, benign_alternative=body.benign_alternative, job_id=body.job_id,
                )
                return {"id": entry.id, "finding_id": entry.finding_id, "disposition": entry.disposition}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/cases/{case_id}/comments", status_code=201)
    def add_comment(case_id: str, body: CommentRequest, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        try:
            with session_factory.begin() as s:
                s.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
                set_transaction_identity(s, user_id, roles)
                case = s.scalar(select(CaseRecord).where(CaseRecord.id == case_id).with_for_update())
                if case is None:
                    raise IntakeError("Case not found")
                if "administrator" not in roles and s.get(CaseAssignment, (case.id, user_id)) is None:
                    raise Forbidden("Case assignment required")
                cm = record_case_comment(s, case, user_id, body=body.body, artifact_id=body.artifact_id)
                return {"id": cm.id, "author_id": cm.author_id, "body": cm.body}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    # ── Artifacts, Review, Closure & Immutable Export ──

    @app.post("/api/cases/{case_id}/artifacts", status_code=201)
    def create_artifact(case_id: str, body: DraftCreateRequest, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                art = create_draft_revision(
                    s, case_id, user_id,
                    analyst_interpretations=body.analyst_interpretations,
                    parent_artifact_id=body.parent_artifact_id,
                )
                return {
                    "id": art.id, "revision_number": art.revision_number, "status": art.status,
                    "payload_digest": art.payload_digest, "validation": art.validation,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str, principal=Depends(require_principal)):
        user_id, roles, _ = principal
        is_priv = bool({"administrator", "auditor"}.intersection(roles))
        with session_factory() as s:
            set_transaction_identity(s, user_id, roles)
            art = s.get(Artifact, artifact_id)
            if art is None:
                raise HTTPException(status_code=404, detail="Artifact not found")
            if not is_priv and (s.get(DatasetGrant, (user_id, art.dataset_id)) is None or s.get(CaseAssignment, (art.case_id, user_id)) is None):
                raise HTTPException(status_code=403, detail="Artifact authorization required")
            ds = s.get(Dataset, art.dataset_id)
            snap = s.get(Snapshot, art.snapshot_id)
            approval = s.scalar(select(Approval).where(Approval.artifact_id == art.id))
            return {
                "id": art.id, "case_id": art.case_id, "revision_number": art.revision_number,
                "parent_artifact_id": art.parent_artifact_id, "status": art.status,
                "payload_digest": art.payload_digest, "narrative_sha256": art.narrative_sha256,
                "manifest_sha256": art.manifest_sha256, "validation": art.validation,
                "contributors": art.contributors_snapshot,
                "narrative": bytes(art.narrative).decode("utf-8"),
                "manifest": json.loads(bytes(art.manifest).decode("utf-8")),
                "approval": approval.envelope_json if approval else None,
                "envelope_digest": approval.envelope_digest if approval else None,
                "evidence_stale": bool(ds and snap and ds.generation > snap.generation),
                "current_dataset_generation": ds.generation if ds else 0,
                "snapshot_generation": snap.generation if snap else 0,
            }

    @app.post("/api/artifacts/{artifact_id}/freeze")
    def freeze_artifact(artifact_id: str, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                art = freeze_artifact_for_review(s, artifact_id, user_id)
                return {"id": art.id, "status": art.status, "payload_digest": art.payload_digest}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/artifacts/{artifact_id}/review")
    def submit_review(artifact_id: str, body: ReviewDecisionRequest, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                approval = review_artifact(s, artifact_id, user_id, decision=body.decision, review_note=body.review_note)
                return {
                    "approval_id": approval.id, "decision": approval.decision,
                    "payload_digest": approval.payload_digest, "envelope_digest": approval.envelope_digest,
                    "envelope": approval.envelope_json,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/artifacts/{artifact_id}/export")
    def export_artifact(artifact_id: str, body: ExportRequest, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                exp = export_approved_artifact(s, artifact_id, user_id, allow_historical=body.allow_historical)
                return {
                    "export_id": exp.export_id,
                    "artifact_id": exp.artifact_id,
                    "export_kind": exp.export_kind,
                    "banner": exp.banner,
                    "payload_digest": exp.payload_digest,
                    "envelope_digest": exp.envelope_digest,
                    "evidence_generation": exp.evidence_generation,
                    "dataset_generation_at_export": exp.dataset_generation_at_export,
                    "narrative": exp.narrative_bytes.decode("utf-8"),
                    "manifest": json.loads(exp.manifest_bytes.decode("utf-8")),
                    "approval_envelope": exp.approval_envelope,
                }
        except Exception as exc:
            raise _map_domain_error(exc) from None

    @app.post("/api/cases/{case_id}/close")
    def close_case(case_id: str, body: CloseCaseRequest, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                case = close_case_without_export(
                    s, case_id, user_id, closed_reason=body.closed_reason, closure_memo=body.closure_memo,
                )
                return {"id": case.id, "status": case.status, "closed_reason": case.closed_reason}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    # ── Admin Revocation (strict AuthGuard FOR UPDATE first) ──

    @app.post("/api/admin/users/{target_user_id}/revoke")
    def admin_revoke(target_user_id: str, body: RevokeRequest, principal=Depends(require_principal)):
        user_id, _, _ = principal
        try:
            with session_factory.begin() as s:
                rev = revoke_principal_access(
                    s, user_id, target_user_id,
                    disable_user=body.disable_user,
                    revoke_sessions=body.revoke_sessions,
                    revoke_dataset_id=body.revoke_dataset_id,
                    revoke_case_id=body.revoke_case_id,
                )
                return {"revoked_user_id": target_user_id, "auth_guard_revision": rev}
        except Exception as exc:
            raise _map_domain_error(exc) from None

    # ── Static Frontend Serving (self-hosted assets only) ──
    static_dir = Path(__file__).resolve().parent / "static"
    dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    asset_root = static_dir if static_dir.is_dir() else dist_dir
    if asset_root.is_dir():
        if (asset_root / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=str(asset_root / "assets")), name="prod-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_entry(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            candidate = asset_root / full_path
            if full_path and candidate.is_file() and asset_root in candidate.resolve().parents:
                return FileResponse(str(candidate))
            index = asset_root / "index.html"
            if index.exists():
                return FileResponse(str(index), media_type="text/html")
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)

    return app


def get_asgi_app() -> FastAPI:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[handler], force=True)
    return create_production_app()
