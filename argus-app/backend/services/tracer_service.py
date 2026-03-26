"""TRACER detection algorithms — direct imports from tracer_agent (real code, not copies).

v8.0: Replaced 1051-line copy with direct imports from the authoritative tracer_agent
source. Every algorithm, validation rule, config constant, and dataclass now comes
from the real Tracer codebase. This module is a thin re-export layer that preserves
the import contract for investigation_service.py and benchmark_service.py.
"""

# ═══ Core Engine ═══
from tracer_agent.src.core.graph_reasoner import GraphReasoner

# ═══ Detection Heuristics ═══
from tracer_agent.src.core.heuristics.structuring import (
    detect_structuring,
    StructuringResult,
)
from tracer_agent.src.core.heuristics.layering import (
    detect_layering,
    LayeringResult,
    LayeringChain,
)

# ═══ SAR Generation ═══
from tracer_agent.src.core.sar_drafter import (
    SARDraft,
    SARDrafter,
    mechanical_sar_template,
)

# ═══ Evidence Synthesis ═══
from tracer_agent.src.core.evidence_synthesizer import (
    EvidenceSynthesizer,
    EvidenceResult,
)

# ═══ LangGraph Workflow ═══
from tracer_agent.src.core.decision_loop import (
    build_workflow,
    InvestigationState,
    # Node functions (for step-by-step execution with progress tracking)
    receive_case,
    analyze_graph,
    detect_typology,
    synthesize_evidence,
    compute_confidence,
    draft_sar,
    validate_sar,
    submit_result,
    # Conditional edge functions
    should_generate_sar,
    should_retry,
)

# ═══ A2A Infrastructure ═══
from tracer_agent.src.core.a2a_client import (
    A2AClient,
    CircuitBreaker,
    CircuitBreakerOpen,
)

# ═══ Authoritative Config ═══
from tracer_agent.src.config import (
    CONFIDENCE_THRESHOLD,
    SAR_MAX_RETRY,
    MAX_DFS_DEPTH,
    MAX_PATHS_PER_SEARCH,
    MAX_NODE_DEGREE,
    DECAY_RATE_MIN,
    DECAY_RATE_MAX,
    DECAY_TOLERANCE,
    MIN_CHAIN_LENGTH,
    MAX_HOP_DELAY_SECONDS,
    STRUCTURING_MIN_AMOUNT_USD,
    STRUCTURING_MAX_AMOUNT_USD,
    STRUCTURING_MIN_AMOUNT_INR,
    STRUCTURING_MAX_AMOUNT_INR,
    STRUCTURING_MIN_COUNT,
    STRUCTURING_MIN_COUNT_INR,
    STRUCTURING_TIME_WINDOW_SECONDS,
    STRUCTURING_TIME_WINDOW_SECONDS_INR,
    AGENT_VERSION as TRACER_VERSION,
)

# ═══ Ralph Runner (Task Management) ═══
from tracer_agent.src.ralph_runner import (
    load_prd,
    save_prd,
    get_next_task,
    all_tasks_complete,
    log_progress,
)

__all__ = [
    # Core engine
    "GraphReasoner",
    # Detection
    "detect_structuring", "StructuringResult",
    "detect_layering", "LayeringResult", "LayeringChain",
    # SAR
    "SARDraft", "SARDrafter", "mechanical_sar_template",
    # Evidence
    "EvidenceSynthesizer", "EvidenceResult",
    # Workflow
    "build_workflow", "InvestigationState",
    "receive_case", "analyze_graph", "detect_typology",
    "synthesize_evidence", "compute_confidence",
    "draft_sar", "validate_sar", "submit_result",
    "should_generate_sar", "should_retry",
    # A2A
    "A2AClient", "CircuitBreaker", "CircuitBreakerOpen",
    # Config
    "CONFIDENCE_THRESHOLD", "SAR_MAX_RETRY", "TRACER_VERSION",
    # Ralph Runner
    "load_prd", "save_prd", "get_next_task", "all_tasks_complete", "log_progress",
]
