## Purple Agent -- The Panopticon Protocol

Autonomous forensic financial crime investigation system with dual-jurisdiction SAR generation, zero-hallucination guarantees, and deterministic output.

**Agent Version:** 7.0.0
**Python:** 3.11+ required

---

## Overview

Purple Agent is a production-grade autonomous financial crime investigator. It operates as a node in an Agent-to-Agent (A2A) network, communicating via Protocol Buffers over HTTP. The system:

- Receives investigation requests via A2A protocol (FastAPI :8080)
- Fetches financial transaction graphs from upstream agents via Protobuf
- Constructs NetworkX MultiDiGraph representations preserving all parallel edges and transaction metadata
- Detects Structuring patterns (fan-in below Currency Transaction Report thresholds) using BFS traversal with currency-grouped threshold comparisons
- Detects Layering patterns (decay chain analysis) using iterative DFS with bounded depth and path explosion circuit breakers
- Synthesizes unstructured text evidence using dual spaCy NER + regex extraction, cross-referencing against ledger ground truth
- Computes confidence scores with a transparent formula gated on configurable thresholds before SAR generation
- Generates FinCEN SAR (US/USD) and FIU-IND STR (India/INR) narratives using the Five Ws framework with LLM generation and mechanical fallback guarantees
- Validates every entity, amount, and timestamp cited in SAR narratives against the source graph -- zero hallucination tolerance
- Achieves 100% entity recall on criminal node detection
- Produces byte-identical output across 10+ consecutive runs

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- An OpenAI API key (for LLM-based SAR generation; mechanical fallback works without it)

### Local Development

```bash
cd purple_agent

# Environment setup
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, verify PYTHONHASHSEED=0

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Run full test suite
PYTHONHASHSEED=0 pytest -p no:randomly -v --tb=short

# Start server
PYTHONHASHSEED=0 python -m src.main
```

### Docker (Single Container)

```bash
docker build -t purple-agent .
docker run -p 8080:8080 \
    --memory=1g --cpus=1.0 \
    --env-file .env \
    purple-agent
```

### Docker Compose (With Green Agent)

```bash
docker compose up --build
# Purple Agent: http://localhost:8080
# Green Agent:  http://localhost:9090
```

### Health Check

```bash
curl -s http://localhost:8080/health | python -m json.tool
# Expected:
# {
#     "status": "healthy",
#     "agent_version": "7.0.0"
# }
```

---

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system design.

```
InvestigationRequest (protobuf)
        |
        v
+--- LangGraph Decision Loop (8 nodes) -------------------+
|                                                          |
|  ingest -> detect_structuring -> detect_layering         |
|    |                                                     |
|    v                                                     |
|  synthesize_evidence -> compute_confidence               |
|                            |           |                 |
|                    >= 0.5  |           | < 0.5           |
|                            v           v                 |
|                      draft_sar      submit               |
|                         |         (LOW_CONFIDENCE)       |
|                         v                                |
|                    validate_sar                           |
|                      |       |                           |
|               pass --+       +-- fail (retry <= 3)       |
|                 |                    |                    |
|                 v                    v                    |
|              submit          draft_sar (retry)           |
|                              |                           |
|                              +-> mechanical SAR -> submit|
+----------------------------------------------------------+
        |
        v
InvestigationResult (protobuf) -> upstream agent
```

Conditional edges:

- `compute_confidence` -> `submit` (when score < CONFIDENCE_THRESHOLD)
- `validate_sar` -> `draft_sar` (retry, max SAR_MAX_RETRY times)
- `validate_sar` -> `submit` (passed OR retries exhausted -> mechanical SAR)

---

## Project Structure

```
purple_agent/
+-- agent.json                    [EXISTS]  A2A agent card (capabilities, endpoints)
+-- scenario.toml                 [EXISTS]  Scenario configuration
+-- Dockerfile                    [EXISTS]  Container definition (requires upgrade to spec)
+-- .dockerignore                 [EXISTS]  Excludes .git, tests, .env, scripts/
+-- requirements.txt              [EXISTS]  Pinned deps (NO >= ranges)
+-- pyproject.toml                [EXISTS]  pytest: asyncio_mode=auto, pythonpath=["."]
+-- ralph.sh                      [EXISTS]  Die-and-restart loop (NO set -e)
+-- prompt.md                     [EXISTS]  LLM system prompt for SAR generation
+-- README.md                     [EXISTS]  Project overview and quick start
+-- ARCHITECTURE.md               [EXISTS]  Full system architecture document
+-- CHANGELOG.md                  [EXISTS]  Release history (Keep a Changelog format)
+-- .env.example                  [EXISTS]  All env vars with PYTHONHASHSEED=0
+-- .gitignore                    [EXISTS]  Does NOT exclude protos/*_pb2.py
+-- protos/
|   +-- __init__.py               [EXISTS]  Package marker (BUG-02 fix)
|   +-- financial_crime.proto     [EXISTS]  7 message types (FROZEN -- shared with Green)
|   +-- financial_crime_pb2.py    [EXISTS]  Generated bindings (committed, not gitignored)
+-- plans/
|   +-- prd.json                  [EXISTS]  20 tasks with dependencies (A1-D5)
+-- progress.txt                  [EXISTS]  Ralph Wiggum iteration log
+-- scripts/
|   +-- preflight.sh              [EXISTS]  Pre-deployment validation (chmod +x)
+-- src/
|   +-- __init__.py               [EXISTS]  Package marker
|   +-- main.py                   [EXISTS]  Entry: load_dotenv -> RedactingFormatter -> uvicorn
|   +-- config.py                 [EXISTS]  SINGLE SOURCE OF TRUTH for all constants
|   +-- baseline_agent.py         [EXISTS]  Minimal viable baseline investigator
|   +-- ralph_runner.py           [EXISTS]  Per-iteration task executor
|   +-- core/
|       +-- __init__.py           [EXISTS]  Package marker
|       +-- a2a_client.py         [EXISTS]  httpx + circuit breaker + retry + protobuf
|       +-- a2a_server.py         [EXISTS]  FastAPI endpoints (/a2a, /health)
|       +-- decision_loop.py      [EXISTS]  LangGraph state machine (8 nodes)
|       +-- graph_reasoner.py     [EXISTS]  MultiDiGraph + BFS + iterative DFS
|       +-- evidence_synthesizer.py [EXISTS] spaCy NER + regex
|       +-- sar_drafter.py        [EXISTS]  LLM Five Ws + mechanical fallback
|       +-- heuristics/
|           +-- __init__.py       [EXISTS]  Package marker
|           +-- structuring.py    [EXISTS]  Fan-in BFS detection
|           +-- layering.py       [EXISTS]  Chain DFS with decay analysis
+-- tests/
    +-- __init__.py               [EXISTS]  Package marker
    +-- conftest.py               [EXISTS]  16 shared fixtures (ground truth data)
    +-- test_agent_card_schema.py  [EXISTS]
    +-- test_protobuf_schema.py       [EXISTS]
    +-- test_a2a_client.py        [EXISTS]  27 tests
    +-- test_a2a_server.py        [EXISTS]
    +-- test_graph_reasoner_core.py [EXISTS]
    +-- test_structuring_detection.py [EXISTS]
    +-- test_layering_detection.py [EXISTS]
    +-- test_evidence_synthesizer.py [EXISTS]
    +-- test_sar_drafter.py       [EXISTS]
    +-- test_decision_loop.py     [EXISTS]
    +-- integration/
        +-- __init__.py           [EXISTS]
        +-- test_full_pipeline.py [EXISTS]
        +-- test_zero_failure.py  [EXISTS]
```

---

## Configuration

All configuration is centralized in `src/config.py` (SSOT). Runtime overrides via environment variables. See `.env.example`.

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | LLM API key (no default; mechanical fallback without) |

### Determinism (DO NOT CHANGE)

| Variable | Description |
|----------|-------------|
| `PYTHONHASHSEED` | Must be 0 (set in Dockerfile and .env) |

### Agent Network

| Variable | Default | Description |
|----------|---------|-------------|
| `GREEN_AGENT_URL` | `http://localhost:9090` | Upstream agent URL |
| `A2A_SERVER_HOST` | `0.0.0.0` | Bind host |
| `A2A_SERVER_PORT` | `8080` | Bind port |

### Detection Thresholds (USD)

| Variable | Default | Description |
|----------|---------|-------------|
| `STRUCTURING_MIN_USD` | `9000` | Lower structuring band |
| `STRUCTURING_MAX_USD` | `9800` | Upper structuring band |
| `CTR_THRESHOLD_USD` | `10000` | CTR reporting threshold |

### Detection Thresholds (INR)

| Variable | Default | Description |
|----------|---------|-------------|
| `STRUCTURING_MIN_INR` | `900000` | Lower structuring band |
| `STRUCTURING_MAX_INR` | `980000` | Upper structuring band |
| `CTR_THRESHOLD_INR` | `1000000` | CTR reporting threshold |

### Confidence and SAR

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIDENCE_THRESHOLD` | `0.5` | SAR filing gate |
| `SAR_LLM_MODEL` | `gpt-4o-mini` | LLM model |
| `SAR_MAX_RETRY` | `3` | Max SAR validation retries |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LOG_JSON_FORMAT` | `true` | JSON structured logging |

---

## Testing

```bash
# Full suite with coverage
PYTHONHASHSEED=0 pytest -p no:randomly -v \
    --cov=src --cov-report=term-missing --cov-fail-under=80

# Integration tests only
PYTHONHASHSEED=0 pytest tests/integration/ -v

# Zero-failure validation
PYTHONHASHSEED=0 pytest tests/integration/test_zero_failure.py -v

# Determinism check (10 runs, pipeline-level)
PYTHONHASHSEED=0 bash scripts/verify_determinism.sh 10

# Security scan
bandit -r src/ -ll
pip-audit --strict
```

---

## Dual Jurisdiction

### FinCEN SAR (United States)

- **Thresholds:** $9,000--$9,800 structuring band, $10,000 CTR
- **Legal basis:** 31 USC 5324 (Bank Secrecy Act)
- **Timezone:** UTC
- **Identifiers:** SWIFT, IBAN

### FIU-IND STR (India / PMLA)

- **Thresholds:** Rs.9,00,000--Rs.9,80,000 structuring band, Rs.10,00,000 CTR
- **Legal basis:** Prevention of Money Laundering Act, 2002
- **Timezone:** Asia/Kolkata (IST, UTC+5:30)
- **Identifiers:** IFSC, PAN

Jurisdiction is determined from InvestigationRequest and stored in pipeline state. All threshold comparisons, date formatting, amount patterns, and identifier validation are jurisdiction-aware. USD thresholds are never applied to INR amounts or vice versa.

---

## Deployment

### Pre-deployment Validation

```bash
PYTHONHASHSEED=0 bash scripts/preflight.sh
```

### Docker Image Characteristics

- Multi-architecture: supports both amd64 and arm64
- Non-root execution (user: agent, UID 1000)
- TCMalloc preloaded for memory performance
- PYTHONHASHSEED=0 baked in for determinism
- spaCy model pre-downloaded at build time
- HEALTHCHECK built in (30s interval, 5s timeout)

### Production Recommendations

- **Memory limit:** 1GB minimum, 2GB recommended
- **CPU:** 1.0 core minimum
- **Logging:** JSON structured output to stdout (12-factor compatible)
- **Secrets:** Pass OPENAI_API_KEY via Docker secrets or env, never bake into image

### Entrypoint

`ralph.sh` implements the die-and-restart supervision loop:

- **Exit 0:** all tasks complete
- **Exit 1:** error or max iterations reached
- **Exit 124:** timeout killed a hung iteration
- **Exit 130:** SIGINT/SIGTERM -- graceful shutdown

---

## API Endpoints

### POST /a2a

- **Content-Type:** `application/x-protobuf`
- **Body:** InvestigationRequest (protobuf binary)
- **Response:** InvestigationResult (protobuf binary)

### GET /health

- **Response:** `{"status": "healthy", "agent_version": "7.0.0"}`

### GET /docs

- FastAPI auto-generated OpenAPI documentation (Swagger UI)

---

## Determinism Guarantees

Purple Agent produces byte-identical output across consecutive runs. Mechanisms: PYTHONHASHSEED=0, sorted() on all set/dict iteration, LLM seed=42 with temperature=0.0, deterministic idempotency keys. Verify with: `scripts/verify_determinism.sh 10`

---

## License

Proprietary. All rights reserved.
