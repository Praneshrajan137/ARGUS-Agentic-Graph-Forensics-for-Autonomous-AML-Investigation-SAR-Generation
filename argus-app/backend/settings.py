import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProductionSettings:
    database_url: str
    public_origin: str
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str
    deployment: str = "production"
    session_seconds: int = 3600
    job_seconds: int = 120
    max_graph_events: int = 20_000
    max_graph_accounts: int = 5_000

    def __post_init__(self):
        if self.deployment not in {"production", "local"}:
            raise ValueError("Explicit production or local deployment is required")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL is required")
        for value in (self.public_origin, self.oidc_issuer):
            parsed = urlsplit(value)
            local = self.deployment == "local" and parsed.hostname in {"localhost", "127.0.0.1"}
            if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Invalid configured origin or issuer")
            if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
                raise ValueError("TLS is required outside loopback-only local development")
        if urlsplit(self.public_origin).path not in {"", "/"}:
            raise ValueError("Public origin cannot include a path")
        if not self.oidc_client_id or not self.oidc_client_secret:
            raise ValueError("Institutional OIDC client configuration is required")
        if not 60 <= self.session_seconds <= 28800 or not 10 <= self.job_seconds <= 300:
            raise ValueError("Session or execution budget is outside supported limits")

    @property
    def secure_cookies(self) -> bool:
        return self.public_origin.startswith("https://")

    @classmethod
    def from_environment(cls):
        return cls(
            database_url=os.environ["ARGUS_DATABASE_URL"],
            public_origin=os.environ["ARGUS_PUBLIC_ORIGIN"].rstrip("/"),
            oidc_issuer=os.environ["ARGUS_OIDC_ISSUER"].rstrip("/"),
            oidc_client_id=os.environ["ARGUS_OIDC_CLIENT_ID"],
            oidc_client_secret=os.environ["ARGUS_OIDC_CLIENT_SECRET"],
            deployment=os.environ.get("ARGUS_DEPLOYMENT", "production"),
        )
