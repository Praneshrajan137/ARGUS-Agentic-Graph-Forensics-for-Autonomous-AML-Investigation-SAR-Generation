import importlib


benchmark = importlib.import_module("argus-app.backend.services.benchmark_service")


def record(**overrides):
    return {
        "status": "COMPLETE", "coverage_status": "COMPLETE",
        "expected_typology": "NONE", "detected_typology": "NONE", "correct": True,
        "entity_precision": None, "entity_recall": None, "entity_f1": None,
        "confidence": 0.0, "assessment_score": None, **overrides,
    }


def test_failure_is_not_a_successful_negative():
    result = benchmark._compute_aggregate([record(status="FAILED")], 10)
    assert result["completed"] == 0
    assert result["failed"] == 1
    assert result["false_positive_rate"] is None


def test_absent_execution_status_is_not_completion():
    row = record()
    del row["status"]
    assert benchmark._compute_aggregate([row], 10)["completed"] == 0


def test_partial_analysis_cannot_establish_negative():
    result = benchmark._compute_aggregate([record(coverage_status="PARTIAL")], 10)
    assert result["evaluated"] == 0
    assert result["partial"] == 1
    assert result["false_positive_rate"] is None


def test_failed_positive_stays_in_end_to_end_denominator():
    rows = [record(expected_typology="STRUCTURING", detected_typology="STRUCTURING"),
            record(expected_typology="STRUCTURING", status="FAILED", correct=False)]
    result = benchmark._compute_aggregate(rows, 10)
    assert result["crime_detection_rate"] == 0.5
    assert result["coverage_rate"] == 0.5


def test_unavailable_entity_metrics_are_not_zero():
    result = benchmark._compute_aggregate([record()], 10)
    assert result["avg_precision"] is None
    assert result["avg_assessment_score"] is None


def test_nearby_pattern_does_not_implicate_subject():
    hits = {"structuring_hits": [{"node": "A", "sources": ["B"]}], "layering_hits": []}
    assert benchmark._subject_typology(hits, "outside") == "NONE"
    assert benchmark._subject_typology(hits, "B") == "STRUCTURING"


def test_fast_and_full_benchmark_evaluation_units_are_distinct():
    full = benchmark._compute_aggregate([record()], 10)
    fast = benchmark._compute_aggregate([record()], 10, evaluation_unit="fast_node_local_sweep")
    assert full["evaluation_unit"] == "full_neighborhood_subject_participation"
    assert fast["evaluation_unit"] == "fast_node_local_sweep"
    assert full["evaluation_unit"] != fast["evaluation_unit"]


def test_investigation_service_never_defaults_missing_validation_to_passed():
    inv_svc = importlib.import_module("argus-app.backend.services.investigation_service")
    state = {
        "case_id": "c-1", "status": "COMPLETE", "detected_typology": "STRUCTURING",
        "involved_entities": ["A"], "confidence_score": 0.6,
        "sar_narrative": "draft", "sar_draft": {"who": "A"},
        "validation_result": {"status": "NOT_RUN", "passed": False, "errors": []},
    }
    resp = inv_svc._langgraph_state_to_response(state, "c-1", "A", "fincen")
    validate_step = next(s for s in resp["steps"] if s["name"] == "validate")
    assert validate_step["status"] == "warning"
    assert "passed" not in validate_step["detail"].lower()
    assert inv_svc._step_detail_from_state("submit", state) != "filed"
