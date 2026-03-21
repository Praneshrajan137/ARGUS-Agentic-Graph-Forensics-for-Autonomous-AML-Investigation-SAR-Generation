"""Graph data routes — 6 endpoints for graph visualization and querying."""
from fastapi import APIRouter, HTTPException, Query

from ..models.state import get_state
from ..models.schemas import (
    GraphStatsResponse, GraphVisualizationResponse,
    NodeListResponse, NodeResponse,
    TransactionResponse, ConnectionResponse,
)
from ..services.forge_service import (
    get_graph_stats, get_visualization_data,
    get_node, get_nodes, get_transactions, get_connections,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats():
    """Return graph statistics and crime summary."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    return get_graph_stats()


@router.get("/visualization", response_model=GraphVisualizationResponse)
async def graph_visualization(limit: int = Query(default=5000, ge=1, le=10000)):
    """Return nodes and edges for D3 force-directed graph visualization."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    return get_visualization_data(limit=limit)


@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    entity_type: str | None = None,
    search: str | None = None,
):
    """Paginated node listing with optional entity_type and search filters."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    return get_nodes(page=page, per_page=per_page, entity_type=entity_type, search=search)


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def node_detail(node_id: str):
    """Return detailed information for a specific node."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    node = get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return node


@router.get("/nodes/{node_id}/transactions", response_model=list[TransactionResponse])
async def node_transactions(node_id: str):
    """Return all transactions involving a specific node."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    if get_node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return get_transactions(node_id)


@router.get("/nodes/{node_id}/connections", response_model=list[ConnectionResponse])
async def node_connections(node_id: str):
    """Return aggregated connections for a specific node."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")
    if get_node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return get_connections(node_id)
