#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Purple Agent — Determinism Verification Script
# Architecture §10: "byte-identical results across 10 consecutive runs"
#
# TWO verification levels:
#   Level 1: Pipeline output SHA-256 digest comparison
#   Level 2: Test suite output stability
# ═══════════════════════════════════════════════════════════════════

set -uo pipefail
# NOTE: NO set -e (Rule 26) — we handle exit codes explicitly

NUM_RUNS="${1:-10}"
OUTPUT_DIR="/tmp/purple_determinism_$$"
FAILED=0

echo "═══════════════════════════════════════════════════════════"
echo "Purple Agent — Determinism Verification"
echo "Runs: $NUM_RUNS | PID: $$ | Output: $OUTPUT_DIR"
echo "═══════════════════════════════════════════════════════════"

# Clean slate
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# ─── Pre-flight ──────────────────────────────────────────────

if [ "${PYTHONHASHSEED:-unset}" != "0" ]; then
    echo "❌ FATAL: PYTHONHASHSEED is not 0 (current: ${PYTHONHASHSEED:-unset})"
    echo "   Run with: PYTHONHASHSEED=0 bash scripts/verify_determinism.sh"
    exit 1
fi

echo ""

# ─── Level 1: Pipeline Output Determinism ────────────────────

echo "Level 1: Pipeline Computation Determinism (detection heuristic output digests)"
echo ""

# Generate a Python script that runs the pipeline with fixture data
# and outputs a deterministic digest of the result.
# [CRIT-05] v3.0: This script runs ACTUAL detection heuristics
# (structuring + layering) and includes their OUTPUTS in the digest.
# v2.0 only digested the static input construction, which is
# tautologically deterministic. v3.0 verifies the COMPUTATION PATH.
#
# ADAPTED: Uses actual GraphReasoner + detect_structuring/detect_layering
# API signatures from the codebase (graph_reasoner, node_id, currency).
cat > "$OUTPUT_DIR/pipeline_digest.py" << 'PYEOF'
"""Run detection heuristics with fixture data, output SHA-256 digest of results.

[CRIT-05] v3.0: This digests ACTUAL DETECTION OUTPUT, not input construction.
The detection heuristics (structuring + layering) are pure Python — no LLM
required — so this script can run without an API key.

ADAPTED: Uses actual GraphReasoner API (load_from_dict, then pass instance
to detect_structuring/detect_layering) instead of the raw graph/transactions
signature from the task spec, which did not match the codebase.
"""
import hashlib
import json
import sys
from dataclasses import asdict
from decimal import Decimal

from src.core.graph_reasoner import GraphReasoner
from src.core.heuristics.structuring import detect_structuring
from src.core.heuristics.layering import detect_layering


def build_test_graph_data() -> tuple:
    """Build a deterministic test graph dict for GraphReasoner.load_from_dict.

    Returns (graph_data dict, mule_id).
    12 sources → 1 mule, all USD, amounts in $9,200–$9,750 band.
    """
    mule_id = "mule_det_001"
    nodes = {
        mule_id: {
            "id": mule_id,
            "name": "Mule Det",
            "entity_type": "individual",
            "jurisdiction": "US",
        }
    }
    transactions = []

    for i in range(12):
        tx_id = f"TX-DET-{i:04d}"
        src = f"src_{i:02d}"
        amount = Decimal("9200") + Decimal(str(i * 50))
        nodes[src] = {
            "id": src,
            "name": f"Source {i}",
            "entity_type": "individual",
            "jurisdiction": "US",
        }
        transactions.append({
            "id": tx_id,
            "source_node": src,
            "target_node": mule_id,
            "amount": amount,
            "currency": "USD",
            "timestamp": 1700000000 + i * 3600,
            "type": "WIRE",
            "reference": "",
            "branch_code": "",
        })

    graph_data = {
        "transactions": transactions,
        "nodes": nodes,
    }
    return graph_data, mule_id


# Build deterministic graph and load into GraphReasoner
graph_data, mule_id = build_test_graph_data()
reasoner = GraphReasoner()
reasoner.load_from_dict(graph_data)

# ── Run ACTUAL detection heuristics ──────────────────────────────
# These are the real computation paths from B2 and B3.
# Their outputs depend on the algorithm, thresholds, sorted() usage,
# and every determinism mechanism in the codebase.

structuring_result = detect_structuring(
    graph_reasoner=reasoner,
    node_id=mule_id,
    currency="USD",
)

layering_result = detect_layering(
    graph_reasoner=reasoner,
    node_id=mule_id,
    max_depth=3,
    currency="USD",
)

# ── Build digest payload from OUTPUTS ────────────────────────────
# Serialize detection results deterministically.
# This verifies that the computation path is deterministic,
# not just that static inputs hash to the same value.

def decimal_serializer(obj):
    """JSON serializer for Decimal values."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")

# Convert dataclass results to dicts for JSON serialization
structuring_dict = asdict(structuring_result)
layering_dict = asdict(layering_result)

digest_payload = json.dumps({
    "input": {
        "mule_id": mule_id,
        "currency": "USD",
        "transaction_count": len(graph_data["transactions"]),
        "node_count": len(graph_data["nodes"]),
    },
    "structuring_output": structuring_dict,
    "layering_output": layering_dict,
}, sort_keys=True, default=decimal_serializer)

digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
print(digest)
PYEOF

echo "  Running $NUM_RUNS pipeline digest computations..."
DIGESTS=()
for i in $(seq 1 "$NUM_RUNS"); do
    DIGEST=$(PYTHONHASHSEED=0 python3 "$OUTPUT_DIR/pipeline_digest.py" 2>/dev/null)
    DIGEST_EXIT=$?
    if [ "$DIGEST_EXIT" -ne 0 ] || [ -z "$DIGEST" ]; then
        echo "  ❌ Run $i: pipeline digest FAILED"
        # Show the error for debugging
        PYTHONHASHSEED=0 python3 "$OUTPUT_DIR/pipeline_digest.py" 2>&1 | tail -5
        FAILED=1
        continue
    fi
    DIGESTS+=("$DIGEST")
    echo "  Run $i: $DIGEST"
done

if [ "$FAILED" -eq 0 ]; then
    # Compare all digests to first
    BASELINE_DIGEST="${DIGESTS[0]}"
    for i in $(seq 1 $((${#DIGESTS[@]} - 1))); do
        if [ "${DIGESTS[$i]}" != "$BASELINE_DIGEST" ]; then
            echo "  ❌ Digest mismatch: run 1 vs run $((i + 1))"
            FAILED=1
        fi
    done
    if [ "$FAILED" -eq 0 ]; then
        echo "  ✅ Level 1 PASSED: All $NUM_RUNS digests identical ($BASELINE_DIGEST)"
    fi
fi

echo ""

# ─── Level 2: Test Suite Determinism ─────────────────────────

echo "Level 2: Test Suite Determinism (output comparison)"
echo ""

for i in $(seq 1 "$NUM_RUNS"); do
    echo "  Run $i/$NUM_RUNS..."
    RUN_DIR="$OUTPUT_DIR/run_$i"
    mkdir -p "$RUN_DIR"

    PYTHONHASHSEED=0 python -m pytest \
        tests/integration/test_full_pipeline.py \
        tests/integration/test_zero_failure.py \
        -p no:randomly \
        -v \
        --tb=line \
        > "$RUN_DIR/test_output.txt" 2>&1
    EXIT_CODE=$?

    if [ "$EXIT_CODE" -ne 0 ]; then
        echo "  ❌ Run $i FAILED (exit code: $EXIT_CODE)"
        FAILED=1
    else
        echo "  ✅ Run $i passed"
    fi
done

if [ "$FAILED" -ne 0 ]; then
    echo ""
    echo "❌ FATAL: One or more runs failed. Cannot verify test determinism."
else
    echo ""
    echo "  Comparing test outputs..."

    BASELINE="$OUTPUT_DIR/run_1"

    for i in $(seq 2 "$NUM_RUNS"); do
        RUN_DIR="$OUTPUT_DIR/run_$i"

        # [HIGH-02] Filter ONLY wall-clock timing metadata.
        # NEVER filter "error", "warnings", or content — those are
        # meaningful differences that must be caught.
        # Filter pattern: lines with elapsed time like "0.45s", "in 1.23 seconds",
        # pytest summary lines with timing ("===... in X.XXs ===")
        grep -v -E "^(=+.*in [0-9]+\.[0-9]+s =+$|.*[0-9]+\.[0-9]+s$)" \
            "$BASELINE/test_output.txt" > "$BASELINE/filtered.txt"
        grep -v -E "^(=+.*in [0-9]+\.[0-9]+s =+$|.*[0-9]+\.[0-9]+s$)" \
            "$RUN_DIR/test_output.txt" > "$RUN_DIR/filtered.txt"

        if diff -q "$BASELINE/filtered.txt" "$RUN_DIR/filtered.txt" > /dev/null 2>&1; then
            echo "  ✅ Run 1 vs Run $i: IDENTICAL"
        else
            echo "  ❌ Run 1 vs Run $i: DIFFER"
            echo "     First differences:"
            diff --unified=0 "$BASELINE/filtered.txt" "$RUN_DIR/filtered.txt" | head -20
            FAILED=1
        fi
    done
fi

echo ""

# ─── Summary ─────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════"

if [ "$FAILED" -ne 0 ]; then
    echo "❌ DETERMINISM CHECK FAILED"
    echo ""
    echo "   Debugging checklist:"
    echo "   1. grep -rn 'list(set(' src/        — set() without sorted()"
    echo "   2. grep -rn 'time\\.time()' src/     — time in computation path"
    echo "   3. grep -rn 'random\\.' src/          — random without seed"
    echo "   4. echo \$PYTHONHASHSEED             — must be 0"
    echo "   5. grep -rn 'CORROBORATING' src/    — must be frozenset/tuple"
    exit 1
else
    echo "✅ DETERMINISM CHECK PASSED"
    echo "   Level 1: Detection heuristics — $NUM_RUNS runs, identical SHA-256 digests"
    echo "   Level 2: Test suite — $NUM_RUNS runs, identical filtered output"
fi

# Cleanup
rm -rf "$OUTPUT_DIR"
exit 0
