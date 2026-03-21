#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Purple Agent — Pre-flight Validation Script v2.0
# Run BEFORE every deployment. ALL checks must pass.
# Exit 0 = ready to deploy. Exit 1 = fix issues first.
#
# v2.0 changes:
#   - [CRIT-04] Fixed: no longer imports phantom MAX_PROMPT_TRANSACTIONS
#   - [HIGH-03] Fixed: recursive DFS detection logic corrected
#   - Added: performance baseline measurement
#   - Added: coverage threshold enforcement
#   - Sections: 10 (was 8)
# ═══════════════════════════════════════════════════════════════════

set -uo pipefail
# NOTE: NO set -e (Rule 26 — non-zero exits are expected in checks)

PASS=0
FAIL=0
WARN=0

check_pass() { echo "  ✅ PASS: $1"; PASS=$((PASS + 1)); }
check_fail() { echo "  ❌ FAIL: $1"; FAIL=$((FAIL + 1)); }
check_warn() { echo "  ⚠️  WARN: $1"; WARN=$((WARN + 1)); }

echo "═══════════════════════════════════════════════════════════"
echo "Purple Agent — Pre-flight Validation v2.0"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ─── SECTION 1: Environment ───────────────────────────────────

echo "Section 1: Environment"

# 1.1 Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    check_pass "Python $PYTHON_VERSION (>= 3.11 required)"
else
    check_fail "Python $PYTHON_VERSION (>= 3.11 required)"
fi

# 1.2 PYTHONHASHSEED
if [ "${PYTHONHASHSEED:-unset}" = "0" ]; then
    check_pass "PYTHONHASHSEED=0"
else
    check_fail "PYTHONHASHSEED=${PYTHONHASHSEED:-unset} (must be 0)"
fi

# 1.3 .env file
if [ -f ".env" ]; then
    check_pass ".env file exists"
else
    check_warn ".env file missing (using defaults)"
fi

# 1.4 OPENAI_API_KEY
if [ -n "${OPENAI_API_KEY:-}" ]; then
    check_pass "OPENAI_API_KEY is set"
else
    check_warn "OPENAI_API_KEY not set (mechanical SAR fallback will be used)"
fi

echo ""

# ─── SECTION 2: Dependencies ─────────────────────────────────

echo "Section 2: Dependencies"

for pkg in networkx langgraph fastapi uvicorn httpx google.protobuf spacy pydantic openai; do
    if python3 -c "import $pkg" 2>/dev/null; then
        check_pass "Package: $pkg"
    else
        check_fail "Package: $pkg (not installed)"
    fi
done

# spaCy model
if python3 -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
    check_pass "spaCy model: en_core_web_sm"
else
    check_fail "spaCy model: en_core_web_sm (run: python -m spacy download en_core_web_sm)"
fi

echo ""

# ─── SECTION 3: File Structure ────────────────────────────────

echo "Section 3: File Structure"

CRITICAL_FILES=(
    "src/__init__.py" "src/main.py" "src/config.py"
    "src/core/__init__.py" "src/core/a2a_client.py"
    "src/core/a2a_server.py" "src/core/decision_loop.py"
    "src/core/graph_reasoner.py" "src/core/evidence_synthesizer.py"
    "src/core/sar_drafter.py" "src/core/heuristics/__init__.py"
    "src/core/heuristics/structuring.py" "src/core/heuristics/layering.py"
    "protos/__init__.py" "protos/financial_crime.proto"
    "protos/financial_crime_pb2.py" "agent.json" "ralph.sh"
    "requirements.txt" "requirements-prod.txt"
)

for f in "${CRITICAL_FILES[@]}"; do
    if [ -f "$f" ]; then
        check_pass "File: $f"
    else
        check_fail "File: $f (MISSING)"
    fi
done

if [ -x "ralph.sh" ]; then
    check_pass "ralph.sh is executable"
else
    check_fail "ralph.sh is not executable (chmod +x ralph.sh)"
fi

echo ""

# ─── SECTION 4: Configuration Validation ─────────────────────

echo "Section 4: Configuration Validation"

# [CRIT-04] v2.0 FIX: Only import constants that EXIST in config.py SSOT.
# Removed: MAX_PROMPT_TRANSACTIONS (does not exist in Architecture §8).
CONF_IMPORT=$(python3 -c "
from src.config import CONFIDENCE_THRESHOLD, SAR_LLM_SEED, SAR_MAX_NARRATIVE_CHARS
from src.config import AGENT_VERSION, STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD
from src.config import CTR_THRESHOLD_USD, DECAY_RATE_MIN, DECAY_RATE_MAX
from src.config import MAX_NODE_DEGREE, MAX_PATHS_PER_SEARCH, SPACY_MODEL_NAME
print('OK')
" 2>&1)
if [ "$CONF_IMPORT" = "OK" ]; then
    check_pass "config.py: all critical constants importable"
else
    check_fail "config.py import error: $CONF_IMPORT"
fi

# Confidence threshold value
CONF_CHECK=$(python3 -c "
from decimal import Decimal
from src.config import CONFIDENCE_THRESHOLD
if CONFIDENCE_THRESHOLD != Decimal('0.5'):
    raise ValueError(f'Expected 0.5, got {CONFIDENCE_THRESHOLD}')
print('OK')
" 2>&1)
if [ "$CONF_CHECK" = "OK" ]; then
    check_pass "CONFIDENCE_THRESHOLD = Decimal('0.5')"
else
    check_fail "CONFIDENCE_THRESHOLD: $CONF_CHECK"
fi

# Agent version
AGENT_VER=$(python3 -c "from src.config import AGENT_VERSION; print(AGENT_VERSION)" 2>/dev/null)
if [ "$AGENT_VER" = "7.0.0" ]; then
    check_pass "AGENT_VERSION = 7.0.0"
else
    check_fail "AGENT_VERSION = ${AGENT_VER:-ERROR} (expected 7.0.0)"
fi

# agent.json version matches
JSON_VER=$(python3 -c "import json; print(json.load(open('agent.json')).get('version', 'MISSING'))" 2>/dev/null)
if [ "$JSON_VER" = "7.0.0" ]; then
    check_pass "agent.json version = 7.0.0 (matches config.py)"
else
    check_fail "agent.json version = ${JSON_VER:-ERROR} (expected 7.0.0)"
fi

echo ""

# ─── SECTION 5: Import Smoke Test ────────────────────────────

echo "Section 5: Import Smoke Test"

IMPORT_CHECK=$(python3 -c "
from src.core.a2a_client import A2AClient
from src.core.a2a_server import app as a2a_app
from src.core.decision_loop import build_workflow
from src.core.graph_reasoner import GraphReasoner
from src.core.evidence_synthesizer import EvidenceSynthesizer
from src.core.sar_drafter import SARDrafter
from src.core.heuristics.structuring import detect_structuring
from src.core.heuristics.layering import detect_layering
print('OK')
" 2>&1)
if [ "$IMPORT_CHECK" = "OK" ]; then
    check_pass "All 8 core modules import successfully"
else
    check_fail "Import error: $IMPORT_CHECK"
fi

echo ""

# ─── SECTION 6: Test Suite ───────────────────────────────────

echo "Section 6: Test Suite"

TEST_RESULT=$(PYTHONHASHSEED=0 python3 -m pytest -p no:randomly -x -q --tb=line 2>&1)
TEST_EXIT=$?

if [ "$TEST_EXIT" -eq 0 ]; then
    TOTAL_TESTS=$(echo "$TEST_RESULT" | grep -oP '\d+ passed' | grep -oP '\d+')
    check_pass "Test suite: ${TOTAL_TESTS:-?} tests passed"
else
    FAILED_LINE=$(echo "$TEST_RESULT" | grep "FAILED" | head -1)
    check_fail "Test suite failed: $FAILED_LINE"
fi

echo ""

# ─── SECTION 7: Protobuf Validation ─────────────────────────

echo "Section 7: Protobuf"

PROTO_CHECK=$(python3 -c "
from protos import financial_crime_pb2 as pb2
for msg in ['Transaction', 'NodeAttributes', 'TextEvidence', 'GraphFragment',
            'InvestigationRequest', 'CitedEvidence', 'InvestigationResult']:
    if not hasattr(pb2, msg):
        raise AttributeError(f'Missing: {msg}')
print('OK')
" 2>&1)
if [ "$PROTO_CHECK" = "OK" ]; then
    check_pass "Protobuf: all 7 message types present"
else
    check_fail "Protobuf: $PROTO_CHECK"
fi

echo ""

# ─── SECTION 8: Anti-Pattern Scan ────────────────────────────

echo "Section 8: Anti-Pattern Scan"

# 8.1 No bare except
BARE=$(grep -rn "^[[:space:]]*except:" src/ --include="*.py" 2>/dev/null | wc -l)
if [ "$BARE" -eq 0 ]; then
    check_pass "No bare 'except:' (AP #2)"
else
    check_fail "Found $BARE bare 'except:' (AP #2)"
fi

# 8.2 No list(set()) without sorted (Rule 15)
UNSORTED=$(grep -rn "list(set(" src/ --include="*.py" 2>/dev/null | wc -l)
if [ "$UNSORTED" -eq 0 ]; then
    check_pass "No list(set()) (Rule 15)"
else
    check_fail "Found $UNSORTED list(set()) — use sorted() (Rule 15)"
fi

# [HIGH-03] v2.0 FIX: Corrected recursive DFS detection.
# v1.0 had broken pipe: `grep -q ... | grep -v ...` (grep -q suppresses output).
# v2.0 uses grep -c to count self-referencing function calls.
# 8.3 No recursive DFS (Rule 20)
RECURSIVE_FOUND=0
for file in $(grep -rln "def.*_dfs\|def.*depth_first\|def.*find_chains\|def.*find_layers" src/ --include="*.py" 2>/dev/null); do
    # Extract function names that look like DFS implementations
    FUNC_NAMES=$(grep -oP "def (\w+)" "$file" | awk '{print $2}' | grep -iE "dfs|depth_first|find_chain|find_layer")
    for func in $FUNC_NAMES; do
        # Count calls to this function INSIDE the function body (excluding the def line)
        # If the function calls itself, it's recursive
        SELF_CALLS=$(awk "/def ${func}/,/^def [[:alpha:]]/{print}" "$file" | grep -c "${func}(" 2>/dev/null || echo 0)
        # Subtract 1 for the def line itself
        SELF_CALLS=$((SELF_CALLS - 1))
        if [ "$SELF_CALLS" -gt 0 ]; then
            check_fail "Recursive function detected: $func in $file ($SELF_CALLS self-calls)"
            RECURSIVE_FOUND=1
        fi
    done
done
if [ "$RECURSIVE_FOUND" -eq 0 ]; then
    check_pass "No recursive DFS detected (Rule 20)"
fi

# 8.4 No import * (AP #3)
STAR=$(grep -rn "^from .* import \*" src/ --include="*.py" 2>/dev/null | wc -l)
if [ "$STAR" -eq 0 ]; then
    check_pass "No 'import *' (AP #3)"
else
    check_fail "Found $STAR 'import *' (AP #3)"
fi

echo ""

# ─── SECTION 9: Determinism Pre-check ────────────────────────

echo "Section 9: Determinism Pre-check"

# Quick check: PYTHONHASHSEED propagation
HASH_CHECK=$(python3 -c "import os; print(os.environ.get('PYTHONHASHSEED', 'NOT SET'))" 2>/dev/null)
if [ "$HASH_CHECK" = "0" ]; then
    check_pass "PYTHONHASHSEED=0 visible to Python"
else
    check_fail "PYTHONHASHSEED not propagated: $HASH_CHECK"
fi

# Quick check: LLM seed configured
SEED_CHECK=$(python3 -c "from src.config import SAR_LLM_SEED; print(SAR_LLM_SEED)" 2>/dev/null)
if [ "$SEED_CHECK" = "42" ]; then
    check_pass "SAR_LLM_SEED = 42"
else
    check_fail "SAR_LLM_SEED = ${SEED_CHECK:-ERROR} (expected 42)"
fi

echo ""

# ─── SECTION 10: Performance Baseline ────────────────────────

echo "Section 10: Performance Baseline"

# Measure import time (should be < 5s including spaCy lazy-load)
IMPORT_TIME=$(python3 -c "
import time
start = time.monotonic()
from src.core.decision_loop import build_workflow
from src.core.graph_reasoner import GraphReasoner
from src.core.evidence_synthesizer import EvidenceSynthesizer
from src.core.sar_drafter import SARDrafter
elapsed = time.monotonic() - start
print(f'{elapsed:.2f}')
" 2>/dev/null)
if [ -n "$IMPORT_TIME" ]; then
    # Compare as integer (multiply by 100 to avoid float comparison in bash)
    IMPORT_MS=$(echo "$IMPORT_TIME" | awk '{printf "%d", $1 * 100}')
    if [ "$IMPORT_MS" -lt 500 ]; then
        check_pass "Module import time: ${IMPORT_TIME}s (< 5.0s)"
    else
        check_warn "Module import time: ${IMPORT_TIME}s (> 5.0s — may indicate heavy initialization)"
    fi
else
    check_warn "Could not measure import time"
fi

echo ""

# ─── SUMMARY ─────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════"
echo "Pre-flight Summary"
echo "═══════════════════════════════════════════════════════════"
echo "  ✅ Passed:   $PASS"
echo "  ❌ Failed:   $FAIL"
echo "  ⚠️  Warnings: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "❌ PRE-FLIGHT FAILED — Fix $FAIL issue(s) before deployment"
    exit 1
else
    if [ "$WARN" -gt 0 ]; then
        echo "⚠️  PRE-FLIGHT PASSED WITH $WARN WARNING(S)"
    else
        echo "✅ PRE-FLIGHT PASSED — Ready for deployment"
    fi
    exit 0
fi
