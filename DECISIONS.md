# Architectural Decision Records (ADR)

This document records the key architectural decisions made for the ARGUS project.

---

## ADR-001: Use NetworkX for Graph Generation

**Status**: Accepted

**Context**:
We need to generate scale-free graphs representing financial transaction networks. Options considered:
- NetworkX (Python)
- igraph (Python/C)
- Neo4j (Graph Database)
- Custom implementation

**Decision**:
Use NetworkX with `scale_free_graph()` function.

**Rationale**:
1. Native Python integration
2. Built-in scale-free graph algorithms (Barabasi-Albert)
3. Extensive documentation and community
4. Sufficient performance for 5k-50k node scale
5. Easy serialization to JSON/Protobuf
6. MultiDiGraph supports parallel edges (multiple transactions between same entities)

**Consequences**:
- (+) Fast development
- (+) Extensive graph algorithms available (BFS, DFS, centrality)
- (-) May need optimization for >100k nodes

---

## ADR-002: Faker + SDV for Synthetic Data

**Status**: Accepted

**Context**:
Need realistic entity data (names, accounts, companies) with statistical correlations.

**Decision**:
Use Faker for entity generation, SDV (Gaussian Copulas) for correlations.

**Rationale**:
1. Faker provides locale-aware realistic data (10+ locales)
2. SDV maintains statistical properties (amount-risk correlation)
3. Both support reproducible seeding
4. Industry-standard tools

**Consequences**:
- (+) Realistic output with locale-matched SWIFT/IBAN/IFSC codes
- (+) Reproducible with seeds
- (-) SDV is a heavy dependency (optional, with random fallback)

---

## ADR-003: Algorithm Over AI Principle

**Status**: Accepted

**Context**:
Some operations could use AI/LLM, but need determinism for testing and reproducibility.

**Decision**:
All mathematical operations (graph generation, crime injection, detection heuristics, assessment scoring) MUST use deterministic Python scripts. LLM is used ONLY for SAR narrative drafting, with mechanical fallback.

**Rationale**:
1. Reproducibility with same seed
2. Testable with exact assertions
3. No API costs for generation or detection
4. Faster execution
5. No hallucination risk in core logic

**Consequences**:
- (+) 100% reproducible output
- (+) Fast and free execution
- (-) More explicit coding required for SAR narrative quality

---

## ADR-004: Protobuf for Serialization

**Status**: Accepted

**Context**:
Need to serialize graph data efficiently for A2A protocol.

**Decision**:
Support both JSON (human-readable) and Protobuf (performance).

**Rationale**:
1. Protobuf: 80% size reduction vs JSON
2. Protobuf: 33x faster deserialization
3. JSON: Easy debugging and manual inspection
4. Both formats for different use cases

**Consequences**:
- (+) Optimal for different scenarios
- (-) Maintain two serialization paths
- (-) Protobuf schema is FROZEN (shared between agents)

---

## ADR-005: FastAPI for A2A Interface

**Status**: Accepted

**Context**:
Need HTTP/JSON-RPC interface for Agent2Agent protocol.

**Decision**:
Use FastAPI with Pydantic models.

**Rationale**:
1. Automatic OpenAPI documentation
2. Built-in validation with Pydantic
3. Async support for performance
4. Modern Python best practices

**Consequences**:
- (+) Self-documenting API
- (+) Type safety via Pydantic
- (-) Requires async understanding

---

## ADR-006: TDD Methodology

**Status**: Accepted

**Context**:
Need high confidence in crime injection accuracy.

**Decision**:
Test-Driven Development with enforced coverage thresholds: 65% (Forge), 90% (Tracer).

**Rationale**:
1. Crime patterns must be exactly correct
2. Prevents regression
3. Documents expected behavior
4. Enables fearless refactoring

**Consequences**:
- (+) High reliability
- (+) Living documentation
- (-) Slower initial development

---

## ADR-007: Ralph Wiggum Die-and-Restart Pattern

**Status**: Accepted

**Context**:
Long-running agent sessions suffer from context rot. Need a mechanism for fresh context each iteration.

**Decision**:
Use `ralph.sh` bash wrapper for die-and-restart cycles. The Tracer Agent runs atomic tasks, writes state to disk, then exits for a fresh restart.

**Rationale**:
1. Zero context rot: fresh context each iteration
2. Persistent progress via state files
3. Atomic tasks: one focused task per cycle
4. Auditable: full history in progress log
5. Resilient: timeouts and max iterations prevent runaway processes

**Consequences**:
- (+) Platform independent via Docker
- (+) Clean separation between iterations
- (-) Overhead of process restart per task

---

## ADR-008: Configuration as Single Source of Truth

**Status**: Accepted

**Context**:
Configuration values (thresholds, ports, model parameters) were scattered across multiple files.

**Decision**:
Centralize all configuration in `config.py` (one per agent), with environment variable overrides via `os.getenv()`.

**Rationale**:
1. Single file to audit for threshold values
2. Environment variables for deployment flexibility
3. Decimal defaults for monetary values (never float)
4. `.env.example` documents all available overrides

**Consequences**:
- (+) Single source of truth
- (+) Easy deployment configuration
- (-) Must remember to add new vars to .env.example

---

## ADR-009: TCMalloc for Memory Performance

**Status**: Accepted

**Context**:
Python's default memory allocator suffers from fragmentation with large graph operations. At 5,000+ nodes with attribute-rich entities, memory usage was higher than necessary.

**Decision**:
Preload Google's TCMalloc (`libtcmalloc_minimal.so.4`) via `LD_PRELOAD` in Docker containers.

**Rationale**:
1. Thread-caching reduces allocation overhead
2. Better memory fragmentation handling for NetworkX graph operations
3. No code changes required (library preload)
4. Industry-standard (used by Google, Meta)

**Consequences**:
- (+) Reduced memory usage under graph workloads
- (+) Zero application code changes
- (-) Linux-only (Windows/macOS development unaffected)
- (-) Adds ~2MB to Docker image

---

## ADR-010: Dual Jurisdiction (FinCEN + FIU-IND)

**Status**: Accepted

**Context**:
Initial implementation only supported USD/FinCEN. Need to demonstrate multi-jurisdiction capability for realistic AML workflows.

**Decision**:
Support both FinCEN SAR (USD, UTC, BSA) and FIU-IND STR (INR, IST, PMLA) throughout the entire pipeline -- from crime injection thresholds through SAR narrative formatting.

**Rationale**:
1. Demonstrates real-world AML complexity
2. Tests jurisdiction-aware threshold logic (USD thresholds must never apply to INR)
3. Different identifier systems (SWIFT/IBAN vs IFSC/PAN)
4. Different timezone formatting (UTC vs IST)
5. Different legal references (BSA vs PMLA)

**Consequences**:
- (+) Realistic multi-jurisdiction testing
- (+) Proves currency-aware detection logic
- (-) More complex threshold management
- (-) SAR templates must handle both formats

---

## ADR-011: Unified Full-Stack App (React + FastAPI)

**Status**: Accepted

**Context**:
The two-agent architecture (Forge + Tracer) required Docker Compose and command-line interaction. Needed an accessible UI for demonstration and evaluation.

**Decision**:
Build a unified application (`argus-app/`) combining a FastAPI backend (integrating Forge Agent logic) with a React 19 frontend, served on a single port (:8000).

**Rationale**:
1. Single deployment target (Render.com)
2. Interactive graph visualization (D3.js canvas for 5,000+ nodes)
3. Investigation pipeline UI with 8-step progress tracker
4. SAR viewer with dual-jurisdiction rendering
5. Assessment scoring with rubric breakdown
6. No Docker Compose required for demonstration

**Consequences**:
- (+) Accessible via web browser
- (+) Single-port deployment
- (+) Interactive graph exploration
- (-) Additional codebase to maintain (React frontend)
- (-) Frontend build step required

---

## ADR-012: Canvas-based D3.js for Graph Visualization

**Status**: Accepted

**Context**:
Need to render financial transaction networks with 5,000+ nodes interactively. SVG-based rendering creates one DOM element per node/edge, causing severe performance degradation at scale.

**Decision**:
Use D3.js with HTML Canvas rendering instead of SVG.

**Rationale**:
1. Canvas renders to a single bitmap -- O(1) DOM elements regardless of graph size
2. Quadtree-based hover detection for interactive node selection
3. Force-directed simulation for organic layout
4. 60fps at 5,000 nodes (SVG drops to <10fps)
5. Theme-aware colors via CSS custom properties

**Consequences**:
- (+) Smooth performance at 5,000+ nodes
- (+) Pan/zoom with D3 zoom behavior
- (-) No CSS styling per-element (colors managed in JS)
- (-) Accessibility: canvas lacks native screen reader support

---

## ADR-013: Decimal Arithmetic for Currency Precision

**Status**: Accepted

**Context**:
IEEE 754 floating-point cannot represent $9,800.00 exactly. Threshold comparisons like `amount < 9800.0` can fail due to rounding (e.g., `9799.999999999998 < 9800.0` passes but `9800.000000000001 < 9800.0` fails). This is unacceptable for regulatory threshold logic.

**Decision**:
All monetary values throughout the system use Python's `Decimal` type. `float` is never used for amounts.

**Rationale**:
1. Exact representation of currency values
2. Correct threshold comparisons for CTR ($10,000) and structuring bands ($9,000-$9,800)
3. Protobuf uses `double` wire type, with `Decimal(str(value))` conversion at Python boundary
4. JSON serialization uses `json.dumps(default=str)`
5. Prevents class of bugs that are invisible in testing but catastrophic in production

**Consequences**:
- (+) Mathematically correct threshold logic
- (+) No floating-point comparison bugs
- (-) Slightly more verbose code (`Decimal("9800")` vs `9800.0`)
- (-) Must convert at all serialization boundaries

---

## Template for Future ADRs

```markdown
## ADR-XXX: [Title]

**Status**: Proposed | Accepted | Deprecated | Superseded

**Context**:
[What is the issue we're addressing?]

**Decision**:
[What did we decide?]

**Rationale**:
[Why did we make this decision?]

**Consequences**:
[What are the results? Both positive and negative.]
```
