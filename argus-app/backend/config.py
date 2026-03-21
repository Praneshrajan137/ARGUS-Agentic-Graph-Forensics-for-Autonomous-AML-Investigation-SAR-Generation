"""Unified backend configuration.

Imports FORGE constants for graph generation and assessment rubric,
and TRACER (tracer_agent) constants as the authoritative source for
all detection thresholds, SAR parameters, and operational config.

v8.0: Purple agent config is now the single source of truth for detection.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import FORGE config — graph generation and assessment rubric
from src.config import (
    AGENT_VERSION as FORGE_VERSION,
    DEFAULT_GRAPH_SIZE, DEFAULT_DIFFICULTY, DEFAULT_SEED,
    CTR_THRESHOLD_USD, STRUCTURING_NUM_SOURCES,
    LAYERING_DEFAULT_CHAIN_LENGTH, LAYERING_INITIAL_AMOUNT,
    RUBRIC_WEIGHT_PATTERN, RUBRIC_WEIGHT_EVIDENCE,
    RUBRIC_WEIGHT_NARRATIVE, RUBRIC_WEIGHT_COMPLETENESS,
    RUBRIC_WEIGHT_EFFICIENCY,
)

# Import TRACER (tracer_agent) config — authoritative source for detection thresholds
from tracer_agent.src.config import (
    AGENT_VERSION as TRACER_VERSION,
    CONFIDENCE_THRESHOLD,
    SAR_MAX_RETRY,
    MIN_CHAIN_LENGTH,
    MAX_DFS_DEPTH,
    DECAY_RATE_MIN, DECAY_RATE_MAX, DECAY_TOLERANCE,
    MAX_HOP_DELAY_SECONDS,
    STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    STRUCTURING_MIN_AMOUNT_INR, STRUCTURING_MAX_AMOUNT_INR,
    STRUCTURING_MIN_COUNT, STRUCTURING_MIN_COUNT_INR,
    STRUCTURING_TIME_WINDOW_SECONDS, STRUCTURING_TIME_WINDOW_SECONDS_INR,
    MAX_NODE_DEGREE, MAX_PATHS_PER_SEARCH,
    SAR_LLM_MODEL, SAR_LLM_TEMPERATURE, SAR_LLM_SEED,
    SAR_MAX_NARRATIVE_CHARS, MAX_PROMPT_TRANSACTIONS,
    SPACY_MODEL_NAME,
)

UNIFIED_VERSION = "1.0.0"
API_PORT = 8000
API_HOST = "0.0.0.0"
