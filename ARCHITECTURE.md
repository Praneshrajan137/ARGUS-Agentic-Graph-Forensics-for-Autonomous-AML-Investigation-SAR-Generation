# ARGUS -- Architecture

## Overview

ARGUS is a full-stack financial crime detection evaluation platform. It generates synthetic financial transaction networks with injected money laundering patterns, autonomously investigates them, and produces regulatory-compliant Suspicious Activity Reports (SARs) -- all with zero hallucination guarantees.

## System Architecture

### Three-Tier Model

```
+----------------------------------------------------------------------+
|                         SYSTEM ARCHITECTURE                           |
+----------------------------------------------------------------------+
|                                                                       |
|  +-----------------+                          +-----------------+     |
|  |  Tracer Agent   |<------ A2A Protocol ---->|   Forge Agent   |     |
|  |    (Client)     |     HTTP + Protobuf      |    (Server)     |     |
|  |    :8080        |                          |    :9090        |     |
|  +-----------------+                          +-----------------+     |
|         |                                            |                |
|         | Requests:                                  | Provides:      |
|         | - get_transactions                         | - 5,000-node   |
|         | - get_kyc_profile                           |   scale-free   |
|         | - get_evidence                              |   graphs       |
|         | - get_account_connections                   | - Crime inject |
|         | - investigation_assessment                  | - Ground truth |
|         |                                            | - Evidence     |
|  +--------------------------------------------------------------+    |
|  |                   UNIFIED APP (:8000)                         |    |
|  |  FastAPI backend integrates Forge + React 19 frontend         |    |
|  |  - D3.js canvas graph visualization                           |    |
|  |  - Investigation pipeline UI                                  |    |
|  |  - SAR viewer, assessment, benchmark                          |    |
|  +--------------------------------------------------------------+    |
+----------------------------------------------------------------------+
```

### Component Overview

```
+----------------------------------------------------------------------+
|                           FORGE AGENT                                 |
+----------------------------------------------------------------------+
|                                                                       |
|  +--------------+    +--------------+    +--------------+             |
|  |   Graph      |--->|    Crime     |--->|   Evidence   |             |
|  |  Generator   |    |   Injector   |    |  Generator   |             |
|  +--------------+    +--------------+    +--------------+             |
|         |                   |                   |                     |
|         v                   v                   v                     |
|  +--------------+    +--------------+    +--------------+             |
|  |  NetworkX    |    | Structuring  |    | SAR Narratives|            |
|  |  Faker/SDV   |    |  Layering    |    | Bank Emails   |            |
|  |  5,000 nodes |    |  Difficulty  |    | Conflicting   |            |
|  +--------------+    +--------------+    +--------------+             |
|                             |                                        |
|                             v                                        |
|                      +--------------+                                |
|                      |     A2A      |                                |
|                      |  Interface   |                                |
|                      |  HTTP/Proto  |                                |
|                      +--------------+                                |
+----------------------------------------------------------------------+
```

## Core Components

### 1. Graph Generator (`src/core/graph_generator.py`)

**Purpose**: Generate scale-free financial transaction networks.

**Technology**: NetworkX (Barabasi-Albert model) + Faker + SDV

**Key Parameters**:
- `n_nodes`: 5,000 (configurable via `GRAPH_SIZE` env var)
- `alpha`: 0.41 (new node -> existing node probability)
- `beta`: 0.54 (edge between existing nodes probability)
- `gamma`: 0.05 (existing node -> new node probability)

**Data Generation**:
- **SDV-Correlated** (preferred): Gaussian Copula synthesizer correlates amounts with risk scores, international transfers with higher amounts
- **Random Fallback**: Uniform random when SDV unavailable

**Locale Support**: Faker with 10+ locales (en_US, en_GB, en_IN, de_DE, fr_FR, ja_JP, zh_CN, etc.). Each node picks a country, then uses that locale's Faker for SWIFT/IBAN codes matching the jurisdiction.

### 2. Crime Injector (`src/core/crime_injector.py`)

**Purpose**: Surgically inject money laundering patterns into legitimate graphs.

**Supported Patterns**:

| Pattern | Description | Key Metrics |
|---------|-------------|-------------|
| Structuring | Fan-in smurfing | 20 sources, 1 mule, $9,000-$9,800 each (USD) |
| Layering | Chain with decay | 2-5% decay per hop, no cycles, configurable chain length |

**Difficulty Levels** (1-10):

| Level | Structuring | Layering |
|-------|------------|----------|
| 1-3 (Trivial) | 4hr window, $9,500-$9,700 | 3 hops, 4-6% decay, 15min intervals |
| 4-6 (Medium) | 48hr window, $9,000-$9,800 | 5-7 hops, 2-5% decay, 30min intervals |
| 7-8 (Hard) | 1-week spread + decoys | 8-10 hops, varied decay, 1-4hr intervals |
| 9-10 (Expert) | 3-month spread, mixed with legit | 15-20 hops, 1-2% decay, 12-48hr intervals |

### 3. Evidence Generator (`src/core/evidence_generator.py`)

**Purpose**: Generate realistic evidence artifacts for investigation challenges.

**Artifacts**:
- **SAR Narratives**: FinCEN format (USD, UTC) and FIU-IND STR format (INR, IST)
- **Internal Bank Emails**: 3 per structuring crime, with suspicious observations
- **Conflicting Evidence**: Amount discrepancies for hallucination resistance testing

### 4. A2A Interface (`src/core/a2a_interface.py`)

**Purpose**: Expose data via Agent-to-Agent protocol for Tracer Agent integration.

**Endpoints**:
- `POST /a2a/tools/get_transactions` -- Transaction history
- `POST /a2a/tools/get_kyc_profile` -- KYC profile lookup
- `POST /a2a/tools/get_evidence` -- Evidence document search
- `POST /a2a/tools/get_account_connections` -- Network connections
- `POST /a2a/investigation_assessment` -- Investigation scoring
- `GET /health` -- Health check
- `GET /agent.json` -- Agent manifest for discovery

**Serialization**:
- JSON (human-readable)
- Protobuf (80% size reduction, 33x faster)

### 5. Tracer Agent (`tracer_agent/`)

See [`tracer_agent/ARCHITECTURE.md`](tracer_agent/ARCHITECTURE.md) for the full 28-rule architecture document.

**Key Components**:
- **Decision Loop** (`decision_loop.py`): 8-node LangGraph state machine
- **Structuring Detection** (`heuristics/structuring.py`): Fan-in BFS with currency-grouped thresholds
- **Layering Detection** (`heuristics/layering.py`): Iterative DFS with bounded depth and decay analysis
- **Evidence Synthesizer** (`evidence_synthesizer.py`): Dual spaCy NER + regex extraction
- **SAR Drafter** (`sar_drafter.py`): GPT-4.1 Five Ws narrative + mechanical fallback
- **A2A Client** (`a2a_client.py`): httpx with circuit breaker, retry, exponential backoff

### 6. Unified App (`argus-app/`)

**Purpose**: Full-stack application combining Forge backend + React 19 frontend.

**Backend** (`argus-app/backend/`):
- FastAPI server on port 8000
- 17+ REST endpoints under `/api/*`
- Lifespan hook generates graph on startup
- Integrates graph generation, crime injection, investigation, and assessment

**Frontend** (`argus-app/frontend/`):
- React 19 with Vite 8 bundler
- 9 pages: Dashboard, Graph Explorer, Investigation, SAR Viewer, Evidence, Assessment, Benchmark, Vision, Settings
- D3.js canvas-based graph visualization (handles 5,000+ nodes)
- TailwindCSS design system ("Forensic Elegance" v6.0)
- Framer Motion animations, Recharts for analytics
- Custom useQuery hook with in-memory caching and stale-while-revalidate

## Data Flow

```
+-----------+     +------------------+     +-----------------+
|  Config   |---->| Graph Generator  |---->| Baseline Graph  |
| (seed,    |     | (NetworkX, SDV,  |     | (5,000 nodes,   |
|  size,    |     |  Faker)          |     |  scale-free)    |
|  diff.)   |     +------------------+     +--------+--------+
+-----------+                                       |
                                                    v
                                       +---------------------+
                                       |   Crime Injector    |
                                       | (Structuring +      |
                                       |  Layering, diff 1-10)|
                                       +----------+----------+
                                                   |
                        +-------------+------------+------------+
                        v             v                         v
                +--------------+ +-----------+ +----------------+
                |Poisoned Graph| |Ground Truth| |   Evidence     |
                |(NetworkX     | |(InjectedCrime| |  Artifacts   |
                | MultiDiGraph)| | dataclass)   | |(SARs, emails)|
                +------+-------+ +-------------+ +------+-------+
                       |                                 |
                       +----------------+----------------+
                                        |
                                        v
                               +-----------------+
                               |  A2A Interface   |
                               |  (FastAPI :9090) |
                               +--------+--------+
                                        |
                           +------------+------------+
                           v                         v
                   +----------------+       +-----------------+
                   | Tracer Agent   |       | Unified App     |
                   | (LangGraph,   |       | (FastAPI :8000 + |
                   |  :8080)       |       |  React frontend) |
                   +----------------+       +-----------------+
```

## Data Models

### Node Schema (Entity)

```python
{
    "entity_id": int,              # Unique identifier
    "entity_type": str,            # "person" | "company" | "bank"
    "name": str,                   # Faker-generated (locale-specific)
    "address": str,                # Full address (locale-matched)
    "swift": str,                  # SWIFT/BIC code
    "iban": str,                   # IBAN (jurisdiction-specific)
    "country": str,                # ISO 3166-1 alpha-2
    "risk_score": float,           # 0.0 - 1.0
    "verification_status": str,    # "verified" | "pending" | "failed"
}
```

### Edge Schema (Transaction)

```python
{
    "transaction_id": str,         # Seeded hex: txn_{hash}
    "source": int,                 # Source node ID
    "target": int,                 # Target node ID
    "amount": Decimal,             # Transaction amount (NEVER float)
    "currency": str,               # ISO 4217 (default: USD)
    "timestamp": datetime,         # Transaction timestamp
    "transaction_type": str,       # "wire" | "ach" | "cash" | "internal"
    "label": str,                  # "legitimate" | "structuring" | "layering"
    "risk_score": float,           # 0.0 - 1.0
    "is_international": bool,      # Cross-border flag
    "memo": str,                   # Description
}
```

### Ground Truth Ledger

```python
@dataclass
class InjectedCrime:
    crime_type: str                # "structuring" | "layering"
    nodes_involved: List[int]      # All nodes in the crime pattern
    edges_involved: List[Tuple[int, int]]  # All edges in the pattern
    metadata: dict                 # evidence_artifacts, amounts, timing, difficulty
```

### Assessment Result

```python
@dataclass
class AssessmentResult:
    entity_metrics: EntityMetrics          # Precision/Recall/F1 (Decimal)
    hallucination_check: HallucinationCheck  # Zero-tolerance validation
    five_ws: FiveWsValidation              # SAR structural completeness
    typology: TypologyScore                # Crime type detection accuracy
    efficiency: EfficiencyScore            # Tool call efficiency tier
    overall_score: Decimal                 # Weighted composite [0.0, 1.0]
    jurisdiction: str                      # "FinCEN" | "FIU-IND"
    currency: str                          # "USD" | "INR"
```

## Technology Stack

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Graph Ops | NetworkX | 3.4.2 | Scale-free topology, power-law distribution |
| Entity Gen | Faker | 40.1.2 | 10+ locale-aware generation |
| Correlations | SDV | 1.15.0 | Gaussian Copulas for statistical realism |
| API Framework | FastAPI | 0.128.0 | Async, automatic OpenAPI docs |
| Serialization | Protobuf | 6.33.4 | 80% size reduction, 33x faster |
| Agent Framework | LangGraph | 0.2.60 | State machine execution |
| NLP | spaCy | 3.8.4 | Named entity recognition |
| LLM | GPT-4.1 (OpenAI) | 1.59.9 | SAR narrative generation |
| Frontend | React | 19.2.4 | Modern UI with hooks |
| Visualization | D3.js | 7.9.0 | Canvas-based force-directed graphs |
| Bundler | Vite | 8.0.0 | Fast HMR, ES module bundling |
| CSS | TailwindCSS | 3.4.19 | Utility-first styling |
| Testing | pytest | 9.0.2 | TDD with 65%+ (Forge) / 90%+ (Tracer) coverage |

## Dual Jurisdiction Support

| Aspect | FinCEN SAR (US) | FIU-IND STR (India) |
|--------|----------------|---------------------|
| Currency | USD | INR |
| CTR Threshold | $10,000 | Rs.10,00,000 |
| Structuring Band | $9,000-$9,800 | Rs.9,00,000-Rs.9,80,000 |
| Legal Basis | Bank Secrecy Act (31 USC 5324) | PMLA 2002 |
| Timezone | UTC | Asia/Kolkata (IST, UTC+5:30) |
| Identifiers | SWIFT, IBAN | IFSC, PAN |

## Directory Structure

```
.
+-- main.py                          Forge Agent CLI entry point
+-- Dockerfile                       Forge Agent multi-stage container (TCMalloc)
+-- docker-compose.yml               Multi-agent orchestration
+-- render.yaml                      Render.com deployment config
+-- requirements.txt                 Forge Agent dependencies (pinned)
+-- src/
|   +-- config.py                    SSOT for all constants (Decimal thresholds)
|   +-- core/
|   |   +-- graph_generator.py       Scale-free graph (Barabasi-Albert)
|   |   +-- crime_injector.py        Structuring + Layering injection
|   |   +-- evidence_generator.py    SAR narratives, emails, conflicting docs
|   |   +-- a2a_interface.py         FastAPI + Protobuf A2A server
|   |   +-- sdv_models.py            Gaussian Copula synthesizer
|   |   +-- result_types.py          Assessment dataclasses (Decimal)
|   +-- utils/
|       +-- validators.py            Input validation
+-- tracer_agent/                    Tracer Agent (see tracer_agent/ARCHITECTURE.md)
+-- argus-app/                       Unified full-stack application
|   +-- backend/                     FastAPI (17+ endpoints, port 8000)
|   +-- frontend/                    React 19 + D3.js + TailwindCSS
+-- protos/                          Shared Protobuf definitions (FROZEN)
+-- tests/                           Forge Agent test suite (pytest)
+-- scripts/                         Utility scripts
+-- .github/workflows/               CI/CD (test.yml, publish-dockerhub.yml)
```

## Design Principles

### 1. Algorithm Over AI

All mathematical operations use deterministic Python scripts, not AI/LLM:
- Graph generation: NetworkX seeded algorithms
- Crime injection: Deterministic pattern insertion
- Detection heuristics: BFS + DFS traversal
- Assessment scoring: Rule-based (no LLM variance)

LLM is used ONLY for SAR narrative drafting, with mechanical fallback.

### 2. Decimal Everywhere

All monetary amounts use `Decimal` type, never `float`:
- Prevents floating-point rounding errors in threshold comparisons
- `json.dumps(default=str)` at serialization boundary
- Protobuf uses `double` wire type with `Decimal(str(...))` at Python boundary

### 3. Zero Hallucination Tolerance

Every entity, amount, and timestamp cited in SAR narratives is validated against the source graph. Hallucinations are treated as regulatory violations and build failures.

### 4. Test-Driven Development

- Forge Agent: 65%+ coverage (enforced in CI)
- Tracer Agent: 90%+ coverage (enforced via `pytest-cov --cov-fail-under=90`)
- 19 test files, 3,300+ lines of tests
- 16 fixtures with mathematically verified ground truth

## Security Considerations

### Data Security

1. **Synthetic Data Only**: No real PII or financial data
2. **Labeled Output**: All crime patterns are explicitly labeled
3. **Deterministic**: Same seed produces identical output
4. **Credential Redaction**: API keys and secrets redacted from logs

### API Security

1. **Input Validation**: All parameters validated via Pydantic
2. **CORS**: Configurable allowed origins
3. **Non-Root Containers**: UID 1000 in all Docker images
4. **No PII Exposure**: Purely random synthetic data
5. **Prompt Injection Defense**: Evidence sanitization strips injection keywords

## Performance

| Metric | Target | Configuration |
|--------|--------|---------------|
| Graph Generation (5k nodes) | <10s | TCMalloc preloaded |
| Crime Injection | <1s | Surgical subgraph insertion |
| Memory Usage | <2GB | TCMalloc + 5k node scale |
| API Response (Forge) | <100ms | FastAPI async |
| Frontend Render (5k nodes) | 60fps | D3.js canvas (not SVG) |

## Future Extensions

1. **Additional Crime Types**: Round-tripping, trade-based ML, fan-out structuring
2. **Multi-Graph Support**: Multiple interconnected networks
3. **OpenTelemetry**: Tracing spans for pipeline observability
4. **Hypothesis Testing**: Property-based testing
5. **Multi-Model LLM Failover**: GPT-4.1 -> Claude -> mechanical
