"""Assessment, ground-truth, config, and reset routes."""
from fastapi import APIRouter, HTTPException
from decimal import Decimal

from ..models.state import get_state, reset_state
from ..models.schemas import (
    AssessmentRequest, AssessmentResponse,
    GroundTruthSummary, ConfigResponse,
    GenerateRequest, GenerateResponse,
)
from ..services.assessment_service import run_assessment
from ..services.forge_service import generate_world
from ..config import (
    FORGE_VERSION, TRACER_VERSION, UNIFIED_VERSION,
    STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    CTR_THRESHOLD_USD,
)
from src.config import (
    MIN_CHAIN_LENGTH, MAX_DFS_DEPTH,
    LAYERING_MIN_DECAY, LAYERING_MAX_DECAY,
    CONFIDENCE_THRESHOLD,
)

from datetime import datetime

router = APIRouter(prefix="/api", tags=["assessment"])


@router.post("/assess", response_model=AssessmentResponse)
async def assess_investigation(request: AssessmentRequest):
    """Evaluate a completed investigation against ground truth."""
    state = get_state()
    if not state.ground_truth:
        raise HTTPException(status_code=400, detail="No ground truth loaded. Generate first.")
    if request.case_id not in state.investigations:
        raise HTTPException(status_code=404, detail=f"Investigation not found: {request.case_id}")
    if state.investigations[request.case_id].get("status") != "COMPLETE":
        raise HTTPException(status_code=400, detail="Investigation not yet complete")

    result = run_assessment(request.case_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/ground-truth/summary", response_model=GroundTruthSummary)
async def ground_truth_summary():
    """Return summary of injected ground truth (without detailed crime data)."""
    state = get_state()
    if not state.ground_truth:
        raise HTTPException(status_code=400, detail="No ground truth loaded. Generate first.")

    crimes = state.ground_truth.get("crimes", [])
    all_nodes: set[str] = set()
    for crime in crimes:
        all_nodes.update(crime.get("nodes_involved", []))

    return GroundTruthSummary(
        total_crimes=len(crimes),
        crime_types=sorted(set(c["crime_type"] for c in crimes)),
        total_criminal_nodes=len(all_nodes),
        difficulty=state.difficulty,
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Return default and runtime configuration values."""
    state = get_state()
    return ConfigResponse(
        forge_version=FORGE_VERSION,
        tracer_version=TRACER_VERSION,
        unified_version=UNIFIED_VERSION,
        seed=state.seed,
        difficulty=state.difficulty,
        graph_size=state.graph_size,
        structuring_band_usd=f"${STRUCTURING_MIN_AMOUNT_USD:,} – ${STRUCTURING_MAX_AMOUNT_USD:,}",
        ctr_threshold_usd=f"${CTR_THRESHOLD_USD:,}",
        layering_decay_range=f"{float(LAYERING_MIN_DECAY)*100:.0f}% – {float(LAYERING_MAX_DECAY)*100:.0f}%",
        min_chain_length=MIN_CHAIN_LENGTH,
        max_dfs_depth=MAX_DFS_DEPTH,
        confidence_threshold=float(CONFIDENCE_THRESHOLD),
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_graph(request: GenerateRequest):
    """Generate a new synthetic financial world with injected crimes."""
    state = get_state()

    # Reset state before regeneration
    reset_state()
    state = get_state()

    generate_world(
        seed=request.seed,
        difficulty=request.difficulty,
        node_count=request.node_count,
    )

    return GenerateResponse(
        status="generated",
        node_count=state.graph.number_of_nodes() if state.graph else 0,
        edge_count=state.graph.number_of_edges() if state.graph else 0,
        crimes_injected=len(state.ground_truth.get("crimes", [])),
        evidence_count=len(state.evidence_documents),
        seed=state.seed,
        difficulty=state.difficulty,
        generated_at=state.generated_at or datetime.now().isoformat(),
    )


@router.post("/reset")
async def reset_everything():
    """Reset all application state (graph, investigations, evidence)."""
    reset_state()
    return {"status": "reset", "message": "All state cleared"}
