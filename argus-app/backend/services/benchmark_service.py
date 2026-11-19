"""Benchmark service — runs investigations on ALL nodes and aggregates metrics.

Orchestrates: generate world → investigate every node → assess each → aggregate.
Designed to run in a background thread with progress updates via AppState.
"""
import logging
import time
from datetime import datetime
from typing import Any

from ..models.state import get_state
from .forge_service import generate_world
from .investigation_service import run_investigation, _networkx_to_reasoner_dict
from .assessment_service import run_assessment
from .tracer_service import GraphReasoner, find_structuring_patterns, detect_layering

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


def _subject_typology(detection: dict, subject_id: str) -> str:
    structuring = any(
        subject_id in {str(hit["node"]), *(str(node) for node in hit.get("sources", []))}
        for hit in detection.get("structuring_hits", [])
    )
    layering = any(subject_id in {str(node) for node in hit.get("chain_nodes", [])}
                   for hit in detection.get("layering_hits", []))
    return "BOTH" if structuring and layering else "STRUCTURING" if structuring else "LAYERING" if layering else "NONE"


def _compute_aggregate(
    node_results: list[dict],
    total_duration_ms: int,
    evaluation_unit: str = "full_neighborhood_subject_participation",
) -> dict:
    completed = [row for row in node_results if row.get("status") == "COMPLETE"]
    evaluated = [row for row in completed if row.get("coverage_status") == "COMPLETE"
                 and row.get("detected_typology") in {"NONE", "STRUCTURING", "LAYERING", "BOTH"}]
    crime_nodes = [row for row in node_results if row["expected_typology"] != "NONE"]
    clean_nodes = [row for row in evaluated if row["expected_typology"] == "NONE"]

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    def mean(key: str) -> float | None:
        values = [row[key] for row in evaluated if row.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    def detection_rate(typology: str) -> float | None:
        expected = [row for row in node_results if row["expected_typology"] in {typology, "BOTH"}]
        found = sum(row["expected_typology"] in {typology, "BOTH"}
                    and row["detected_typology"] in {typology, "BOTH"} for row in evaluated)
        return ratio(found, len(expected))

    structuring_rate = detection_rate("STRUCTURING")
    layering_rate = detection_rate("LAYERING")
    return {
        "total_investigations": len(node_results), "completed": len(completed),
        "failed": len(node_results) - len(completed), "evaluated": len(evaluated),
        "partial": len(completed) - len(evaluated),
        "coverage_rate": ratio(len(evaluated), len(node_results)),
        "evaluation_unit": evaluation_unit,
        "structuring_detected": bool(structuring_rate), "layering_detected": bool(layering_rate),
        "crime_detection_rate": ratio(sum(row["expected_typology"] != "NONE" and row.get("correct") is True
                                          for row in evaluated), len(crime_nodes)),
        "false_positive_rate": ratio(sum(row["detected_typology"] != "NONE" for row in clean_nodes), len(clean_nodes)),
        "avg_precision": mean("entity_precision"), "avg_recall": mean("entity_recall"),
        "avg_f1": mean("entity_f1"), "avg_confidence": mean("confidence"),
        "avg_assessment_score": mean("assessment_score"), "total_duration_ms": total_duration_ms,
        "avg_duration_ms": ratio(total_duration_ms, len(node_results)),
        "structuring_detection_rate": structuring_rate, "layering_detection_rate": layering_rate,
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
    with state._lock:
        state.benchmarks[benchmark_id] = benchmark

    try:
        # Step 1: Generate world if requested
        if config.get("generate", False):
            with state._lock:
                benchmark["current_node"] = "generating..."
            generate_world(
                seed=config.get("seed", 42),
                difficulty=config.get("difficulty", 5),
                node_count=config.get("node_count", 1000),
            )

        if state.graph is None:
            with state._lock:
                benchmark["status"] = "FAILED"
                benchmark["completed_at"] = datetime.now().isoformat()
            return

        # Step 2: Build target node list (ALL nodes)
        all_node_ids = sorted(str(n) for n in state.graph.nodes())
        with state._lock:
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
                status = inv_result.get("status", "FAILED")
                if status != "COMPLETE":
                    raise ValueError("Investigation did not complete")
                coverage_status = (inv_result.get("coverage") or {}).get("status", "NOT_REPORTED")
                detected = _subject_typology(inv_result.get("detection_results") or {}, node_id)
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
                status = "FAILED"
                coverage_status = "NOT_EVALUATED"
                detected = None
                confidence = 0.0
                assessment_score = None
                precision = recall = f1 = None

            duration_ms = int((time.time() - t0) * 1000)
            correct = _is_detection_correct(expected, detected) if status == "COMPLETE" and coverage_status == "COMPLETE" else None

            node_results.append({
                "node_id": node_id,
                "status": status,
                "coverage_status": coverage_status,
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
            with state._lock:
                benchmark["completed_count"] = idx + 1
                benchmark["current_node"] = node_id
                benchmark["progress"] = round(((idx + 1) / len(all_node_ids)) * 100, 1)
                benchmark["node_results"] = node_results

        # Step 5: Compute aggregate metrics
        total_duration_ms = int((time.time() - t_total_start) * 1000)
        aggregate = _compute_aggregate(
            node_results, total_duration_ms,
            evaluation_unit="full_neighborhood_subject_participation",
        )

        with state._lock:
            benchmark["status"] = "COMPLETE"
            benchmark["aggregate"] = aggregate
            benchmark["node_results"] = node_results
            benchmark["completed_at"] = datetime.now().isoformat()

        logger.info(
            "Benchmark %s complete: %d nodes, detection_rate=%s, FPR=%s, F1=%s",
            benchmark_id, len(all_node_ids),
            f"{aggregate['crime_detection_rate'] * 100:.2f}%" if aggregate["crime_detection_rate"] is not None else "N/A",
            f"{aggregate['false_positive_rate'] * 100:.2f}%" if aggregate["false_positive_rate"] is not None else "N/A",
            f"{aggregate['avg_f1']:.4f}" if aggregate["avg_f1"] is not None else "N/A",
        )

    except Exception as e:
        logger.error("Benchmark %s failed: %s", benchmark_id, e)
        with state._lock:
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
    with state._lock:
        state.benchmarks[benchmark_id] = benchmark

    try:
        # Step 1: Generate world if requested
        if config.get("generate", False):
            with state._lock:
                benchmark["current_node"] = "generating..."
            generate_world(
                seed=config.get("seed", 42),
                difficulty=config.get("difficulty", 5),
                node_count=config.get("node_count", 1000),
            )

        if state.graph is None:
            with state._lock:
                benchmark["status"] = "FAILED"
                benchmark["completed_at"] = datetime.now().isoformat()
            return

        # Step 2: Load FULL graph into GraphReasoner ONCE
        with state._lock:
            benchmark["current_node"] = "loading graph..."
        graph_dict = _networkx_to_reasoner_dict(state.graph, subject_id=None)
        reasoner = GraphReasoner()
        reasoner.load_from_dict(graph_dict)

        # Step 3: Build target node list and typology map
        all_node_ids = sorted(str(n) for n in state.graph.nodes())
        with state._lock:
            benchmark["total_count"] = len(all_node_ids)
        typology_map = _build_expected_typology_map(state.ground_truth)

        # Step 4: Determine currency from jurisdiction
        currency = "INR" if config.get("jurisdiction") == "fiu_ind" else "USD"
        hop_depth = config.get("hop_depth", 3)
        node_results: list[dict] = []
        t_total_start = time.time()

        participation: dict[str, set[str]] = {}
        seen_structuring: set[tuple] = set()
        seen_layering: set[tuple[str, ...]] = set()
        # Fast node-local sweep attributes deduplicated findings to participants;
        # kept distinct from full neighborhood discovery via evaluation_unit.
        for idx, node_id in enumerate(all_node_ids):
            expected = typology_map.get(node_id, "NONE")
            is_crime = expected != "NONE"

            t0 = time.time()
            try:
                s_patterns = find_structuring_patterns(reasoner, node_id, currency=currency)
                l_result = detect_layering(reasoner, node_id, max_depth=hop_depth, currency=currency)
                status = "COMPLETE"
                coverage_status = reasoner.coverage["status"]
                for pattern in s_patterns:
                    finding_key = (
                        pattern.target_node, pattern.currency, pattern.mode,
                        pattern.window_start, pattern.window_end,
                        tuple(tx["tx_id"] for tx in pattern.qualifying_transactions),
                    )
                    if finding_key not in seen_structuring:
                        seen_structuring.add(finding_key)
                        for participant in [pattern.target_node, *pattern.counterpart_nodes]:
                            participation.setdefault(participant, set()).add("STRUCTURING")
                for chain in l_result.chains:
                    chain_key = tuple(tx["tx_id"] for tx in chain.chain_transactions)
                    if chain_key not in seen_layering:
                        seen_layering.add(chain_key)
                        for participant in chain.chain_nodes:
                            participation.setdefault(participant, set()).add("LAYERING")

                s_detected = bool(s_patterns)
                l_detected = l_result.detected

                if s_detected and l_detected:
                    detected = "BOTH"
                elif s_detected:
                    detected = "STRUCTURING"
                elif l_detected:
                    detected = "LAYERING"
                else:
                    detected = "NONE"

                s_conf = max((float(p.confidence) for p in s_patterns), default=0.0)
                l_conf = float(l_result.confidence) if l_detected else 0.0
                confidence = max(s_conf, l_conf)

            except Exception as e:
                logger.warning("Fast sweep failed for node %s: %s", node_id, type(e).__name__)
                status = "FAILED"
                coverage_status = "NOT_EVALUATED"
                detected = None
                confidence = 0.0

            duration_ms = int((time.time() - t0) * 1000)
            correct = _is_detection_correct(expected, detected) if status == "COMPLETE" and coverage_status == "COMPLETE" else None

            node_results.append({
                "node_id": node_id,
                "status": status,
                "coverage_status": coverage_status,
                "is_crime_node": is_crime,
                "expected_typology": expected,
                "detected_typology": detected,
                "correct": correct,
                "confidence": confidence,
                "investigation_case_id": f"fast-{benchmark_id[:8]}-{idx}",
                "assessment_score": None,
                "duration_ms": duration_ms,
                "entity_precision": None,
                "entity_recall": None,
                "entity_f1": None,
            })

            # Update progress
            with state._lock:
                benchmark["completed_count"] = idx + 1
                benchmark["current_node"] = node_id
                benchmark["progress"] = round(((idx + 1) / len(all_node_ids)) * 100, 1)
                benchmark["node_results"] = node_results

        sweep_complete = reasoner.coverage["status"] == "COMPLETE" and all(row["status"] == "COMPLETE" for row in node_results)
        for row in node_results:
            if row["status"] != "COMPLETE":
                continue
            kinds = participation.get(row["node_id"], set())
            row["detected_typology"] = "BOTH" if len(kinds) == 2 else next(iter(kinds), "NONE")
            row["coverage_status"] = "COMPLETE" if sweep_complete else "PARTIAL"
            row["correct"] = _is_detection_correct(row["expected_typology"], row["detected_typology"]) if sweep_complete else None
        total_duration_ms = int((time.time() - t_total_start) * 1000)
        aggregate = _compute_aggregate(
            node_results, total_duration_ms, evaluation_unit="fast_node_local_sweep",
        )

        with state._lock:
            benchmark["status"] = "COMPLETE"
            benchmark["aggregate"] = aggregate
            benchmark["node_results"] = node_results
            benchmark["completed_at"] = datetime.now().isoformat()

        logger.info(
            "Fast benchmark %s complete: %d nodes in %.1fs, detection_rate=%.2f%%, FPR=%.2f%%",
            benchmark_id, len(all_node_ids),
            total_duration_ms / 1000,
            (aggregate["crime_detection_rate"] or 0) * 100,
            (aggregate["false_positive_rate"] or 0) * 100,
        )

    except Exception as e:
        logger.error("Fast benchmark %s failed: %s", benchmark_id, e)
        with state._lock:
            benchmark["status"] = "FAILED"
            benchmark["completed_at"] = datetime.now().isoformat()
