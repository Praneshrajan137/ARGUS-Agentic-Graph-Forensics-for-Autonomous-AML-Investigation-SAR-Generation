"""Institutional OIDC Authorization Code + PKCE, rotating sessions, CSRF, and 4-level lock guards.

Uses maintained joserfc + httpx libraries (zero custom identity cryptography).
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.jwk import KeySet
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import (
    AuditEvent, AuthFlow, AuthGuard, CaseAssignment, DatasetGrant, User,
    UserSession, set_transaction_identity, utcnow,
)
from .services.intake_service import Forbidden, IntakeError
from .settings import ProductionSettings

SESSION_COOKIE = "argus_session"
AUTH_BIND_COOKIE = "argus_auth_bind"
CSRF_HEADER = "X-CSRF-Token"
FLOW_TTL_SECONDS = 300


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class AuthError(ValueError):
    pass


class OIDCClient:
    """Standards-compliant OIDC Authorization Code + PKCE verifier using joserfc + httpx."""

    def __init__(self, settings: ProductionSettings, *, http_client: httpx.Client | None = None):
        self.settings = settings
        self._http = http_client
        self._discovery: dict[str, Any] | None = None
        self._jwks: KeySet | None = None
        self._jwks_fetched_at: float = 0.0

    def _client(self) -> httpx.Client:
        if self._http is not None:
            return self._http
        return httpx.Client(timeout=10.0)

    def get_discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        url = f"{self.settings.oidc_issuer}/.well-known/openid-configuration"
        close_after = self._http is None
        client = self._client()
        try:
            resp = client.get(url)
            resp.raise_for_status()
            doc = resp.json()
        finally:
            if close_after:
                client.close()
        if doc.get("issuer", "").rstrip("/") != self.settings.oidc_issuer:
            raise AuthError("OIDC discovery issuer mismatch")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not doc.get(key):
                raise AuthError(f"OIDC discovery missing {key}")
        self._discovery = doc
        return doc

    def get_jwks(self, *, force_refresh: bool = False) -> KeySet:
        now = time.monotonic()
        if not force_refresh and self._jwks is not None and (now - self._jwks_fetched_at) < 300:
            return self._jwks
        doc = self.get_discovery()
        close_after = self._http is None
        client = self._client()
        try:
            resp = client.get(doc["jwks_uri"])
            resp.raise_for_status()
            data = resp.json()
        finally:
            if close_after:
                client.close()
        self._jwks = KeySet.import_key_set(data)
        self._jwks_fetched_at = now
        return self._jwks

    @property
    def redirect_uri(self) -> str:
        return f"{self.settings.public_origin}/api/auth/callback"

    def start_login(self, session: Session) -> tuple[str, str]:
        """Create one-time PKCE/state/nonce flow and return (authorize_url, browser_bind_token)."""
        doc = self.get_discovery()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        browser_bind = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(seconds=FLOW_TTL_SECONDS)

        session.add(AuthFlow(
            state_hash=sha256_text(state),
            verifier=verifier,
            nonce=nonce,
            browser_hash=sha256_text(browser_bind),
            expires_at=expires_at,
        ))
        session.flush()

        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_s256(verifier),
            "code_challenge_method": "S256",
        }
        return f"{doc['authorization_endpoint']}?{urlencode(params)}", browser_bind

    def exchange_and_verify(
        self,
        session: Session,
        *,
        code: str,
        state: str,
        browser_bind: str | None,
    ) -> tuple[User, str, str]:
        """Validate callback, verify JWKS/iss/aud/nonce/exp, and issue rotating session + CSRF."""
        if not code or not state or not browser_bind:
            raise AuthError("Missing OIDC callback parameters or browser binding")

        flow = session.get(AuthFlow, sha256_text(state))
        if flow is None:
            raise AuthError("Invalid or already consumed OIDC state")
        session.delete(flow)
        session.flush()

        if flow.expires_at < utcnow():
            raise AuthError("OIDC authentication flow expired")
        if not hmac.compare_digest(flow.browser_hash, sha256_text(browser_bind)):
            raise AuthError("Browser binding mismatch")

        doc = self.get_discovery()
        close_after = self._http is None
        client = self._client()
        try:
            resp = client.post(
                doc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                    "code_verifier": flow.verifier,
                },
            )
            if resp.status_code != 200:
                raise AuthError("OIDC token exchange rejected")
            token_data = resp.json()
        finally:
            if close_after:
                client.close()

        id_token = token_data.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise AuthError("OIDC response missing id_token")

        jwks = self.get_jwks()
        try:
            decoded = jwt.decode(id_token, jwks)
        except Exception:
            # Refresh JWKS once on possible key rotation
            jwks = self.get_jwks(force_refresh=True)
            try:
                decoded = jwt.decode(id_token, jwks)
            except Exception as exc:
                raise AuthError("ID token signature verification failed") from exc

        claims = decoded.claims
        registry = jwt.JWTClaimsRegistry(
            iss={"essential": True, "value": self.settings.oidc_issuer},
            aud={"essential": True, "value": self.settings.oidc_client_id},
            sub={"essential": True},
            exp={"essential": True},
            iat={"essential": True},
            nonce={"essential": True, "value": flow.nonce},
        )
        try:
            registry.validate(claims)
        except Exception as exc:
            raise AuthError(f"ID token claim validation failed: {type(exc).__name__}") from exc

        subject = str(claims["sub"])
        display_name = str(claims.get("name") or claims.get("preferred_username") or subject)[:255]

        # Acquire AuthGuard FOR SHARE before issuing session
        session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
        user = session.scalar(
            select(User).where(User.issuer == self.settings.oidc_issuer, User.subject == subject)
        )
        if user is None:
            # Auto-provision with explicit roles only when IdP supplies allowlisted roles; default least-privilege empty
            allowed_roles = {"analyst", "reviewer", "administrator", "auditor"}
            raw_roles = claims.get("roles") if isinstance(claims.get("roles"), list) else []
            mapped_roles = sorted(r for r in raw_roles if r in allowed_roles)
            user = User(
                issuer=self.settings.oidc_issuer,
                subject=subject,
                display_name=display_name,
                roles=mapped_roles,
                enabled=True,
            )
            session.add(user)
            session.flush()
        else:
            if not user.enabled:
                raise Forbidden("Account is disabled")
            user.display_name = display_name

        raw_session, raw_csrf = issue_session(session, user.id, self.settings.session_seconds)
        session.add(AuditEvent(
            actor_id=user.id,
            event_type="USER_SIGNED_IN",
            resource_id=user.id,
            detail={"issuer": self.settings.oidc_issuer},
        ))
        session.flush()
        return user, raw_session, raw_csrf


def issue_session(session: Session, user_id: str, session_seconds: int) -> tuple[str, str]:
    """Create a fresh opaque session token and bound CSRF token (stored hashed only)."""
    raw_token = secrets.token_urlsafe(32)
    raw_csrf = secrets.token_urlsafe(32)
    session.add(UserSession(
        token_hash=sha256_text(raw_token),
        user_id=user_id,
        csrf_hash=sha256_text(raw_csrf),
        expires_at=utcnow() + timedelta(seconds=session_seconds),
    ))
    session.flush()
    return raw_token, raw_csrf


def authenticate_session(session: Session, raw_token: str | None) -> tuple[User, UserSession]:
    """Authenticate cookie token under AuthGuard FOR SHARE and bind transaction-local RLS identity."""
    if not raw_token:
        raise AuthError("Authentication required")
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    user_session = session.get(UserSession, sha256_text(raw_token), populate_existing=True)
    if user_session is None or user_session.expires_at < utcnow():
        raise AuthError("Session expired or invalid")
    user = session.get(User, user_session.user_id, populate_existing=True)
    if user is None or not user.enabled:
        raise Forbidden("Account disabled")
    set_transaction_identity(session, user.id, user.roles)
    return user, user_session


def verify_csrf_token(user_session: UserSession, provided_token: str | None) -> None:
    if not provided_token or not hmac.compare_digest(user_session.csrf_hash, sha256_text(provided_token)):
        raise Forbidden("Invalid or missing CSRF token")


def logout_session(session: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update())
    existing = session.get(UserSession, sha256_text(raw_token))
    if existing:
        actor_id = existing.user_id
        session.delete(existing)
        session.add(AuditEvent(
            actor_id=actor_id,
            event_type="USER_SIGNED_OUT",
            resource_id=actor_id,
            detail={},
        ))
        session.flush()


def revoke_principal_access(
    session: Session,
    admin_id: str,
    target_user_id: str,
    *,
    disable_user: bool = True,
    revoke_sessions: bool = True,
    revoke_dataset_id: str | None = None,
    revoke_case_id: str | None = None,
) -> int:
    """Revoke permissions/sessions acquiring AuthGuard FOR UPDATE FIRST (strict lock order #1)."""
    guard = session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update().execution_options(populate_existing=True))
    admin = session.get(User, admin_id, populate_existing=True)
    if admin is None or not admin.enabled or "administrator" not in (admin.roles or []):
        raise Forbidden("Administrator role required for revocation")
    set_transaction_identity(session, admin.id, admin.roles)

    target = session.get(User, target_user_id, populate_existing=True)
    if target is None:
        raise IntakeError("Target user not found")

    if disable_user:
        target.enabled = False
    if revoke_sessions:
        session.execute(delete(UserSession).where(UserSession.user_id == target_user_id))
    if revoke_dataset_id:
        session.execute(delete(DatasetGrant).where(
            DatasetGrant.user_id == target_user_id,
            DatasetGrant.dataset_id == revoke_dataset_id,
        ))
    if revoke_case_id:
        session.execute(delete(CaseAssignment).where(
            CaseAssignment.user_id == target_user_id,
            CaseAssignment.case_id == revoke_case_id,
        ))

    guard.revision += 1
    session.add(AuditEvent(
        actor_id=admin.id,
        event_type="ACCESS_REVOKED",
        resource_id=target_user_id,
        detail={
            "disable_user": disable_user,
            "revoke_sessions": revoke_sessions,
            "revoke_dataset_id": revoke_dataset_id,
            "revoke_case_id": revoke_case_id,
            "auth_guard_revision": guard.revision,
        },
    ))
    session.flush()
    return guard.revision
