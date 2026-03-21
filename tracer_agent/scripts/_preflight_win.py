"""Windows-compatible preflight runner (mirrors scripts/preflight.sh)."""
import sys
import os
import json
import time
from decimal import Decimal

PASS = 0
FAIL = 0
WARN = 0


def check_pass(msg):
    global PASS
    PASS += 1
    print(f"  PASS: {msg}")


def check_fail(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL: {msg}")


def check_warn(msg):
    global WARN
    WARN += 1
    print(f"  WARN: {msg}")


# === Section 1: Environment ===
print("Section 1: Environment")

v = sys.version_info
if v >= (3, 11):
    check_pass(f"Python {v.major}.{v.minor}")
else:
    check_fail(f"Python {v.major}.{v.minor} (>= 3.11 required)")

hashseed = os.environ.get("PYTHONHASHSEED", "unset")
if hashseed == "0":
    check_pass("PYTHONHASHSEED=0")
else:
    check_fail(f"PYTHONHASHSEED={hashseed} (must be 0)")

if os.path.isfile(".env"):
    check_pass(".env file exists")
else:
    check_warn(".env file missing")

if os.environ.get("OPENAI_API_KEY"):
    check_pass("OPENAI_API_KEY set")
else:
    check_warn("OPENAI_API_KEY not set")

print()

# === Section 2: Dependencies ===
print("Section 2: Dependencies")

for pkg in ["networkx", "langgraph", "fastapi", "uvicorn", "httpx",
            "google.protobuf", "spacy", "pydantic", "openai"]:
    try:
        __import__(pkg)
        check_pass(f"Package: {pkg}")
    except ImportError:
        check_fail(f"Package: {pkg} (not installed)")

try:
    import spacy
    spacy.load("en_core_web_sm")
    check_pass("spaCy model: en_core_web_sm")
except Exception:
    check_fail("spaCy model: en_core_web_sm")

print()

# === Section 3: File Structure ===
print("Section 3: File Structure")

critical_files = [
    "src/__init__.py", "src/main.py", "src/config.py",
    "src/core/__init__.py", "src/core/a2a_client.py",
    "src/core/a2a_server.py", "src/core/decision_loop.py",
    "src/core/graph_reasoner.py", "src/core/evidence_synthesizer.py",
    "src/core/sar_drafter.py", "src/core/heuristics/__init__.py",
    "src/core/heuristics/structuring.py", "src/core/heuristics/layering.py",
    "protos/__init__.py", "protos/financial_crime.proto",
    "protos/financial_crime_pb2.py", "agent.json", "ralph.sh",
    "requirements.txt", "requirements-prod.txt",
]

for f in critical_files:
    if os.path.isfile(f):
        check_pass(f"File: {f}")
    else:
        check_fail(f"File: {f} (MISSING)")

print()

# === Section 4: Configuration ===
print("Section 4: Configuration Validation")

try:
    from src.config import (
        CONFIDENCE_THRESHOLD, SAR_LLM_SEED, SAR_MAX_NARRATIVE_CHARS,
        AGENT_VERSION, STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
        CTR_THRESHOLD_USD, DECAY_RATE_MIN, DECAY_RATE_MAX,
        MAX_NODE_DEGREE, MAX_PATHS_PER_SEARCH, SPACY_MODEL_NAME,
    )
    check_pass("config.py: all critical constants importable")

    if CONFIDENCE_THRESHOLD == Decimal("0.5"):
        check_pass("CONFIDENCE_THRESHOLD = Decimal('0.5')")
    else:
        check_fail(f"CONFIDENCE_THRESHOLD = {CONFIDENCE_THRESHOLD}")

    if AGENT_VERSION == "7.0.0":
        check_pass("AGENT_VERSION = 7.0.0")
    else:
        check_fail(f"AGENT_VERSION = {AGENT_VERSION}")

    with open("agent.json", encoding="utf-8") as fh:
        jv = json.load(fh).get("version", "MISSING")
    if jv == "7.0.0":
        check_pass("agent.json version = 7.0.0")
    else:
        check_fail(f"agent.json version = {jv}")

except Exception as e:
    check_fail(f"Config import: {e}")

print()

# === Section 5: Import Smoke Test ===
print("Section 5: Import Smoke Test")

try:
    from src.core.a2a_client import A2AClient
    from src.core.a2a_server import app as a2a_app
    from src.core.decision_loop import build_workflow
    from src.core.graph_reasoner import GraphReasoner
    from src.core.evidence_synthesizer import EvidenceSynthesizer
    from src.core.sar_drafter import SARDrafter
    from src.core.heuristics.structuring import detect_structuring
    from src.core.heuristics.layering import detect_layering
    check_pass("All 8 core modules import successfully")
except Exception as e:
    check_fail(f"Import error: {e}")

print()

# === Section 7: Protobuf ===
print("Section 7: Protobuf")

try:
    from protos import financial_crime_pb2 as pb2
    msgs = ["Transaction", "NodeAttributes", "TextEvidence", "GraphFragment",
            "InvestigationRequest", "CitedEvidence", "InvestigationResult"]
    for msg in msgs:
        assert hasattr(pb2, msg), f"Missing: {msg}"
    check_pass("All 7 Protobuf message types present")
except Exception as e:
    check_fail(f"Protobuf: {e}")

print()

# === Section 8: Anti-Pattern Scan ===
print("Section 8: Anti-Pattern Scan")

import re

src_dir = "src"
bare_except_count = 0
import_star_count = 0
list_set_count = 0

for root, dirs, files in os.walk(src_dir):
    for fname in files:
        if not fname.endswith(".py"):
            continue
        path = os.path.join(root, fname)
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        for line in lines:
            if re.match(r"^\s*except:\s*$", line):
                bare_except_count += 1
            if re.match(r"^from\s+.*\s+import\s+\*", line.strip()):
                import_star_count += 1
            if "list(set(" in line:
                list_set_count += 1

if bare_except_count == 0:
    check_pass("No bare 'except:' (AP #2)")
else:
    check_fail(f"Found {bare_except_count} bare 'except:' (AP #2)")

if list_set_count == 0:
    check_pass("No list(set()) (Rule 15)")
else:
    check_fail(f"Found {list_set_count} list(set()) — use sorted() (Rule 15)")

if import_star_count == 0:
    check_pass("No 'import *' (AP #3)")
else:
    check_fail(f"Found {import_star_count} 'import *' (AP #3)")

print()

# === Section 9: Determinism Pre-check ===
print("Section 9: Determinism Pre-check")

if os.environ.get("PYTHONHASHSEED") == "0":
    check_pass("PYTHONHASHSEED=0 visible to Python")
else:
    check_fail(f"PYTHONHASHSEED not propagated: {os.environ.get('PYTHONHASHSEED', 'NOT SET')}")

try:
    from src.config import SAR_LLM_SEED
    if SAR_LLM_SEED == 42:
        check_pass("SAR_LLM_SEED = 42")
    else:
        check_fail(f"SAR_LLM_SEED = {SAR_LLM_SEED}")
except Exception:
    check_fail("SAR_LLM_SEED import failed")

print()

# === Section 10: Performance Baseline ===
print("Section 10: Performance Baseline")

t0 = time.monotonic()
from src.core.decision_loop import build_workflow  # noqa: F811
from src.core.graph_reasoner import GraphReasoner  # noqa: F811
from src.core.evidence_synthesizer import EvidenceSynthesizer  # noqa: F811
from src.core.sar_drafter import SARDrafter  # noqa: F811
elapsed = time.monotonic() - t0

if elapsed < 5.0:
    check_pass(f"Module import time: {elapsed:.2f}s (< 5.0s)")
else:
    check_warn(f"Module import time: {elapsed:.2f}s (> 5.0s)")

print()

# === Summary ===
print("=" * 55)
print("Pre-flight Summary")
print("=" * 55)
print(f"  Passed:   {PASS}")
print(f"  Failed:   {FAIL}")
print(f"  Warnings: {WARN}")
print()

if FAIL > 0:
    print(f"PRE-FLIGHT FAILED -- Fix {FAIL} issue(s) before deployment")
    sys.exit(1)
else:
    if WARN > 0:
        print(f"PRE-FLIGHT PASSED WITH {WARN} WARNING(S)")
    else:
        print("PRE-FLIGHT PASSED -- Ready for deployment")
    sys.exit(0)
