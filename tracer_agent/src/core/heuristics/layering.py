"""
Layering Detection Heuristic
PRD Reference: Task B3
Package Version: v8.0

Detects money laundering layering patterns where funds flow through
a chain of intermediary accounts with systematic value decay (2-5%
per hop, representing "service fees" or deliberate obfuscation).

v8.0 [P4v8-05]: Currency consistency validation within chains.
  A chain mixing USD and INR transactions produces meaningless decay
  calculations. All transactions in a chain must share the same currency.
v8.0 [P4v8-08]: detect_layering accepts optional currency parameter.
  LayeringChain and LayeringResult record the detected currency for
  downstream SAR jurisdiction formatting.

v7.0 [P4-13]: chain_length renamed to hop_count for clarity.

CRITICAL: All amount comparisons use Decimal arithmetic.
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from tracer_agent.src.config import (
    DECAY_RATE_MIN,
    DECAY_RATE_MAX,
    DECAY_TOLERANCE,
    MIN_CHAIN_LENGTH,
    MAX_HOP_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass
class LayeringChain:
    """A single detected layering chain.

    v8.0 [P4v8-08]: currency records the chain's currency for SAR formatting.
    v7.0 [P4-13]: hop_count = number of transactions in the chain.
    """
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
    """
    Calculate the decay rate for a single hop.

    Returns:
        Decay rate as Decimal (e.g., 0.03 for 3%), or None if invalid.
    """
    if amount_in <= Decimal("0"):
        return None
    try:
        decay = (amount_in - amount_out) / amount_in
        return decay
    except (InvalidOperation, ZeroDivisionError):
        return None


def _analyze_chain(
    chain: list[dict],
    *,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    decay_min: Decimal = DECAY_RATE_MIN,
    decay_max: Decimal = DECAY_RATE_MAX,
    decay_tolerance: Decimal = DECAY_TOLERANCE,
    max_hop_delay_seconds: int = MAX_HOP_DELAY_SECONDS,
) -> LayeringChain | None:
    """Analyze a single DFS chain for layering characteristics."""
    if len(chain) < min_chain_length:
        return None

    currencies_in_chain = set(tx.get("currency", "USD") for tx in chain)
    if len(currencies_in_chain) != 1:
        logger.info(
            f"Chain rejected: mixed currencies {currencies_in_chain} detected. "
            f"Cross-currency decay calculations are meaningless. "
            f"Chain nodes: {chain[0]['source_node']} -> ... -> {chain[-1]['target_node']}"
        )
        return None
    chain_currency = currencies_in_chain.pop()

    decay_rates: list[Decimal] = []
    effective_min = decay_min - decay_tolerance
    effective_max = decay_max + decay_tolerance

    for i in range(len(chain) - 1):
        current_tx = chain[i]
        next_tx = chain[i + 1]

        time_gap = next_tx["timestamp"] - current_tx["timestamp"]
        if not 0 <= time_gap <= max_hop_delay_seconds:
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
    *,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    decay_min: Decimal = DECAY_RATE_MIN,
    decay_max: Decimal = DECAY_RATE_MAX,
    decay_tolerance: Decimal = DECAY_TOLERANCE,
    max_hop_delay_seconds: int = MAX_HOP_DELAY_SECONDS,
    deadline_monotonic: float | None = None,
    prune_constraints: bool = True,
) -> LayeringResult:
    """
    Detect maximal qualifying layering chains originating from a specific node.

    Uses constraint-pruned deterministic DFS by default so invalid reverse-time,
    mixed-currency, or non-decaying edges do not exhaust MAX_PATHS_PER_SEARCH,
    while preserving exact equivalence with exhaustive simple-path enumeration.
    """
    effective_min = decay_min - decay_tolerance
    effective_max = decay_max + decay_tolerance

    def _valid_transition(prev_tx: dict | None, next_tx: dict) -> bool:
        next_cur = next_tx.get("currency", "USD")
        if currency is not None and next_cur != currency:
            return False
        if prev_tx is None:
            return next_tx["amount"] > Decimal("0")
        if prev_tx.get("currency", "USD") != next_cur:
            return False
        time_gap = next_tx["timestamp"] - prev_tx["timestamp"]
        if not 0 <= time_gap <= max_hop_delay_seconds:
            return False
        decay = _calculate_hop_decay(prev_tx["amount"], next_tx["amount"])
        return decay is not None and effective_min <= decay <= effective_max

    if prune_constraints:
        raw_chains = graph_reasoner.dfs_trace_chains(
            node_id,
            max_depth=max_depth,
            edge_filter=_valid_transition,
            min_length=min_chain_length,
            deadline_monotonic=deadline_monotonic,
        )
    else:
        raw_chains = graph_reasoner.dfs_trace_chains(
            node_id,
            max_depth=max_depth,
            deadline_monotonic=deadline_monotonic,
        )

    candidates: dict[tuple[str, ...], LayeringChain] = {}
    for raw_chain in raw_chains:
        if currency is not None and raw_chain[0].get("currency", "USD") != currency:
            continue
        for end in range(len(raw_chain), min_chain_length - 1, -1):
            prefix = raw_chain[:end]
            identity = tuple(tx["tx_id"] for tx in prefix)
            if identity in candidates:
                break
            analyzed = _analyze_chain(
                prefix,
                min_chain_length=min_chain_length,
                decay_min=decay_min,
                decay_max=decay_max,
                decay_tolerance=decay_tolerance,
                max_hop_delay_seconds=max_hop_delay_seconds,
            )
            if analyzed is not None:
                candidates[identity] = analyzed
                break

    extended_prefixes = {
        identity[:end]
        for identity in candidates
        for end in range(min_chain_length, len(identity))
    }
    detected_chains = [
        candidates[identity] for identity in sorted(candidates)
        if identity not in extended_prefixes
    ]

    if detected_chains:
        longest = max(c.hop_count for c in detected_chains)
        chain_confidence = min(
            Decimal(str(longest)) / Decimal(str(min_chain_length * 2)),
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
                f"{decay_min*100}-{decay_max*100}% decay. "
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
