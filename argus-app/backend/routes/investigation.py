"""Investigation routes — 4 endpoints for running and querying investigations."""
import asyncio
import threading
import time
import uuid
from fastapi import APIRouter, HTTPException

from ..models.state import get_state
from ..models.schemas import (
    InvestigationRequest, InvestigationResponse,
    InvestigationListResponse, PipelineStatusResponse,
)
from ..services.investigation_service import run_investigation
from ..services.baseline_service import run_baseline_investigation

router = APIRouter(prefix="/api/investigation", tags=["investigation"])


@router.post("/investigate", response_model=InvestigationResponse)
async def create_investigation(request: InvestigationRequest):
    """Launch the 8-step investigation pipeline in a background thread.

    Returns immediately with case_id + PENDING status.
    Frontend polls GET /{case_id}/progress for real-time step updates.
    """
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")

    # Generate case_id if not provided
    case_id = request.case_id or f"case-{uuid.uuid4().hex[:12]}"

    # Resolve subject node
    subject_id = request.subject_id
    resolved = None
    for candidate in [subject_id, int(subject_id) if subject_id.isdigit() else None]:
        if candidate is not None and candidate in state.graph:
            resolved = candidate
            break
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Subject not found: {subject_id}")

    # Fire-and-return: launch investigation in background thread
    thread = threading.Thread(
        target=run_investigation,
        kwargs={
            "case_id": case_id,
            "subject_id": str(resolved),
            "hop_depth": request.hop_depth,
            "jurisdiction": request.jurisdiction,
        },
        daemon=True,
    )
    thread.start()

    # Give thread a moment to seed state.investigations[case_id]
    time.sleep(0.05)

    # Return the PENDING investigation entry
    investigation = state.investigations.get(case_id)
    if investigation is None:
        # Thread hasn't seeded yet — return a minimal PENDING response
        return InvestigationResponse(
            case_id=case_id,
            subject_id=str(resolved),
            jurisdiction=request.jurisdiction,
            status="PENDING",
        )

    return investigation


@router.get("/list", response_model=InvestigationListResponse)
async def list_investigations():
    """Return all completed and in-progress investigations."""
    state = get_state()
    investigations = list(state.investigations.values())
    return InvestigationListResponse(
        investigations=investigations,
        total=len(investigations),
    )


@router.get("/{case_id}", response_model=InvestigationResponse)
async def get_investigation(case_id: str):
    """Return a specific investigation by case_id."""
    state = get_state()
    investigation = state.investigations.get(case_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation not found: {case_id}")
    return investigation


@router.get("/{case_id}/progress", response_model=PipelineStatusResponse)
async def get_investigation_progress(case_id: str):
    """Return pipeline progress for a specific investigation."""
    state = get_state()
    investigation = state.investigations.get(case_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation not found: {case_id}")

    steps = investigation.get("steps", [])
    completed = sum(1 for s in steps if s.get("status") == "complete")
    total = max(len(steps), 8)
    progress_pct = round((completed / total) * 100, 1)

    current_step = ""
    for s in reversed(steps):
        if s.get("status") in ("running", "complete"):
            current_step = s.get("name", "")
            break

    return PipelineStatusResponse(
        case_id=case_id,
        status=investigation.get("status", "UNKNOWN"),
        current_step=current_step,
        steps=steps,
        progress_pct=progress_pct,
    )


@router.post("/baseline")
async def baseline_investigation(request: InvestigationRequest):
    """Run a baseline (naive heuristic) investigation for comparison against Tracer."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")

    # Resolve subject node
    subject_id = request.subject_id
    resolved = None
    for candidate in [subject_id, int(subject_id) if subject_id.isdigit() else None]:
        if candidate is not None and candidate in state.graph:
            resolved = candidate
            break
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Subject not found: {subject_id}")

    result = await asyncio.to_thread(
        run_baseline_investigation,
        subject_id=str(resolved),
        hop_depth=request.hop_depth,
    )
    return result
