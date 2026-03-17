"""Investigation pipeline — 8-step state machine matching Architecture S3.

v5.0 D-47: Complete implementation (v4.0 had skeleton comments only).
v6.0: No functional changes. Bridge logic and pipeline are production-verified.
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


def run_investigation(
    case_id: str,
    subject_id: str,
    hop_depth: int = 3,
    jurisdiction: str = "fincen",
) -> dict[str, Any]:
    """Run the full 8-step investigation pipeline.

    Returns a result dict stored in AppState.investigations[case_id].
    """
    state = get_state()
    if state.graph is None:
        return {"case_id": case_id, "status": "FAILED", "error": "No graph loaded"}

    steps: list[dict] = []
    result: dict[str, Any] = {
        "case_id": case_id,
        "subject_id": subject_id,
        "jurisdiction": jurisdiction,
        "status": "IN_PROGRESS",
        "steps": steps,
    }

    # ── Step 1: RECEIVE ──
    t0 = time.time()
    result["investigation_start"] = datetime.now().isoformat()
    steps.append({"name": "receive", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"Case {case_id} created"})

    # ── Step 2: ANALYZE ──
    t0 = time.time()
    try:
        graph_dict = _networkx_to_reasoner_dict(state.graph, subject_id, hop_depth)
        reasoner = GraphReasoner()
        reasoner.load_from_dict(graph_dict)
        steps.append({"name": "analyze", "status": "complete",
                       "duration_ms": int((time.time() - t0) * 1000),
                       "detail": f"{reasoner.get_node_count()} nodes, {reasoner.get_edge_count()} edges"})
    except Exception as e:
        steps.append({"name": "analyze", "status": "failed",
                       "duration_ms": int((time.time() - t0) * 1000),
                       "detail": str(e)})
        result["status"] = "FAILED"
        result["error"] = f"Graph analysis failed: {e}"
        state.investigations[case_id] = result
        return result

    # ── Step 3: DETECT ──
    t0 = time.time()
    currency = "INR" if jurisdiction == "fiu_ind" else "USD"
    structuring_hits: list[dict] = []
    layering_hits: list[dict] = []
    all_criminal_nodes: set[str] = set()

    for node_id in reasoner.get_all_node_ids():
        s_result = detect_structuring(reasoner, node_id, currency=currency)
        if s_result.detected:
            structuring_hits.append({
                "node": node_id, "mode": s_result.mode,
                "sources": s_result.counterpart_nodes,
                "tx_count": s_result.transaction_count,
                "total": str(s_result.total_amount), "currency": s_result.currency,
                "transactions": [tx["tx_id"] for tx in s_result.qualifying_transactions],
            })
            all_criminal_nodes.add(node_id)
            all_criminal_nodes.update(s_result.counterpart_nodes)

        l_result = detect_layering(reasoner, node_id, max_depth=hop_depth, currency=currency)
        if l_result.detected:
            for chain in l_result.chains:
                layering_hits.append({
                    "start_node": node_id, "chain_nodes": chain.chain_nodes,
                    "hop_count": chain.hop_count, "avg_decay": str(chain.avg_decay_rate),
                    "currency": chain.currency,
                    "transactions": [tx["tx_id"] for tx in chain.chain_transactions],
                })
                all_criminal_nodes.update(chain.chain_nodes)

    has_s = len(structuring_hits) > 0
    has_l = len(layering_hits) > 0
    typology = "BOTH" if has_s and has_l else ("STRUCTURING" if has_s else ("LAYERING" if has_l else "NONE"))
    involved = sorted(all_criminal_nodes)
    detection_results = {"typology": typology, "structuring_hits": structuring_hits, "layering_hits": layering_hits}

    steps.append({"name": "detect", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"{typology} ({len(structuring_hits)}S, {len(layering_hits)}L)"})

    # ── Step 4: SYNTHESIZE ──
    t0 = time.time()
    evidence_package = {"verdict": "NOT_APPLICABLE", "discrepancies": []}
    if typology != "NONE" and state.evidence_documents:
        try:
            synthesizer = EvidenceSynthesizer()
            text_evidence = [
                {"content": doc.get("body", doc.get("narrative", "")), **doc}
                for doc in state.evidence_documents
                if str(doc.get("subject_id", "")) == str(subject_id) or not doc.get("subject_id")
            ]
            total_inflow = Decimal("0")
            for tx in graph_dict.get("transactions", []):
                if tx["target_node"] == str(subject_id):
                    total_inflow += tx["amount"]
            ledger_data = {"total_inflow": total_inflow, "entity_id": str(subject_id),
                           "transactions": graph_dict.get("transactions", [])}
            ev_result = synthesizer.synthesize(ledger_data, text_evidence, currency=currency)
            evidence_package = {"verdict": ev_result.verdict, "reasoning": ev_result.reasoning,
                                "discrepancies": ev_result.discrepancies,
                                "amounts": [str(a) for a in ev_result.extracted_amounts]}
        except Exception as e:
            logger.warning("Evidence synthesis failed: %s", e)
            evidence_package = {"verdict": "INSUFFICIENT_DATA", "discrepancies": []}

    steps.append({"name": "synthesize", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": evidence_package["verdict"]})

    # ── Step 5: COMPUTE CONFIDENCE ──
    t0 = time.time()
    CORROBORATING = frozenset({"CORROBORATED", "SUSPICIOUS_DISCREPANCY", "CONFIRMED", "PARTIAL_MATCH"})
    if typology == "NONE":
        confidence = 0.0
    else:
        base = 0.6 if typology == "BOTH" else 0.3
        evidence_boost = 0.2 if evidence_package.get("verdict", "") in CORROBORATING else 0.0
        discrepancy_boost = 0.2 if len(evidence_package.get("discrepancies", [])) > 0 else 0.0
        confidence = min(1.0, base + evidence_boost + discrepancy_boost)

    if confidence < 0.5:
        typology = "NONE"
        detection_results["typology"] = "NONE"

    steps.append({"name": "compute", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"confidence={confidence:.2f}, gate={'PASS' if confidence >= 0.5 else 'FAIL'}"})

    # ── Step 6: DRAFT SAR ──
    t0 = time.time()
    sar_narrative = ""
    sar_draft_dict = None
    if typology != "NONE":
        try:
            draft = mechanical_sar_template(detection_results, graph_dict, jurisdiction)
            sar_narrative = draft.raw_narrative
            sar_draft_dict = {"who": draft.who, "what": draft.what, "where": draft.where,
                              "when": draft.when, "why": draft.why, "cited_tx_ids": draft.cited_tx_ids}
        except Exception as e:
            logger.error("SAR drafting failed: %s", e)
            sar_narrative = f"SAR generation failed: {e}"

    steps.append({"name": "draft", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"{len(sar_narrative)} chars" if sar_narrative else "skipped"})

    # ── Step 7: VALIDATE SAR ──
    t0 = time.time()
    validation_errors: list[str] = []
    if sar_draft_dict:
        graph_nodes = set(graph_dict.get("nodes", {}).keys())
        graph_tx_ids = {tx["id"] for tx in graph_dict.get("transactions", [])}
        for cited_tx in sar_draft_dict.get("cited_tx_ids", []):
            if cited_tx not in graph_tx_ids:
                validation_errors.append(f"Hallucinated TX: {cited_tx}")
        for entity in sar_draft_dict.get("who", "").split(", "):
            entity = entity.strip()
            if entity and entity != "Entities not identified" and entity not in graph_nodes:
                validation_errors.append(f"Hallucinated entity: {entity}")

    steps.append({"name": "validate",
                   "status": "complete" if not validation_errors else "warning",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"{len(validation_errors)} issues" if validation_errors else "passed"})

    # ── Step 8: SUBMIT ──
    t0 = time.time()
    idem_input = f"{case_id}{typology}{''.join(sorted(involved))}"
    idempotency_key = hashlib.sha256(idem_input.encode("utf-8")).hexdigest()

    result.update({
        "status": "COMPLETE",
        "detected_typology": typology,
        "involved_entities": involved,
        "confidence_score": confidence,
        "sar_narrative": sar_narrative,
        "sar_draft": sar_draft_dict,
        "evidence_package": evidence_package,
        "detection_results": detection_results,
        "validation_errors": validation_errors,
        "idempotency_key": idempotency_key,
        "investigation_timestamp": int(time.time()),
        "steps": steps,
    })

    steps.append({"name": "submit", "status": "complete",
                   "duration_ms": int((time.time() - t0) * 1000),
                   "detail": f"idem_key={idempotency_key[:16]}..."})

    state.investigations[case_id] = result
    return result
