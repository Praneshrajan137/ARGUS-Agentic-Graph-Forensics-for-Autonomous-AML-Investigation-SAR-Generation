# ARGUS: Agentic Graph Forensics for Autonomous AML Investigation & SAR Generation

**A Zero-Failure Synthetic Financial Crime Investigation Platform**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)

---

## Abstract

ARGUS is a full-stack financial crime detection evaluation platform. A **Forge Agent** generates synthetic financial transaction networks (5,000 nodes, Barabasi-Albert scale-free topology) with surgically injected money laundering patterns, while a **Tracer Agent** autonomously investigates those networks, detects structuring and layering typologies, and generates regulatory-compliant Suspicious Activity Reports (SARs). A **Unified App** combines both agents with a React-based interactive frontend for graph visualization, investigation workflows, and assessment scoring.

The agents communicate via an Agent-to-Agent (A2A) protocol using Protocol Buffers over HTTP, enabling realistic end-to-end AML investigation workflows.

### System at a Glance

| Component | Role | Port | Technology |
|-----------|------|------|------------|
| **Forge Agent** | World simulator, data generator, evaluator | `:9090` | NetworkX, SDV, Faker, FastAPI |
| **Tracer Agent** | Autonomous forensic investigator | `:8080` | LangGraph, spaCy, GPT-4.1, FastAPI |
| **Unified App** | Full-stack UI + integrated backend | `:8000` | FastAPI, React 19, D3.js, Vite |

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Dual Jurisdiction** | FinCEN SAR (USD) and FIU-IND STR (INR/PMLA) support |
| **Zero Hallucination** | Every entity, amount, and timestamp in SAR narratives validated against source graph |
| **Deterministic Output** | PYTHONHASHSEED=0, sorted iteration, LLM seed=42, temperature=0.0 |
| **Statistical Realism** | SDV Gaussian Copulas for correlated transaction data |
| **Locale-Aligned Entities** | SWIFT/IBAN/IFSC/PAN codes match country jurisdictions |
| **Dynamic Difficulty** | 10 levels from trivial to expert |
| **Mechanical Fallback** | SAR generation always succeeds, even without LLM access |
| **Interactive Visualization** | D3.js canvas-based graph explorer for 5,000+ node networks |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend development)
- An OpenAI API key (for LLM-based SAR generation; mechanical fallback works without it)

### Unified App (Recommended)

The unified app combines Forge + Tracer + React UI on a single port:

```bash
# Clone the repository
git clone https://github.com/Praneshrajan137/ARGUS-Agentic-Graph-Forensics-for-Autonomous-AML-Investigation---SAR-Generation.git
cd ARGUS-Agentic-Graph-Forensics-for-Autonomous-AML-Investigation---SAR-Generation

# Deploy via Render (uses render.yaml)
# Or run locally:
cd argus-app
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m backend.main
# App available at http://localhost:8000
```

### End-to-End Investigation (Two-Agent Mode)

Run a complete AML investigation with both agents communicating via A2A:

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=sk-your-key-here

# Start both agents (E2E mode: Tracer Agent runs as FastAPI server)
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d

# Wait for both agents to become healthy
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml ps

# Trigger investigations against known criminal nodes
python scripts/trigger_investigation.py

# View logs
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml logs -f

# Tear down
docker-compose -f docker-compose.yml -f docker-compose.e2e.yml down
```

The trigger script sends investigation requests for known criminal nodes and reports:
- Detected typology (STRUCTURING, LAYERING, BOTH, NONE)
- Generated SAR narrative (Five Ws structure)
- Involved entities and entity recall vs ground truth
- Confidence score

### Docker Compose (Standard Mode)

```bash
# Build and run both agents
docker-compose up --build

# Forge Agent starts on :9090, generates data, waits for connections
# Tracer Agent starts on :8080, runs the Ralph Wiggum task loop
```

### Local Development

```bash
# Forge Agent
pip install -r requirements.txt
python main.py generate --output-dir ./outputs --seed 42 --difficulty 5
python main.py serve --port 9090

# Tracer Agent (separate terminal)
cd tracer_agent
cp .env.example .env   # Edit: set OPENAI_API_KEY
pip install -r requirements.txt
python -m spacy download en_core_web_sm
PYTHONHASHSEED=0 python -m src.main
```

---

## Architecture

```
+------------------------------------------------------------------+
|                            ARGUS                                  |
|   Agentic Graph Forensics for Autonomous AML Investigation       |
+------------------------------------------------------------------+
|                                                                   |
|  +------------------------+         +---------------------------+ |
|  |     FORGE AGENT        |         |      TRACER AGENT         | |
|  |    (World Simulator)   | Protobuf|   (Forensic Investigator) | |
|  |                        | <-----> |                           | |
|  |  - Graph Generator     |  A2A    |  - 8-Node LangGraph Loop  | |
|  |  - Crime Injector      |  HTTP   |  - BFS Structuring Det.   | |
|  |  - Evidence Generator  |         |  - DFS Layering Detection  | |
|  |  - Assessment API      |         |  - spaCy NER + Regex      | |
|  |  - SDV Gaussian Copula |         |  - GPT-4.1 SAR Drafter    | |
|  |                        |         |  - Zero-Hallucination Val. | |
|  +------------------------+         +---------------------------+ |
|        :9090                               :8080                  |
|                                                                   |
|  +--------------------------------------------------------------+ |
|  |                     UNIFIED APP (:8000)                       | |
|  |  FastAPI backend + React 19 frontend                          | |
|  |  - D3.js canvas graph visualization (5,000+ nodes)            | |
|  |  - Investigation pipeline UI with 8-step tracker              | |
|  |  - Dual-jurisdiction SAR viewer (FinCEN / FIU-IND)            | |
|  |  - Assessment scoring with rubric breakdown                   | |
|  |  - Evidence browser with keyword search                       | |
|  +--------------------------------------------------------------+ |
+------------------------------------------------------------------+

A2A Protocol Flow:
  Tracer  --[InvestigationRequest (protobuf)]--> Forge
  Forge   --[GraphFragment (protobuf)]---------> Tracer
  Tracer  --[InvestigationResult (protobuf)]--> Forge
```

### Tracer Agent Decision Loop (8 Nodes)

```
receive -> analyze -> detect -> synthesize -> compute_confidence
                                                  |          |
                                           >= 0.5 |          | < 0.5
                                                  v          v
                                               draft      submit
                                                  |     (LOW_CONFIDENCE)
                                                  v
                                              validate
                                               |    |
                                          pass |    | fail (retry <= 3)
                                               v    v
                                            submit  draft -> mechanical SAR -> submit
```

### Forge Agent Components

| Module | Purpose | Technology |
|--------|---------|------------|
| `graph_generator.py` | Scale-free financial networks (5,000 nodes) | NetworkX, Faker, SDV |
| `crime_injector.py` | Structuring and layering patterns | Difficulty-based obfuscation |
| `evidence_generator.py` | SARs, emails, conflicting docs | NLU challenge generation |
| `a2a_interface.py` | HTTP API for Tracer Agents | FastAPI, Protobuf |

### Tracer Agent Components

| Module | Purpose | Technology |
|--------|---------|------------|
| `decision_loop.py` | 8-node LangGraph state machine | LangGraph |
| `graph_reasoner.py` | MultiDiGraph traversal | NetworkX |
| `heuristics/structuring.py` | Fan-in BFS detection | BFS, Decimal arithmetic |
| `heuristics/layering.py` | Chain DFS with decay analysis | Iterative DFS |
| `evidence_synthesizer.py` | Text-ledger cross-reference | spaCy, regex |
| `sar_drafter.py` | Five Ws narrative generation | GPT-4.1, mechanical fallback |
| `a2a_client.py` | Forge Agent communication | httpx, circuit breaker |
| `a2a_server.py` | Investigation endpoint | FastAPI |

### Unified App Components

| Module | Purpose | Technology |
|--------|---------|------------|
| `backend/main.py` | Unified FastAPI server (17+ endpoints) | FastAPI, Pydantic |
| `frontend/src/components/graph/` | Interactive network visualization | D3.js (canvas), React 19 |
| `frontend/src/pages/` | 9 application pages | React Router v7 |
| `frontend/src/api/client.js` | API client with caching | Custom useQuery hook |

---

## API Reference

### Forge Agent (`:9090`)

All endpoints use JSON. Include `X-Participant-ID` header for efficiency tracking.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/agent.json` | GET | Agent manifest |
| `/a2a/tools/get_transactions` | POST | Get transactions for an account |
| `/a2a/tools/get_kyc_profile` | POST | Get KYC profile for an account |
| `/a2a/tools/get_evidence` | POST | Search evidence documents |
| `/a2a/tools/get_account_connections` | POST | Get account connection graph |
| `/a2a/investigation_assessment` | POST | Submit investigation for scoring |

### Tracer Agent (`:8080`)

| Endpoint | Method | Content-Type | Description |
|----------|--------|-------------|-------------|
| `/health` | GET | JSON | Health check |
| `/agent.json` | GET | JSON | Agent capability manifest |
| `/a2a` | POST | `application/x-protobuf` or `application/json` | Submit investigation request |
| `/docs` | GET | HTML | OpenAPI documentation (Swagger UI) |

**Tracer Agent `/a2a` request (JSON):**

```json
{
  "case_id": "CASE-001",
  "subject_id": "42",
  "hop_depth": 3,
  "jurisdiction": "fincen"
}
```

**Tracer Agent `/a2a` response fields:** `case_id`, `sar_narrative`, `typology_detected`, `involved_entities`, `confidence_score`, `jurisdiction`, `investigation_timestamp`, `status`.

### Unified App (`:8000`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health status |
| `/api/generate` | POST | Generate new graph |
| `/api/graph/stats` | GET | Graph statistics |
| `/api/graph/visualization` | GET | Graph data for D3.js rendering |
| `/api/nodes/{id}` | GET | Node details |
| `/api/transactions` | GET | Transaction list |
| `/api/evidence` | GET | Evidence document search |
| `/api/investigation/submit` | POST | Start investigation |
| `/api/assessment/results` | GET | View assessment results |

---

## Project Structure

```
.
+-- main.py                          Forge Agent CLI entry point
+-- Dockerfile                       Forge Agent container
+-- docker-compose.yml               Multi-agent orchestration
+-- docker-compose.e2e.yml           E2E override (Tracer as FastAPI server)
+-- requirements.txt                 Forge Agent dependencies
+-- render.yaml                      Render.com deployment config
+-- scenario.toml                    Scenario configuration
+-- src/                             Forge Agent source
|   +-- core/
|   |   +-- graph_generator.py       NetworkX + SDV network generation
|   |   +-- crime_injector.py        Structuring and layering injection
|   |   +-- evidence_generator.py    SAR/email/memo generation
|   |   +-- a2a_interface.py         FastAPI + Protobuf A2A server
|   |   +-- sdv_models.py            Gaussian Copula models
|   +-- utils/
|       +-- validators.py            Input validation
+-- tracer_agent/                    Tracer Agent (autonomous investigator)
|   +-- Dockerfile                   Python 3.11, TCMalloc, non-root
|   +-- requirements.txt             Pinned dependencies
|   +-- src/
|   |   +-- main.py                  FastAPI server entry point
|   |   +-- config.py                Single source of truth (all constants)
|   |   +-- core/
|   |       +-- decision_loop.py     LangGraph 8-node state machine
|   |       +-- graph_reasoner.py    MultiDiGraph + BFS + iterative DFS
|   |       +-- evidence_synthesizer.py  spaCy NER + regex
|   |       +-- sar_drafter.py       GPT-4.1 Five Ws + mechanical fallback
|   |       +-- a2a_client.py        httpx + circuit breaker + retry
|   |       +-- a2a_server.py        FastAPI (/a2a, /health)
|   |       +-- heuristics/
|   |           +-- structuring.py   Fan-in BFS detection
|   |           +-- layering.py      Chain DFS with decay analysis
|   +-- tests/                       16 fixtures, integration tests
|   +-- protos/                      Protobuf schema (FROZEN, shared)
|   +-- README.md                    Tracer Agent documentation
|   +-- ARCHITECTURE.md              Full architecture document
+-- argus-app/                       Unified full-stack application
|   +-- Dockerfile                   Unified app container
|   +-- backend/
|   |   +-- main.py                  FastAPI server (17+ endpoints)
|   |   +-- config.py                Unified app configuration
|   |   +-- routes/                  API route modules
|   |   +-- services/                Business logic (forge_service, etc.)
|   |   +-- models/                  Pydantic schemas + state management
|   +-- frontend/
|       +-- src/
|       |   +-- pages/               9 pages (Dashboard, GraphExplorer, etc.)
|       |   +-- components/          Shared + domain-specific components
|       |   +-- api/client.js        API client with caching
|       |   +-- hooks/               useQuery, useHotkeys
|       |   +-- index.css            Design system ("Forensic Elegance" v6.0)
|       +-- vite.config.js           Vite bundler config
|       +-- tailwind.config.js       TailwindCSS theme
+-- scripts/
|   +-- trigger_investigation.py     E2E investigation trigger
|   +-- run_benchmark.py             Reproducibility benchmark
+-- protos/                          Shared Protobuf definitions
+-- outputs/                         Generated data (gitignored)
+-- tests/                           Forge Agent test suite
```

---

## Evaluation Rubric

Tracer Agents are scored by the Forge Agent on five dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Pattern Identification** | 28% | Precision/Recall/F1 for crime detection |
| **Evidence Quality** | 20% | Use of transaction data and supporting evidence |
| **Narrative Clarity** | 16% | Quality and structure of investigation report |
| **Completeness** | 16% | Coverage of ground truth indicators |
| **Efficiency** | 20% | Tool calls used (fewer = better) |

---

## Difficulty Levels

| Level | Time Spread | Amount Variance | Detection Rate (Baseline) |
|-------|-------------|-----------------|---------------------------|
| 1-3 | 4 hours | $9,500-$9,700 | 95%+ |
| 4-6 | 48 hours | $9,000-$9,800 | 60-70% |
| 7-8 | 1 week | $7,500-$9,800 + decoys | 30-40% |
| 9-10 | 3 months | Minimal patterns, long gaps | <20% |

---

## Reproducibility

Both agents are designed for deterministic, reproducible evaluation:

- **Seeded random generation**: All random operations use configurable seed
- **Deterministic crime injection**: Same seed = identical crime patterns
- **LLM determinism**: `SAR_LLM_SEED=42`, `SAR_LLM_TEMPERATURE=0.0`
- **Hash stability**: `PYTHONHASHSEED=0`, `sorted()` on all set/dict iteration
- **Fixed assessment logic**: Rule-based scoring (no LLM variance in evaluation)

```bash
# Run reproducibility benchmark
python scripts/run_benchmark.py --seed 42 --difficulty 5 --runs 3 --output results.json
```

---

## Resource Requirements

| Resource | Requirement |
|----------|-------------|
| RAM | 4GB minimum, 8GB recommended |
| Disk | 500MB for dependencies + outputs |
| CPU | Any modern CPU |
| Network | Required for Docker pulls and OpenAI API |

---

## Testing

```bash
# Forge Agent tests
pytest tests/ -v

# Tracer Agent tests
cd tracer_agent
PYTHONHASHSEED=0 pytest -p no:randomly -v --cov=src --cov-report=term-missing

# Frontend tests
cd argus-app/frontend
npm run test
```

---

## Documentation

| Document | Location | Description |
|----------|----------|-------------|
| Tracer Agent README | [`tracer_agent/README.md`](tracer_agent/README.md) | Quick start, configuration, API |
| Tracer Agent Architecture | [`tracer_agent/ARCHITECTURE.md`](tracer_agent/ARCHITECTURE.md) | Full system design, 28 rules, state machine |
| Tracer Agent Changelog | [`tracer_agent/CHANGELOG.md`](tracer_agent/CHANGELOG.md) | Release history |
| Unified App README | [`argus-app/README.md`](argus-app/README.md) | Full-stack app setup and API |
| Frontend README | [`argus-app/frontend/README.md`](argus-app/frontend/README.md) | React frontend architecture |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) | System-wide architecture document |
| Decisions | [`DECISIONS.md`](DECISIONS.md) | Architectural Decision Records |
| PRD | [`PRD.md`](PRD.md) | Product Requirements Document |
| Scenario Config | [`scenario.toml`](scenario.toml) | Forge Agent scenario parameters |

---

## Citation

```bibtex
@software{argus_aml,
  title = {ARGUS: Agentic Graph Forensics for Autonomous AML Investigation & SAR Generation},
  author = {Pranesh Rajan},
  year = {2026},
  url = {https://github.com/Praneshrajan137/ARGUS-Agentic-Graph-Forensics-for-Autonomous-AML-Investigation---SAR-Generation}
}
```

---

**Version:** 8.0.0 | **Status:** Production Ready
