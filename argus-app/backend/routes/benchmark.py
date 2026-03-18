"""Benchmark routes — run all-node investigations and aggregate detection metrics."""
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException

from ..models.state import get_state
from ..models.schemas import (
    BenchmarkRequest, BenchmarkResponse,
    BenchmarkProgressResponse, BenchmarkListResponse,
)
from ..services.benchmark_service import run_benchmark, run_benchmark_fast

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.post("/run", response_model=BenchmarkResponse)
async def start_benchmark(request: BenchmarkRequest):
    """Start a full benchmark run in a background thread.

    Returns immediately with benchmark_id. Poll /progress for updates.
    """
    state = get_state()

    # If not generating, require an existing graph
    if not request.generate and state.graph is None:
        raise HTTPException(
            status_code=400,
            detail="No graph loaded. Either generate first or set generate=true.",
        )

    benchmark_id = f"bench-{uuid.uuid4().hex[:12]}"
    config = {
        "mode": request.mode,
        "hop_depth": request.hop_depth,
        "jurisdiction": request.jurisdiction,
        "generate": request.generate,
        "seed": request.seed,
        "difficulty": request.difficulty,
        "node_count": request.node_count,
    }

    # Dispatch based on mode
    target_fn = run_benchmark_fast if request.mode == "fast" else run_benchmark
    thread = threading.Thread(
        target=target_fn,
        args=(benchmark_id, config),
        daemon=True,
    )
    thread.start()

    # Give thread a moment to initialize state.benchmarks[id]
    time.sleep(0.05)

    benchmark = state.benchmarks.get(benchmark_id)
    if benchmark is None:
        return BenchmarkResponse(
            benchmark_id=benchmark_id,
            status="RUNNING",
            config=config,
            total_count=request.node_count if request.generate else (state.graph.number_of_nodes() if state.graph else 0),
            started_at="",
        )

    return BenchmarkResponse(**benchmark)


# NOTE: /list MUST come before /{benchmark_id} to avoid FastAPI matching "list" as an ID
@router.get("/list", response_model=BenchmarkListResponse)
async def list_benchmarks():
    """List all benchmark runs."""
    state = get_state()
    benchmarks = list(state.benchmarks.values())
    return BenchmarkListResponse(
        benchmarks=[BenchmarkResponse(**b) for b in benchmarks],
        total=len(benchmarks),
    )


@router.get("/{benchmark_id}/progress", response_model=BenchmarkProgressResponse)
async def get_benchmark_progress(benchmark_id: str):
    """Lightweight progress endpoint for polling during benchmark runs."""
    state = get_state()
    benchmark = state.benchmarks.get(benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail=f"Benchmark not found: {benchmark_id}")
    return BenchmarkProgressResponse(
        benchmark_id=benchmark_id,
        status=benchmark.get("status", "UNKNOWN"),
        progress=benchmark.get("progress", 0.0),
        current_node=benchmark.get("current_node", ""),
        completed_count=benchmark.get("completed_count", 0),
        total_count=benchmark.get("total_count", 0),
    )


@router.get("/{benchmark_id}", response_model=BenchmarkResponse)
async def get_benchmark(benchmark_id: str):
    """Get full benchmark results including per-node results."""
    state = get_state()
    benchmark = state.benchmarks.get(benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail=f"Benchmark not found: {benchmark_id}")
    return BenchmarkResponse(**benchmark)
