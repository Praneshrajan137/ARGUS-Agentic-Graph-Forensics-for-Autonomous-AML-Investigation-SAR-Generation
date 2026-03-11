## Purple Agent -- The Panopticon Protocol

Autonomous forensic financial crime investigation system with dual-jurisdiction SAR generation, zero-hallucination guarantees, and deterministic output.

**Agent Version:** 7.1.0
**Python:** 3.11+ required
**SAR Model:** GPT-4.1

---

## Overview

Purple Agent is a production-grade autonomous financial crime investigator. It operates as a node in an Agent-to-Agent (A2A) network, communicating via Protocol Buffers over HTTP. The system:

- Receives investigation requests via A2A protocol (FastAPI :8080)
- Fetches financial transaction graphs from the Green Agent via Protobuf
- Constructs NetworkX MultiDiGraph representations preserving all parallel edges and transaction metadata
- Detects Structuring patterns (fan-in below Currency Transaction Report thresholds) using BFS traversal with currency-grouped threshold comparisons
- Detects Layering patterns (decay chain analysis) using iterative DFS with bounded depth and path explosion circuit breakers
- Synthesizes unstructured text evidence using dual spaCy NER + regex extraction, cross-referencing against ledger ground truth
- Computes confidence scores with a transparent formula gated on configurable thresholds before SAR generation
- Generates FinCEN SAR (US/USD) and FIU-IND STR (India/INR) narratives using the Five Ws framework with GPT-4.1 and mechanical fallback guarantees
- Validates every entity, amount, and timestamp cited in SAR narratives against the source graph -- zero hallucination tolerance
- Submits results to the Green Agent with SHA-256 idempotency keys for deduplication
- Produces deterministic output across consecutive runs (PYTHONHASHSEED=0, LLM seed=42)

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

### End-to-End Investigation (Docker Compose)

Run a full AML investigation with both Green and Purple agents:

```bash
# From the project root (not purple_agent/)
# Set your OpenAI API key in the environment
export OPENAI_API_KEY=sk-your-key-here

# Start both agents
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d

# Watch logs
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml logs -f

# Trigger investigations (from host, once both agents are healthy)
python scripts/trigger_investigation.py

# Tear down
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml down
```

The E2E override (`docker-compose.e2e.yml`) starts the Purple Agent as a FastAPI server on port 8080 instead of running the Ralph Wiggum task loop. The trigger script sends investigation requests for known criminal nodes and reports SAR narratives, entity recall, and confidence scores.

### Health Check

```bash
curl -s http://localhost:8080/health | python -m json.tool
# Expected:
# {
#     "status": "healthy",
#     "service": "purple_agent",
#     "version": "7.1.0"
# }
```

---

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete system design.

### LangGraph Decision Loop (8 nodes)

```
InvestigationRequest (protobuf / JSON)
        |
        v
+--- LangGraph Decision Loop (8 nodes) -------------------+
|                                                          |
|  receive -> analyze -> detect -> synthesize              |
|                                       |                  |
|                                       v                  |
|                              compute_confidence          |
|                               |             |            |
|                       >= 0.5  |             | < 0.5      |
|                               v             v            |
|                            draft         submit          |
|                              |        (LOW_CONFIDENCE)   |
|                              v                           |
|                          validate                        |
|                           |       |                      |
|                    pass --+       +-- fail (retry <= 3)  |
|                      |                    |              |
|                      v                    v              |
|                   submit          draft (retry)          |
|                                   |                      |
|                                   +-> mechanical SAR     |
|                                       -> submit          |
+----------------------------------------------------------+
        |
        v
InvestigationResult (protobuf / JSON) -> Green Agent
```

Node responsibilities:

| Node | Implementation | Responsibility |
|------|---------------|----------------|
| `receive` | `receive_case()` | Initialize investigation, set status to IN_PROGRESS |
| `analyze` | `analyze_graph()` | Fetch GraphFragment from Green Agent via A2A Client |
| `detect` | `detect_typology()` | Run structuring (BFS) and layering (DFS) on all nodes |
| `synthesize` | `synthesize_evidence()` | Cross-reference text evidence with ledger via spaCy NER |
| `compute_confidence` | `compute_confidence()` | Score computation; gate on CONFIDENCE_THRESHOLD |
| `draft` | `draft_sar()` | GPT-4.1 Five Ws narrative with prompt injection sanitization |
| `validate` | `validate_sar()` | Verify every cited entity/amount/timestamp exists in graph |
| `submit` | `submit_result()` | A2A submission with SHA-256 idempotency key |

Conditional edges:

- `compute_confidence` -> `submit` (when score < CONFIDENCE_THRESHOLD)
- `validate` -> `draft` (retry, max SAR_MAX_RETRY times)
- `validate` -> `submit` (passed OR retries exhausted -> mechanical SAR)

---

## Project Structure

```
purple_agent/
+-- agent.json                     A2A agent card (capabilities, endpoints)
+-- scenario.toml                  Scenario configuration
+-- Dockerfile                     Multi-stage: Python 3.11, TCMalloc, non-root
+-- .dockerignore                  Excludes .git, tests, .env, scripts/
+-- requirements.txt               Pinned deps (NO >= ranges)
+-- requirements-prod.txt          Production subset (no test deps)
+-- pyproject.toml                 pytest: asyncio_mode=auto, pythonpath=["."]
+-- ralph.sh                       Die-and-restart loop (NO set -e)
+-- prompt.md                      LLM system prompt for SAR generation
+-- README.md                      This file
+-- ARCHITECTURE.md                Full system architecture document
+-- CHANGELOG.md                   Release history (Keep a Changelog format)
+-- .env.example                   All env vars with PYTHONHASHSEED=0
+-- .gitignore                     Does NOT exclude protos/*_pb2.py
+-- protos/
|   +-- __init__.py                Package marker
|   +-- financial_crime.proto      7 message types (FROZEN -- shared with Green)
|   +-- financial_crime_pb2.py     Generated bindings (committed)
+-- plans/
|   +-- prd.json                   20 tasks with dependencies (A1-D5)
+-- scripts/
|   +-- preflight.sh               Pre-deployment validation
+-- src/
|   +-- __init__.py
|   +-- main.py                    Entry: load_dotenv -> RedactingFormatter -> uvicorn
|   +-- config.py                  SINGLE SOURCE OF TRUTH for all constants
|   +-- baseline_agent.py          Minimal viable baseline investigator
|   +-- ralph_runner.py            Per-iteration task executor
|   +-- core/
|       +-- __init__.py
|       +-- a2a_client.py          httpx + circuit breaker + retry + protobuf
|       +-- a2a_server.py          FastAPI endpoints (/a2a, /health)
|       +-- decision_loop.py       LangGraph state machine (8 nodes)
|       +-- graph_reasoner.py      MultiDiGraph + BFS + iterative DFS
|       +-- evidence_synthesizer.py spaCy NER + regex
|       +-- sar_drafter.py         LLM Five Ws + mechanical fallback
|       +-- heuristics/
|           +-- __init__.py
|           +-- structuring.py     Fan-in BFS detection
|           +-- layering.py        Chain DFS with decay analysis
+-- tests/
    +-- conftest.py                16 shared fixtures (ground truth data)
    +-- test_agent_card_schema.py
    +-- test_protobuf_schema.py
    +-- test_a2a_client.py         27 tests
    +-- test_a2a_server.py
    +-- test_graph_reasoner_core.py
    +-- test_structuring_detection.py
    +-- test_layering_detection.py
    +-- test_evidence_synthesizer.py
    +-- test_sar_drafter.py
    +-- test_decision_loop.py
    +-- integration/
        +-- test_full_pipeline.py
        +-- test_zero_failure.py
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
| `SAR_LLM_MODEL` | `gpt-4.1` | LLM model for narrative generation |
| `SAR_LLM_TEMPERATURE` | `0.0` | Greedy decoding |
| `SAR_LLM_SEED` | `42` | Deterministic seed |
| `SAR_MAX_RETRY` | `3` | Max SAR validation retries |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |

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

### Docker Image Characteristics

- Multi-stage build: builder + runtime
- ARM64 and amd64 compatible (Python 3.11-slim base)
- Non-root execution (user: agent, UID 1000)
- TCMalloc preloaded for memory performance
- PYTHONHASHSEED=0 baked in for determinism
- spaCy en_core_web_sm model pre-downloaded at build time
- HEALTHCHECK built in (30s interval, 5s timeout)

### Production Recommendations

- **Memory limit:** 1GB minimum, 2GB recommended
- **CPU:** 1.0 core minimum
- **Logging:** Structured output to stdout (12-factor compatible)
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

- **Content-Type:** `application/x-protobuf` or `application/json`
- **Body:** InvestigationRequest (protobuf binary or JSON)
- **Response:** InvestigationResult (protobuf binary or JSON, based on Accept header)

JSON request example:

```json
{
  "case_id": "CASE-001",
  "subject_id": "42",
  "hop_depth": 3,
  "jurisdiction": "fincen"
}
```

JSON response fields: `case_id`, `sar_narrative`, `typology_detected`, `involved_entities`, `confidence_score`, `jurisdiction`, `investigation_timestamp`, `status`.

### GET /health

- **Response:** `{"status": "healthy", "service": "purple_agent", "version": "7.1.0"}`

### GET /agent.json

- Agent capability manifest (A2A discovery)

### GET /docs

- FastAPI auto-generated OpenAPI documentation (Swagger UI)

---

## Determinism Guarantees

Purple Agent produces deterministic output across consecutive runs. Mechanisms: PYTHONHASHSEED=0, sorted() on all set/dict iteration, LLM seed=42 with temperature=0.0, deterministic idempotency keys.

---

## License

Proprietary. All rights reserved.
