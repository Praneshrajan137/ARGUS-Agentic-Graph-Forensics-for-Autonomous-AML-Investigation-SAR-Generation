"""Milestone C tests: fail-closed config, OIDC PKCE/JWKS, CSRF, RBAC/IDOR, non-owner RLS & 2-connection lock races."""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND.parent))

from backend.auth import OIDCClient, pkce_s256, revoke_principal_access  # noqa: E402
from backend.database import (  # noqa: E402
    CaseAssignment, CaseRecord, Dataset, DatasetGrant, User,
    create_engine_from_url, make_session_factory, set_transaction_identity,
)
from backend.production import create_production_app  # noqa: E402
from backend.services.intake_service import Forbidden, activate_batch, parse_batch  # noqa: E402
from backend.services.review_service import (  # noqa: E402
    create_draft_revision, export_approved_artifact, freeze_artifact_for_review,
    review_artifact,
)
from backend.settings import ProductionSettings  # noqa: E402
from backend.testing.local_idp import create_local_idp_app  # noqa: E402
from backend.tests.test_intake import files  # noqa: E402


def test_fail_closed_production_settings():
    with pytest.raises(ValueError, match="PostgreSQL"):
        ProductionSettings("sqlite:///test.db", "https://argus.bank", "https://idp.bank", "cid", "sec")
    with pytest.raises(ValueError, match="TLS"):
        ProductionSettings("postgresql+psycopg://u:p@db/a", "http://argus.bank", "https://idp.bank", "cid", "sec", deployment="production")
    with pytest.raises(ValueError, match="OIDC"):
        ProductionSettings("postgresql+psycopg://u:p@db/a", "https://argus.bank", "https://idp.bank", "", "sec")
    ok = ProductionSettings(
        "postgresql+psycopg://u:p@127.0.0.1/a", "http://127.0.0.1:8000", "http://127.0.0.1:9000",
        "cid", "sec", deployment="local",
    )
    assert ok.secure_cookies is False


def test_local_idp_oidc_pkce_discovery_jwks_and_token_signing():
    idp_app = create_local_idp_app(
        issuer="http://127.0.0.1:9000",
        client_id="argus-local-client",
        client_secret="argus-local-secret",
        allowed_redirect_uri="http://127.0.0.1:8000/api/auth/callback",
    )
    client = TestClient(idp_app)
    disc = client.get("/.well-known/openid-configuration").json()
    assert disc["issuer"] == "http://127.0.0.1:9000"
    assert len(client.get("/jwks.json").json()["keys"]) == 1

    verifier = "v" * 48
    auth_resp = client.get("/authorize", params={
        "response_type": "code",
        "client_id": "argus-local-client",
        "redirect_uri": "http://127.0.0.1:8000/api/auth/callback",
        "state": "st-1",
        "nonce": "nc-1",
        "code_challenge": pkce_s256(verifier),
        "code_challenge_method": "S256",
        "persona": "analyst-1",
    }, follow_redirects=False)
    assert auth_resp.status_code == 302
    code = parse_qs(urlsplit(auth_resp.headers["location"]).query)["code"][0]

    # Wrong PKCE verifier must be rejected
    bad_tok = client.post("/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": "http://127.0.0.1:8000/api/auth/callback",
        "client_id": "argus-local-client", "client_secret": "argus-local-secret",
        "code_verifier": "wrong" * 10,
    })
    assert bad_tok.status_code == 400

    # Fresh code with matching verifier returns valid RS256 ID token
    auth_resp2 = client.get("/authorize", params={
        "response_type": "code", "client_id": "argus-local-client",
        "redirect_uri": "http://127.0.0.1:8000/api/auth/callback",
        "state": "st-2", "nonce": "nc-2",
        "code_challenge": pkce_s256(verifier), "code_challenge_method": "S256",
        "persona": "reviewer-1",
    }, follow_redirects=False)
    code2 = parse_qs(urlsplit(auth_resp2.headers["location"]).query)["code"][0]
    ok_tok = client.post("/token", data={
        "grant_type": "authorization_code", "code": code2,
        "redirect_uri": "http://127.0.0.1:8000/api/auth/callback",
        "client_id": "argus-local-client", "client_secret": "argus-local-secret",
        "code_verifier": verifier,
    })
    assert ok_tok.status_code == 200
    assert "id_token" in ok_tok.json()


def test_production_app_excludes_all_research_routes_and_sets_security_headers():
    cfg = ProductionSettings(
        "postgresql+psycopg://u:p@127.0.0.1:5432/unused",
        "http://127.0.0.1:8000", "http://127.0.0.1:9000",
        "argus-local-client", "argus-local-secret", deployment="local",
    )
    app = create_production_app(cfg)
    paths = {route.path for route in app.routes}
    for forbidden_prefix in ("/api/generate", "/api/reset", "/api/ground-truth", "/api/benchmark", "/api/assess", "/api/agent"):
        assert not any(p.startswith(forbidden_prefix) for p in paths), f"Research route leaked: {forbidden_prefix}"

    client = TestClient(app)
    live = client.get("/api/health/live")
    assert live.status_code == 200
    assert live.headers["Cache-Control"] == "no-store"
    assert live.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in live.headers["Content-Security-Policy"]
    assert "fonts.googleapis.com" not in live.headers["Content-Security-Policy"]


@pytest.fixture
def pg_prod_env():
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
    schema = "auth_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine_from_url(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        cfg = ProductionSettings(
            url, "http://127.0.0.1:8000", "http://127.0.0.1:9000",
            "argus-local-client", "argus-local-secret", deployment="local",
        )
        idp_app = create_local_idp_app(
            issuer=cfg.oidc_issuer, client_id=cfg.oidc_client_id,
            client_secret=cfg.oidc_client_secret,
            allowed_redirect_uri=f"{cfg.public_origin}/api/auth/callback",
        )
        idp_http = TestClient(idp_app, base_url=cfg.oidc_issuer)
        oidc = OIDCClient(cfg, http_client=idp_http)
        app = create_production_app(cfg, engine=engine, oidc_client=oidc)
        yield engine, make_session_factory(engine), app, idp_app, schema
        idp_http.close()
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def _login_persona(app_client: TestClient, idp_app, persona: str) -> dict:
    idp_client = TestClient(idp_app)
    r1 = app_client.get(f"/api/auth/login?persona={persona}", follow_redirects=False)
    assert r1.status_code == 302
    r2 = idp_client.get(r1.headers["location"], follow_redirects=False)
    assert r2.status_code == 302
    r3 = app_client.get(r2.headers["location"], follow_redirects=False)
    assert r3.status_code == 200
    return r3.json()


def test_pg_oidc_csrf_idor_and_bulk_source_permission(pg_prod_env):
    _, factory, app, idp_app, _ = pg_prod_env
    c_admin = TestClient(app, base_url="http://127.0.0.1:8000")
    c_a1 = TestClient(app, base_url="http://127.0.0.1:8000")
    c_a2 = TestClient(app, base_url="http://127.0.0.1:8000")

    admin_info = _login_persona(c_admin, idp_app, "admin-1")
    a1_info = _login_persona(c_a1, idp_app, "analyst-1")
    a2_info = _login_persona(c_a2, idp_app, "analyst-2")

    # Missing CSRF token on POST must fail with 403
    no_csrf = c_admin.post("/api/datasets", json={"name": "Bank", "namespace": "bank"})
    assert no_csrf.status_code == 403

    # Create dataset as admin with valid CSRF
    ds = c_admin.post(
        "/api/datasets", json={"name": "Bank", "namespace": "bank"},
        headers={"X-CSRF-Token": admin_info["csrf_token"]},
    ).json()

    # Grant a1 dataset import WITHOUT bulk source download; grant a2 NOTHING
    with factory.begin() as s:
        s.add(DatasetGrant(user_id=a1_info["user_id"], dataset_id=ds["id"], can_import=True, can_download_source=False))

    # a2 (no dataset grant) cannot see dataset or create case (IDOR check)
    assert c_a2.get("/api/datasets").json()["datasets"] == []
    assert c_a2.post(
        "/api/cases", json={"dataset_id": ds["id"], "subject_id": "002", "title": "Unauthorized"},
        headers={"X-CSRF-Token": a2_info["csrf_token"]},
    ).status_code == 403

    # a1 imports a batch and creates a case
    raw = files()
    imp = c_a1.post(
        f"/api/datasets/{ds['id']}/imports",
        data={"expected_generation": "0"},
        files={k: (f"{k}.csv", v, "text/csv") for k, v in raw.items()},
        headers={"X-CSRF-Token": a1_info["csrf_token"], "Idempotency-Key": "imp-1"},
    )
    assert imp.status_code == 201
    case = c_a1.post(
        "/api/cases", json={"dataset_id": ds["id"], "subject_id": "002", "title": "Case A1"},
        headers={"X-CSRF-Token": a1_info["csrf_token"]},
    ).json()

    # a1 can inspect cited case records, but CANNOT download full raw source files (can_download_source=False)
    assert c_a1.get(f"/api/cases/{case['id']}/records").status_code == 200
    with factory() as s:
        sf_id = s.execute(text("SELECT id FROM source_file LIMIT 1")).scalar()
    assert c_a1.get(f"/api/datasets/{ds['id']}/files/{sf_id}").status_code == 403
    assert c_admin.get(f"/api/datasets/{ds['id']}/files/{sf_id}").status_code == 200

    # a2 cannot directly access a1's case (direct-object IDOR protection)
    assert c_a2.get(f"/api/cases/{case['id']}").status_code == 403


def test_pg_two_connection_revocation_vs_export_race(pg_prod_env):
    """Two-connection lock race: revocation acquires AuthGuard FOR UPDATE first, denying export."""
    _, factory, _, _, _ = pg_prod_env
    with factory.begin() as s:
        admin = User(issuer="idp", subject="adm", display_name="Adm", roles=["administrator"])
        analyst = User(issuer="idp", subject="an1", display_name="An", roles=["analyst"])
        reviewer = User(issuer="idp", subject="rv1", display_name="Rv", roles=["reviewer"])
        ds = Dataset(name="Bank", namespace="bank")
        s.add_all([admin, analyst, reviewer, ds])
        s.flush()
        s.add_all([
            DatasetGrant(user_id=analyst.id, dataset_id=ds.id, can_import=True),
            DatasetGrant(user_id=reviewer.id, dataset_id=ds.id, can_import=False),
        ])
        act = activate_batch(s, ds.id, analyst.id, parse_batch(files(), "bank", None), 0, "k1")
        case = CaseRecord(dataset_id=ds.id, snapshot_id=act.snapshot_id, subject_id="002", title="Race", created_by=analyst.id)
        s.add(case)
        s.flush()
        s.add_all([CaseAssignment(case_id=case.id, user_id=analyst.id), CaseAssignment(case_id=case.id, user_id=reviewer.id)])
        art = create_draft_revision(s, case.id, analyst.id)
        freeze_artifact_for_review(s, art.id, analyst.id)
        review_artifact(s, art.id, reviewer.id, decision="APPROVED")
        ids = {"admin": admin.id, "reviewer": reviewer.id, "art": art.id}

    revocation_locked = threading.Event()
    export_started = threading.Event()

    def do_revoke():
        with factory.begin() as s:
            revoke_principal_access(s, ids["admin"], ids["reviewer"], disable_user=True)
            revocation_locked.set()
            export_started.wait(timeout=2.0)
            time.sleep(0.1)

    def do_export():
        revocation_locked.wait(timeout=5.0)
        export_started.set()
        with factory.begin() as s:
            return export_approved_artifact(s, ids["art"], ids["reviewer"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_rev = pool.submit(do_revoke)
        f_exp = pool.submit(do_export)
        f_rev.result()
        with pytest.raises(Forbidden):
            f_exp.result()


def test_pg_non_owner_non_bypassrls_pooled_isolation(pg_prod_env):
    """Verify PostgreSQL RLS isolates unassigned cases under a non-owner, non-BYPASSRLS role."""
    engine, factory, _, _, schema = pg_prod_env
    role_name = f"argus_rls_{uuid4().hex[:8]}"
    with factory.begin() as s:
        u1 = User(issuer="idp", subject="u1", display_name="U1", roles=["analyst"])
        u2 = User(issuer="idp", subject="u2", display_name="U2", roles=["analyst"])
        ds = Dataset(name="Bank", namespace="bank")
        s.add_all([u1, u2, ds])
        s.flush()
        s.add(DatasetGrant(user_id=u1.id, dataset_id=ds.id, can_import=True))
        act = activate_batch(s, ds.id, u1.id, parse_batch(files(), "bank", None), 0, "rls1")
        c1 = CaseRecord(dataset_id=ds.id, snapshot_id=act.snapshot_id, subject_id="002", title="U1 Case", created_by=u1.id)
        s.add(c1)
        s.flush()
        s.add(CaseAssignment(case_id=c1.id, user_id=u1.id))
        u1_id, u2_id = u1.id, u2.id

    with engine.begin() as conn:
        conn.execute(text(f'CREATE ROLE "{role_name}" NOLOGIN NOBYPASSRLS'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role_name}"'))
        conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO "{role_name}"'))
    try:
        with factory.begin() as s:
            s.execute(text(f'SET LOCAL ROLE "{role_name}"'))
            set_transaction_identity(s, u1_id, ["analyst"])
            assert len(s.scalars(select(CaseRecord)).all()) == 1
        # Same pooled connection reused by unassigned user u2 -> sees 0 rows!
        with factory.begin() as s:
            s.execute(text(f'SET LOCAL ROLE "{role_name}"'))
            set_transaction_identity(s, u2_id, ["analyst"])
            assert len(s.scalars(select(CaseRecord)).all()) == 0
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'REVOKE ALL ON ALL TABLES IN SCHEMA "{schema}" FROM "{role_name}"'))
            conn.execute(text(f'REVOKE USAGE ON SCHEMA "{schema}" FROM "{role_name}"'))
            conn.execute(text(f'DROP ROLE "{role_name}"'))
