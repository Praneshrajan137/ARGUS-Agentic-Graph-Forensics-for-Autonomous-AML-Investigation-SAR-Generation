"""TRACER detection algorithms — copied from purple_agent for zero-import-risk integration.

v5.0: Constant remapping applied for FORGE config compatibility.
v6.0: Unchanged from v5.0 — all detection logic is pure Python with Decimal arithmetic.

Components copied:
  1. GraphReasoner        (from purple_agent/src/core/graph_reasoner.py)
  2. StructuringResult    (from purple_agent/src/core/heuristics/structuring.py)
  3. detect_structuring   (from purple_agent/src/core/heuristics/structuring.py)
  4. LayeringChain/Result (from purple_agent/src/core/heuristics/layering.py)
  5. detect_layering      (from purple_agent/src/core/heuristics/layering.py)
  6. SARDraft             (from purple_agent/src/core/sar_drafter.py)
  7. mechanical_sar_template (from purple_agent/src/core/sar_drafter.py)
  8. EvidenceResult       (from purple_agent/src/core/evidence_synthesizer.py)
  9. EvidenceSynthesizer  (from purple_agent/src/core/evidence_synthesizer.py)
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

import networkx as nx

# ═══ IMPORTS FROM FORGE CONFIG (all safe, no side effects) ═══
from src.config import (
    # Structuring (names match TRACER exactly)
    STRUCTURING_MIN_AMOUNT_USD, STRUCTURING_MAX_AMOUNT_USD,
    CTR_THRESHOLD_USD, STRUCTURING_MIN_COUNT,
    STRUCTURING_TIME_WINDOW_SECONDS,
    STRUCTURING_MIN_AMOUNT_INR, STRUCTURING_MAX_AMOUNT_INR,
    CTR_THRESHOLD_INR, STRUCTURING_MIN_COUNT_INR,
    STRUCTURING_TIME_WINDOW_SECONDS_INR,
    # Layering (FORGE names — aliases below)
    LAYERING_MIN_DECAY, LAYERING_MAX_DECAY,
    DECAY_TOLERANCE, MIN_CHAIN_LENGTH,
    MAX_DFS_DEPTH, MAX_HOP_DELAY_SECONDS,
    # Graph safety
    MAX_NODE_DEGREE, MAX_PATHS_PER_SEARCH,
    # Evidence synthesis
    AMOUNT_PATTERNS,
    IFSC_SEARCH_COMPILED, PAN_SEARCH_COMPILED,
    SWIFT_SEARCH_COMPILED, IBAN_SEARCH_COMPILED,
    EVIDENCE_DISCREPANCY_THRESHOLD_USD, EVIDENCE_DISCREPANCY_THRESHOLD_INR,
    # SAR formatting
    TIMEZONE_FINCEN, TIMEZONE_FIU_IND,
)

# ═══ CONSTANT REMAPPING (v5.0 D-44 fix) ═══
# FORGE uses LAYERING_MIN_DECAY / LAYERING_MAX_DECAY (Decimal).
# TRACER code uses DECAY_RATE_MIN / DECAY_RATE_MAX.
# These aliases bridge the naming gap.
DECAY_RATE_MIN = LAYERING_MIN_DECAY   # Decimal("0.02")
DECAY_RATE_MAX = LAYERING_MAX_DECAY   # Decimal("0.05")

# TRACER-only constants not in FORGE config — defined locally
SPACY_MODEL_NAME = "en_core_web_sm"
VELOCITY_THRESHOLD = Decimal("5000")

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# GRAPH REASONER (from purple_agent/src/core/graph_reasoner.py)
# ═══════════════════════════════════════════════════════════════════

class GraphReasoner:
    """The forensic graph reasoning engine.

    Uses MultiDiGraph to preserve all parallel transactions between entities.
    Provides BFS (1-hop) for structuring fan-in/fan-out detection and
    DFS (chain traversal) for layering detection with decay analysis.

    v8.0: Total-degree super-node protection (Rule 21). Empty TX rejection (Rule 19).
    v7.0: Full Architecture S4 Step 2.5 ingestion validation suite.
    v6.1: Iterative DFS with explicit stack (Rule 20). NaN guard (Rule 2).
    """

    def __init__(self) -> None:
        """Initialize with empty MultiDiGraph."""
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def _check_super_node(self, node_id: str) -> bool:
        """Check if a node exceeds the super-node degree limit.

        v8.0 [P4v8-06]: Uses TOTAL degree (in_degree + out_degree).
        """
        total_degree = self.graph.degree(node_id)
        if total_degree > MAX_NODE_DEGREE:
            logger.warning(
                f"Super-node detected: {node_id} has total degree {total_degree} "
                f"(limit: {MAX_NODE_DEGREE}). Skipping to prevent OOM. "
                f"(in={self.graph.in_degree(node_id)}, "
                f"out={self.graph.out_degree(node_id)})"
            )
            return True
        return False

    def load_from_dict(self, graph_data: dict) -> None:
        """Load a graph from dict (deserialized Protobuf or test fixture).

        Implements the COMPLETE Architecture S4 Step 2.5 validation suite.
        """
        if self.graph.number_of_nodes() > 0:
            logger.warning(
                "load_from_dict called on non-empty graph "
                f"({self.graph.number_of_nodes()} nodes, "
                f"{self.graph.number_of_edges()} edges). Clearing all data."
            )
        self.graph.clear()

        transactions = graph_data.get("transactions", [])
        if not transactions:
            raise ValueError(
                "GraphFragment contains zero transactions. "
                "An empty graph produces false negatives (clearing criminals). "
                "This is treated as a fetch failure per Rule 19."
            )

        for node_id, attrs in sorted(graph_data.get("nodes", {}).items()):
            self.graph.add_node(node_id, **attrs)

        seen_tx_ids: set[str] = set()

        for tx in transactions:
            tx_id = tx["id"]

            if tx_id in seen_tx_ids:
                logger.warning(
                    f"Duplicate tx_id '{tx_id}': keeping first occurrence, "
                    f"skipping duplicate (source={tx['source_node']}, "
                    f"target={tx['target_node']}, amount={tx['amount']}). "
                    f"Rule 27: NEVER silently overwrite."
                )
                continue
            seen_tx_ids.add(tx_id)

            if not isinstance(tx["amount"], Decimal):
                raise TypeError(
                    f"Transaction {tx_id}: amount must be Decimal, "
                    f"got {type(tx['amount']).__name__} with value {tx['amount']}"
                )

            if not tx["amount"].is_finite():
                raise ValueError(
                    f"Transaction {tx_id}: amount must be finite, "
                    f"got {tx['amount']} (NaN and Infinity are forbidden)"
                )

            raw_currency = tx.get("currency")
            if raw_currency is not None and raw_currency == "":
                raise ValueError(
                    f"Transaction {tx_id}: currency must be non-empty. "
                    f"Provide a valid ISO currency code (e.g., 'USD', 'INR')."
                )
            currency = raw_currency or "USD"

            timestamp = tx.get("timestamp", 0)
            if timestamp <= 0:
                logger.warning(
                    f"Transaction {tx_id}: timestamp={timestamp} is <= 0. "
                    f"Proceeding with defensive default (not rejecting)."
                )

            source = tx["source_node"]
            target = tx["target_node"]
            if source == target:
                logger.info(
                    f"Transaction {tx_id}: self-loop detected "
                    f"(source_node == target_node == '{source}'). "
                    f"Retaining for analysis."
                )

            self.graph.add_edge(
                source,
                target,
                key=tx_id,
                tx_id=tx_id,
                amount=tx["amount"],
                currency=currency,
                timestamp=timestamp,
                tx_type=tx.get("type", "WIRE"),
                branch_code=tx.get("branch_code", ""),
            )

        if self.graph.number_of_edges() == 0:
            raise ValueError(
                f"GraphFragment contained {len(transactions)} transaction(s) but "
                f"zero edges were loaded (all may have been duplicates). "
                f"An empty graph produces false negatives per Rule 19."
            )

    def get_1hop_incoming(self, node_id: str) -> list[dict]:
        """BFS 1-hop: Get all incoming transactions to a node."""
        if node_id not in self.graph:
            return []
        if self._check_super_node(node_id):
            return []

        incoming: list[dict] = []
        for predecessor in self.graph.predecessors(node_id):
            for edge_key, edge_data in self.graph[predecessor][node_id].items():
                incoming.append({
                    "tx_id": edge_data["tx_id"],
                    "source_node": predecessor,
                    "target_node": node_id,
                    "amount": edge_data["amount"],
                    "currency": edge_data["currency"],
                    "timestamp": edge_data["timestamp"],
                    "tx_type": edge_data["tx_type"],
                    "branch_code": edge_data.get("branch_code", ""),
                })
        return sorted(incoming, key=lambda x: x["tx_id"])

    def get_1hop_outgoing(self, node_id: str) -> list[dict]:
        """BFS 1-hop: Get all outgoing transactions from a node."""
        if node_id not in self.graph:
            return []
        if self._check_super_node(node_id):
            return []

        outgoing: list[dict] = []
        for successor in self.graph.successors(node_id):
            for edge_key, edge_data in self.graph[node_id][successor].items():
                outgoing.append({
                    "tx_id": edge_data["tx_id"],
                    "source_node": node_id,
                    "target_node": successor,
                    "amount": edge_data["amount"],
                    "currency": edge_data["currency"],
                    "timestamp": edge_data["timestamp"],
                    "tx_type": edge_data["tx_type"],
                    "branch_code": edge_data.get("branch_code", ""),
                })
        return sorted(outgoing, key=lambda x: x["tx_id"])

    def dfs_trace_chains(
        self, start_node: str, max_depth: int | None = None
    ) -> list[list[dict]]:
        """DFS: Trace all outflow chains from start_node.

        Returns list of chains (each chain = list of transaction dicts).
        ITERATIVE implementation using explicit stack (Rule 20).
        """
        if max_depth is None:
            max_depth = MAX_DFS_DEPTH

        if start_node not in self.graph:
            return []

        all_chains: list[list[dict]] = []
        initial_visited = frozenset({start_node})
        stack: list[tuple[str, list[dict], frozenset, int]] = [
            (start_node, [], initial_visited, 0)
        ]

        while stack:
            if len(all_chains) >= MAX_PATHS_PER_SEARCH:
                break

            current_node, current_chain, visited, depth = stack.pop()

            if depth >= max_depth:
                if current_chain:
                    all_chains.append(current_chain)
                continue

            outgoing = self.get_1hop_outgoing(current_node)

            if not outgoing:
                if current_chain:
                    all_chains.append(current_chain)
                continue

            unvisited_txs = [
                tx for tx in outgoing
                if tx["target_node"] not in visited
            ]

            if not unvisited_txs:
                if current_chain:
                    all_chains.append(current_chain)
                continue

            for tx in reversed(unvisited_txs):
                if len(all_chains) >= MAX_PATHS_PER_SEARCH:
                    if current_chain:
                        all_chains.append(current_chain)
                    break

                next_node = tx["target_node"]
                new_chain = current_chain + [tx]
                new_visited = visited | {next_node}
                stack.append((next_node, new_chain, new_visited, depth + 1))

        if len(all_chains) >= MAX_PATHS_PER_SEARCH:
            logger.warning(
                f"DFS from {start_node}: path limit reached ({MAX_PATHS_PER_SEARCH}). "
                "Results are truncated."
            )

        return all_chains

    def get_node_attributes(self, node_id: str) -> dict | None:
        """Get attributes for a node, or None if not found."""
        if node_id not in self.graph:
            return None
        return dict(self.graph.nodes[node_id])

    def get_subgraph(self, node_ids: list[str]) -> nx.MultiDiGraph:
        """Extract a read-only COPY of the subgraph for the specified nodes."""
        valid_nodes = [n for n in node_ids if n in self.graph]
        return self.graph.subgraph(valid_nodes).copy()

    def get_all_node_ids(self) -> list[str]:
        """Return all node IDs sorted alphabetically (Rule 15)."""
        return sorted(self.graph.nodes())

    def has_node(self, node_id: str) -> bool:
        """Check whether a node ID exists in the graph."""
        return node_id in self.graph

    def get_edge_count(self) -> int:
        """Return total number of edges (transactions) in the graph."""
        return self.graph.number_of_edges()

    def get_node_count(self) -> int:
        """Return total number of nodes (entities) in the graph."""
        return self.graph.number_of_nodes()


# ═══════════════════════════════════════════════════════════════════
# STRUCTURING DETECTION (from purple_agent/src/core/heuristics/structuring.py)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StructuringResult:
    """Result of structuring detection on a single node."""
    detected: bool
    mode: str
    target_node: str
    counterpart_nodes: list[str] = field(default_factory=list)
    qualifying_transactions: list[dict] = field(default_factory=list)
    total_amount: Decimal = Decimal("0")
    transaction_count: int = 0
    currency: str = "USD"
    confidence: Decimal = Decimal("0")
    reasoning: str = ""

    @property
    def source_nodes(self) -> list[str]:
        """Backward-compatible alias for counterpart_nodes."""
        return self.counterpart_nodes


def _get_thresholds(currency: str) -> tuple[Decimal, Decimal, int, int]:
    """Get jurisdiction-specific thresholds."""
    if currency == "INR":
        return (
            STRUCTURING_MIN_AMOUNT_INR,
            STRUCTURING_MAX_AMOUNT_INR,
            STRUCTURING_MIN_COUNT_INR,
            STRUCTURING_TIME_WINDOW_SECONDS_INR,
        )
    return (
        STRUCTURING_MIN_AMOUNT_USD,
        STRUCTURING_MAX_AMOUNT_USD,
        STRUCTURING_MIN_COUNT,
        STRUCTURING_TIME_WINDOW_SECONDS,
    )


def _filter_by_currency(transactions: list[dict], currency: str) -> list[dict]:
    """Filter transactions to only those matching the target currency.

    v8.0 [P4v8-02]: Implements Rule 14.
    """
    return [tx for tx in transactions if tx.get("currency") == currency]


def _filter_qualifying_transactions(
    transactions: list[dict],
    min_amount: Decimal,
    max_amount: Decimal,
    time_window_seconds: int,
) -> list[dict]:
    """Filter transactions within the structuring amount range and time window."""
    if not transactions:
        return []

    amount_qualifying = [
        tx for tx in transactions
        if min_amount <= tx["amount"] <= max_amount
    ]
    if not amount_qualifying:
        return []

    latest_ts = max(tx["timestamp"] for tx in amount_qualifying)
    window_start = latest_ts - time_window_seconds

    return [tx for tx in amount_qualifying if tx["timestamp"] >= window_start]


def _compute_confidence(
    qualifying_count: int,
    unique_counterparts: int,
    min_count: int,
    time_window_seconds: int,
    qualifying_transactions: list[dict],
) -> Decimal:
    """Compute multi-factor confidence score for structuring detection."""
    count_factor = min(
        Decimal(str(qualifying_count)) / Decimal(str(min_count * 3)),
        Decimal("0.5"),
    )

    if qualifying_count > 0:
        diversity_factor = min(
            Decimal(str(unique_counterparts)) / Decimal(str(qualifying_count)),
            Decimal("1"),
        ) * Decimal("0.3")
    else:
        diversity_factor = Decimal("0")

    time_factor = Decimal("0")
    if qualifying_transactions:
        timestamps = [tx["timestamp"] for tx in qualifying_transactions]
        time_span = max(timestamps) - min(timestamps)
        tight_window = time_window_seconds // 4
        if time_span <= tight_window:
            time_factor = Decimal("0.2")

    confidence = min(count_factor + diversity_factor + time_factor, Decimal("1"))
    return confidence


def detect_structuring(
    graph_reasoner,
    node_id: str,
    currency: str = "USD",
) -> StructuringResult:
    """Detect structuring patterns centered on a specific node.

    v8.0 [P4v8-02]: Transactions filtered by currency BEFORE threshold comparison.
    v7.0 [P4-08]: Fan-in checked FIRST and takes precedence.
    """
    min_amount, max_amount, min_count, time_window = _get_thresholds(currency)

    # === CHECK 1: Fan-In (Many -> node_id) ===
    incoming = graph_reasoner.get_1hop_incoming(node_id)
    if incoming:
        currency_filtered_in = _filter_by_currency(incoming, currency)
        qualifying_in = _filter_qualifying_transactions(
            currency_filtered_in, min_amount, max_amount, time_window,
        )
        if len(qualifying_in) >= min_count:
            counterparts = sorted(set(tx["source_node"] for tx in qualifying_in))
            total = sum(tx["amount"] for tx in qualifying_in)
            confidence = _compute_confidence(
                len(qualifying_in), len(counterparts), min_count,
                time_window, qualifying_in,
            )

            return StructuringResult(
                detected=True,
                mode="FAN_IN",
                target_node=node_id,
                counterpart_nodes=counterparts,
                qualifying_transactions=qualifying_in,
                total_amount=total,
                transaction_count=len(qualifying_in),
                currency=currency,
                confidence=confidence,
                reasoning=(
                    f"STRUCTURING (Fan-In) detected at node '{node_id}': "
                    f"{len(qualifying_in)} transactions in [{min_amount}-{max_amount}] "
                    f"{currency} range within {time_window}s window. "
                    f"Total: {total} {currency} from {len(counterparts)} unique sources."
                ),
            )

    # === CHECK 2: Fan-Out (node_id -> Many) ===
    outgoing = graph_reasoner.get_1hop_outgoing(node_id)
    if outgoing:
        currency_filtered_out = _filter_by_currency(outgoing, currency)
        qualifying_out = _filter_qualifying_transactions(
            currency_filtered_out, min_amount, max_amount, time_window,
        )
        if len(qualifying_out) >= min_count:
            counterparts = sorted(set(tx["target_node"] for tx in qualifying_out))
            total = sum(tx["amount"] for tx in qualifying_out)
            confidence = _compute_confidence(
                len(qualifying_out), len(counterparts), min_count,
                time_window, qualifying_out,
            )

            return StructuringResult(
                detected=True,
                mode="FAN_OUT",
                target_node=node_id,
                counterpart_nodes=counterparts,
                qualifying_transactions=qualifying_out,
                total_amount=total,
                transaction_count=len(qualifying_out),
                currency=currency,
                confidence=confidence,
                reasoning=(
                    f"STRUCTURING (Fan-Out) detected at node '{node_id}': "
                    f"{len(qualifying_out)} outgoing transactions in "
                    f"[{min_amount}-{max_amount}] {currency} range. "
                    f"Total: {total} {currency} to {len(counterparts)} unique targets."
                ),
            )

    # === No structuring detected ===
    return StructuringResult(
        detected=False,
        mode="NONE",
        target_node=node_id,
        currency=currency,
        reasoning=f"No structuring pattern detected at node '{node_id}'.",
    )


# ═══════════════════════════════════════════════════════════════════
# LAYERING DETECTION (from purple_agent/src/core/heuristics/layering.py)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class LayeringChain:
    """A single detected layering chain."""
    chain_nodes: list[str]
    chain_transactions: list[dict]
    decay_rates: list[Decimal]
    avg_decay_rate: Decimal = Decimal("0")
    hop_count: int = 0
    start_amount: Decimal = Decimal("0")
    end_amount: Decimal = Decimal("0")
    currency: str = "USD"

    @property
    def chain_length(self) -> int:
        """Backward-compatible alias for hop_count."""
        return self.hop_count


@dataclass
class LayeringResult:
    """Result of layering detection from a start node."""
    detected: bool
    start_node: str
    chains: list[LayeringChain] = field(default_factory=list)
    total_chains_found: int = 0
    confidence: Decimal = Decimal("0")
    currency: str = "USD"
    reasoning: str = ""


def _calculate_hop_decay(amount_in: Decimal, amount_out: Decimal) -> Decimal | None:
    """Calculate the decay rate for a single hop."""
    if amount_in <= Decimal("0"):
        return None
    try:
        decay = (amount_in - amount_out) / amount_in
        return decay
    except (InvalidOperation, ZeroDivisionError):
        return None


def _analyze_chain(chain: list[dict]) -> LayeringChain | None:
    """Analyze a single DFS chain for layering characteristics.

    v8.0 [P4v8-05]: Validates currency consistency across all transactions.
    """
    if len(chain) < MIN_CHAIN_LENGTH:
        return None

    currencies_in_chain = set(tx.get("currency", "USD") for tx in chain)
    if len(currencies_in_chain) != 1:
        logger.info(
            f"Chain rejected: mixed currencies {currencies_in_chain} detected. "
            f"Cross-currency decay calculations are meaningless."
        )
        return None
    chain_currency = currencies_in_chain.pop()

    decay_rates: list[Decimal] = []
    effective_min = DECAY_RATE_MIN - DECAY_TOLERANCE
    effective_max = DECAY_RATE_MAX + DECAY_TOLERANCE

    for i in range(len(chain) - 1):
        current_tx = chain[i]
        next_tx = chain[i + 1]

        time_gap = abs(next_tx["timestamp"] - current_tx["timestamp"])
        if time_gap > MAX_HOP_DELAY_SECONDS:
            return None

        decay = _calculate_hop_decay(current_tx["amount"], next_tx["amount"])
        if decay is None:
            return None

        if not (effective_min <= decay <= effective_max):
            return None

        decay_rates.append(decay)

    if not decay_rates:
        return None

    chain_nodes = [chain[0]["source_node"]]
    for tx in chain:
        chain_nodes.append(tx["target_node"])

    avg_decay = sum(decay_rates) / Decimal(str(len(decay_rates)))

    return LayeringChain(
        chain_nodes=chain_nodes,
        chain_transactions=chain,
        decay_rates=decay_rates,
        avg_decay_rate=avg_decay,
        hop_count=len(chain),
        start_amount=chain[0]["amount"],
        end_amount=chain[-1]["amount"],
        currency=chain_currency,
    )


def detect_layering(
    graph_reasoner,
    node_id: str,
    max_depth: int | None = None,
    currency: str | None = None,
) -> LayeringResult:
    """Detect layering patterns originating from a specific node.

    v8.0 [P4v8-08]: Optional currency parameter.
    """
    raw_chains = graph_reasoner.dfs_trace_chains(node_id, max_depth=max_depth)

    detected_chains: list[LayeringChain] = []
    for raw_chain in raw_chains:
        analyzed = _analyze_chain(raw_chain)
        if analyzed is not None:
            if currency is not None and analyzed.currency != currency:
                continue
            detected_chains.append(analyzed)

    if detected_chains:
        longest = max(c.hop_count for c in detected_chains)
        chain_confidence = min(
            Decimal(str(longest)) / Decimal(str(MIN_CHAIN_LENGTH * 2)),
            Decimal("1"),
        )
        count_bonus = min(
            Decimal(str(len(detected_chains))) / Decimal("5"),
            Decimal("0.2"),
        )
        confidence = min(chain_confidence + count_bonus, Decimal("1"))

        result_currency = currency if currency else detected_chains[0].currency

        return LayeringResult(
            detected=True,
            start_node=node_id,
            chains=detected_chains,
            total_chains_found=len(detected_chains),
            confidence=confidence,
            currency=result_currency,
            reasoning=(
                f"LAYERING detected from node '{node_id}': "
                f"{len(detected_chains)} chain(s) with systematic "
                f"{DECAY_RATE_MIN*100}-{DECAY_RATE_MAX*100}% decay. "
                f"Longest chain: {longest} hop(s). "
                f"Currency: {result_currency}."
            ),
        )

    return LayeringResult(
        detected=False,
        start_node=node_id,
        currency=currency or "USD",
        reasoning=f"No layering pattern detected from node '{node_id}'.",
    )


# ═══════════════════════════════════════════════════════════════════
# SAR DRAFTER — Mechanical Template Only (from purple_agent/src/core/sar_drafter.py)
# DO NOT copy SARDrafter class or _build_prompt (needs LLM constants)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SARDraft:
    """Parsed SAR draft with Five Ws sections."""
    who: str = ""
    what: str = ""
    where: str = ""
    when: str = ""
    why: str = ""
    cited_tx_ids: list[str] = field(default_factory=list)
    raw_narrative: str = ""
    jurisdiction: str = "fincen"


def _get_timezone(jurisdiction: str):
    """Get timezone object for jurisdiction-specific formatting."""
    tz_name = TIMEZONE_FIU_IND if jurisdiction == "fiu_ind" else TIMEZONE_FINCEN
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except ImportError:
        if jurisdiction == "fiu_ind":
            return timezone(timedelta(hours=5, minutes=30))
        return timezone.utc


def _format_timestamp(epoch: int, jurisdiction: str) -> str:
    """Format a Unix epoch timestamp as ISO 8601 with jurisdiction timezone."""
    if epoch <= 0:
        return "Unknown"
    tz = _get_timezone(jurisdiction)
    dt = datetime.fromtimestamp(epoch, tz=tz)
    return dt.strftime('%Y-%m-%dT%H:%M:%S%z')


def mechanical_sar_template(
    detection_results: dict,
    graph_data: dict,
    jurisdiction: str,
) -> SARDraft:
    """Generate a SAR using a mechanical template (no LLM).

    v6.1 [ALN-05] — Rule 24: "LLM retry exhaustion -> mechanical SAR template,
    never empty narrative."
    Zero hallucination by construction: only references entities and
    transactions present in the detection_results and graph_data.
    """
    typology = detection_results.get("typology", "UNKNOWN")
    struct_hits = detection_results.get("structuring_hits", [])
    layer_hits = detection_results.get("layering_hits", [])

    all_entities: set[str] = set()
    all_tx_ids: list[str] = []
    for hit in struct_hits:
        all_entities.add(hit.get("node", ""))
        all_entities.update(hit.get("sources", []))
        all_tx_ids.extend(hit.get("transactions", []))
    for hit in layer_hits:
        all_entities.add(hit.get("start_node", ""))
        all_entities.update(hit.get("chain_nodes", []))
        all_tx_ids.extend(hit.get("transactions", []))

    sorted_entities = sorted(all_entities - {""})
    sorted_tx_ids = sorted(set(all_tx_ids))

    timestamps = sorted(
        tx.get("timestamp", 0)
        for tx in graph_data.get("transactions", [])
        if tx.get("timestamp", 0) > 0
    )
    if timestamps:
        time_range = (
            f"{_format_timestamp(timestamps[0], jurisdiction)} to "
            f"{_format_timestamp(timestamps[-1], jurisdiction)}"
        )
    else:
        time_range = "Timestamps unavailable"

    who = ", ".join(sorted_entities) if sorted_entities else "Entities not identified"
    what = f"Suspected {typology} activity detected by automated analysis."
    where = (
        "United States (FinCEN jurisdiction)"
        if jurisdiction == "fincen"
        else "India (FIU-IND/PMLA jurisdiction)"
    )
    when = time_range

    why_lines: list[str] = []
    for hit in struct_hits:
        currency = hit.get("currency", "USD")
        why_lines.append(
            f"Structuring ({hit.get('mode', 'UNKNOWN')}): "
            f"{hit.get('tx_count', 0)} sub-threshold transactions "
            f"totaling {hit.get('total', '0')} {currency} "
            f"via node {hit.get('node', 'N/A')}."
        )
    for hit in layer_hits:
        why_lines.append(
            f"Layering: {hit.get('hop_count', hit.get('chain_length', 0))}-hop chain from "
            f"{hit.get('start_node', 'N/A')}, "
            f"avg decay {hit.get('avg_decay', 'N/A')}."
        )
    why = " ".join(why_lines) if why_lines else "Automated pattern detection triggered SAR filing."

    raw_narrative = (
        f"<WHO>{who}</WHO>\n"
        f"<WHAT>{what}</WHAT>\n"
        f"<WHERE>{where}</WHERE>\n"
        f"<WHEN>{when}</WHEN>\n"
        f"<WHY>{why}</WHY>\n"
        f"<TRANSACTIONS>{', '.join(sorted_tx_ids)}</TRANSACTIONS>"
    )

    return SARDraft(
        who=who, what=what, where=where, when=when, why=why,
        cited_tx_ids=sorted_tx_ids,
        raw_narrative=raw_narrative,
        jurisdiction=jurisdiction,
    )


# ═══════════════════════════════════════════════════════════════════
# EVIDENCE SYNTHESIZER (from purple_agent/src/core/evidence_synthesizer.py)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EvidenceResult:
    """Result of evidence synthesis."""
    verdict: str
    reasoning: str
    discrepancies: list[dict] = field(default_factory=list)
    extracted_entities: list[dict] = field(default_factory=list)
    extracted_amounts: list[Decimal] = field(default_factory=list)


class EvidenceSynthesizer:
    """Cross-references ledger data (ground truth) with unstructured text evidence.

    Two-pass entity extraction pipeline:
      Pass 1: spaCy statistical NER (PERSON, ORG, GPE, MONEY, DATE)
      Pass 2: Regex for structured financial IDs (IFSC, PAN, SWIFT, IBAN, refs)
      Pass 3: Merge and deduplicate results

    spaCy model loaded lazily on first use (Rule 12).
    """

    def __init__(self) -> None:
        """Initialize synthesizer. spaCy model loaded on first use."""
        self._nlp = None
        self._nlp_loaded = False

    def _get_nlp(self):
        """Lazy-load spaCy model on first use."""
        if not self._nlp_loaded:
            self._nlp_loaded = True
            try:
                import spacy
                self._nlp = spacy.load(
                    SPACY_MODEL_NAME,
                    disable=["tagger", "parser", "lemmatizer"],
                )
                logger.info("spaCy %s loaded successfully.", SPACY_MODEL_NAME)
            except (OSError, ImportError) as e:
                self._nlp = None
                logger.warning(
                    "spaCy %s not available (%s). "
                    "Falling back to regex-only NER.",
                    SPACY_MODEL_NAME, e,
                )
        return self._nlp

    def extract_entities_from_text(self, text: str) -> list[dict]:
        """Extract entities using spaCy NER + regex."""
        entities: list[dict] = []
        seen: set[tuple[str, str]] = set()

        # Pass 1: spaCy NER
        nlp = self._get_nlp()
        if nlp is not None:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "MONEY", "DATE"):
                    key = (ent.text, ent.label_)
                    if key not in seen:
                        seen.add(key)
                        entities.append({
                            "text": ent.text,
                            "label": ent.label_,
                            "start": ent.start_char,
                            "end": ent.end_char,
                            "source": "spacy_ner",
                        })

        # Pass 2: Regex (always runs regardless of spaCy availability)
        for match in re.finditer(
            r'(?:User|Account|Subject|Entity)\s+(\w+)', text, re.IGNORECASE,
        ):
            key = (match.group(0), "REFERENCE")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(0),
                    "id": match.group(1),
                    "label": "REFERENCE",
                    "source": "regex_reference",
                })

        for match in IFSC_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "IFSC")
            if key not in seen:
                seen.add(key)
                entities.append({"text": match.group(), "label": "IFSC", "source": "regex_ifsc"})

        for match in PAN_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "PAN")
            if key not in seen:
                seen.add(key)
                entities.append({"text": match.group(), "label": "PAN", "source": "regex_pan"})

        for match in SWIFT_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "SWIFT")
            if key not in seen:
                seen.add(key)
                entities.append({"text": match.group(), "label": "SWIFT", "source": "regex_swift"})

        for match in IBAN_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "IBAN")
            if key not in seen:
                seen.add(key)
                entities.append({"text": match.group(), "label": "IBAN", "source": "regex_iban"})

        return entities

    def extract_amounts_from_text(self, text: str) -> list[Decimal]:
        """Extract monetary amounts from unstructured text."""
        amounts: list[Decimal] = []
        seen_amounts: set[Decimal] = set()

        for pattern_name, pattern in AMOUNT_PATTERNS.items():
            for match in re.finditer(pattern, text):
                try:
                    raw = match.group(0) if not match.groups() else match.group(1)

                    cleaned = (
                        raw.replace("$", "")
                        .replace("\u20b9", "")   # ₹ (U+20B9 Indian Rupee Sign)
                        .replace(",", "")
                    )
                    cleaned = re.sub(r"^Rs\.?\s*", "", cleaned).strip()

                    if pattern_name == "inr_lakh":
                        amount = Decimal(cleaned) * Decimal("100000")
                    elif pattern_name == "inr_crore":
                        amount = Decimal(cleaned) * Decimal("10000000")
                    elif pattern_name == "usd_k":
                        amount = Decimal(cleaned) * Decimal("1000")
                    else:
                        amount = Decimal(cleaned)

                    if not amount.is_finite():
                        continue

                    if amount not in seen_amounts:
                        seen_amounts.add(amount)
                        amounts.append(amount)
                except (InvalidOperation, ValueError):
                    continue

        return amounts

    def synthesize(
        self,
        ledger_data: dict,
        text_evidence: list[dict | str],
        currency: str = "USD",
    ) -> EvidenceResult:
        """Cross-reference ledger (ground truth) with text evidence."""
        if not text_evidence:
            return EvidenceResult(
                verdict="INSUFFICIENT_DATA",
                reasoning="No unstructured text evidence available for cross-reference.",
            )

        ledger_amount = ledger_data.get("total_inflow")
        entity_id = ledger_data.get("entity_id", "unknown")

        if ledger_amount is None:
            return EvidenceResult(
                verdict="INSUFFICIENT_DATA",
                reasoning=f"No ledger inflow data available for entity {entity_id}.",
            )

        threshold = (
            EVIDENCE_DISCREPANCY_THRESHOLD_INR
            if currency == "INR"
            else EVIDENCE_DISCREPANCY_THRESHOLD_USD
        )

        all_entities: list[dict] = []
        all_amounts: list[Decimal] = []
        per_amount_discrepancies: list[dict] = []

        for evidence in text_evidence:
            text = evidence["content"] if isinstance(evidence, dict) else evidence

            entities = self.extract_entities_from_text(text)
            all_entities.extend(entities)

            amounts = self.extract_amounts_from_text(text)
            all_amounts.extend(amounts)

            for text_amount in amounts:
                if text_amount != ledger_amount:
                    diff = abs(text_amount - ledger_amount)
                    if diff > threshold:
                        per_amount_discrepancies.append({
                            "type": "AMOUNT_MISMATCH",
                            "text_claims": str(text_amount),
                            "ledger_shows": str(ledger_amount),
                            "difference": str(diff),
                            "entity": entity_id,
                        })

        # Level 2 — sum comparison clears false positives
        discrepancies = per_amount_discrepancies
        if per_amount_discrepancies and len(all_amounts) >= 2:
            amount_sum = sum(all_amounts)
            sum_diff = abs(amount_sum - ledger_amount)
            if sum_diff <= threshold:
                logger.info(
                    "Entity %s: %d per-amount discrepancy(ies) cleared by sum comparison.",
                    entity_id, len(per_amount_discrepancies),
                )
                discrepancies = []

        if discrepancies:
            verdict = "SUSPICIOUS_DISCREPANCY"
            reasoning = (
                f"DISCREPANCY DETECTED for entity {entity_id}: "
                f"Text evidence claims amounts that differ from ledger records. "
                f"Ledger (ground truth) shows {ledger_amount} {currency}. "
                f"Found {len(discrepancies)} discrepancy(ies). "
                f"This is EVIDENCE of potential structuring or misrepresentation."
            )
        else:
            verdict = "CONSISTENT"
            reasoning = (
                f"Text evidence for entity {entity_id} is consistent with "
                f"ledger data. "
                f"No discrepancies detected across {len(text_evidence)} "
                f"evidence items."
            )

        return EvidenceResult(
            verdict=verdict,
            reasoning=reasoning,
            discrepancies=discrepancies,
            extracted_entities=all_entities,
            extracted_amounts=all_amounts,
        )
