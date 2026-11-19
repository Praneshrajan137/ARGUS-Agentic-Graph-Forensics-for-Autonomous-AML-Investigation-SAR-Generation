"""
Tests for Structuring (Smurfing) Detection -- Purple Agent v8.0
PRD Reference: Task B2
TDD: Tests written FIRST, implementation SECOND.

Tests cover:
  - Fan-in smurfing detection (20 sub-threshold deposits)
  - Counterpart node identification (100% recall)
  - Correct mule identification
  - Transaction count and totals (Decimal)
  - Confidence scoring (valid range, increases with more TXs)
  - Negative cases (legitimate hub, below/above threshold, too few TXs)
  - Boundary testing (exact min $9,000, exact max $9,800)
  - INR jurisdiction (Indian PMLA thresholds)
  - Fan-out detection and fan-in precedence
  - Time window expiration
  - v8.0: Mixed currency isolation (Rule 14)
"""
from decimal import Decimal
from itertools import combinations
from random import Random

import pytest

from tracer_agent.src.core.graph_reasoner import GraphReasoner
from tracer_agent.src.core.heuristics.structuring import detect_structuring
from tracer_agent.src.config import STRUCTURING_MIN_COUNT


# ===================================================================
# Helper to load scenario into GraphReasoner
# ===================================================================

def _load(scenario: dict) -> GraphReasoner:
    gr = GraphReasoner()
    gr.load_from_dict(scenario)
    return gr


# ===================================================================
# Detection Tests (Fan-In)
# ===================================================================

class TestFanInDetection:

    def test_detects_smurfing_fan_in(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        assert result.detected is True
        assert result.mode == "FAN_IN"

    def test_identifies_all_counterpart_nodes(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        expected = sorted(structuring_scenario["criminal_sources"])
        assert result.counterpart_nodes == expected

    def test_correct_mule_node(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        assert result.target_node == "mule_1"

    def test_transaction_count(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        assert result.transaction_count == 20

    def test_total_amount_is_decimal(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        if not isinstance(result.total_amount, Decimal):
            raise TypeError(
                f"total_amount is {type(result.total_amount).__name__}, expected Decimal"
            )
        assert result.total_amount == structuring_scenario["expected_total_criminal_inflow"]

    def test_all_transactions_have_ids(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        for tx in result.qualifying_transactions:
            assert tx.get("tx_id"), f"Transaction missing tx_id: {tx}"


# ===================================================================
# Confidence Tests
# ===================================================================

class TestConfidence:

    def test_confidence_score_in_valid_range(self, structuring_scenario: dict) -> None:
        gr = _load(structuring_scenario)
        result = detect_structuring(gr, "mule_1", "USD")
        assert Decimal("0.33") <= result.confidence <= Decimal("1")

    def test_confidence_increases_with_more_transactions(self) -> None:
        """30 TXs should yield higher confidence than 10 TXs (at min_count boundary)."""
        def _build(n: int) -> GraphReasoner:
            gr = GraphReasoner()
            nodes = {"target": {"name": "Target"}}
            txs = []
            for i in range(1, n + 1):
                src = f"src_{i:03d}"
                nodes[src] = {"name": f"Source {i}"}
                txs.append({
                    "id": f"TX-CONF-{i:03d}",
                    "source_node": src,
                    "target_node": "target",
                    "amount": Decimal("9200"),
                    "currency": "USD",
                    "timestamp": 1700000000 + (i * 600),
                    "type": "WIRE",
                })
            gr.load_from_dict({"transactions": txs, "nodes": nodes})
            return gr

        gr_10 = _build(STRUCTURING_MIN_COUNT)
        gr_30 = _build(30)
        result_10 = detect_structuring(gr_10, "target", "USD")
        result_30 = detect_structuring(gr_30, "target", "USD")
        assert result_10.detected is True
        assert result_30.detected is True
        assert result_30.confidence > result_10.confidence


# ===================================================================
# Negative Cases
# ===================================================================

class TestNegativeCases:

    def test_legitimate_hub_not_detected(self) -> None:
        """Clean fixture: 5 salary deposits of $3,000 each. Not structuring."""
        gr = GraphReasoner()
        nodes = {"corp": {"name": "LegitCorp"}}
        txs = []
        for i in range(1, 6):
            src = f"emp_{i}"
            nodes[src] = {"name": f"Employee {i}"}
            txs.append({
                "id": f"TX-SAL-{i}",
                "source_node": src,
                "target_node": "corp",
                "amount": Decimal("3000"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 3600),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "corp", "USD")
        assert result.detected is False

    def test_below_threshold_not_detected(self) -> None:
        """$8,999.99 amounts: below $9K structuring range."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, 21):
            src = f"src_{i:02d}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-BELOW-{i:03d}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("8999.99"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is False

    def test_above_threshold_not_detected(self) -> None:
        """$10,001 amounts: above CTR, not structuring band."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, 21):
            src = f"src_{i:02d}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-ABOVE-{i:03d}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("10001"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is False

    def test_too_few_transactions_not_detected(self) -> None:
        """5 transactions < STRUCTURING_MIN_COUNT (10)."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, 6):
            src = f"src_{i}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-FEW-{i}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("9200"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is False


# ===================================================================
# Boundary Tests
# ===================================================================

class TestBoundaries:

    def test_boundary_exact_min_amount(self) -> None:
        """$9,000.00 exact: included in detection range (>=)."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            src = f"src_{i:02d}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-EXMIN-{i:03d}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("9000"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is True

    def test_boundary_exact_max_amount(self) -> None:
        """$9,800.00 exact: included in detection range (<=)."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            src = f"src_{i:02d}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-EXMAX-{i:03d}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("9800"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is True


# ===================================================================
# INR Jurisdiction Tests
# ===================================================================

class TestINRJurisdiction:

    def test_indian_structuring_detected(self, indian_scenario: dict) -> None:
        gr = _load(indian_scenario)
        result = detect_structuring(gr, "mule_in_1", "INR")
        assert result.detected is True
        assert result.mode == "FAN_IN"
        assert result.currency == "INR"


# ===================================================================
# Fan-Out and Precedence Tests
# ===================================================================

class TestFanOutAndPrecedence:

    def test_fan_out_detected(self) -> None:
        """One source, many sub-threshold outgoing -> FAN_OUT detected."""
        gr = GraphReasoner()
        nodes = {"source": {"name": "Source"}}
        txs = []
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            tgt = f"tgt_{i:02d}"
            nodes[tgt] = {"name": f"Target {i}"}
            txs.append({
                "id": f"TX-FOUT-{i:03d}",
                "source_node": "source",
                "target_node": tgt,
                "amount": Decimal("9300"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "source", "USD")
        assert result.detected is True
        assert result.mode == "FAN_OUT"

    def test_fan_in_takes_precedence_over_fan_out(self) -> None:
        """v7.0 [P4-17]: Node with BOTH incoming and outgoing structuring -> FAN_IN returned."""
        gr = GraphReasoner()
        nodes = {"hub": {"name": "Hub"}}
        txs = []
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            src = f"in_{i:02d}"
            nodes[src] = {"name": f"In Source {i}"}
            txs.append({
                "id": f"TX-HUB-IN-{i:03d}",
                "source_node": src,
                "target_node": "hub",
                "amount": Decimal("9400"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 1800),
                "type": "WIRE",
            })
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            tgt = f"out_{i:02d}"
            nodes[tgt] = {"name": f"Out Target {i}"}
            txs.append({
                "id": f"TX-HUB-OUT-{i:03d}",
                "source_node": "hub",
                "target_node": tgt,
                "amount": Decimal("9500"),
                "currency": "USD",
                "timestamp": 1700000000 + 50000 + (i * 1800),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "hub", "USD")
        assert result.detected is True
        assert result.mode == "FAN_IN"


# ===================================================================
# Time Window Tests
# ===================================================================

class TestTimeWindow:

    def test_time_window_expired_not_detected(self) -> None:
        """Transactions >48hrs apart: outside STRUCTURING_TIME_WINDOW_SECONDS."""
        gr = GraphReasoner()
        nodes = {"target": {"name": "Target"}}
        txs = []
        for i in range(1, STRUCTURING_MIN_COUNT + 1):
            src = f"src_{i:02d}"
            nodes[src] = {"name": f"Source {i}"}
            txs.append({
                "id": f"TX-EXPIRED-{i:03d}",
                "source_node": src,
                "target_node": "target",
                "amount": Decimal("9200"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 200000),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_structuring(gr, "target", "USD")
        assert result.detected is False


# ===================================================================
# v8.0 Mixed Currency Tests
# ===================================================================

class TestMixedCurrency:

    def test_mixed_currency_not_cross_detected(self, mixed_currency_scenario: dict) -> None:
        """v8.0 [P4v8-11]: INR TXs don't trigger USD detection and vice versa.

        Verifies that when detecting USD structuring, only USD transactions
        are considered in the qualifying count and amounts.
        """
        gr = _load(mixed_currency_scenario)

        usd_result = detect_structuring(gr, "mixed_mule", "USD")
        assert usd_result.detected is True
        assert usd_result.currency == "USD"
        for tx in usd_result.qualifying_transactions:
            assert tx["currency"] == "USD", (
                f"Non-USD transaction {tx['tx_id']} found in USD detection result"
            )

        inr_result = detect_structuring(gr, "mixed_mule", "INR")
        assert inr_result.detected is True
        assert inr_result.currency == "INR"
        for tx in inr_result.qualifying_transactions:
            assert tx["currency"] == "INR", (
                f"Non-INR transaction {tx['tx_id']} found in INR detection result"
            )


# All-history regressions and an exhaustive small-fixture oracle.
def _window_event(index, timestamp, *, direction="FAN_IN", currency="USD", amount="9500"):
    source, target = f"peer_{index}", "hub"
    if direction == "FAN_OUT":
        source, target = target, source
    return {
        "id": f"event_{index:03d}",
        "source_node": source,
        "target_node": target,
        "amount": Decimal(amount),
        "currency": currency,
        "timestamp": 1700000000 + timestamp,
    }


def _ids(result):
    return tuple(tx["tx_id"] for tx in result.qualifying_transactions)


def _brute_force_windows(events, min_count, window):
    """Enumerate subsets, not sliding pointers or the production helpers."""
    eligible = [
        event for event in events
        if event["currency"] == "USD"
        and Decimal("9000") <= event["amount"] <= Decimal("9800")
    ]
    candidates = set()
    for count in range(min_count, len(eligible) + 1):
        for group in combinations(eligible, count):
            times = [event["timestamp"] for event in group]
            if max(times) - min(times) <= window:
                candidates.add(frozenset(event["id"] for event in group))
    return {
        tuple(sorted(candidate)) for candidate in candidates
        if not any(candidate < other for other in candidates)
    }


class TestAllHistoryWindows:
    def test_earlier_cluster_survives_later_qualifying_noise(self):
        events = [_window_event(i, i * 60) for i in range(STRUCTURING_MIN_COUNT)]
        events.append(_window_event(99, 10 * 86400))
        result = detect_structuring(_load({"transactions": events}), "hub")
        assert result.detected
        assert _ids(result) == tuple(event["id"] for event in events[:-1])
        assert result.total_amount == Decimal("9500") * STRUCTURING_MIN_COUNT
        assert result.window_start == events[0]["timestamp"]
        assert result.window_end == events[-2]["timestamp"]

    def test_disjoint_clusters_and_both_directions_are_returned(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_patterns

        events = []
        for cluster in range(2):
            for direction in ("FAN_IN", "FAN_OUT"):
                for i in range(STRUCTURING_MIN_COUNT):
                    events.append(_window_event(
                        len(events), cluster * 10 * 86400 + i * 60, direction=direction,
                    ))
        expected = find_structuring_patterns(_load({"transactions": events}), "hub")
        assert len(expected) == 4
        assert [(r.window_start, r.mode) for r in expected] == sorted(
            (r.window_start, r.mode) for r in expected
        )
        assert {r.mode for r in expected} == {"FAN_IN", "FAN_OUT"}
        assert all(r.transaction_count == STRUCTURING_MIN_COUNT for r in expected)
        for seed in range(4):
            shuffled = list(events)
            Random(seed).shuffle(shuffled)
            actual = find_structuring_patterns(_load({"transactions": shuffled}), "hub")
            assert actual == expected
        single = detect_structuring(_load({"transactions": events}), "hub")
        assert single == expected[0]  # stable earliest fan-in tie-break

    def test_single_result_chooses_strongest_window_not_latest_or_first_direction(self):
        events = [_window_event(i, i) for i in range(STRUCTURING_MIN_COUNT)]
        events += [
            _window_event(100 + i, 10 * 86400 + i, direction="FAN_OUT")
            for i in range(STRUCTURING_MIN_COUNT * 2)
        ]
        result = detect_structuring(_load({"transactions": events}), "hub")
        assert result.mode == "FAN_OUT"
        assert result.transaction_count == STRUCTURING_MIN_COUNT * 2
        assert all(tx["timestamp"] >= 1700000000 + 10 * 86400
                   for tx in result.qualifying_transactions)

    def test_preselected_cash_uses_same_windows_without_fabricated_diversity(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_windows

        events = [_window_event(i, i, amount="9500.01") for i in range(STRUCTURING_MIN_COUNT)]
        known = find_structuring_windows(events, "hub")
        cash = []
        for i, event in enumerate(events):
            event = dict(event, type="CASH_DEPOSIT")
            event.pop("source_node")
            if i % 3 == 1:
                event["source_node"] = None
            elif i % 3 == 2:
                event["source_node"] = " "
            cash.append(event)
        cash.append(dict(cash[0]))  # same event twice is not another deposit
        result, = find_structuring_windows(cash, "hub")
        assert result.counterpart_nodes == []
        assert result.transaction_count == STRUCTURING_MIN_COUNT
        assert result.total_amount == Decimal("9500.01") * STRUCTURING_MIN_COUNT
        assert _ids(result) == _ids(known[0])
        assert result.confidence == known[0].confidence - Decimal("0.3")
        assert all("tx_id" not in event for event in cash)  # caller input untouched

    def test_preselected_duplicate_ids_follow_graph_first_occurrence_policy(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_windows

        events = [_window_event(i, i) for i in range(STRUCTURING_MIN_COUNT)]
        # A duplicate USD version must not revive an ID already loaded as INR.
        events.insert(0, dict(events[0], currency="INR"))
        assert not detect_structuring(_load({"transactions": events}), "hub").detected
        assert find_structuring_windows(events, "hub") == []

    @pytest.mark.parametrize("changes, error", [
        ({"amount": 9500.0}, TypeError),
        ({"amount": Decimal("NaN")}, ValueError),
        ({"id": ""}, ValueError),
    ])
    def test_preselected_events_preserve_decimal_and_identity_guards(self, changes, error):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_windows

        with pytest.raises(error):
            find_structuring_windows([dict(_window_event(0, 0), **changes)], "hub")

    def test_repeated_parallel_amounts_remain_distinct_events(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_patterns

        events = [dict(_window_event(i, 0), source_node="same_peer")
                  for i in range(STRUCTURING_MIN_COUNT)]
        result, = find_structuring_patterns(_load({"transactions": events}), "hub")
        assert result.transaction_count == STRUCTURING_MIN_COUNT
        assert len(_ids(result)) == len(set(_ids(result)))
        assert result.counterpart_nodes == ["same_peer"]

    def test_currency_isolation_cannot_combine_subthreshold_counts(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_patterns

        events = [_window_event(i, i, currency="USD" if i % 2 else "INR")
                  for i in range(STRUCTURING_MIN_COUNT)]
        reasoner = _load({"transactions": events})
        assert find_structuring_patterns(reasoner, "hub", "USD") == []
        assert find_structuring_patterns(reasoner, "hub", "INR") == []

    @pytest.mark.parametrize("times", [
        [0, 0, 0, 0, 0, 0], [0, 1, 8, 9, 16, 17], [0, 0, 8, 9, 9, 17],
        [0, 1, 2, 20, 21, 22], [0, 9, 18, 27, 36, 45],
    ])
    def test_shared_windows_match_exhaustive_subset_oracle(self, monkeypatch, times):
        from tracer_agent.src.core.heuristics import structuring

        monkeypatch.setattr(structuring, "STRUCTURING_MIN_COUNT", 3)
        monkeypatch.setattr(structuring, "STRUCTURING_TIME_WINDOW_SECONDS", 8)
        events = [_window_event(i, timestamp) for i, timestamp in enumerate(times)]
        expected = _brute_force_windows(events, 3, 8)
        for seed in range(3):
            shuffled = list(events)
            Random(seed).shuffle(shuffled)
            results = structuring.find_structuring_windows(shuffled, "hub")
            assert {_ids(result) for result in results} == expected
            assert len(results) == len(expected) <= len(events)
            for result in results:
                timestamps = [tx["timestamp"] for tx in result.qualifying_transactions]
                assert (result.window_start, result.window_end) == (min(timestamps), max(timestamps))
                assert result.window_end - result.window_start <= 8

    def test_seeded_small_windows_match_independent_oracle(self, monkeypatch):
        from tracer_agent.src.core.heuristics import structuring

        monkeypatch.setattr(structuring, "STRUCTURING_MIN_COUNT", 3)
        monkeypatch.setattr(structuring, "STRUCTURING_TIME_WINDOW_SECONDS", 8)
        rng = Random(719)
        for _ in range(30):
            events = [
                _window_event(i, rng.randrange(25), currency=rng.choice(["USD", "USD", "INR"]),
                              amount=rng.choice(["8999.99", "9000", "9500.01", "9800", "9800.01"]))
                for i in range(8)
            ]
            rng.shuffle(events)
            results = structuring.find_structuring_windows(events, "hub")
            assert {_ids(result) for result in results} == _brute_force_windows(events, 3, 8)

    def test_dense_window_output_is_not_combinatorial(self):
        from tracer_agent.src.core.heuristics.structuring import find_structuring_windows

        results = find_structuring_windows([_window_event(i, i) for i in range(200)], "hub")
        assert len(results) == 1
        assert results[0].transaction_count == 200
