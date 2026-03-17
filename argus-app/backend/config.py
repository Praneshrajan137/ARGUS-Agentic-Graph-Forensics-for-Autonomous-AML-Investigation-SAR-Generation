"""Unified backend configuration.

Imports FORGE constants as the Single Source of Truth.
All values are Decimal-safe and overridable via environment variables.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import FORGE config constants (safe — no side effects)
from src.config import (
    AGENT_VERSION as FORGE_VERSION,
    DEFAULT_GRAPH_SIZE, DEFAULT_DIFFICULTY, DEFAULT_SEED,
    STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    CTR_THRESHOLD_USD, STRUCTURING_NUM_SOURCES,
    LAYERING_DEFAULT_CHAIN_LENGTH, LAYERING_INITIAL_AMOUNT,
    RUBRIC_WEIGHT_PATTERN, RUBRIC_WEIGHT_EVIDENCE,
    RUBRIC_WEIGHT_NARRATIVE, RUBRIC_WEIGHT_COMPLETENESS,
    RUBRIC_WEIGHT_EFFICIENCY,
)

UNIFIED_VERSION = "1.0.0"
TRACER_VERSION = "7.0.0"
API_PORT = 8000
API_HOST = "0.0.0.0"
