"""
Tests for Layering Detection -- Purple Agent v8.0
PRD Reference: Task B3
TDD: Tests written FIRST, implementation SECOND.

Tests cover:
  - Chain detection (3% decay detected, hop_count >= MIN_CHAIN_LENGTH)
  - Decay rate validation (within [0.02, 0.05] tolerance band)
  - Amounts are Decimal throughout
  - Confidence scoring (nonzero for detected chains)
  - Negative cases (no decay, excessive decay, short chain, slow chain, increasing amounts)
  - Multiple chains detection
  - v8.0: Mixed currency chain rejection, currency recorded in result
"""
from decimal import Decimal
from itertools import permutations
from random import Random

import pytest

from tracer_agent.src.core.graph_reasoner import GraphReasoner
from tracer_agent.src.core.heuristics.layering import detect_layering
from tracer_agent.src.config import MIN_CHAIN_LENGTH


# ===================================================================
# Helper
# ===================================================================

def _load(scenario: dict) -> GraphReasoner:
    gr = GraphReasoner()
    gr.load_from_dict(scenario)
    return gr


# ===================================================================
# Detection Tests
# ===================================================================

class TestLayeringDetection:

    def test_detects_layering_chain(self, layering_scenario: dict) -> None:
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        assert result.detected is True
        assert result.total_chains_found >= 1

    def test_hop_count_meets_minimum(self, layering_scenario: dict) -> None:
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        for chain in result.chains:
            assert chain.hop_count >= MIN_CHAIN_LENGTH

    def test_decay_rate_in_range(self, layering_scenario: dict) -> None:
        """Decay rates within [0.02, 0.05] +/- tolerance."""
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        for chain in result.chains:
            for rate in chain.decay_rates:
                assert Decimal("0.015") <= rate <= Decimal("0.055"), (
                    f"Decay rate {rate} outside tolerance band"
                )

    def test_chain_nodes_correct(self, layering_scenario: dict) -> None:
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        chain = result.chains[0]
        expected_nodes = layering_scenario["chain_nodes"]
        assert chain.chain_nodes == expected_nodes

    def test_amounts_are_decimal(self, layering_scenario: dict) -> None:
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        chain = result.chains[0]
        if not isinstance(chain.start_amount, Decimal):
            raise TypeError(f"start_amount is {type(chain.start_amount)}, expected Decimal")
        if not isinstance(chain.end_amount, Decimal):
            raise TypeError(f"end_amount is {type(chain.end_amount)}, expected Decimal")
        for rate in chain.decay_rates:
            if not isinstance(rate, Decimal):
                raise TypeError(f"decay rate is {type(rate)}, expected Decimal")

    def test_confidence_score_nonzero(self, layering_scenario: dict) -> None:
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        assert result.confidence > Decimal("0")


# ===================================================================
# Negative Cases
# ===================================================================

class TestNegativeCases:

    def test_no_decay_not_detected(self) -> None:
        """Equal amounts along chain = NOT layering (0% decay outside range)."""
        gr = GraphReasoner()
        nodes = {f"nd_{i}": {"name": f"Node {i}"} for i in range(5)}
        txs = []
        for i in range(4):
            txs.append({
                "id": f"TX-NODEC-{i+1}",
                "source_node": f"nd_{i}",
                "target_node": f"nd_{i+1}",
                "amount": Decimal("100000"),
                "currency": "USD",
                "timestamp": 1700000000 + (i * 7200),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "nd_0")
        assert result.detected is False

    def test_excessive_decay_not_detected(self) -> None:
        """>5.5% decay: outside range + tolerance."""
        gr = GraphReasoner()
        nodes = {f"ex_{i}": {"name": f"Node {i}"} for i in range(5)}
        amounts = [Decimal("100000"), Decimal("92000"), Decimal("84640"), Decimal("77868.80")]
        txs = []
        for i in range(4):
            txs.append({
                "id": f"TX-EXDEC-{i+1}",
                "source_node": f"ex_{i}",
                "target_node": f"ex_{i+1}",
                "amount": amounts[i],
                "currency": "USD",
                "timestamp": 1700000000 + (i * 7200),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "ex_0")
        assert result.detected is False

    def test_short_chain_not_detected(self) -> None:
        """2 hops < MIN_CHAIN_LENGTH (3)."""
        gr = GraphReasoner()
        nodes = {f"sh_{i}": {"name": f"Node {i}"} for i in range(3)}
        txs = [
            {
                "id": "TX-SHORT-1",
                "source_node": "sh_0",
                "target_node": "sh_1",
                "amount": Decimal("100000"),
                "currency": "USD",
                "timestamp": 1700000000,
                "type": "WIRE",
            },
            {
                "id": "TX-SHORT-2",
                "source_node": "sh_1",
                "target_node": "sh_2",
                "amount": Decimal("97000"),
                "currency": "USD",
                "timestamp": 1700007200,
                "type": "WIRE",
            },
        ]
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "sh_0")
        assert result.detected is False

    def test_slow_chain_not_detected(self) -> None:
        """72-hour gaps > MAX_HOP_DELAY_SECONDS (43200s = 12h)."""
        gr = GraphReasoner()
        nodes = {f"sl_{i}": {"name": f"Node {i}"} for i in range(5)}
        amounts = [Decimal("100000"), Decimal("97000"), Decimal("94090"), Decimal("91267.30")]
        txs = []
        for i in range(4):
            txs.append({
                "id": f"TX-SLOW-{i+1}",
                "source_node": f"sl_{i}",
                "target_node": f"sl_{i+1}",
                "amount": amounts[i],
                "currency": "USD",
                "timestamp": 1700000000 + (i * 259200),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "sl_0")
        assert result.detected is False

    def test_increasing_amounts_not_detected(self) -> None:
        """Amounts grow along chain: not decay, not layering."""
        gr = GraphReasoner()
        nodes = {f"inc_{i}": {"name": f"Node {i}"} for i in range(5)}
        amounts = [Decimal("100000"), Decimal("103000"), Decimal("106090"), Decimal("109272.70")]
        txs = []
        for i in range(4):
            txs.append({
                "id": f"TX-INC-{i+1}",
                "source_node": f"inc_{i}",
                "target_node": f"inc_{i+1}",
                "amount": amounts[i],
                "currency": "USD",
                "timestamp": 1700000000 + (i * 7200),
                "type": "WIRE",
            })
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "inc_0")
        assert result.detected is False


# ===================================================================
# Multiple Chains Test
# ===================================================================

class TestMultipleChains:

    def test_multiple_chains_found(self, layering_boundary_scenario: dict) -> None:
        """Graph with 2 distinct valid layering paths (min2pct and max5pct)."""
        gr = _load(layering_boundary_scenario)
        chains_found = []
        for prefix in ["min2pct", "max5pct"]:
            origin = f"{prefix}_0"
            result = detect_layering(gr, origin)
            if result.detected:
                chains_found.append(prefix)
        assert len(chains_found) == 2, f"Expected 2 detected, got {chains_found}"


# ===================================================================
# v8.0 Tests
# ===================================================================

class TestV8Enhancements:

    def test_mixed_currency_chain_rejected(self) -> None:
        """v8.0 [P4v8-05]: USD->INR chain produces meaningless decay."""
        gr = GraphReasoner()
        nodes = {f"mx_{i}": {"name": f"Node {i}"} for i in range(5)}
        txs = [
            {
                "id": "TX-MX-1",
                "source_node": "mx_0",
                "target_node": "mx_1",
                "amount": Decimal("100000"),
                "currency": "USD",
                "timestamp": 1700000000,
                "type": "WIRE",
            },
            {
                "id": "TX-MX-2",
                "source_node": "mx_1",
                "target_node": "mx_2",
                "amount": Decimal("97000"),
                "currency": "INR",
                "timestamp": 1700007200,
                "type": "WIRE",
            },
            {
                "id": "TX-MX-3",
                "source_node": "mx_2",
                "target_node": "mx_3",
                "amount": Decimal("94090"),
                "currency": "USD",
                "timestamp": 1700014400,
                "type": "WIRE",
            },
            {
                "id": "TX-MX-4",
                "source_node": "mx_3",
                "target_node": "mx_4",
                "amount": Decimal("91267.30"),
                "currency": "INR",
                "timestamp": 1700021600,
                "type": "WIRE",
            },
        ]
        gr.load_from_dict({"transactions": txs, "nodes": nodes})
        result = detect_layering(gr, "mx_0")
        assert result.detected is False

    def test_chain_currency_recorded(self, layering_scenario: dict) -> None:
        """v8.0 [P4v8-08]: LayeringChain.currency is set correctly."""
        gr = _load(layering_scenario)
        result = detect_layering(gr, "layer_origin")
        assert result.detected is True
        for chain in result.chains:
            assert chain.currency == "USD"
        assert result.currency == "USD"


def _chain_event(tx_id, source, target, amount, timestamp, currency="USD"):
    return {
        "id": tx_id, "source_node": source, "target_node": target,
        "amount": Decimal(amount), "timestamp": 1700000000 + timestamp,
        "currency": currency,
    }


def _prefix_events():
    return [
        _chain_event("a", "A", "B", "100000", 0),
        _chain_event("b", "B", "C", "97000", 10),
        _chain_event("c", "C", "D", "94090", 20),
    ]


def _cited_sequences(result):
    return [tuple(tx["tx_id"] for tx in chain.chain_transactions) for chain in result.chains]


def _brute_force_layering(events, start, max_depth, currency=None):
    """Exhaust all event permutations, independently of DFS and analyzer."""
    from tracer_agent.src.config import (
        DECAY_RATE_MIN, DECAY_RATE_MAX, DECAY_TOLERANCE, MAX_HOP_DELAY_SECONDS,
    )

    valid = set()
    for length in range(MIN_CHAIN_LENGTH, min(max_depth, len(events)) + 1):
        for chain in permutations(events, length):
            if chain[0]["source_node"] != start:
                continue
            if any(a["target_node"] != b["source_node"] for a, b in zip(chain, chain[1:])):
                continue
            nodes = [start] + [event["target_node"] for event in chain]
            if len(nodes) != len(set(nodes)):
                continue
            currencies = {event["currency"] for event in chain}
            if len(currencies) != 1 or (currency is not None and currencies != {currency}):
                continue
            valid_hops = True
            for a, b in zip(chain, chain[1:]):
                if not 0 <= b["timestamp"] - a["timestamp"] <= MAX_HOP_DELAY_SECONDS:
                    valid_hops = False
                    break
                if a["amount"] <= 0:
                    valid_hops = False
                    break
                decay = (a["amount"] - b["amount"]) / a["amount"]
                if not DECAY_RATE_MIN - DECAY_TOLERANCE <= decay <= DECAY_RATE_MAX + DECAY_TOLERANCE:
                    valid_hops = False
                    break
            if valid_hops:
                valid.add(tuple(event["id"] for event in chain))
    # A valid extension already cites its prefix: keep only maximal evidence.
    return sorted(sequence for sequence in valid if not any(
        len(other) > len(sequence) and other[:len(sequence)] == sequence for other in valid
    ))


class TestChronologicalSubchains:
    def test_reverse_timestamps_are_not_layering(self):
        events = _prefix_events()
        for i, event in enumerate(events):
            event["timestamp"] = 1700000020 - i * 10
        assert not detect_layering(_load({"transactions": events}), "A").detected

    @pytest.mark.parametrize("gap, expected", [(0, True), (43200, True), (43201, False), (-1, False)])
    def test_signed_hop_delay_boundaries(self, gap, expected):
        events = _prefix_events()
        for i, event in enumerate(events):
            event["timestamp"] = 1700100000 + i * gap
        assert detect_layering(_load({"transactions": events}), "A").detected is expected

    @pytest.mark.parametrize("tail", [
        _chain_event("tail", "D", "E", "1", 30),
        _chain_event("tail", "D", "E", "91267.3", 19),
        _chain_event("tail", "D", "E", "91267.3", 86400),
        _chain_event("tail", "D", "E", "91267.3", 30, "INR"),
    ])
    def test_valid_prefix_survives_irrelevant_tail(self, tail):
        result = detect_layering(_load({"transactions": _prefix_events() + [tail]}), "A")
        assert result.detected
        assert _cited_sequences(result) == [("a", "b", "c")]
        assert result.chains[0].end_amount == Decimal("94090")
        assert result.chains[0].hop_count == MIN_CHAIN_LENGTH

    def test_branching_bad_tails_do_not_duplicate_same_prefix(self):
        events = _prefix_events() + [
            _chain_event("tail_x", "D", "E", "1", 30),
            _chain_event("tail_y", "D", "F", "2", 30),
        ]
        result = detect_layering(_load({"transactions": events}), "A")
        assert _cited_sequences(result) == [("a", "b", "c")]
        assert result.total_chains_found == 1

    def test_parallel_equal_amount_events_are_not_collapsed(self):
        events = _prefix_events() + [_chain_event("b_parallel", "B", "C", "97000", 10)]
        result = detect_layering(_load({"transactions": events}), "A")
        assert _cited_sequences(result) == [("a", "b", "c"), ("a", "b_parallel", "c")]

    def test_prefix_already_cited_by_valid_extension_is_not_duplicated(self):
        events = _prefix_events() + [
            _chain_event("good", "D", "E", "91267.3", 30),
            _chain_event("bad", "D", "F", "1", 30),
        ]
        result = detect_layering(_load({"transactions": events}), "A")
        assert _cited_sequences(result) == [("a", "b", "c", "good")]

    @pytest.mark.parametrize("max_depth", [2, 3, 4, 5])
    @pytest.mark.parametrize("currency", [None, "USD", "INR"])
    def test_brute_force_oracle_with_parallel_events_cycles_and_bad_tail(self, max_depth, currency):
        events = _prefix_events() + [
            _chain_event("parallel", "B", "C", "97000", 10),
            _chain_event("good", "D", "E", "91267.3", 30),
            _chain_event("backwards", "D", "F", "91267.3", 19),
            _chain_event("cycle", "D", "A", "91267.3", 30),
        ]
        expected = _brute_force_layering(events, "A", max_depth, currency)
        for seed in range(3):
            shuffled = list(events)
            Random(seed).shuffle(shuffled)
            result = detect_layering(_load({"transactions": shuffled}), "A", max_depth, currency)
            assert _cited_sequences(result) == expected
            assert result.total_chains_found == len(expected)
            assert result.detected is bool(expected)

    def test_seeded_mixed_currency_graphs_match_independent_oracle(self):
        rng = Random(143)
        for _ in range(25):
            events = _prefix_events() + [
                _chain_event("parallel", "B", "C", "97000", 10),
                _chain_event("tail", "D", "E", "91267.3", 30),
            ]
            for event in events:
                event["timestamp"] += rng.choice([-30, 0, 0, 10])
                event["currency"] = rng.choice(["USD", "USD", "USD", "INR"])
                event["amount"] *= rng.choice([Decimal("1"), Decimal("1"), Decimal("2")])
            expected = _brute_force_layering(events, "A", 4)
            result = detect_layering(_load({"transactions": events}), "A", 4)
            assert _cited_sequences(result) == expected

    def test_constraint_pruning_preserves_valid_chain_under_path_cap_noise(self, monkeypatch):
        import tracer_agent.src.core.graph_reasoner as gr_mod
        monkeypatch.setattr(gr_mod, "MAX_PATHS_PER_SEARCH", 5)
        # 20 non-decaying noise branches sorted alphabetically BEFORE the valid chain
        events = [
            _chain_event(f"00_noise_{i:02d}", "A", f"N{i}", "5000", 0)
            for i in range(20)
        ] + [
            _chain_event("z1", "A", "B", "100000", 0),
            _chain_event("z2", "B", "C", "97000", 10),
            _chain_event("z3", "C", "D", "94090", 20),
        ]
        gr_pruned = _load({"transactions": events})
        res_pruned = detect_layering(gr_pruned, "A", max_depth=4, prune_constraints=True)
        # Constraint pruning still finds the valid chain (or at minimum doesn't waste hops expanding invalid tails)
        assert _cited_sequences(res_pruned) == [("z1", "z2", "z3")]

    def test_expired_deadline_marks_coverage_partial(self):
        import time
        gr = _load({"transactions": _prefix_events()})
        result = detect_layering(gr, "A", max_depth=4, deadline_monotonic=time.monotonic() - 1.0)
        assert result.detected is False
        assert gr.coverage["status"] == "PARTIAL"
        assert any(lim["reason"] == "DEADLINE_EXCEEDED" for lim in gr.coverage["limitations"])
