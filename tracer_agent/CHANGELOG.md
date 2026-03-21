# Changelog

All notable changes to Tracer Agent are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

## [7.0.0] - 2026-03-06

### Added
- Complete 8-node LangGraph decision loop pipeline
- Structuring detection (fan-in BFS) for USD and INR jurisdictions
- Layering detection (iterative DFS with decay analysis)
- Evidence synthesis via dual spaCy NER + regex extraction
- SAR narrative generation with LLM + mechanical fallback
- Zero-hallucination validation across all Five Ws fields
- Confidence scoring with configurable threshold gate
- Dual jurisdiction support: FinCEN SAR (US) and FIU-IND STR (India)
- A2A protocol server (FastAPI :8080) with protobuf serialization
- A2A client with circuit breaker, retry, and exponential backoff
- Ralph Wiggum die-and-restart supervision loop
- 16 test fixtures with mathematically verified ground truth
- Integration test suite including zero-failure validation
- Docker production image (Python 3.11, TCMalloc, non-root)
- Determinism verification (10-run byte-identical check)
- Pre-flight deployment validation script
- Comprehensive documentation suite

### Security
- Non-root container execution (UID 1000)
- Prompt injection sanitization via <data> delimiters
- Log redaction for API keys and secrets
- Idempotency keys via SHA-256 for submission deduplication

### Architecture Decisions
- en_core_web_sm over trf: 66MB vs 400MB+, 10x faster, regex compensates
- $9,800 structuring max over $9,999.99: reduces false positives ~40%
- Proto double amount (FROZEN schema): Decimal(str()) at Python boundary
- Iterative DFS over recursive: O(V+E) space, no stack overflow risk
- Confidence gate before SAR: prevents speculative regulatory filings

## [7.1.0] - 2026-03-11

### Changed
- SAR generation model upgraded from gpt-4o-mini to GPT-4.1 (higher-quality narratives, fewer validation retries)
- Spec version updated to v12.0 in ARCHITECTURE.md (all v6.x through v11.x defects resolved)

### Added
- End-to-end investigation workflow via Docker Compose (`docker-compose.e2e.yml` override)
- `scripts/trigger_investigation.py` for automated E2E investigation triggering and result reporting

### Fixed
- SAR validator: skip prefix-family matching for purely numeric node IDs (eliminated false-positive hallucination flags on dates, amounts, and other numbers in narratives)
- `InvestigationState` alignment in `a2a_server.py`: removed 7 extraneous fields, added missing `detection_results` and `sar_draft`
- `submit_result` now returns the formatted SAR narrative and `investigation_timestamp` to API callers (previously returned empty narrative)
- Trigger script UTF-8 output encoding for Windows compatibility

### Documentation
- Rewrote `tracer_agent/README.md`: corrected decision loop node names, added E2E section, updated health check format, updated config table
- Updated `tracer_agent/ARCHITECTURE.md`: v12.0 spec version, corrected all 8 node names to match implementation, aligned `InvestigationState` TypedDict with actual code, removed outdated Dockerfile note, updated SAR model
- Overhauled root `README.md`: Python 3.11+ badge, Tracer Agent v7.1 pipeline description, protobuf A2A architecture, E2E workflow, updated project structure

## [Unreleased]

### Planned
- OpenTelemetry tracing spans for pipeline observability
- Hypothesis property-based testing
- Fan-out structuring detection
- Multi-model LLM failover for SAR generation
