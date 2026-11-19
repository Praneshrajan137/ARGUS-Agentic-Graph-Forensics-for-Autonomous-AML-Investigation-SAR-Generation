"""
Test: LangGraph Decision Loop -- State Machine
PRD Reference: Task A7
Updated for v9.0 API (uppercase statuses, renamed functions/fields).
"""
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tracer_agent.src.core.decision_loop import (
    InvestigationState,
    receive_case,
    detect_typology,
    synthesize_evidence,
    compute_confidence,
    should_generate_sar,
    draft_sar,
    validate_sar,
    should_retry,
    submit_result,
    build_workflow,
)


def _make_initial_state(**overrides: Any) -> InvestigationState:
    """Build a minimal valid initial state with optional overrides.

    v9.0: Uses the minimal operational subset of Architecture S5.
    """
    base: InvestigationState = {
        "case_id": "CASE-TEST-001",
        "subject_id": "suspect_001",
        "jurisdiction": "fincen",
        "hop_depth": 3,
        "graph_fragment": None,
        "detected_typology": None,
        "detection_results": None,
        "evidence_package": None,
        "sar_narrative": None,
        "sar_draft": None,
        "validation_result": None,
        "involved_entities": [],
        "confidence_score": 0.0,
        "investigation_start_timestamp": 0,
        "investigation_timestamp": 0,
        "status": "pending",
        "retry_count": 0,
        "error_message": None,
    }
    return {**base, **overrides}


# ═══════════════════════════════════════════════════════════════════
# Receive Case Node (v9.0: was "ingest")
# ═══════════════════════════════════════════════════════════════════

class TestReceiveCase:
    def test_receive_case_sets_in_progress(self):
        """receive_case should set status to IN_PROGRESS."""
        state = _make_initial_state()
        result = receive_case(state)
        assert result["status"] == "IN_PROGRESS", (
            f"Expected IN_PROGRESS, got {result['status']}"
        )

    def test_receive_case_sets_start_timestamp(self):
        """receive_case should set investigation_start_timestamp."""
        state = _make_initial_state()
        result = receive_case(state)
        assert result["investigation_start_timestamp"] != 0, (
            "Start timestamp should be set"
        )

    def test_receive_case_preserves_graph_fragment(self):
        """receive_case does not validate graph — that's analyze_graph's job."""
        state = _make_initial_state(graph_fragment=None)
        result = receive_case(state)
        # receive_case always succeeds (v9.0: graph validation is in analyze_graph)
        assert result["status"] == "IN_PROGRESS"


# ═══════════════════════════════════════════════════════════════════
# Detection Node (v9.0: detect_typology replaces detect_structuring + detect_layering)
# ═══════════════════════════════════════════════════════════════════

class TestDetection:
    def test_detect_typology_passes_through_on_failure(self):
        state = _make_initial_state(status="FAILED")
        result = detect_typology(state)
        assert result["status"] == "FAILED", "Should preserve FAILED status"

    def test_detect_typology_handles_none_graph(self):
        """With None graph, detect_typology should handle gracefully."""
        state = _make_initial_state(status="IN_PROGRESS", graph_fragment=None)
        result = detect_typology(state)
        # With null/empty graph, detection finds nothing
        assert result.get("detected_typology") == "NONE"


# ═══════════════════════════════════════════════════════════════════
# Evidence Synthesis
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceSynthesis:
    def test_synthesize_evidence_returns_package_on_no_typology(self):
        """When typology is NONE, evidence synthesis returns NOT_APPLICABLE."""
        state = _make_initial_state(status="IN_PROGRESS", detected_typology="NONE")
        result = synthesize_evidence(state)
        pkg = result["evidence_package"]
        assert pkg is not None, "evidence_package should not be None"
        assert pkg["verdict"] == "NOT_APPLICABLE"

    def test_synthesize_evidence_skips_on_failure(self):
        state = _make_initial_state(status="FAILED")
        result = synthesize_evidence(state)
        assert result["status"] == "FAILED", "Should preserve FAILED status"


# ═══════════════════════════════════════════════════════════════════
# Confidence Scoring (uses state_builder from conftest v12.0)
# ═══════════════════════════════════════════════════════════════════

class TestConfidenceScoring:
    """Test compute_confidence with v9.0 formula:
    base = 0.3 (one typology) | 0.6 (BOTH)
    + 0.2 if verdict in CORROBORATING_VERDICTS
    + 0.2 if discrepancies non-empty
    Score = min(1.0, base + evidence_boost + discrepancy_boost)
    """

    def test_confidence_high(self):
        """STRUCTURING(0.3) + corroboration(0.2) + discrepancy(0.2) = 0.7"""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="STRUCTURING",
            evidence_package={
                "verdict": "MATCH", "checked_count": 1,
                "discrepancies": ["amount mismatch"],
            },
        )
        result = compute_confidence(state)
        assert result["confidence_score"] == 0.7

    def test_confidence_low(self):
        """LAYERING(0.3) with no evidence = 0.3 < threshold -> suppressed."""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="LAYERING",
            evidence_package={"verdict": "INSUFFICIENT_DATA", "discrepancies": []},
        )
        result = compute_confidence(state)
        assert result["confidence_score"] == 0.3
        # Low confidence should skip SAR
        route = should_generate_sar(result)
        assert route == "submit"

    def test_confidence_both_typologies(self):
        """BOTH(0.6) + corroboration(0.2) = 0.8"""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="BOTH",
            evidence_package={"verdict": "MATCH", "checked_count": 1, "discrepancies": []},
        )
        result = compute_confidence(state)
        assert result["confidence_score"] == 0.8

    def test_confidence_zero(self):
        """NONE = 0.0"""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="NONE",
            evidence_package={"verdict": "NOT_APPLICABLE", "discrepancies": []},
        )
        result = compute_confidence(state)
        assert result["confidence_score"] == 0.0

    def test_confidence_exact_boundary(self):
        """STRUCTURING(0.3) + corroboration(0.2) = 0.5 == threshold -> SAR generated."""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="STRUCTURING",
            evidence_package={"verdict": "MATCH", "checked_count": 1, "discrepancies": []},
        )
        result = compute_confidence(state)
        assert result["confidence_score"] == 0.5
        route = should_generate_sar(result)
        assert route == "draft", "0.5 == threshold; should generate SAR"

    def test_confidence_failed_state_passthrough(self):
        """Failed state should pass through unchanged."""
        state = _make_initial_state(status="FAILED")
        result = compute_confidence(state)
        assert result["status"] == "FAILED"


# ═══════════════════════════════════════════════════════════════════
# SAR Drafting and Validation
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def isolate_research_transport(monkeypatch):
    monkeypatch.setattr("tracer_agent.src.core.a2a_client.A2AClient.submit_result", AsyncMock(return_value={"status": "accepted"}))
    monkeypatch.setattr("tracer_agent.src.core.a2a_client.A2AClient.fetch_graph", AsyncMock(side_effect=ConnectionError("Offline fixture")))


class TestSARDraftingAndValidation:
    def test_draft_sar_skips_on_none_typology(self):
        """When typology is NONE, draft_sar should return empty narrative."""
        state = _make_initial_state(
            status="IN_PROGRESS",
            detected_typology="NONE",
            sar_narrative=None,
        )
        result = draft_sar(state)
        assert result["sar_narrative"] == "", "NONE typology -> empty narrative"

    def test_validate_sar_is_not_applicable_without_findings(self):
        state = _make_initial_state(
            status="IN_PROGRESS", detected_typology="NONE", sar_draft=None, retry_count=0,
        )
        result = validate_sar(state)
        assert result["validation_result"]["status"] == "NOT_APPLICABLE"
        assert result["validation_result"]["passed"] is False

    def test_validate_sar_handles_failed_status(self):
        """FAILED state should produce a failed validation result."""
        state = _make_initial_state(
            status="FAILED",
            retry_count=0,
        )
        result = validate_sar(state)
        assert result["validation_result"]["passed"] is False

    def test_validate_sar_missing_required_draft_triggers_retry(self):
        state = _make_initial_state(status="IN_PROGRESS", detected_typology="STRUCTURING", retry_count=0)
        validated = validate_sar(state)
        assert should_retry(validated) == "draft"

    def test_should_retry_submit_on_pass(self):
        state = _make_initial_state(
            validation_result={"passed": True, "errors": []},
            retry_count=1,
        )
        assert should_retry(state) == "submit", "Passed validation should submit"

    def test_should_retry_draft_on_failure(self):
        state = _make_initial_state(
            validation_result={"passed": False, "errors": ["err"]},
            retry_count=1,
        )
        assert should_retry(state) == "draft", "Failed validation should retry draft"

    def test_should_retry_submit_on_max_retries(self):
        state = _make_initial_state(
            validation_result={"passed": False, "errors": ["err"]},
            retry_count=3,
        )
        assert should_retry(state) == "submit", "Max retries should submit"


# ═══════════════════════════════════════════════════════════════════
# Submit Node (v9.0: submit_result sets "COMPLETE")
# ═══════════════════════════════════════════════════════════════════

class TestSubmissionContracts:
    def test_contract_failed_state_cannot_be_submitted(self, monkeypatch):
        send = AsyncMock()
        monkeypatch.setattr("tracer_agent.src.core.a2a_client.A2AClient.submit_result", send)
        result = submit_result(_make_initial_state(status="FAILED", error_message="Invalid graph"))
        assert result["status"] == "FAILED"
        send.assert_not_called()

    def test_contract_transport_failure_is_not_completion(self, monkeypatch):
        monkeypatch.setattr(
            "tracer_agent.src.core.a2a_client.A2AClient.submit_result",
            AsyncMock(side_effect=RuntimeError("Unavailable")),
        )
        result = submit_result(_make_initial_state(status="IN_PROGRESS", detected_typology="NONE"))
        assert result["status"] == "FAILED"
        assert result["error_message"]

    def test_contract_required_missing_draft_fails(self):
        result = validate_sar(_make_initial_state(status="IN_PROGRESS", detected_typology="STRUCTURING"))
        assert result["validation_result"]["status"] == "FAILED"
        assert result["validation_result"]["passed"] is False

    def test_contract_skipped_validation_is_not_passed(self):
        result = validate_sar(_make_initial_state(status="IN_PROGRESS", detected_typology="NONE"))
        assert result["validation_result"]["status"] == "NOT_APPLICABLE"
        assert result["validation_result"]["passed"] is False

    def test_contract_failed_state_cannot_retry(self):
        state = _make_initial_state(status="FAILED", validation_result={"passed": False}, retry_count=0)
        assert should_retry(state) == "submit"

    def test_contract_invalid_fallback_is_not_submitted(self, monkeypatch):
        from tracer_agent.src.core.sar_drafter import SARValidation
        send = AsyncMock()
        monkeypatch.setattr("tracer_agent.src.core.a2a_client.A2AClient.submit_result", send)
        monkeypatch.setattr(
            "tracer_agent.src.core.sar_drafter.SARDrafter.validate_sar",
            lambda *args: SARValidation(passed=False, errors=["Invalid evidence"]),
        )
        result = submit_result(_make_initial_state(status="IN_PROGRESS", detected_typology="STRUCTURING", confidence_score=0.8))
        assert result["status"] == "FAILED"
        send.assert_not_called()


class TestSubmit:
    def test_submit_sets_complete_only_after_acknowledgement(self):
        state = _make_initial_state(status="IN_PROGRESS", detected_typology="NONE")
        result = submit_result(state)
        assert result["status"] == "COMPLETE"

    def test_submit_preserves_failed_state(self):
        state = _make_initial_state(status="FAILED")
        assert submit_result(state)["status"] == "FAILED"


# ═══════════════════════════════════════════════════════════════════
# Workflow Compilation and End-to-End
# ═══════════════════════════════════════════════════════════════════

class TestWorkflow:
    def test_workflow_compiles(self):
        workflow = build_workflow()
        assert workflow is not None, "Workflow should compile successfully"

    async def test_workflow_preserves_graph_fetch_failure(self):
        result = await build_workflow().ainvoke(_make_initial_state())
        assert result["status"] == "FAILED"
        assert result["error_message"]

    async def test_workflow_runs_with_valid_graph(self):
        from decimal import Decimal
        fragment = {
            "transactions": [{"id": "TX-1", "source_node": "a", "target_node": "b",
                              "amount": Decimal("100"), "currency": "USD", "timestamp": 1700000000}],
            "nodes": {"a": {"id": "a"}, "b": {"id": "b"}}, "text_evidence": [],
        }
        result = await build_workflow().ainvoke(_make_initial_state(graph_fragment=fragment))
        assert result["status"] == "COMPLETE"
        assert result["validation_result"]["status"] == "NOT_APPLICABLE"
