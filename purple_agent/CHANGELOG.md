# Changelog

All notable changes to Purple Agent are documented in this file.
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

## [Unreleased]

### Planned
- OpenTelemetry tracing spans for pipeline observability
- Hypothesis property-based testing
- Fan-out structuring detection
- Multi-model LLM failover for SAR generation
