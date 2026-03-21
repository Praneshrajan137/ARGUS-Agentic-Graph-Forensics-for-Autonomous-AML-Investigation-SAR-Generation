"""
Test: LangGraph Decision Loop -- State Machine
PRD Reference: Task A7
Updated for v9.0 API (uppercase statuses, renamed functions/fields).
"""
from typing import Any

from src.core.decision_loop import (
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
                "verdict": "CORROBORATED",
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
            evidence_package={"verdict": "CORROBORATED", "discrepancies": []},
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
            evidence_package={"verdict": "CORROBORATED", "discrepancies": []},
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

    def test_validate_sar_passes_when_no_draft(self):
        """If sar_draft is None (no crime), validation auto-passes."""
        state = _make_initial_state(
            status="IN_PROGRESS",
            sar_draft=None,
            retry_count=0,
        )
        result = validate_sar(state)
        assert result["validation_result"]["passed"] is True

    def test_validate_sar_handles_failed_status(self):
        """FAILED state should produce a failed validation result."""
        state = _make_initial_state(
            status="FAILED",
            retry_count=0,
        )
        result = validate_sar(state)
        assert result["validation_result"]["passed"] is False

    def test_validate_sar_failure_triggers_retry_flow(self):
        """Integration: validate_sar failure -> should_retry -> draft."""
        state = _make_initial_state(
            status="FAILED",
            retry_count=0,
        )
        validated = validate_sar(state)
        decision = should_retry(validated)
        assert decision == "draft", f"Expected retry to 'draft', got '{decision}'"

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

class TestSubmit:
    def test_submit_sets_complete_status(self):
        """v9.0: submit_result sets status to COMPLETE (uppercase)."""
        state = _make_initial_state(status="IN_PROGRESS")
        result = submit_result(state)
        assert result["status"] == "COMPLETE", (
            f"Expected COMPLETE, got {result['status']}"
        )

    def test_submit_preserves_failed_state(self):
        """submit_result catches exceptions and still returns COMPLETE."""
        state = _make_initial_state(status="FAILED")
        result = submit_result(state)
        # v9.0: submit_result always sets COMPLETE (even on error)
        assert result["status"] == "COMPLETE"


# ═══════════════════════════════════════════════════════════════════
# Workflow Compilation and End-to-End
# ═══════════════════════════════════════════════════════════════════

class TestWorkflow:
    def test_workflow_compiles(self):
        workflow = build_workflow()
        assert workflow is not None, "Workflow should compile successfully"

    async def test_workflow_runs_with_none_graph(self):
        """End-to-end: None graph_fragment -> FAILED status from analyze_graph,
        then submit_result catches the error and returns COMPLETE."""
        workflow = build_workflow()
        initial = _make_initial_state()
        result = await workflow.ainvoke(initial)
        # v9.0: submit_result always returns COMPLETE (even after failures)
        assert result["status"] == "COMPLETE", (
            f"Expected COMPLETE, got {result['status']}"
        )

    async def test_workflow_runs_with_valid_graph(self):
        """End-to-end: Valid graph -> COMPLETE (no detection in unit test env)."""
        workflow = build_workflow()
        fragment = {
            "transactions": [{"id": "TX-1"}],
            "nodes": {"a": {"id": "a"}},
            "text_evidence": [],
            "ground_truth_criminals": [],
        }
        initial = _make_initial_state(graph_fragment=fragment)
        result = await workflow.ainvoke(initial)
        assert result["status"] == "COMPLETE", (
            f"Expected COMPLETE, got {result['status']}"
        )
