═══ PART 0: PRE-FLIGHT + MONOREPO SETUP ═══

SESSION GOAL:
Validate existing codebase, create directory scaffold, create .cursorrules v6.0.

PREREQUISITE:
Paste MASTER_CONTEXT_v6.0.md at the START of the session before this prompt.

───────────────────────────────────────────────────────────────────────

STEP 1 — Create directory scaffold:

argus-app/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   └── state.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── forge_service.py
│   │   ├── tracer_service.py
│   │   ├── investigation_service.py
│   │   └── assessment_service.py
│   └── routes/
│       ├── __init__.py
│       ├── health.py
│       ├── graph.py
│       ├── investigation.py
│       ├── evidence.py
│       └── assessment.py
└── frontend/                      # (scaffolded in Part 2)

All __init__.py files should be empty.

───────────────────────────────────────────────────────────────────────

STEP 2 — Validate FORGE imports.

Create argus-app/backend/test_imports.py:

```python
"""Import validation — run from project root: PYTHONHASHSEED=0 python argus-app/backend/test_imports.py"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ═══ FORGE CORE IMPORTS (safe — no side effects) ═══
from src.core.graph_generator import generate_scale_free_graph, add_entity_attributes, add_transaction_attributes
from src.core.crime_injector import inject_structuring, inject_layering, StructuringConfig, LayeringConfig
from src.core.evidence_generator import EvidenceGenerator
from src.core.result_types import EntityMetrics, HallucinationCheck, FiveWsValidation, AssessmentResult
from src.config import AGENT_VERSION as FORGE_VERSION

# ═══ CONSTANT REMAPPING VALIDATION (v5.0 D-44/D-45) ═══
from src.config import LAYERING_MIN_DECAY, LAYERING_MAX_DECAY, DECAY_TOLERANCE
from src.config import MAX_DFS_DEPTH, MAX_PATHS_PER_SEARCH, MAX_NODE_DEGREE
from src.config import MIN_CHAIN_LENGTH, MAX_HOP_DELAY_SECONDS
from src.config import AMOUNT_PATTERNS, IFSC_SEARCH_COMPILED
from src.config import EVIDENCE_DISCREPANCY_THRESHOLD_USD, EVIDENCE_DISCREPANCY_THRESHOLD_INR
from src.config import TIMEZONE_FINCEN, TIMEZONE_FIU_IND
from src.config import (
    STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    CTR_THRESHOLD_USD, STRUCTURING_MIN_COUNT,
    STRUCTURING_TIME_WINDOW_SECONDS,
    STRUCTURING_MIN_AMOUNT_INR, STRUCTURING_MAX_AMOUNT_INR,
    CTR_THRESHOLD_INR, STRUCTURING_MIN_COUNT_INR,
    STRUCTURING_TIME_WINDOW_SECONDS_INR,
)
from decimal import Decimal

# NOTE: VELOCITY_THRESHOLD is a TRACER-only constant (purple_agent/src/config.py).
# It does NOT exist in src/config.py (FORGE). It will be defined locally in
# tracer_service.py when TRACER detection logic is copied in Part 1B.

# ═══ VALUE VERIFICATION ═══
assert LAYERING_MIN_DECAY == Decimal("0.02"), f"Expected 0.02, got {LAYERING_MIN_DECAY}"
assert LAYERING_MAX_DECAY == Decimal("0.05"), f"Expected 0.05, got {LAYERING_MAX_DECAY}"
assert DECAY_TOLERANCE == Decimal("0.005"), f"Expected 0.005, got {DECAY_TOLERANCE}"
assert STRUCTURING_MIN_AMOUNT_USD == Decimal("9000"), f"Expected 9000, got {STRUCTURING_MIN_AMOUNT_USD}"
assert CTR_THRESHOLD_USD == Decimal("10000"), f"Expected 10000, got {CTR_THRESHOLD_USD}"
assert MAX_DFS_DEPTH == 15, f"Expected 15, got {MAX_DFS_DEPTH}"
assert MAX_NODE_DEGREE == 500, f"Expected 500, got {MAX_NODE_DEGREE}"
assert MAX_PATHS_PER_SEARCH == 1000, f"Expected 1000, got {MAX_PATHS_PER_SEARCH}"

# ═══ GRAPH TYPE VERIFICATION ═══
import networkx as nx
G = generate_scale_free_graph(n_nodes=50, seed=42)
assert isinstance(G, nx.MultiDiGraph), f"Expected MultiDiGraph, got {type(G).__name__}"

print(f"✓ FORGE version: {FORGE_VERSION}")
print(f"✓ LAYERING_MIN_DECAY (= TRACER DECAY_RATE_MIN): {LAYERING_MIN_DECAY}")
print(f"✓ LAYERING_MAX_DECAY (= TRACER DECAY_RATE_MAX): {LAYERING_MAX_DECAY}")
print(f"✓ Graph type: {type(G).__name__} ({G.number_of_nodes()} nodes)")
print(f"✓ generate_scale_free_graph: {generate_scale_free_graph}")
print(f"✓ StructuringConfig: {StructuringConfig}")
print(f"✓ EntityMetrics: {EntityMetrics}")
print("═══ ALL FORGE IMPORTS PASSED — constant remapping verified ═══")

# DO NOT import from src.core.a2a_interface — it creates a FastAPI app!
# DO NOT import purple_agent modules via sys.path — namespace collision!
# Detection modules will be COPIED into tracer_service.py in Part 1B.
```

Run: cd project_root && set PYTHONHASHSEED=0 && python argus-app/backend/test_imports.py
Expected: "ALL FORGE IMPORTS PASSED — constant remapping verified"

───────────────────────────────────────────────────────────────────────

STEP 3 — Create .cursorrules at argus-app/.cursorrules

See the generated .cursorrules file for the full governance content derived
from Master Context v6.0 critical rules, design system, and architecture.

───────────────────────────────────────────────────────────────────────

STEP 4 — Create .env.example:

OPENAI_API_KEY=sk-your-key-here
GRAPH_SIZE=1000
DIFFICULTY=5
SEED=42
PYTHONHASHSEED=0

───────────────────────────────────────────────────────────────────────

VERIFICATION:
  ☐ All directories exist with empty __init__.py
  ☐ test_imports.py passes with all value assertions
  ☐ .cursorrules created
  ☐ .env.example created

═══ END PART 0 ═══
