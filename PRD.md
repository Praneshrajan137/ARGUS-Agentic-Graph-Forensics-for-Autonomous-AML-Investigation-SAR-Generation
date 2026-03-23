# Product Requirements Document
## ARGUS Forge Agent

**Version**: 8.0
**Status**: Complete
**Last Updated**: 2026-03-23

---

## 1. Executive Summary

### 1.1 Project Overview

**Project Name**: ARGUS Forge Agent
**Codename**: ARGUS
**Mission**: Zero-Failure Synthetic Financial Crime Simulator

The ARGUS Forge Agent is a financial crime simulator that generates mathematically consistent synthetic economies with surgically injected money laundering typologies. This system produces labeled training data for the Tracer Agent (investigation/detection AI) without exposing real financial data or compromising privacy.

### 1.2 Objectives

1. Generate realistic scale-free financial transaction networks (5,000 nodes, Barabasi-Albert topology)
2. Inject precise money laundering patterns (Structuring, Layering) with 10 difficulty levels
3. Generate evidence artifacts (SAR narratives, bank emails, conflicting documents)
4. Produce labeled datasets for ML training and AML system testing
5. Support dual jurisdiction: FinCEN SAR (USD) and FIU-IND STR (INR/PMLA)
6. Expose data via Agent2Agent (A2A) protocol for seamless integration

### 1.3 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Graph Generation Time | <10 seconds | Achieved |
| Memory Usage | <2GB (TCMalloc) | Achieved |
| Test Coverage | 65%+ (Forge), 90%+ (Tracer) | Achieved |
| Crime Label Accuracy | 100% | Achieved |
| Zero Failures | 50+ iterations | Achieved |
| Deterministic Output | Byte-identical across 10 runs | Achieved |

---

## 2. Problem Statement

### 2.1 Current Challenges

**AML Analyst Bottleneck**: Financial crime investigators spend 70-80% of their time on data gathering and preparation, leaving only 20-30% for actual analysis and investigation.

**Training Data Scarcity**:
- Real financial crime data is sensitive and protected
- Labeled datasets are extremely rare
- Synthetic data lacks realistic patterns and correlations

**ML Model Limitations**:
- Models trained on unrealistic data perform poorly in production
- Lack of ground truth labels prevents proper evaluation
- Imbalanced datasets (crime is rare) cause detection issues

### 2.2 Impact

Without high-quality synthetic training data:
- AML systems generate excessive false positives (90%+ false positive rates)
- Analysts waste time investigating legitimate transactions
- Real crimes slip through due to alert fatigue
- Regulatory compliance suffers

---

## 3. Solution Overview

### 3.1 Architecture

```
+----------------------------------------------------------------------+
|                       ARGUS FORGE AGENT                               |
+----------------------------------------------------------------------+
|                                                                       |
|   +-------------+     +-------------+     +-------------+            |
|   |   GENERATE  |---->|   INJECT    |---->|  GENERATE   |            |
|   |   Graph     |     |   Crime     |     |  Evidence   |            |
|   +-------------+     +-------------+     +-------------+            |
|         |                   |                   |                     |
|   NetworkX +          Structuring +       SAR narratives +           |
|   Faker + SDV         Layering            Bank emails +              |
|   5,000 nodes         Difficulty 1-10     Conflicting docs           |
|                                                                       |
|                     +-------------+                                  |
|                     |   EXPOSE    |                                  |
|                     |   via A2A   |                                  |
|                     +-------------+                                  |
|                           |                                          |
|                     HTTP/JSON-RPC +                                  |
|                     Protobuf                                         |
+----------------------------------------------------------------------+
```

### 3.2 Core Components

1. **Graph Generator**: Creates scale-free financial networks using NetworkX (Barabasi-Albert model)
2. **Entity Generator**: Populates nodes with locale-aware data using Faker (10+ locales)
3. **Correlation Engine**: Maintains statistical relationships using SDV Gaussian Copulas
4. **Crime Injector**: Surgically injects Structuring and Layering patterns (difficulty 1-10)
5. **Evidence Generator**: Creates SAR narratives, bank emails, and conflicting documents
6. **A2A Interface**: Exposes data via Agent2Agent protocol (FastAPI + Protobuf)

### 3.3 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Graph Operations | NetworkX | 3.4.2 | Scale-free graph generation |
| Entity Generation | Faker | 40.1.2 | Locale-aware realistic names, accounts |
| Correlations | SDV | 1.15.0 | Statistical relationship modeling |
| API Framework | FastAPI | 0.128.0 | HTTP/JSON-RPC interface |
| Serialization | Protobuf | 6.33.4 | 80% size reduction, 33x faster |
| Data Validation | Pydantic | 2.12.5 | Type-safe request/response models |
| Testing | pytest | 9.0.2 | TDD with 65%+ coverage |

---

## 4. User Stories

### US-001: Generate Scale-Free Graph

**As** the system
**I need to** generate a scale-free graph with 5,000 nodes
**So that** I have a realistic baseline financial network

#### Acceptance Criteria

- [x] Graph has configurable node count (default 5,000)
- [x] Degree distribution follows power-law (scale-free property verified)
- [x] Graph generation completes in less than 10 seconds
- [x] Peak memory usage remains below 2GB (TCMalloc optimization)
- [x] Same seed produces identical graph (reproducibility)
- [x] Entity attributes are locale-aware (10+ locales with SWIFT/IBAN matching)

#### Technical Specification

```python
# NetworkX Scale-Free Graph Configuration
nx.scale_free_graph(
    n=5000,
    alpha=0.41,  # P(new node connected to existing node)
    beta=0.54,   # P(edge between two existing nodes)
    gamma=0.05,  # P(new node connected from existing node)
    seed=42      # Reproducibility
)

# Parameter Constraint: alpha + beta + gamma = 1.0
# 0.41 + 0.54 + 0.05 = 1.00
```

---

### US-002: Inject Structuring Crime

**As** the system
**I need to** inject a structuring (smurfing) crime pattern
**So that** the graph contains labeled money laundering activity

#### Acceptance Criteria

- [x] Creates configurable source nodes (default 20 smurfs)
- [x] All transfers target a single mule node
- [x] All transaction amounts between $9,000 and $9,800 (USD) / Rs.9,00,000-Rs.9,80,000 (INR)
- [x] Time window varies by difficulty (4hr to 3 months)
- [x] All crime edges are labeled as "structuring"
- [x] No amount equals or exceeds CTR threshold ($10,000 USD / Rs.10,00,000 INR)
- [x] Evidence artifacts generated (SAR narratives, bank emails)

---

### US-003: Inject Layering Crime

**As** the system
**I need to** inject a layering crime pattern with decay
**So that** the graph contains complex money trail obfuscation

#### Acceptance Criteria

- [x] Creates a directed chain of transfers (no branches)
- [x] Chain contains NO cycles (validated via `validate_no_cycles`)
- [x] Each hop has 2-5% decay in amount (Decimal arithmetic)
- [x] Amounts monotonically decrease along chain
- [x] All crime edges are labeled as "layering"
- [x] Chain length varies by difficulty (3-20 hops)
- [x] Evidence artifacts generated with conflicting amounts

---

### US-004: Expose via A2A Protocol

**As** the system
**I need to** expose data via Agent2Agent protocol
**So that** the Tracer Agent can consume the synthetic data

#### Acceptance Criteria

- [x] `agent.json` manifest file is created and accessible
- [x] Health endpoint (`/health`) returns status
- [x] Tool endpoints serve transactions, KYC profiles, evidence, connections
- [x] Investigation assessment endpoint scores Tracer Agent results
- [x] Data available in JSON and Protobuf formats
- [x] X-Participant-ID header tracking for efficiency scoring

---

### US-005: Evidence Generation

**As** the system
**I need to** generate realistic evidence artifacts
**So that** the Tracer Agent's NLU and hallucination resistance can be tested

#### Acceptance Criteria

- [x] SAR narratives in FinCEN format (USD, UTC, BSA references)
- [x] SAR narratives in FIU-IND format (INR, IST, PMLA references)
- [x] Internal bank emails with suspicious transaction observations
- [x] Conflicting evidence with amount discrepancies
- [x] Evidence tied to injected crime ground truth

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Requirement | Target | Achieved |
|-------------|--------|----------|
| Graph generation (5k nodes) | <10 seconds | Yes |
| Crime injection | <1 second | Yes |
| API response time | <500ms | Yes |
| Memory (TCMalloc) | <2GB | Yes |

### 5.2 Scalability

| Scale | Nodes | Expected Time | Memory |
|-------|-------|---------------|--------|
| Default | 5,000 | <10s | <1GB |
| Medium | 10,000 | <30s | <2GB |
| Large | 50,000 | <5min | <4GB |

### 5.3 Reliability

- **Zero failures** across 50+ consecutive iterations
- **100% reproducibility** with same seed
- **Mechanical SAR fallback** when LLM unavailable
- **Comprehensive error handling** with meaningful messages

### 5.4 Maintainability

- **Test coverage**: 65%+ (Forge), 90%+ (Tracer), enforced in CI
- **Type hints**: All functions fully typed, mypy strict mode
- **Code style**: Black + Ruff enforced
- **Decimal precision**: All monetary values use Decimal, never float

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Context rot during long sessions | High | High | Ralph Wiggum die-and-restart loop |
| Data quality issues | Medium | High | SDV statistical validation, deterministic seeds |
| Performance degradation at scale | Medium | Medium | TCMalloc, Protobuf serialization |
| Unrealistic graph topology | Low | High | Validated scale-free distribution |
| LLM unavailability | Medium | Low | Mechanical SAR fallback (always succeeds) |

---

## 7. Implementation Roadmap

### Phase 1: Foundation
- [x] Project structure
- [x] Configuration (config.py SSOT)
- [x] PRD and Architecture documentation

### Phase 2: Graph Generation
- [x] Scale-free graph generator (NetworkX)
- [x] Faker entity generation (10+ locales)
- [x] SDV correlation modeling
- [x] Scale-free property validation

### Phase 3: Crime Injection
- [x] Structuring injection (fan-in, difficulty 1-10)
- [x] Layering injection (chain with decay, difficulty 1-10)
- [x] Cycle detection and prevention
- [x] Dual jurisdiction thresholds (USD + INR)

### Phase 4: Evidence Generation
- [x] SAR narrative generation (FinCEN + FIU-IND formats)
- [x] Bank email artifacts
- [x] Conflicting evidence for hallucination testing

### Phase 5: A2A Interface
- [x] FastAPI application with tool endpoints
- [x] JSON + Protobuf serialization
- [x] Agent manifest (agent.json)
- [x] Investigation assessment scoring

### Phase 6: Unified App
- [x] FastAPI unified backend (17+ endpoints)
- [x] React 19 frontend with D3.js graph visualization
- [x] Investigation pipeline UI
- [x] SAR viewer, assessment, benchmark pages
- [x] Render.com deployment

### Phase 7: Integration & Validation
- [x] End-to-end integration tests
- [x] Performance benchmarking
- [x] CI/CD pipelines (GitHub Actions)
- [x] Docker multi-stage builds (TCMalloc, non-root)
- [x] Documentation suite

---

## 8. Glossary

| Term | Definition |
|------|------------|
| **A2A Protocol** | Agent2Agent -- communication protocol for AI agents |
| **CTR** | Currency Transaction Report -- required for transactions >= $10,000 (USD) or Rs.10,00,000 (INR) |
| **FinCEN** | Financial Crimes Enforcement Network (US) |
| **FIU-IND** | Financial Intelligence Unit - India |
| **Layering** | Money laundering technique using chain transfers with decay |
| **Mule** | Account used to receive illicit funds |
| **PMLA** | Prevention of Money Laundering Act, 2002 (India) |
| **Scale-Free Graph** | Network where degree distribution follows power law |
| **SDV** | Synthetic Data Vault -- library for generating correlated data |
| **Smurfing** | Synonym for structuring |
| **Structuring** | Breaking large transactions into smaller ones to avoid CTR |
| **TCMalloc** | Thread-Caching Malloc -- Google's memory allocator for performance |

---

## 9. Appendix

### A. References

1. Barabasi-Albert model for scale-free networks
2. FinCEN Bank Secrecy Act requirements
3. Prevention of Money Laundering Act (PMLA), 2002
4. Google A2A Protocol specification
5. SDV Gaussian Copula documentation

### B. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial PRD creation |
| 8.0 | 2026-03-23 | Updated to reflect complete implementation: 5,000 nodes, dual jurisdiction, evidence generation, unified app, all phases complete |
