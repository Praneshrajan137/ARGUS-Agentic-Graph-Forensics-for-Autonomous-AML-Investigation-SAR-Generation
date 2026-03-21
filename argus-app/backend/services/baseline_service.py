"""Baseline agent adapter — subclasses tracer_agent's BaselinePurpleAgent for in-process use.

The baseline agent is an intentionally naive investigator used for comparison
against the real Tracer. It uses simple heuristics (count incoming edges,
check amounts) instead of the full LangGraph workflow.

This adapter subclasses BaselinePurpleAgent and overrides the HTTP-based
tool methods (get_transactions, get_connections) with direct in-memory
AppState reads, allowing the baseline agent to run within the unified deployment.
"""
import logging
from typing import Any

from tracer_agent.src.baseline_agent import BaselinePurpleAgent

from ..models.state import get_state

logger = logging.getLogger(__name__)


class InProcessBaselineAgent(BaselinePurpleAgent):
    """Baseline agent that reads from in-memory AppState instead of HTTP.

    Subclasses the real BaselinePurpleAgent from tracer_agent/src/baseline_agent.py,
    overriding get_transactions and get_connections to read from the unified
    backend's in-memory Forge graph instead of making HTTP calls to Forge.

    All heuristic logic (simple_structuring_heuristic, simple_layering_heuristic,
    run_investigation, _generate_narrative) is inherited unchanged from the
    real BaselinePurpleAgent.
    """

    def __init__(self):
        # Initialize parent without a real Forge URL (we override HTTP methods)
        super().__init__(forge_agent_url="http://in-process", participant_id="baseline_tracer_agent")

    def get_transactions(self, account_id: str, limit: int = 100) -> list[dict]:
        """Override: read transactions from in-memory graph instead of HTTP."""
        self.tool_calls += 1
        state = get_state()
        if state.graph is None:
            return []

        # Resolve node_id
        node_id = account_id
        if node_id not in state.graph:
            try:
                node_id = int(account_id)
            except (ValueError, TypeError):
                return []
        if node_id not in state.graph:
            return []

        transactions = []
        # Incoming
        for pred in state.graph.predecessors(node_id):
            for _, data in state.graph[pred][node_id].items():
                transactions.append({
                    "source": str(pred),
                    "target": str(node_id),
                    "amount": float(data.get("amount", 0)),
                    "transaction_type": data.get("transaction_type", "wire"),
                    "timestamp": data.get("timestamp", 0),
                })
        # Outgoing
        for succ in state.graph.successors(node_id):
            for _, data in state.graph[node_id][succ].items():
                transactions.append({
                    "source": str(node_id),
                    "target": str(succ),
                    "amount": float(data.get("amount", 0)),
                    "transaction_type": data.get("transaction_type", "wire"),
                    "timestamp": data.get("timestamp", 0),
                })

        return transactions[:limit]

    def get_connections(self, account_id: str) -> list[dict]:
        """Override: read connections from in-memory graph instead of HTTP."""
        self.tool_calls += 1
        state = get_state()
        if state.graph is None:
            return []

        node_id = account_id
        if node_id not in state.graph:
            try:
                node_id = int(account_id)
            except (ValueError, TypeError):
                return []
        if node_id not in state.graph:
            return []

        connections = []
        predecessors = set(state.graph.predecessors(node_id))
        successors = set(state.graph.successors(node_id))

        for pred in predecessors:
            rel = "both" if pred in successors else "sender"
            connections.append({"node_id": str(pred), "relationship": rel})
        for succ in successors:
            if succ not in predecessors:
                connections.append({"node_id": str(succ), "relationship": "receiver"})

        return connections

    def get_evidence(self, keyword=None, limit: int = 50) -> list[dict]:
        """Override: read evidence from in-memory AppState instead of HTTP."""
        self.tool_calls += 1
        state = get_state()
        docs = state.evidence_documents
        if keyword:
            docs = [d for d in docs if keyword.lower() in str(d).lower()]
        return docs[:limit]

    def get_kyc_profile(self, account_id: str) -> dict:
        """Override: read KYC profile from in-memory graph node attributes."""
        self.tool_calls += 1
        state = get_state()
        if state.graph is None:
            return {}

        node_id = account_id
        if node_id not in state.graph:
            try:
                node_id = int(account_id)
            except (ValueError, TypeError):
                return {}
        if node_id not in state.graph:
            return {}

        data = state.graph.nodes.get(node_id, {})
        return {
            "account_id": str(node_id),
            "name": data.get("name", f"Entity {node_id}"),
            "entity_type": data.get("entity_type", "individual"),
            "country": data.get("country", "US"),
            "risk_score": data.get("risk_score", 0.5),
        }


def run_baseline_investigation(
    subject_id: str,
    hop_depth: int = 3,
) -> dict[str, Any]:
    """Run a baseline investigation for comparison against the real Tracer."""
    agent = InProcessBaselineAgent()
    result = agent.run_investigation([str(subject_id)])
    return {
        "mode": "baseline",
        "subject_id": str(subject_id),
        "tool_calls": agent.tool_calls,
        **result,
    }
