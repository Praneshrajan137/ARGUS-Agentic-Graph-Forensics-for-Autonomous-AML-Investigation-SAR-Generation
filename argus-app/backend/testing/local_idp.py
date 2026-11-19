"""Local synthetic OIDC Identity Provider for development and automated testing.

NEVER a production bypass: implements genuine OIDC Discovery, JWKS (RS256),
Authorization Code + PKCE (S256), state/nonce binding, and exact redirect checks.
"""
import base64
import hashlib
import html
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

DEFAULT_PERSONAS: dict[str, dict[str, Any]] = {
    "analyst-1": {"sub": "analyst-1", "name": "Morgan Ellis (Analyst)", "roles": ["analyst"]},
    "analyst-2": {"sub": "analyst-2", "name": "Jordan Patel (Analyst)", "roles": ["analyst"]},
    "reviewer-1": {"sub": "reviewer-1", "name": "Avery Brooks (Reviewer)", "roles": ["reviewer"]},
    "admin-1": {"sub": "admin-1", "name": "Taylor Chen (Administrator)", "roles": ["administrator", "analyst", "reviewer"]},
    "auditor-1": {"sub": "auditor-1", "name": "Casey Rivera (Auditor)", "roles": ["auditor"]},
}


def _pkce_s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def create_local_idp_app(
    *,
    issuer: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    allowed_redirect_uri: str | None = None,
) -> FastAPI:
    resolved_issuer = (issuer or os.getenv("LOCAL_IDP_ISSUER", "http://127.0.0.1:9000")).rstrip("/")
    resolved_client_id = client_id or os.getenv("ARGUS_OIDC_CLIENT_ID", "argus-local-client")
    resolved_client_secret = client_secret or os.getenv("ARGUS_OIDC_CLIENT_SECRET", "argus-local-secret")
    resolved_redirect = allowed_redirect_uri or os.getenv("LOCAL_IDP_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/callback")

    rsa_key = RSAKey.generate_key(2048, parameters={"kid": "argus-local-idp-key-1", "use": "sig", "alg": "RS256"})
    key_set = KeySet([rsa_key])
    auth_codes: dict[str, dict[str, Any]] = {}

    idp = FastAPI(title="ARGUS Local Synthetic OIDC IdP")

    @idp.get("/.well-known/openid-configuration")
    def discovery():
        return {
            "issuer": resolved_issuer,
            "authorization_endpoint": f"{resolved_issuer}/authorize",
            "token_endpoint": f"{resolved_issuer}/token",
            "jwks_uri": f"{resolved_issuer}/jwks.json",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
        }

    @idp.get("/jwks.json")
    def jwks():
        return JSONResponse(key_set.as_dict(private=False))

    @idp.get("/authorize")
    def authorize(
        response_type: str = Query(...),
        client_id: str = Query(...),
        redirect_uri: str = Query(...),
        state: str = Query(...),
        nonce: str = Query(...),
        code_challenge: str = Query(...),
        code_challenge_method: str = Query("S256"),
        persona: str | None = Query(None),
    ):
        if response_type != "code" or client_id != resolved_client_id:
            raise HTTPException(status_code=400, detail="Invalid OIDC client or response_type")
        if redirect_uri != resolved_redirect:
            raise HTTPException(status_code=400, detail="Redirect URI mismatch")
        if code_challenge_method != "S256" or not code_challenge:
            raise HTTPException(status_code=400, detail="PKCE S256 required")

        if persona in DEFAULT_PERSONAS:
            code = secrets.token_urlsafe(32)
            auth_codes[code] = {
                "persona": DEFAULT_PERSONAS[persona],
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "expires_at": time.time() + 120,
            }
            return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302)

        buttons = []
        for pid, info in DEFAULT_PERSONAS.items():
            q = urlencode({
                "response_type": response_type, "client_id": client_id, "redirect_uri": redirect_uri,
                "state": state, "nonce": nonce, "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method, "persona": pid,
            })
            buttons.append(
                f'<li style="margin:8px 0"><a href="/authorize?{html.escape(q)}" '
                f'style="display:inline-block;padding:10px 16px;border:1px solid #cbd5e1;border-radius:8px;'
                f'text-decoration:none;color:#0f172a;font-family:sans-serif">'
                f'{html.escape(info["name"])} — roles: {html.escape(", ".join(info["roles"]))}</a></li>'
            )
        return HTMLResponse(
            "<!doctype html><html><body style='max-width:560px;margin:40px auto;font-family:sans-serif'>"
            "<h1>ARGUS Local Test Identity Provider</h1>"
            "<p>Select a synthetic test identity to complete OIDC Authorization Code + PKCE sign-in:</p>"
            f"<ul style='list-style:none;padding:0'>{''.join(buttons)}</ul></body></html>"
        )

    @idp.post("/token")
    def token(
        grant_type: str = Form(...),
        code: str = Form(...),
        redirect_uri: str = Form(...),
        client_id: str = Form(...),
        client_secret: str = Form(...),
        code_verifier: str = Form(...),
    ):
        if grant_type != "authorization_code":
            raise HTTPException(status_code=400, detail="Unsupported grant_type")
        if client_id != resolved_client_id or client_secret != resolved_client_secret:
            raise HTTPException(status_code=401, detail="Invalid client credentials")
        record = auth_codes.pop(code, None)
        if record is None or record["expires_at"] < time.time():
            raise HTTPException(status_code=400, detail="Invalid or expired authorization code")
        if record["redirect_uri"] != redirect_uri:
            raise HTTPException(status_code=400, detail="Redirect URI mismatch")
        if _pkce_s256(code_verifier) != record["code_challenge"]:
            raise HTTPException(status_code=400, detail="PKCE verifier check failed")

        now = int(time.time())
        persona = record["persona"]
        claims = {
            "iss": resolved_issuer,
            "sub": persona["sub"],
            "aud": resolved_client_id,
            "iat": now,
            "exp": now + 300,
            "nonce": record["nonce"],
            "name": persona["name"],
            "roles": persona["roles"],
        }
        id_token = jwt.encode({"alg": "RS256", "kid": "argus-local-idp-key-1"}, claims, rsa_key)
        return {
            "access_token": secrets.token_urlsafe(24),
            "token_type": "Bearer",
            "expires_in": 300,
            "id_token": id_token,
        }

    return idp


app = create_local_idp_app()
