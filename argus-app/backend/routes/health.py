"""Health route."""
from fastapi import APIRouter

from ..config import FORGE_VERSION, TRACER_VERSION, UNIFIED_VERSION
from ..models.state import get_state
from ..models.schemas import HealthResponse

import time

router = APIRouter(prefix="/api", tags=["health"])
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return system health status."""
    state = get_state()
    return HealthResponse(
        status="ok",
        forge_version=FORGE_VERSION,
        tracer_version=TRACER_VERSION,
        unified_version=UNIFIED_VERSION,
        graph_loaded=state.graph is not None,
        node_count=state.graph.number_of_nodes() if state.graph else 0,
        edge_count=state.graph.number_of_edges() if state.graph else 0,
        uptime_seconds=round(time.time() - _start_time, 2),
    )
