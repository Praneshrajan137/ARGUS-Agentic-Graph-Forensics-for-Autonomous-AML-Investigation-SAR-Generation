"""Assessment service — COPIED pure functions from src/core/a2a_interface.py.

These are PURE FUNCTIONS with no FastAPI dependency, no protobuf.
They evaluate investigation quality against ground truth.
"""
import re
import logging
from decimal import Decimal
from typing import Any

import networkx as nx

from src.config import (
    RUBRIC_WEIGHT_PATTERN, RUBRIC_WEIGHT_EVIDENCE,
    RUBRIC_WEIGHT_NARRATIVE, RUBRIC_WEIGHT_COMPLETENESS,
    RUBRIC_WEIGHT_EFFICIENCY,
    SAR_FIVE_WS_PATTERN,
    CTR_THRESHOLD_USD, STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    CONFIDENCE_THRESHOLD,
    EFFICIENCY_TIER_EXCELLENT_MAX, EFFICIENCY_TIER_GOOD_MAX, EFFICIENCY_TIER_FAIR_MAX,
)
from src.core.result_types import (
    EntityMetrics, HallucinationCheck, FiveWsValidation,
    TypologyScore, EfficiencyScore, AssessmentResult,
)

from ..models.state import get_state

logger = logging.getLogger(__name__)


def _compute_entity_metrics(
    investigation_data: dict[str, Any],
    ground_truth: dict[str, Any],
) -> EntityMetrics:
    """Compute entity-level Precision/Recall/F1 against ground truth."""
    gt_entities: set[str] = set()
    for crime in ground_truth.get('crimes', []):
        for node in crime.get('nodes_involved', []):
            gt_entities.add(str(node))

    predicted: set[str] = set()
    for acct in investigation_data.get('suspicious_accounts', []):
        predicted.add(str(acct))
    for crime in investigation_data.get('identified_crimes', []):
        for node in crime.get('nodes', []):
            predicted.add(str(node))

    # Also include involved_entities from investigation results
    for entity in investigation_data.get('involved_entities', []):
        predicted.add(str(entity))

    tp = sorted(predicted & gt_entities)
    fp = sorted(predicted - gt_entities)
    fn = sorted(gt_entities - predicted)

    return EntityMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def _compute_typology_score(
    identified_crimes: list[dict[str, Any]],
    actual_crimes: list[dict[str, Any]],
) -> TypologyScore:
    """Score whether the investigation correctly identified the crime typology."""
    if not actual_crimes:
        return TypologyScore(correct=True, confidence=Decimal("1"))

    expected_types = {c.get('crime_type', '') for c in actual_crimes}
    detected_types = {c.get('crime_type', '') for c in identified_crimes}

    primary = actual_crimes[0].get('crime_type', 'unknown')
    detected_primary = identified_crimes[0].get('crime_type', '') if identified_crimes else ''

    # Proportional scoring: F1 over crime type sets
    tp = len(expected_types & detected_types)
    fp = len(detected_types - expected_types)
    fn = len(expected_types - detected_types)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    correct = f1 == 1.0

    return TypologyScore(
        expected_typology=primary,
        detected_typology=detected_primary,
        correct=correct,
        confidence=Decimal(str(round(f1, 4))),
        reasoning=f"Expected {expected_types}, detected {detected_types}; F1={f1:.4f}",
    )


def _check_hallucinations(
    investigation_data: dict[str, Any],
    graph: nx.MultiDiGraph | None,
) -> HallucinationCheck:
    """Check if the investigation references entities/amounts not in the graph."""
    result = HallucinationCheck()

    if graph is None:
        result.details = "No graph loaded, skipping hallucination check"
        return result

    graph_nodes = {str(n) for n in graph.nodes()}
    graph_amounts = set()
    for _, _, data in graph.edges(data=True):
        amt = data.get('amount')
        if amt is not None:
            graph_amounts.add(str(round(float(amt), 2)))

    cited_entities = set()
    for acct in investigation_data.get('suspicious_accounts', []):
        cited_entities.add(str(acct))
    for crime in investigation_data.get('identified_crimes', []):
        for node in crime.get('nodes', []):
            cited_entities.add(str(node))
    for entity in investigation_data.get('involved_entities', []):
        cited_entities.add(str(entity))

    for entity in cited_entities:
        if entity not in graph_nodes:
            result.hallucinated_entities.append(entity)

    # Check cited amounts in SAR narrative
    sar_text = investigation_data.get('sar_narrative', '') or investigation_data.get('narrative', '')
    if sar_text:
        amount_pattern = re.compile(r'\$[\d,]+(?:\.\d{2})?')
        for match in amount_pattern.finditer(sar_text):
            raw = match.group().replace('$', '').replace(',', '')
            try:
                cited_amount = str(round(float(raw), 2))
                threshold_whitelist = {
                    float(CTR_THRESHOLD_USD),
                    float(STRUCTURING_MIN_AMOUNT_USD),
                    float(STRUCTURING_MAX_AMOUNT_USD),
                }
                if cited_amount not in graph_amounts and float(cited_amount) not in threshold_whitelist:
                    result.hallucinated_amounts.append(match.group())
            except ValueError:
                pass

    result.passed = result.total_hallucinations == 0
    if not result.passed:
        result.details = (
            f"Found {len(result.hallucinated_entities)} hallucinated entities "
            f"and {len(result.hallucinated_amounts)} hallucinated amounts"
        )

    return result


def _validate_five_ws(sar_narrative: str) -> FiveWsValidation:
    """Validate SAR narrative for Five Ws completeness."""
    result = FiveWsValidation()

    if not sar_narrative:
        result.missing_sections = ["WHO", "WHAT", "WHERE", "WHEN", "WHY"]
        return result

    found_tags = set()
    for match in SAR_FIVE_WS_PATTERN.finditer(sar_narrative):
        tag = match.group(1).upper()
        content = match.group(2).strip()
        if content:
            found_tags.add(tag)

    if found_tags:
        result.who_present = "WHO" in found_tags
        result.what_present = "WHAT" in found_tags
        result.where_present = "WHERE" in found_tags
        result.when_present = "WHEN" in found_tags
        result.why_present = "WHY" in found_tags
    else:
        text_lower = sar_narrative.lower()
        result.who_present = any(kw in text_lower for kw in ['subject', 'account id', 'name:', 'entity'])
        result.what_present = any(kw in text_lower for kw in ['structuring', 'layering', 'suspicious', 'pattern'])
        result.where_present = any(kw in text_lower for kw in ['branch', 'bank', 'jurisdiction', 'account'])
        result.when_present = any(kw in text_lower for kw in ['hour', 'window', 'period', 'date', 'time'])
        result.why_present = any(kw in text_lower for kw in ['threshold', 'evade', 'obscure', 'laundering', 'concern'])

    for tag, present in [
        ("WHO", result.who_present), ("WHAT", result.what_present),
        ("WHERE", result.where_present), ("WHEN", result.when_present),
        ("WHY", result.why_present),
    ]:
        if not present:
            result.missing_sections.append(tag)

    return result


def _compute_efficiency_score(tool_count: int) -> EfficiencyScore:
    """Compute efficiency score from tool call count using config tiers."""
    if tool_count <= EFFICIENCY_TIER_EXCELLENT_MAX:
        return EfficiencyScore(tool_call_count=tool_count, tier="excellent", score=Decimal("100"))
    elif tool_count <= EFFICIENCY_TIER_GOOD_MAX:
        return EfficiencyScore(tool_call_count=tool_count, tier="good", score=Decimal("80"))
    elif tool_count <= EFFICIENCY_TIER_FAIR_MAX:
        return EfficiencyScore(tool_call_count=tool_count, tier="fair", score=Decimal("60"))
    else:
        raw = max(40.0 - (tool_count - EFFICIENCY_TIER_FAIR_MAX) * 0.1, 10.0)
        return EfficiencyScore(tool_call_count=tool_count, tier="poor", score=Decimal(str(round(raw, 2))))


def _find_missed_indicators(
    investigation_data: dict[str, Any],
    ground_truth: dict[str, Any],
) -> list[str]:
    """Identify indicators that were missed by the investigation."""
    missed = []

    crimes = ground_truth.get('crimes', [])
    identified_crimes = investigation_data.get('identified_crimes', [])
    identified_types = {c.get('crime_type') for c in identified_crimes}

    # Also check detected_typology
    detected = investigation_data.get('detected_typology', 'NONE')
    if detected != 'NONE':
        identified_types.add(detected.lower())

    for crime in crimes:
        crime_type = crime.get('crime_type', '')
        metadata = crime.get('metadata', {})

        if crime_type == 'structuring' and 'structuring' not in identified_types:
            mule_id = metadata.get('mule_id')
            source_count = metadata.get('source_count', 0)
            missed.append(
                f"Structuring pattern: {source_count} sources to mule node {mule_id}"
            )

        if crime_type == 'layering' and 'layering' not in identified_types:
            chain_length = metadata.get('chain_length', 0)
            initial = float(metadata.get('initial_amount', 0))
            final = float(metadata.get('final_amount', 0))
            missed.append(
                f"Layering chain: {chain_length} hops, ${initial:,.2f} -> ${final:,.2f}"
            )

    return missed


def run_assessment(case_id: str) -> dict[str, Any]:
    """Run full assessment of a completed investigation.

    1. Loads investigation from AppState
    2. Loads ground_truth from AppState
    3. Calls each assessment function
    4. Applies rubric weights from config
    5. Returns a unified assessment dict
    """
    state = get_state()
    investigation = state.investigations.get(case_id)
    if investigation is None:
        return {"error": f"Investigation {case_id} not found"}

    ground_truth = state.ground_truth
    if not ground_truth:
        return {"error": "No ground truth loaded"}

    # Build investigation_data dict from the stored investigation
    investigation_data = {
        "involved_entities": investigation.get("involved_entities", []),
        "detected_typology": investigation.get("detected_typology", "NONE"),
        "sar_narrative": investigation.get("sar_narrative", ""),
        "confidence_score": investigation.get("confidence_score", 0.0),
        "identified_crimes": [],
        "suspicious_accounts": investigation.get("involved_entities", []),
    }

    # Build identified_crimes from detection_results
    detection = investigation.get("detection_results", {})
    typology = detection.get("typology", "NONE")
    if typology in ("STRUCTURING", "BOTH"):
        investigation_data["identified_crimes"].append({"crime_type": "structuring", "nodes": investigation.get("involved_entities", [])})
    if typology in ("LAYERING", "BOTH"):
        investigation_data["identified_crimes"].append({"crime_type": "layering", "nodes": investigation.get("involved_entities", [])})

    # 1. Entity Metrics
    entity_metrics = _compute_entity_metrics(investigation_data, ground_truth)

    # 2. Typology Score
    actual_crimes = ground_truth.get('crimes', [])
    typology_score = _compute_typology_score(
        investigation_data.get('identified_crimes', []), actual_crimes
    )

    # 3. Hallucination Check
    hallucination_check = _check_hallucinations(investigation_data, state.graph)

    # 4. Five Ws Validation
    five_ws = _validate_five_ws(investigation_data.get('sar_narrative', ''))

    # 5. Efficiency Score (use a default for backend-driven investigations)
    efficiency = _compute_efficiency_score(8)  # 8 pipeline steps

    # 6. Weighted Overall Score
    pattern_score = float(typology_score.score) * 100
    evidence_score = float(entity_metrics.f1) * 100
    narrative_score = float(five_ws.completeness_score) * 100
    completeness_score = float(entity_metrics.recall) * 100
    eff_score = float(efficiency.score)

    hallucination_penalty = min(hallucination_check.total_hallucinations * 20, 50)

    total_score = (
        pattern_score * float(RUBRIC_WEIGHT_PATTERN) +
        evidence_score * float(RUBRIC_WEIGHT_EVIDENCE) +
        narrative_score * float(RUBRIC_WEIGHT_NARRATIVE) +
        completeness_score * float(RUBRIC_WEIGHT_COMPLETENESS) +
        eff_score * float(RUBRIC_WEIGHT_EFFICIENCY)
    )
    total_score = max(0, round(total_score - hallucination_penalty, 2))

    # 7. Missed indicators
    missed = _find_missed_indicators(investigation_data, ground_truth)

    return {
        "case_id": case_id,
        "overall_score": total_score,
        "entity_metrics": {
            "precision": float(entity_metrics.precision),
            "recall": float(entity_metrics.recall),
            "f1_score": float(entity_metrics.f1),
            "true_positives": entity_metrics.true_positives,
            "false_positives": entity_metrics.false_positives,
            "false_negatives": entity_metrics.false_negatives,
        },
        "rubric_breakdown": {
            "pattern_detection": round(pattern_score * float(RUBRIC_WEIGHT_PATTERN), 2),
            "evidence_analysis": round(evidence_score * float(RUBRIC_WEIGHT_EVIDENCE), 2),
            "narrative_quality": round(narrative_score * float(RUBRIC_WEIGHT_NARRATIVE), 2),
            "completeness": round(completeness_score * float(RUBRIC_WEIGHT_COMPLETENESS), 2),
            "efficiency": round(eff_score * float(RUBRIC_WEIGHT_EFFICIENCY), 2),
        },
        "hallucination_check": {
            "passed": hallucination_check.passed,
            "total_hallucinations": hallucination_check.total_hallucinations,
            "hallucinated_entities": hallucination_check.hallucinated_entities,
            "hallucinated_amounts": hallucination_check.hallucinated_amounts,
        },
        # Frontend-friendly flattened fields
        "hallucination_count": hallucination_check.total_hallucinations,
        "hallucination_details": (
            hallucination_check.hallucinated_entities + hallucination_check.hallucinated_amounts
        ),
        "five_ws_validation": {
            "completeness_score": str(five_ws.completeness_score),
            "is_complete": five_ws.is_complete,
            "missing_sections": five_ws.missing_sections,
        },
        # Frontend-friendly boolean keys
        "five_ws": {
            "who": five_ws.who_present,
            "what": five_ws.what_present,
            "where": five_ws.where_present,
            "when": five_ws.when_present,
            "why": five_ws.why_present,
        },
        "missed_indicators": missed,
    }
