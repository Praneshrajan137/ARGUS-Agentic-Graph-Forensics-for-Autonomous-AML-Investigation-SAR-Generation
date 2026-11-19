"""
Structuring (Smurfing) Detection Heuristic
PRD Reference: Task B2
Package Version: v8.0

Detects deliberate fragmentation of large transactions into smaller ones
to evade Currency Transaction Report (CTR) thresholds.

Detection Modes:
  - Fan-In:  Many sources -> one collector (classic smurfing)
  - Fan-Out: One source -> many targets (U-Turn structuring)

v8.0 [P4v8-02]: Transactions are FILTERED BY CURRENCY before threshold
comparison. Rule 14: "Group by currency BEFORE comparing against thresholds."
v7.0 passed all transactions regardless of currency, causing INR amounts to
be incorrectly matched against USD thresholds in mixed-currency scenarios.

All-history detection returns inclusion-maximal chronological windows in both
modes. The single-result API selects the strongest window; fan-in wins ties.

Thresholds are jurisdiction-aware:
  - USD: $9,000 - $9,800 per transaction (FinCEN CTR = $10,000)
  - INR: 9,00,000 - 9,80,000 per transaction (PMLA CTR = 10,00,000)

CRITICAL: All amounts are Decimal. All comparisons use Decimal arithmetic.
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from tracer_agent.src.config import (
    STRUCTURING_MIN_AMOUNT_USD,
    STRUCTURING_MAX_AMOUNT_USD,
    STRUCTURING_MIN_AMOUNT_INR,
    STRUCTURING_MAX_AMOUNT_INR,
    STRUCTURING_MIN_COUNT,
    STRUCTURING_MIN_COUNT_INR,
    STRUCTURING_TIME_WINDOW_SECONDS,
    STRUCTURING_TIME_WINDOW_SECONDS_INR,
)

logger = logging.getLogger(__name__)


@dataclass
class StructuringResult:
    """Result of structuring detection on a single node.

    v7.0 [P4-14]: counterpart_nodes contains:
      - Fan-In mode: the source node IDs (depositors / smurfs)
      - Fan-Out mode: the target node IDs (recipients)
    """
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
    # Actual first/last cited event timestamps (inclusive), not a latest-only anchor.
    window_start: int | None = None
    window_end: int | None = None

    @property
    def source_nodes(self) -> list[str]:
        """Backward-compatible alias for counterpart_nodes."""
        return self.counterpart_nodes


def _get_thresholds(currency: str, *, strict_currency: bool = False) -> tuple[Decimal, Decimal, int, int]:
    """Get jurisdiction-specific thresholds.

    When strict_currency=True (production path), unsupported currencies raise
    ValueError instead of silently falling back to USD thresholds.
    """
    if currency == "INR":
        return (
            STRUCTURING_MIN_AMOUNT_INR,
            STRUCTURING_MAX_AMOUNT_INR,
            STRUCTURING_MIN_COUNT_INR,
            STRUCTURING_TIME_WINDOW_SECONDS_INR,
        )
    if currency == "USD" or not strict_currency:
        return (
            STRUCTURING_MIN_AMOUNT_USD,
            STRUCTURING_MAX_AMOUNT_USD,
            STRUCTURING_MIN_COUNT,
            STRUCTURING_TIME_WINDOW_SECONDS,
        )
    raise ValueError(f"Unsupported structuring policy currency: {currency!r}")


def _exact_decimal_sum(values: list[Decimal]) -> Decimal:
    """Sum Decimals without silent global-context rounding."""
    if not values:
        return Decimal("0")
    lowest_exp = min(v.as_tuple().exponent for v in values)
    highest_digit = max(v.adjusted() for v in values)
    with localcontext() as ctx:
        ctx.prec = max(ctx.prec, highest_digit - lowest_exp + len(str(len(values))) + 4)
        return sum(values, Decimal("0"))


def _filter_by_currency(transactions: list[dict], currency: str) -> list[dict]:
    """
    Filter transactions to only those matching the target currency.

    v8.0 [P4v8-02]: Implements Rule 14 -- "Group by currency BEFORE
    comparing against thresholds." Without this filter, an INR transaction
    of 9,200 would incorrectly match USD $9,000-$9,800 thresholds.

    Args:
        transactions: All transactions (any currency).
        currency: Target currency to filter for ("USD" or "INR").

    Returns:
        Only transactions where tx["currency"] == currency.
    """
    return [tx for tx in transactions if tx.get("currency") == currency]


def _compute_confidence(
    qualifying_count: int,
    unique_counterparts: int,
    min_count: int,
    time_window_seconds: int,
    qualifying_transactions: list[dict],
) -> Decimal:
    """
    Compute multi-factor confidence score for structuring detection.

    v7.0 [P4-09]: Multi-factor replaces binary min(count/min_count, 1).
    v8.0 [P4v8-09]: time_factor uses integer arithmetic (time_window // 4).

    Three factors:
      (a) Count ratio: [0, 0.5]. Saturates at 3x min_count.
      (b) Source diversity: [0, 0.3]. More unique counterparties = higher.
      (c) Time clustering: 0.2 if all TXs within 25% of time window.
    """
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


def find_structuring_windows(
    transactions: list[dict],
    node_id: str,
    currency: str = "USD",
    mode: str = "FAN_IN",
    *,
    thresholds: tuple[Decimal, Decimal, int, int] | None = None,
    strict_currency: bool = False,
) -> list[StructuringResult]:
    """Find all inclusion-maximal qualifying windows in preselected events.

    The caller selects events belonging to this node/direction (including cash
    events that cannot be represented as graph edges). Events require a tx_id
    or id, Decimal amount, currency and timestamp. Missing/blank counterpart
    IDs are unknown, never synthetic sources contributing to diversity. Input
    is not mutated; duplicate event IDs keep their first occurrence (Rule 27).

    A two-pointer sweep over (timestamp, tx_id) produces at most N windows,
    rather than enumerating all qualifying subsets. Windows that add events
    while dropping older ones are distinct, even when they overlap. Subsets
    with the same right endpoint are redundant and omitted. Amount and time
    boundaries are inclusive. Evidence is sorted by ID; window_start/end are
    the actual minimum/maximum cited timestamps.
    """
    if mode not in ("FAN_IN", "FAN_OUT"):
        raise ValueError("mode must be FAN_IN or FAN_OUT")
    if thresholds is not None:
        min_amount, max_amount, min_count, time_window = thresholds
    else:
        min_amount, max_amount, min_count, time_window = _get_thresholds(
            currency, strict_currency=strict_currency,
        )
    unique_events: dict[str, dict] = {}
    for tx in transactions:
        tx_id = tx.get("tx_id") or tx.get("id")
        if not isinstance(tx_id, str) or not tx_id.strip():
            raise ValueError("Structuring events require a non-empty tx_id or id")
        if tx_id in unique_events:
            logger.warning("Duplicate structuring event ID '%s': keeping first occurrence.", tx_id)
            continue
        unique_events[tx_id] = dict(tx, tx_id=tx_id)

    # Deduplicate globally before currency filtering, matching graph ingestion.
    eligible: list[dict] = []
    for tx in _filter_by_currency(list(unique_events.values()), currency):
        if not isinstance(tx["amount"], Decimal):
            raise TypeError(f"Transaction {tx['tx_id']}: amount must be Decimal")
        if not tx["amount"].is_finite():
            raise ValueError(f"Transaction {tx['tx_id']}: amount must be finite")
        if min_amount <= tx["amount"] <= max_amount:
            eligible.append(tx)
    eligible.sort(key=lambda tx: (tx["timestamp"], tx["tx_id"]))

    results: list[StructuringResult] = []
    right = previous_right = 0
    counterpart_key = "source_node" if mode == "FAN_IN" else "target_node"
    label = "Fan-In" if mode == "FAN_IN" else "Fan-Out"
    for left, first in enumerate(eligible):
        while right < len(eligible) and eligible[right]["timestamp"] - first["timestamp"] <= time_window:
            right += 1
        # Same right endpoint means this is a subset of an earlier window.
        if right == previous_right:
            continue
        previous_right = right
        if right - left < min_count:
            continue

        qualifying = sorted(eligible[left:right], key=lambda tx: tx["tx_id"])
        counterparts = sorted({
            tx[counterpart_key] for tx in qualifying
            if tx.get(counterpart_key) and tx[counterpart_key].strip()
        })
        total = _exact_decimal_sum([tx["amount"] for tx in qualifying])
        window_start = first["timestamp"]
        window_end = eligible[right - 1]["timestamp"]
        results.append(StructuringResult(
            detected=True,
            mode=mode,
            target_node=node_id,
            counterpart_nodes=counterparts,
            qualifying_transactions=qualifying,
            total_amount=total,
            transaction_count=len(qualifying),
            currency=currency,
            confidence=_compute_confidence(
                len(qualifying), len(counterparts), min_count, time_window, qualifying,
            ),
            reasoning=(
                f"STRUCTURING ({label}) detected at node '{node_id}': "
                f"{len(qualifying)} transactions in [{min_amount}-{max_amount}] "
                f"{currency} range within {time_window}s window. "
                f"Event scope: [{window_start}, {window_end}]. "
                f"Total: {total} {currency}; {len(counterparts)} known unique counterparties."
            ),
            window_start=window_start,
            window_end=window_end,
        ))
    return results


def find_structuring_patterns(
    graph_reasoner,
    node_id: str,
    currency: str = "USD",
    *,
    thresholds: tuple[Decimal, Decimal, int, int] | None = None,
    strict_currency: bool = False,
) -> list[StructuringResult]:
    """Return every distinct window in both directions, chronologically.

    Finding identity is (node, currency, mode, window_start, window_end,
    sorted cited event IDs). Graph degree truncation remains visible through
    graph_reasoner.coverage; an empty result alone does not imply completeness.
    """
    results = find_structuring_windows(
        graph_reasoner.get_1hop_incoming(node_id),
        node_id,
        currency,
        "FAN_IN",
        thresholds=thresholds,
        strict_currency=strict_currency,
    )
    results.extend(find_structuring_windows(
        graph_reasoner.get_1hop_outgoing(node_id),
        node_id,
        currency,
        "FAN_OUT",
        thresholds=thresholds,
        strict_currency=strict_currency,
    ))
    return sorted(results, key=lambda result: (
        result.window_start, result.window_end, result.mode,
        tuple(tx["tx_id"] for tx in result.qualifying_transactions),
    ))


def detect_structuring(
    graph_reasoner,
    node_id: str,
    currency: str = "USD",
) -> StructuringResult:
    """Return the strongest finding while retaining the single-result API.

    Rank by confidence, then event count. Ties prefer fan-in (legacy behavior),
    then earliest actual scope and sorted event IDs. Evidence and Decimal totals
    come exclusively from that finding's window, never from combined windows.
    """
    findings = find_structuring_patterns(graph_reasoner, node_id, currency)
    if findings:
        return min(findings, key=lambda result: (
            -result.confidence, -result.transaction_count, result.mode != "FAN_IN",
            result.window_start, result.window_end,
            tuple(tx["tx_id"] for tx in result.qualifying_transactions),
        ))
    return StructuringResult(
        detected=False,
        mode="NONE",
        target_node=node_id,
        currency=currency,
        reasoning=f"No structuring pattern detected at node '{node_id}'.",
    )
