"""Benchmark service — runs investigations on ALL nodes and aggregates metrics.

Orchestrates: generate world → investigate every node → assess each → aggregate.
Designed to run in a background thread with progress updates via AppState.
"""
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from ..models.state import get_state
from .forge_service import generate_world
from .investigation_service import run_investigation, _networkx_to_reasoner_dict
from .assessment_service import run_assessment
from .tracer_service import GraphReasoner, detect_structuring, detect_layering

logger = logging.getLogger(__name__)


def _build_expected_typology_map(ground_truth: dict) -> dict[str, str]:
    """Map each node ID to its expected typology from ground truth."""
    structuring_nodes: set[str] = set()
    layering_nodes: set[str] = set()

    for crime in ground_truth.get("crimes", []):
        crime_type = crime.get("crime_type", "")
        nodes = {str(n) for n in crime.get("nodes_involved", [])}
        if crime_type == "structuring":
            structuring_nodes.update(nodes)
        elif crime_type == "layering":
            layering_nodes.update(nodes)

    typology_map: dict[str, str] = {}
    for node_id in structuring_nodes | layering_nodes:
        in_s = node_id in structuring_nodes
        in_l = node_id in layering_nodes
        if in_s and in_l:
            typology_map[node_id] = "BOTH"
        elif in_s:
            typology_map[node_id] = "STRUCTURING"
        else:
            typology_map[node_id] = "LAYERING"

    return typology_map


def _is_detection_correct(expected: str, detected: str) -> bool:
    """Check if detected typology matches or includes expected."""
    if expected == "NONE":
        return detected == "NONE"
    if expected == "BOTH":
        return detected == "BOTH"
    if expected == "STRUCTURING":
        return detected in ("STRUCTURING", "BOTH")
    if expected == "LAYERING":
        return detected in ("LAYERING", "BOTH")
    return expected == detected


def _compute_aggregate(node_results: list[dict], total_duration_ms: int) -> dict:
    """Compute aggregate metrics from all per-node results."""
    completed = [r for r in node_results if r.get("detected_typology") is not None]
    failed = len(node_results) - len(completed)

    crime_nodes = [r for r in completed if r["expected_typology"] != "NONE"]
    clean_nodes = [r for r in completed if r["expected_typology"] == "NONE"]
    structuring_nodes = [r for r in completed if r["expected_typology"] in ("STRUCTURING", "BOTH")]
    layering_nodes = [r for r in completed if r["expected_typology"] in ("LAYERING", "BOTH")]

    # Detection rates
    crime_correct = sum(1 for r in crime_nodes if r["correct"])
    crime_detection_rate = crime_correct / len(crime_nodes) if crime_nodes else 0.0

    clean_flagged = sum(1 for r in clean_nodes if r["detected_typology"] != "NONE")
    false_positive_rate = clean_flagged / len(clean_nodes) if clean_nodes else 0.0

    s_correct = sum(1 for r in structuring_nodes if r["detected_typology"] in ("STRUCTURING", "BOTH"))
    structuring_detection_rate = s_correct / len(structuring_nodes) if structuring_nodes else 0.0

    l_correct = sum(1 for r in layering_nodes if r["detected_typology"] in ("LAYERING", "BOTH"))
    layering_detection_rate = l_correct / len(layering_nodes) if layering_nodes else 0.0

    # Averages across all completed investigations
    avg_precision = sum(r["entity_precision"] for r in completed) / len(completed) if completed else 0.0
    avg_recall = sum(r["entity_recall"] for r in completed) / len(completed) if completed else 0.0
    avg_f1 = sum(r["entity_f1"] for r in completed) / len(completed) if completed else 0.0
    avg_confidence = sum(r["confidence"] for r in completed) / len(completed) if completed else 0.0
    avg_assessment = sum(r["assessment_score"] for r in completed) / len(completed) if completed else 0.0
    avg_duration = total_duration_ms / len(completed) if completed else 0.0

    return {
        "total_investigations": len(node_results),
        "completed": len(completed),
        "failed": failed,
        "structuring_detected": structuring_detection_rate > 0,
        "layering_detected": layering_detection_rate > 0,
        "crime_detection_rate": round(crime_detection_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "avg_precision": round(avg_precision, 4),
        "avg_recall": round(avg_recall, 4),
        "avg_f1": round(avg_f1, 4),
        "avg_confidence": round(avg_confidence, 4),
        "avg_assessment_score": round(avg_assessment, 2),
        "total_duration_ms": total_duration_ms,
        "avg_duration_ms": round(avg_duration, 1),
        "structuring_detection_rate": round(structuring_detection_rate, 4),
        "layering_detection_rate": round(layering_detection_rate, 4),
    }


def run_benchmark(benchmark_id: str, config: dict[str, Any]) -> None:
    """Run full benchmark: investigate every node, assess, aggregate.

    Updates state.benchmarks[benchmark_id] in-place for progress polling.
    Called from a background thread — do NOT return results, store in state.
    """
    state = get_state()
    started_at = datetime.now().isoformat()

    # Initialize benchmark record
    benchmark = {
        "benchmark_id": benchmark_id,
        "status": "RUNNING",
        "config": config,
        "progress": 0.0,
        "current_node": "",
        "completed_count": 0,
        "total_count": 0,
        "aggregate": None,
        "node_results": [],
        "started_at": started_at,
        "completed_at": None,
    }
    state.benchmarks[benchmark_id] = benchmark

    try:
        # Step 1: Generate world if requested
        if config.get("generate", False):
            benchmark["current_node"] = "generating..."
            generate_world(
                seed=config.get("seed", 42),
                difficulty=config.get("difficulty", 5),
                node_count=config.get("node_count", 1000),
            )

        if state.graph is None:
            benchmark["status"] = "FAILED"
            benchmark["completed_at"] = datetime.now().isoformat()
            return

        # Step 2: Build target node list (ALL nodes)
        all_node_ids = sorted(str(n) for n in state.graph.nodes())
        benchmark["total_count"] = len(all_node_ids)

        # Step 3: Build expected typology map
        typology_map = _build_expected_typology_map(state.ground_truth)

        hop_depth = config.get("hop_depth", 3)
        jurisdiction = config.get("jurisdiction", "fincen")
        node_results: list[dict] = []
        t_total_start = time.time()

        # Step 4: Investigate every node
        for idx, node_id in enumerate(all_node_ids):
            case_id = f"bench-{benchmark_id[:8]}-{idx}"
            expected = typology_map.get(node_id, "NONE")
            is_crime = expected != "NONE"

            t0 = time.time()
            try:
                inv_result = run_investigation(
                    case_id=case_id,
                    subject_id=node_id,
                    hop_depth=hop_depth,
                    jurisdiction=jurisdiction,
                )
                detected = inv_result.get("detected_typology", "NONE")
                confidence = inv_result.get("confidence_score", 0.0)

                # Run assessment
                assess = run_assessment(case_id)
                assessment_score = assess.get("overall_score", 0.0)
                entity_metrics = assess.get("entity_metrics", {})
                precision = entity_metrics.get("precision", 0.0)
                recall = entity_metrics.get("recall", 0.0)
                f1 = entity_metrics.get("f1_score", 0.0)

            except Exception as e:
                logger.warning("Benchmark investigation failed for node %s: %s", node_id, e)
                detected = "NONE"
                confidence = 0.0
                assessment_score = 0.0
                precision = recall = f1 = 0.0

            duration_ms = int((time.time() - t0) * 1000)
            correct = _is_detection_correct(expected, detected)

            node_results.append({
                "node_id": node_id,
                "is_crime_node": is_crime,
                "expected_typology": expected,
                "detected_typology": detected,
                "correct": correct,
                "confidence": confidence,
                "investigation_case_id": case_id,
                "assessment_score": assessment_score,
                "duration_ms": duration_ms,
                "entity_precision": precision,
                "entity_recall": recall,
                "entity_f1": f1,
            })

            # Update progress
            benchmark["completed_count"] = idx + 1
            benchmark["current_node"] = node_id
            benchmark["progress"] = round(((idx + 1) / len(all_node_ids)) * 100, 1)
            benchmark["node_results"] = node_results

        # Step 5: Compute aggregate metrics
        total_duration_ms = int((time.time() - t_total_start) * 1000)
        aggregate = _compute_aggregate(node_results, total_duration_ms)

        benchmark["status"] = "COMPLETE"
        benchmark["aggregate"] = aggregate
        benchmark["node_results"] = node_results
        benchmark["completed_at"] = datetime.now().isoformat()

        logger.info(
            "Benchmark %s complete: %d nodes, detection_rate=%.2f%%, FPR=%.2f%%, F1=%.4f",
            benchmark_id, len(all_node_ids),
            aggregate["crime_detection_rate"] * 100,
            aggregate["false_positive_rate"] * 100,
            aggregate["avg_f1"],
        )

    except Exception as e:
        logger.error("Benchmark %s failed: %s", benchmark_id, e)
        benchmark["status"] = "FAILED"
        benchmark["completed_at"] = datetime.now().isoformat()


def run_benchmark_fast(benchmark_id: str, config: dict[str, Any]) -> None:
    """Fast sweep: run detection heuristics on every node without full pipeline.

    Loads entire graph into GraphReasoner once, then calls detect_structuring
    and detect_layering on each node. Skips BFS subgraph, evidence synthesis,
    SAR generation, and assessment. ~30s for 1000 nodes.
    """
    state = get_state()
    started_at = datetime.now().isoformat()

    benchmark = {
        "benchmark_id": benchmark_id,
        "status": "RUNNING",
        "config": config,
        "progress": 0.0,
        "current_node": "",
        "completed_count": 0,
        "total_count": 0,
        "aggregate": None,
        "node_results": [],
        "started_at": started_at,
        "completed_at": None,
    }
    state.benchmarks[benchmark_id] = benchmark

    try:
        # Step 1: Generate world if requested
        if config.get("generate", False):
            benchmark["current_node"] = "generating..."
            generate_world(
                seed=config.get("seed", 42),
                difficulty=config.get("difficulty", 5),
                node_count=config.get("node_count", 1000),
            )

        if state.graph is None:
            benchmark["status"] = "FAILED"
            benchmark["completed_at"] = datetime.now().isoformat()
            return

        # Step 2: Load FULL graph into GraphReasoner ONCE
        benchmark["current_node"] = "loading graph..."
        graph_dict = _networkx_to_reasoner_dict(state.graph, subject_id=None)
        reasoner = GraphReasoner()
        reasoner.load_from_dict(graph_dict)

        # Step 3: Build target node list and typology map
        all_node_ids = sorted(str(n) for n in state.graph.nodes())
        benchmark["total_count"] = len(all_node_ids)
        typology_map = _build_expected_typology_map(state.ground_truth)

        # Step 4: Determine currency from jurisdiction
        currency = "INR" if config.get("jurisdiction") == "fiu_ind" else "USD"
        hop_depth = config.get("hop_depth", 3)
        node_results: list[dict] = []
        t_total_start = time.time()

        # Step 5: Run detection on every node
        for idx, node_id in enumerate(all_node_ids):
            expected = typology_map.get(node_id, "NONE")
            is_crime = expected != "NONE"

            t0 = time.time()
            try:
                s_result = detect_structuring(reasoner, node_id, currency=currency)
                l_result = detect_layering(reasoner, node_id, max_depth=hop_depth)

                s_detected = s_result.detected
                l_detected = l_result.detected

                if s_detected and l_detected:
                    detected = "BOTH"
                elif s_detected:
                    detected = "STRUCTURING"
                elif l_detected:
                    detected = "LAYERING"
                else:
                    detected = "NONE"

                # Take max confidence from either detection
                s_conf = float(s_result.confidence) if s_detected else 0.0
                l_conf = float(l_result.confidence) if l_detected else 0.0
                confidence = max(s_conf, l_conf)

            except Exception as e:
                logger.warning("Fast sweep failed for node %s: %s", node_id, e)
                detected = "NONE"
                confidence = 0.0

            duration_ms = int((time.time() - t0) * 1000)
            correct = _is_detection_correct(expected, detected)

            node_results.append({
                "node_id": node_id,
                "is_crime_node": is_crime,
                "expected_typology": expected,
                "detected_typology": detected,
                "correct": correct,
                "confidence": confidence,
                "investigation_case_id": f"fast-{benchmark_id[:8]}-{idx}",
                "assessment_score": 0.0,
                "duration_ms": duration_ms,
                "entity_precision": 0.0,
                "entity_recall": 0.0,
                "entity_f1": 0.0,
            })

            # Update progress
            benchmark["completed_count"] = idx + 1
            benchmark["current_node"] = node_id
            benchmark["progress"] = round(((idx + 1) / len(all_node_ids)) * 100, 1)
            benchmark["node_results"] = node_results

        # Step 6: Compute aggregate metrics
        total_duration_ms = int((time.time() - t_total_start) * 1000)
        aggregate = _compute_aggregate(node_results, total_duration_ms)

        benchmark["status"] = "COMPLETE"
        benchmark["aggregate"] = aggregate
        benchmark["node_results"] = node_results
        benchmark["completed_at"] = datetime.now().isoformat()

        logger.info(
            "Fast benchmark %s complete: %d nodes in %.1fs, detection_rate=%.2f%%, FPR=%.2f%%",
            benchmark_id, len(all_node_ids),
            total_duration_ms / 1000,
            aggregate["crime_detection_rate"] * 100,
            aggregate["false_positive_rate"] * 100,
        )

    except Exception as e:
        logger.error("Fast benchmark %s failed: %s", benchmark_id, e)
        benchmark["status"] = "FAILED"
        benchmark["completed_at"] = datetime.now().isoformat()
