"""ARGUS unified backend — FastAPI application.

Single FastAPI server on port 8000 with 17+ REST endpoints under /api/*.
Lifespan hook generates the graph on startup with PYTHONHASHSEED=0.
"""
import json
import logging
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ── sys.path setup ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .config import API_PORT, API_HOST, UNIFIED_VERSION
from .services.forge_service import generate_world
from .models.state import get_state

# ── Credential-safe log formatter (inline — avoids importing tracer_agent.src.main
#    which would trigger its module-level `app = create_app()` and fail because
#    `from src.core.a2a_server import ...` resolves against the wrong sys.path) ──
_REDACT_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+'),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
]


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts API keys, tokens and passwords from log output."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern in _REDACT_PATTERNS:
            message = pattern.sub("[REDACTED]", message)
        return message


# Configure root logger
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(RedactingFormatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)

logger = logging.getLogger("argus.backend")


# ═══ Custom JSON encoder for Decimal serialization (Rule 9) ═══

class DecimalEncoder(json.JSONEncoder):
    """Encode Decimal as string per Rule 9: json.dumps(default=str)."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class DecimalJSONResponse(JSONResponse):
    """JSONResponse that handles Decimal serialization."""
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")


# ═══ Lifespan hook — generates graph on startup ═══

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: generate graph on startup, cleanup on shutdown."""
    seed = int(os.getenv("SEED", "42"))
    difficulty = int(os.getenv("DIFFICULTY", "5"))
    graph_size = int(os.getenv("GRAPH_SIZE", "5000"))

    logger.info(
        "ARGUS backend starting — seed=%d, difficulty=%d, graph_size=%d",
        seed, difficulty, graph_size,
    )

    t0 = time.time()
    try:
        generate_world(seed=seed, difficulty=difficulty, node_count=graph_size)
        state = get_state()
        state.generation_epoch = time.time()
        elapsed = time.time() - t0
        logger.info(
            "World generated in %.2fs — %d nodes, %d edges, %d evidence docs",
            elapsed,
            state.graph.number_of_nodes() if state.graph else 0,
            state.graph.number_of_edges() if state.graph else 0,
            len(state.evidence_documents),
        )
    except Exception as e:
        logger.error("Failed to generate world: %s", e, exc_info=True)
        state = get_state()
        state.generation_error = str(e)

    yield

    logger.info("ARGUS backend shutting down")


# ═══ FastAPI app ═══

app = FastAPI(
    title="ARGUS — Agentic Graph Forensics",
    description="Unified backend for financial crime investigation and SAR generation",
    version=UNIFIED_VERSION,
    lifespan=lifespan,
    default_response_class=DecimalJSONResponse,
)

# ── CORS middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ARGUS-Epoch"],
)


# ── Epoch middleware — sends generation epoch on every response ──
@app.middleware("http")
async def epoch_header(request: Request, call_next):
    response = await call_next(request)
    state = get_state()
    response.headers["X-ARGUS-Epoch"] = str(int(state.generation_epoch))
    return response


# ── Register routers ──
from .routes.health import router as health_router
from .routes.graph import router as graph_router
from .routes.investigation import router as investigation_router
from .routes.evidence import router as evidence_router
from .routes.assessment import router as assessment_router
from .routes.benchmark import router as benchmark_router
from .routes.agent import router as agent_router

app.include_router(health_router)
app.include_router(graph_router)
app.include_router(investigation_router)
app.include_router(evidence_router)
app.include_router(assessment_router)
app.include_router(benchmark_router)
app.include_router(agent_router)

# ── Production mode: serve frontend static files ──
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_BACKEND_STATIC = Path(__file__).resolve().parent / "static"
_STATIC_DIR = _BACKEND_STATIC if _BACKEND_STATIC.is_dir() else _FRONTEND_DIST

if _STATIC_DIR.is_dir() and os.getenv("ARGUS_ENV") == "production":
    logger.info("Production mode: serving frontend from %s", _STATIC_DIR)

    if (_STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="static-assets")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        fav = _STATIC_DIR / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav), media_type="image/svg+xml")
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return JSONResponse({"error": "frontend not built"}, status_code=404)

    logger.info("SPA catch-all enabled for React Router deep links")


# ── Logging setup ──
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "argus_app.backend.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )
