"""Investigation pipeline — real LangGraph 8-node state machine from tracer_agent.

v8.0: Replaced manual 320-line pipeline with the real LangGraph workflow from
tracer_agent/src/core/decision_loop.py. The argus-app backend now acts as a
facade that pre-populates the graph_fragment from in-memory Forge data, invokes
the authentic Tracer workflow, and translates results for the frontend API.

The bridge function _networkx_to_reasoner_dict() is preserved for Forge→Tracer
schema mapping (field name remapping, entity_type normalization, timestamp
conversion, BFS reachability).
"""
import hashlib
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any

import networkx as nx

from ..models.state import get_state
from .tracer_service import (
    build_workflow, InvestigationState,
    GraphReasoner, detect_structuring, detect_layering,
    EvidenceSynthesizer, SARDraft, mechanical_sar_template,
)

logger = logging.getLogger(__name__)

# v5.0 D-48: entity_type remapping (FORGE → TRACER proto values)
_ENTITY_TYPE_MAP = {"person": "individual", "company": "business"}


def _networkx_to_reasoner_dict(
    graph: nx.MultiDiGraph,
    subject_id: str | None = None,
    hop_depth: int = 3,
) -> dict:
    """Convert FORGE NetworkX graph to TRACER GraphReasoner dict format.

    v5.0: entity_type remapping (D-48), self-loop documentation (D-54).
    v8.0: Includes text_evidence from AppState for evidence synthesis.
    Field name mapping: see APPENDIX C in build plan.
    """
    from datetime import datetime as dt_cls

    # BFS to find reachable nodes within hop_depth
    if subject_id is not None:
        resolved = None
        for candidate in [subject_id, int(subject_id) if subject_id.isdigit() else None]:
            if candidate is not None and candidate in graph:
                resolved = candidate
                break
        if resolved is None:
            return {"transactions": [], "nodes": {}}

        reachable = {resolved}
        queue = deque([(resolved, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= hop_depth:
                continue
            # D-54: self-loops cause node as own neighbor; visited set prevents re-processing
            for neighbor in set(graph.successors(node)) | set(graph.predecessors(node)):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append((neighbor, depth + 1))
    else:
        reachable = set(graph.nodes())

    # Build transactions with FIELD NAME MAPPING
    transactions = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        if u not in reachable and v not in reachable:
            continue
        amount = data.get("amount", 0)
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        ts = data.get("timestamp", 0)
        if isinstance(ts, dt_cls):
            ts = int(ts.timestamp())
        elif isinstance(ts, str):
            try:
                ts = int(dt_cls.fromisoformat(ts).timestamp())
            except (ValueError, TypeError):
                ts = 0
        elif not isinstance(ts, int):
            ts = 0

        transactions.append({
            "id": str(data.get("transaction_id", f"txn_{u}_{v}_{key}")),
            "source_node": str(u),
            "target_node": str(v),
            "amount": amount,
            "currency": data.get("currency", "USD"),
            "timestamp": ts,
            "type": str(data.get("transaction_type", "WIRE")).upper(),
            "reference": "",
            "branch_code": "",
        })

    # Build nodes with FIELD NAME MAPPING
    nodes = {}
    for node_id in sorted(reachable, key=str):
        data = graph.nodes.get(node_id, {})
        sid = str(node_id)
        risk_raw = data.get("risk_score", 0.5)
        raw_et = data.get("entity_type", "individual")
        nodes[sid] = {
            "id": sid,
            "name": data.get("name", f"Entity {node_id}"),
            "entity_type": _ENTITY_TYPE_MAP.get(raw_et, raw_et),
            "jurisdiction": data.get("country", "US"),
            "account_id": sid,
            "ifsc_code": data.get("ifsc_code", ""),
            "pan_number": data.get("pan_number", ""),
            "address": data.get("address", ""),
            "risk_rating": "high" if risk_raw > 0.7 else ("medium" if risk_raw > 0.3 else "low"),
            "swift_code": data.get("swift", ""),
        }

    return {"transactions": transactions, "nodes": nodes}


def _inject_text_evidence(graph_dict: dict, subject_id: str) -> dict:
    """Inject text evidence from AppState into the graph fragment.

    The LangGraph synthesize_evidence node reads text_evidence from
    graph_fragment. This bridge injects evidence documents so the
    real Tracer evidence synthesis pipeline can process them.
    """
    state = get_state()
    text_evidence = []
    for doc in state.evidence_documents:
        doc_subject = str(doc.get("subject_id", ""))
        # Include evidence related to the subject or untagged evidence
        if doc_subject == str(subject_id) or not doc_subject:
            text_evidence.append({
                "id": doc.get("id", f"ev-{uuid.uuid4().hex[:8]}"),
                "source_type": doc.get("type", "document"),
                "content": doc.get("body", doc.get("narrative", doc.get("content", ""))),
                "associated_entity": str(doc.get("subject_id", "")),
                "timestamp": int(doc.get("timestamp", 0)) if doc.get("timestamp") else 0,
            })
    graph_dict["text_evidence"] = text_evidence
    return graph_dict


def _langgraph_state_to_response(
    result_state: dict,
    case_id: str,
    subject_id: str,
    jurisdiction: str,
) -> dict[str, Any]:
    """Translate LangGraph InvestigationState → frontend API response format.

    Maps the LangGraph state fields to the response dict the frontend expects,
    including reconstructed pipeline steps for the PipelineTracker component.
    """
    typology = result_state.get("detected_typology", "NONE")
    involved = sorted(result_state.get("involved_entities", []))
    confidence = result_state.get("confidence_score", 0.0)
    sar_narrative = result_state.get("sar_narrative", "") or ""
    sar_draft = result_state.get("sar_draft")
    evidence_package = result_state.get("evidence_package") or {}
    detection_results = result_state.get("detection_results") or {}
    validation_result = result_state.get("validation_result") or {}
    retry_count = result_state.get("retry_count", 0)
    status = result_state.get("status", "FAILED")
    error_message = result_state.get("error_message")

    # Reconstruct validation_errors from validation_result
    validation_errors = validation_result.get("errors", []) if not validation_result.get("passed", True) else []

    # Compute idempotency key (same formula as tracer_agent submit_result)
    idem_input = f"{case_id}{typology}{''.join(sorted(involved))}"
    idempotency_key = hashlib.sha256(idem_input.encode("utf-8")).hexdigest()

    # Reconstruct pipeline steps for the frontend PipelineTracker
    steps = _reconstruct_steps(result_state)

    # Determine SAR mode (LLM vs Mechanical)
    sar_mode = "none"
    if sar_draft:
        # If the narrative contains XML-like Five Ws tags without FinCEN/FIU header, it's mechanical
        if sar_narrative.startswith("<WHO>") or sar_narrative.startswith("═══"):
            sar_mode = "mechanical"
        else:
            sar_mode = "llm"

    return {
        "case_id": case_id,
        "subject_id": subject_id,
        "jurisdiction": jurisdiction,
        "status": status,
        "detected_typology": typology,
        "involved_entities": involved,
        "confidence_score": confidence,
        "sar_narrative": sar_narrative,
        "sar_draft": sar_draft,
        "sar_mode": sar_mode,
        "evidence_package": evidence_package,
        "detection_results": detection_results,
        "validation_errors": validation_errors,
        "validation_result": validation_result,
        "retry_count": retry_count,
        "idempotency_key": idempotency_key,
        "investigation_timestamp": result_state.get("investigation_timestamp", int(time.time())),
        "investigation_start": datetime.now().isoformat(),
        "steps": steps,
        "error": error_message,
    }


def _reconstruct_steps(result_state: dict) -> list[dict]:
    """Reconstruct pipeline steps from LangGraph result state.

    The LangGraph workflow doesn't track per-step timing, so we infer
    step statuses from the final state. This provides the frontend
    PipelineTracker with the data it needs.
    """
    status = result_state.get("status", "FAILED")
    typology = result_state.get("detected_typology", "NONE")
    confidence = result_state.get("confidence_score", 0.0)
    validation = result_state.get("validation_result") or {}
    evidence = result_state.get("evidence_package") or {}
    sar_draft = result_state.get("sar_draft")
    graph = result_state.get("graph_fragment") or {}
    error = result_state.get("error_message")

    node_count = len(graph.get("nodes", {}))
    edge_count = len(graph.get("transactions", []))

    steps = [
        {"name": "receive", "status": "complete", "duration_ms": 0,
         "detail": f"Case {result_state.get('case_id', '')} created"},
    ]

    # Analyze step
    if status == "FAILED" and error and "graph" in error.lower():
        steps.append({"name": "analyze", "status": "failed", "duration_ms": 0, "detail": error})
        return steps
    steps.append({"name": "analyze", "status": "complete", "duration_ms": 0,
                   "detail": f"{node_count} nodes, {edge_count} edges"})

    # Detect step
    if status == "FAILED" and error and "detection" in error.lower():
        steps.append({"name": "detect", "status": "failed", "duration_ms": 0, "detail": error})
        return steps
    detection = result_state.get("detection_results") or {}
    s_count = len(detection.get("structuring_hits", []))
    l_count = len(detection.get("layering_hits", []))
    steps.append({"name": "detect", "status": "complete", "duration_ms": 0,
                   "detail": f"{typology} ({s_count}S, {l_count}L)"})

    # Synthesize step
    steps.append({"name": "synthesize", "status": "complete", "duration_ms": 0,
                   "detail": evidence.get("verdict", "NOT_APPLICABLE")})

    # Compute step
    gate = "PASS" if confidence >= 0.5 else "FAIL"
    steps.append({"name": "compute", "status": "complete", "duration_ms": 0,
                   "detail": f"confidence={confidence:.2f}, gate={gate}"})

    # Draft step
    if typology != "NONE" and confidence >= 0.5:
        sar_len = len(result_state.get("sar_narrative", "") or "")
        retry_count = result_state.get("retry_count", 0)
        detail = f"{sar_len} chars"
        if retry_count > 0:
            detail += f" (retries={retry_count})"
        steps.append({"name": "draft", "status": "complete", "duration_ms": 0, "detail": detail})

        # Validate step
        val_status = "complete" if validation.get("passed", True) else "warning"
        val_errors = validation.get("errors", [])
        steps.append({"name": "validate", "status": val_status, "duration_ms": 0,
                       "detail": f"{len(val_errors)} issues" if val_errors else "passed"})
    else:
        steps.append({"name": "draft", "status": "complete", "duration_ms": 0, "detail": "skipped"})
        steps.append({"name": "validate", "status": "complete", "duration_ms": 0, "detail": "skipped"})

    # Submit step
    idem_key = result_state.get("idempotency_key", "")
    if not idem_key:
        involved = sorted(result_state.get("involved_entities", []))
        idem_input = f"{result_state.get('case_id', '')}{typology}{''.join(involved)}"
        idem_key = hashlib.sha256(idem_input.encode("utf-8")).hexdigest()
    steps.append({"name": "submit", "status": "complete", "duration_ms": 0,
                   "detail": f"idem_key={idem_key[:16]}..."})

    return steps


def run_investigation(
    case_id: str,
    subject_id: str,
    hop_depth: int = 3,
    jurisdiction: str = "fincen",
) -> dict[str, Any]:
    """Run the full 8-step investigation using the real LangGraph workflow.

    This function:
    1. Converts in-memory Forge graph → TRACER dict format (BFS reachability)
    2. Injects text evidence from AppState
    3. Pre-populates graph_fragment in LangGraph state (unified mode)
    4. Invokes the real 8-node LangGraph decision loop
    5. Translates result → frontend API response format
    """
    state = get_state()
    if state.graph is None:
        return {"case_id": case_id, "status": "FAILED", "error": "No graph loaded", "steps": []}

    # Step 1: Convert Forge graph → TRACER dict format
    graph_dict = _networkx_to_reasoner_dict(state.graph, subject_id, hop_depth)

    if not graph_dict.get("transactions"):
        return {
            "case_id": case_id,
            "subject_id": subject_id,
            "status": "FAILED",
            "error": f"Subject {subject_id} not found or no transactions within {hop_depth} hops",
            "steps": [{"name": "analyze", "status": "failed", "duration_ms": 0,
                        "detail": f"Subject {subject_id} not reachable"}],
        }

    # Step 2: Inject text evidence from AppState
    graph_dict = _inject_text_evidence(graph_dict, subject_id)

    # Step 3: Build initial LangGraph state with pre-populated graph_fragment
    initial_state: InvestigationState = {
        "case_id": case_id,
        "subject_id": str(subject_id),
        "jurisdiction": jurisdiction,
        "hop_depth": hop_depth,
        "graph_fragment": graph_dict,
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
        "status": "PENDING",
        "retry_count": 0,
        "error_message": None,
    }

    # Step 4: Run the real LangGraph 8-node workflow
    try:
        workflow = build_workflow()
        result_state = workflow.invoke(initial_state)
    except Exception as e:
        logger.error("LangGraph workflow failed for case %s: %s", case_id, e, exc_info=True)
        result_state = {
            **initial_state,
            "status": "FAILED",
            "error_message": f"LangGraph workflow failed: {e}",
        }

    # Step 5: Translate → frontend API response format
    result = _langgraph_state_to_response(result_state, case_id, str(subject_id), jurisdiction)

    # Store in AppState for retrieval by GET endpoints
    state.investigations[case_id] = result
    return result
