# The Panopticon Protocol

**A Zero-Failure Synthetic Financial Crime Investigation Platform**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

---

## Abstract

The Panopticon Protocol is a two-agent system for financial crime detection evaluation. A **Green Agent** generates synthetic financial transaction networks with surgically injected money laundering patterns, while a **Purple Agent** autonomously investigates those networks, detects structuring and layering typologies, and generates regulatory-compliant Suspicious Activity Reports (SARs).

The agents communicate via an Agent-to-Agent (A2A) protocol using Protocol Buffers over HTTP, enabling realistic end-to-end AML investigation workflows.

### System at a Glance

| Component | Role | Port | Technology |
|-----------|------|------|------------|
| **Green Agent** | World simulator, data generator, evaluator | `:8000` | NetworkX, SDV, Faker, FastAPI |
| **Purple Agent** | Autonomous forensic investigator | `:8080` | LangGraph, spaCy, GPT-4.1, FastAPI |

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

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- An OpenAI API key (for LLM-based SAR generation; mechanical fallback works without it)

### End-to-End Investigation (Recommended)

Run a complete AML investigation with both agents communicating via A2A:

```bash
# Clone the repository
git clone https://github.com/Praneshrajan137/The-Agentic-Financial-Defense-Swarm-Forensic-AML-Graph-Reasoning-Engine.git
cd The-Agentic-Financial-Defense-Swarm-Forensic-AML-Graph-Reasoning-Engine

# Set your OpenAI API key
export OPENAI_API_KEY=sk-your-key-here

# Start both agents (E2E mode: Purple Agent runs as FastAPI server)
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

# Green Agent starts on :8000, generates data, waits for connections
# Purple Agent starts on :8080, runs the Ralph Wiggum task loop
```

### Local Development

```bash
# Green Agent
pip install -r requirements.txt
python main.py generate --output-dir ./outputs --seed 42 --difficulty 5
python main.py serve --port 8000

# Purple Agent (separate terminal)
cd purple_agent
cp .env.example .env   # Edit: set OPENAI_API_KEY
pip install -r requirements.txt
python -m spacy download en_core_web_sm
PYTHONHASHSEED=0 python -m src.main
```

---

## Architecture

```
+------------------------------------------------------------------+
|                    THE PANOPTICON PROTOCOL                        |
+------------------------------------------------------------------+
|                                                                   |
|  +------------------------+         +---------------------------+ |
|  |     GREEN AGENT        |         |      PURPLE AGENT         | |
|  |    (World Simulator)   | Protobuf|   (Forensic Investigator) | |
|  |                        | <-----> |                           | |
|  |  - Graph Generator     |  A2A    |  - 8-Node LangGraph Loop  | |
|  |  - Crime Injector      |  HTTP   |  - BFS Structuring Det.   | |
|  |  - Evidence Generator  |         |  - DFS Layering Detection  | |
|  |  - Assessment API      |         |  - spaCy NER + Regex      | |
|  |  - SDV Gaussian Copula |         |  - GPT-4.1 SAR Drafter    | |
|  |                        |         |  - Zero-Hallucination Val. | |
|  +------------------------+         +---------------------------+ |
|        :8000                               :8080                  |
+------------------------------------------------------------------+

A2A Protocol Flow:
  Purple  --[InvestigationRequest (protobuf)]--> Green
  Green   --[GraphFragment (protobuf)]--------> Purple
  Purple  --[InvestigationResult (protobuf)]--> Green
```

### Purple Agent Decision Loop (8 Nodes)

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

### Green Agent Components

| Module | Purpose | Technology |
|--------|---------|------------|
| `graph_generator.py` | Scale-free financial networks | NetworkX, Faker, SDV |
| `crime_injector.py` | Structuring and layering patterns | Difficulty-based obfuscation |
| `evidence_generator.py` | SARs, emails, conflicting docs | NLU challenge generation |
| `a2a_interface.py` | HTTP API for Purple Agents | FastAPI, Protobuf |

### Purple Agent Components

| Module | Purpose | Technology |
|--------|---------|------------|
| `decision_loop.py` | 8-node LangGraph state machine | LangGraph |
| `graph_reasoner.py` | MultiDiGraph traversal | NetworkX |
| `heuristics/structuring.py` | Fan-in BFS detection | BFS, Decimal arithmetic |
| `heuristics/layering.py` | Chain DFS with decay analysis | Iterative DFS |
| `evidence_synthesizer.py` | Text-ledger cross-reference | spaCy, regex |
| `sar_drafter.py` | Five Ws narrative generation | GPT-4.1, mechanical fallback |
| `a2a_client.py` | Green Agent communication | httpx, circuit breaker |
| `a2a_server.py` | Investigation endpoint | FastAPI |

---

## API Reference

### Green Agent (`:8000`)

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

### Purple Agent (`:8080`)

| Endpoint | Method | Content-Type | Description |
|----------|--------|-------------|-------------|
| `/health` | GET | JSON | Health check |
| `/agent.json` | GET | JSON | Agent capability manifest |
| `/a2a` | POST | `application/x-protobuf` or `application/json` | Submit investigation request |
| `/docs` | GET | HTML | OpenAPI documentation (Swagger UI) |

**Purple Agent `/a2a` request (JSON):**

```json
{
  "case_id": "CASE-001",
  "subject_id": "42",
  "hop_depth": 3,
  "jurisdiction": "fincen"
}
```

**Purple Agent `/a2a` response fields:** `case_id`, `sar_narrative`, `typology_detected`, `involved_entities`, `confidence_score`, `jurisdiction`, `investigation_timestamp`, `status`.

---

## Project Structure

```
.
+-- main.py                          Green Agent CLI entry point
+-- Dockerfile                       Green Agent container
+-- docker-compose.yml               Multi-agent orchestration
+-- docker-compose.e2e.yml           E2E override (Purple as FastAPI server)
+-- requirements.txt                 Green Agent dependencies
+-- scenario.toml                    Scenario configuration
+-- src/                             Green Agent source
|   +-- core/
|   |   +-- graph_generator.py       NetworkX + SDV network generation
|   |   +-- crime_injector.py        Structuring and layering injection
|   |   +-- evidence_generator.py    SAR/email/memo generation
|   |   +-- a2a_interface.py         FastAPI + Protobuf A2A server
|   |   +-- sdv_models.py            Gaussian Copula models
|   +-- utils/
|       +-- validators.py            Input validation
+-- purple_agent/                    Purple Agent (autonomous investigator)
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
|   +-- README.md                    Purple Agent documentation
|   +-- ARCHITECTURE.md              Full architecture document
+-- scripts/
|   +-- trigger_investigation.py     E2E investigation trigger
|   +-- run_benchmark.py             Reproducibility benchmark
+-- outputs/                         Generated data (gitignored)
+-- tests/                           Green Agent test suite
```

---

## Evaluation Rubric

Purple Agents are scored by the Green Agent on five dimensions:

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
# Green Agent tests
pytest tests/ -v

# Purple Agent tests
cd purple_agent
PYTHONHASHSEED=0 pytest -p no:randomly -v --cov=src --cov-report=term-missing
```

---

## Documentation

| Document | Location | Description |
|----------|----------|-------------|
| Purple Agent README | [`purple_agent/README.md`](purple_agent/README.md) | Quick start, configuration, API |
| Purple Agent Architecture | [`purple_agent/ARCHITECTURE.md`](purple_agent/ARCHITECTURE.md) | Full system design, 28 rules, state machine |
| Purple Agent Changelog | [`purple_agent/CHANGELOG.md`](purple_agent/CHANGELOG.md) | Release history |
| Scenario Config | [`scenario.toml`](scenario.toml) | Green Agent scenario parameters |

---

## Citation

```bibtex
@software{panopticon_protocol,
  title = {The Panopticon Protocol: A Synthetic Financial Crime Investigation Platform},
  year = {2026},
  url = {https://github.com/Praneshrajan137/The-Agentic-Financial-Defense-Swarm-Forensic-AML-Graph-Reasoning-Engine}
}
```

---

**Version:** 7.1.0 | **Status:** Production Ready
