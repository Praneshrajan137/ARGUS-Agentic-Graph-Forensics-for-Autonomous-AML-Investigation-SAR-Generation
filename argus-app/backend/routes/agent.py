"""Purple Agent A2A endpoints — exposes the real Tracer agent via the ARGUS backend.

Provides:
- GET  /api/agent/health      → Purple agent health + version info
- GET  /api/agent/agent.json   → Agent capability card
- GET  /api/agent/config       → Full Tracer config (80+ constants)
- POST /api/agent/a2a          → A2A investigation endpoint (JSON)
"""
import json
import logging
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..models.state import get_state
from ..services.investigation_service import run_investigation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

_AGENT_JSON_PATH = Path(__file__).resolve().parent.parent.parent.parent / "tracer_agent" / "agent.json"


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


@router.get("/health")
async def agent_health():
    """Purple agent health status."""
    from tracer_agent.src.config import AGENT_VERSION
    state = get_state()
    return {
        "status": "healthy",
        "service": "tracer_agent",
        "version": AGENT_VERSION,
        "mode": "unified",
        "graph_loaded": state.graph is not None,
        "node_count": state.graph.number_of_nodes() if state.graph else 0,
        "edge_count": state.graph.number_of_edges() if state.graph else 0,
    }


@router.get("/agent.json")
async def agent_card():
    """Serve the tracer agent capability card."""
    if not _AGENT_JSON_PATH.exists():
        raise HTTPException(status_code=404, detail="agent.json not found")
    with open(_AGENT_JSON_PATH) as f:
        card = json.load(f)
    # Update endpoint to reflect unified deployment
    card["communication"]["endpoint"] = "/api/agent/a2a"
    card["communication"]["mode"] = "unified"
    return JSONResponse(content=card)


@router.get("/config")
async def agent_config():
    """Expose tracer_agent's full config (80+ constants) for the frontend Settings page."""
    from tracer_agent.src import config as tc

    # Collect all uppercase public constants
    config_dict = {}
    for name in sorted(dir(tc)):
        if name.startswith("_") or not name[0].isupper():
            continue
        val = getattr(tc, name)
        # Skip compiled regex patterns and module-level objects
        if callable(val) and not isinstance(val, Decimal):
            continue
        if hasattr(val, "pattern"):  # compiled regex
            config_dict[name] = val.pattern
        elif isinstance(val, (str, int, float, bool)):
            config_dict[name] = val
        elif isinstance(val, Decimal):
            config_dict[name] = str(val)
        elif isinstance(val, dict):
            # Amount patterns dict — serialize pattern strings
            config_dict[name] = {k: v if isinstance(v, str) else str(v) for k, v in val.items()}
        elif isinstance(val, (list, tuple)):
            config_dict[name] = [str(v) for v in val]

    return config_dict


@router.post("/a2a")
async def handle_a2a_investigation(request_body: dict):
    """Handle A2A protocol investigation requests (JSON mode).

    Accepts the same schema as tracer_agent's /a2a endpoint but routes
    through the unified backend's in-memory Forge data.
    """
    subject_id = request_body.get("subject_id") or request_body.get("graph_entry_point")
    if not subject_id:
        raise HTTPException(status_code=422, detail="subject_id (or graph_entry_point) is required")

    hop_depth = request_body.get("hop_depth", 3)
    if not isinstance(hop_depth, int) or hop_depth <= 0:
        raise HTTPException(status_code=422, detail=f"hop_depth must be positive integer, got {hop_depth}")

    case_id = request_body.get("case_id", f"CASE-{int(time.time())}")
    jurisdiction = request_body.get("jurisdiction", "fincen")

    result = run_investigation(
        case_id=case_id,
        subject_id=str(subject_id),
        hop_depth=hop_depth,
        jurisdiction=jurisdiction,
    )

    # Return in A2A response format
    return {
        "case_id": result.get("case_id"),
        "sar_narrative": result.get("sar_narrative", ""),
        "typology_detected": result.get("detected_typology", "NONE"),
        "involved_entities": sorted(result.get("involved_entities", [])),
        "confidence_score": result.get("confidence_score", 0.0),
        "jurisdiction": result.get("jurisdiction", "fincen"),
        "investigation_timestamp": result.get("investigation_timestamp", int(time.time())),
        "status": result.get("status", "FAILED"),
        "error_message": result.get("error"),
    }
