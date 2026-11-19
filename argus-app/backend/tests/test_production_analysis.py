"""Milestone D: production scoped analysis, cash windowing, policy/business-day & observation tests."""
import sys
from decimal import Decimal
from pathlib import Path
from random import Random


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND.parent))

from backend.models.policy import (  # noqa: E402
    BusinessDayConfig, CurrencyStructuringThreshold, RulePolicy,
)
from backend.services.analysis_service import run_scoped_analysis  # noqa: E402
from backend.services.observation_service import evaluate_scoped_observation  # noqa: E402


def _rec(kind: str, ext_id: str, payload: dict, row_num: int = 1) -> dict:
    return {
        "record_id": f"rec-{kind}-{ext_id}",
        "kind": kind,
        "external_id": ext_id,
        "digest": "d" * 64,
        "source_file_id": f"sf-{kind}",
        "row_number": row_num,
        "payload": {"id": ext_id, **payload},
    }


def _base_entities_and_accounts(account_ids=("A001", "A002")):
    records = [_rec("entities", "E1", {"entity_type": "PERSON", "name": "Subject One"})]
    for idx, aid in enumerate(account_ids, 1):
        records.append(_rec("accounts", aid, {"account_type": "CHECKING", "currency": "USD"}, idx))
        records.append(_rec("relationships", f"R-{aid}", {
            "entity_id": "E1", "account_id": aid, "role": "OWNER",
            "valid_from": "2024-01-01T00:00:00+00:00", "valid_to": None,
        }, idx))
    return records


def test_cash_only_structuring_detects_without_fabricating_graph_counterparties():
    records = _base_entities_and_accounts(("CASH-1",))
    for i in range(10):
        records.append(_rec("transactions", f"C-{i:02d}", {
            "event_type": "CASH_DEPOSIT",
            "source_account_id": None,
            "target_account_id": "CASH-1",
            "amount": "9500",
            "currency": "USD",
            "event_at": f"2025-01-02T10:{i:02d}:00+00:00",
            "posted_at": "2025-01-03T00:00:00+00:00",
            "related_event_id": None,
            "status": "POSTED",
        }, i + 1))

    result = run_scoped_analysis(records, "CASH-1")
    assert result["coverage"]["status"] == "COMPLETE"
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["typology"] == "STRUCTURING"
    assert finding["channel"] == "CASH"
    assert finding["known_counterparty_count"] == 0
    assert finding["accounts"] == ["CASH-1"]
    assert finding["total_amount"] == "95000"
    assert result["graph"]["nodes"] == [{"id": "CASH-1", "account_type": "CHECKING", "currency": "USD", "is_subject": True}]
    assert result["graph"]["edges"] == []


def test_unsupported_currency_never_falls_back_to_usd_and_is_excluded_explicitly():
    records = _base_entities_and_accounts(("A001", "A002"))
    for i in range(12):
        records.append(_rec("transactions", f"EUR-{i:02d}", {
            "event_type": "TRANSFER",
            "source_account_id": "A001",
            "target_account_id": "A002",
            "amount": "9500",
            "currency": "EUR",
            "event_at": f"2025-01-02T10:{i:02d}:00+00:00",
            "posted_at": "2025-01-03T00:00:00+00:00",
            "related_event_id": None,
            "status": "POSTED",
        }, i + 1))

    result = run_scoped_analysis(records, "A002")
    assert result["findings"] == []
    assert result["coverage"]["excluded_breakdown"]["UNSUPPORTED_STRUCTURING_CURRENCY"] == 12


def test_reversals_pending_and_fx_events_are_visibly_excluded():
    records = _base_entities_and_accounts(("A001", "A002"))
    records.extend([
        _rec("transactions", "T-1", {
            "event_type": "TRANSFER", "source_account_id": "A001", "target_account_id": "A002",
            "amount": "9500", "currency": "USD", "event_at": "2025-01-02T10:00:00+00:00",
            "posted_at": "2025-01-02T11:00:00+00:00", "related_event_id": None, "status": "POSTED",
        }, 1),
        _rec("transactions", "T-1-REV", {
            "event_type": "REVERSAL", "source_account_id": "A002", "target_account_id": "A001",
            "amount": "9500", "currency": "USD", "event_at": "2025-01-02T10:30:00+00:00",
            "posted_at": "2025-01-02T11:30:00+00:00", "related_event_id": "T-1", "status": "POSTED",
        }, 2),
        _rec("transactions", "T-PEND", {
            "event_type": "TRANSFER", "source_account_id": "A001", "target_account_id": "A002",
            "amount": "9500", "currency": "USD", "event_at": "2025-01-02T10:45:00+00:00",
            "posted_at": "2025-01-02T11:45:00+00:00", "related_event_id": None, "status": "PENDING",
        }, 3),
        _rec("transactions", "T-FX", {
            "event_type": "FX_CONVERSION", "source_account_id": "A001", "target_account_id": "A002",
            "amount": "9500", "currency": "USD", "event_at": "2025-01-02T10:50:00+00:00",
            "posted_at": "2025-01-02T11:50:00+00:00", "related_event_id": None, "status": "POSTED",
        }, 4),
    ])
    result = run_scoped_analysis(records, "A002")
    breakdown = result["coverage"]["excluded_breakdown"]
    assert breakdown["REVERSED_ORIGINAL_EVENT"] == 1
    assert breakdown["REVERSAL_EVENT"] == 1
    assert breakdown["PENDING_EVENT"] == 1
    assert breakdown["FX_EVENT_UNSUPPORTED"] == 1
    assert result["coverage"]["considered_events"] == 0


def test_institution_business_day_window_respects_cutoff_and_weekends():
    # Friday 18:00 ET (23:00 UTC) rolls into Monday business day; Monday 10:00 ET (15:00 UTC)
    # is the SAME Monday business day, even though >60h wall-clock elapsed if compared to Thursday!
    bd_policy = RulePolicy(
        policy_id="us-bd-test",
        policy_version="1.0",
        rationale="Test institutional business-day grouping",
        is_synthetic_preset=True,
        structuring_thresholds={
            "USD": CurrencyStructuringThreshold("USD", Decimal("9000"), Decimal("9800"), 3, 86400),
        },
        business_day=BusinessDayConfig(
            mode="INSTITUTION_BUSINESS_DAY",
            institution_timezone="America/New_York",
            cutoff_hour=17,
            business_days_window=1,  # same single business day
            holidays=("2025-01-20",),  # MLK Day Monday -> rolls to Tuesday Jan 21
        ),
    )
    records = _base_entities_and_accounts(("A001",))
    # Fri Jan 17 2025 18:00 ET (23:00Z) -> after cutoff -> skips Sat/Sun + Mon holiday -> Tue Jan 21
    # Mon Jan 20 2025 12:00 ET (17:00Z) -> holiday -> Tue Jan 21
    # Tue Jan 21 2025 10:00 ET (15:00Z) -> Tue Jan 21
    times = [
        "2025-01-17T23:00:00+00:00",
        "2025-01-20T17:00:00+00:00",
        "2025-01-21T15:00:00+00:00",
    ]
    for i, ts in enumerate(times, 1):
        records.append(_rec("transactions", f"BD-{i}", {
            "event_type": "CASH_DEPOSIT", "source_account_id": None, "target_account_id": "A001",
            "amount": "9500", "currency": "USD", "event_at": ts, "posted_at": ts,
            "related_event_id": None, "status": "POSTED",
        }, i))

    # Under 1 business day (with cutoff + holiday), all 3 share business day 2025-01-21 -> detected!
    res_bd = run_scoped_analysis(records, "A001", policy=bd_policy)
    assert len(res_bd["findings"]) == 1
    assert res_bd["findings"][0]["window_mode"] == "INSTITUTION_BUSINESS_DAY"

    # Under 24h rolling UTC seconds, Fri 23:00Z to Tue 15:00Z spans 88h -> NOT detected!
    rolling_policy = RulePolicy(
        policy_id="us-roll-test",
        policy_version="1.0",
        rationale="Rolling comparison",
        is_synthetic_preset=True,
        structuring_thresholds=bd_policy.structuring_thresholds,
        business_day=BusinessDayConfig(mode="ROLLING_SECONDS"),
    )
    res_roll = run_scoped_analysis(records, "A001", policy=rolling_policy)
    assert res_roll["findings"] == []


def test_metamorphic_record_order_invariance_and_temporal_owners():
    records = [
        _rec("entities", "E1", {"entity_type": "PERSON", "name": "Prior Owner"}),
        _rec("entities", "E2", {"entity_type": "PERSON", "name": "New Owner"}),
        _rec("accounts", "A001", {"account_type": "CHECKING", "currency": "USD"}),
        _rec("accounts", "A002", {"account_type": "CHECKING", "currency": "USD"}),
        _rec("accounts", "A003", {"account_type": "CHECKING", "currency": "USD"}),
        _rec("accounts", "A004", {"account_type": "CHECKING", "currency": "USD"}),
        _rec("relationships", "R1", {"entity_id": "E1", "account_id": "A001", "role": "OWNER",
             "valid_from": "2024-01-01T00:00:00+00:00", "valid_to": "2025-01-01T00:00:00+00:00"}),
        _rec("relationships", "R2", {"entity_id": "E2", "account_id": "A001", "role": "OWNER",
             "valid_from": "2025-01-01T00:00:00+00:00", "valid_to": None}),
        _rec("transactions", "L1", {"event_type": "TRANSFER", "source_account_id": "A001", "target_account_id": "A002",
             "amount": "100000", "currency": "USD", "event_at": "2024-06-01T10:00:00+00:00",
             "posted_at": "2024-06-01T10:00:00+00:00", "related_event_id": None, "status": "POSTED"}),
        _rec("transactions", "L2", {"event_type": "TRANSFER", "source_account_id": "A002", "target_account_id": "A003",
             "amount": "97000", "currency": "USD", "event_at": "2024-06-01T11:00:00+00:00",
             "posted_at": "2024-06-01T11:00:00+00:00", "related_event_id": None, "status": "POSTED"}),
        _rec("transactions", "L3", {"event_type": "TRANSFER", "source_account_id": "A003", "target_account_id": "A004",
             "amount": "94090", "currency": "USD", "event_at": "2024-06-01T12:00:00+00:00",
             "posted_at": "2024-06-01T12:00:00+00:00", "related_event_id": None, "status": "POSTED"}),
    ]
    baseline = run_scoped_analysis(records, "A001")
    assert len(baseline["findings"]) == 1
    assert baseline["findings"][0]["typology"] == "LAYERING"
    # L1 occurred in 2024 -> source owner at event time is E1, NOT E2!
    l1_edge = next(e for e in baseline["graph"]["edges"] if e["event_id"] == "L1")
    assert l1_edge["source_owners_at_event"] == ["E1"]

    for seed in range(5):
        shuffled = list(records)
        Random(seed).shuffle(shuffled)
        again = run_scoped_analysis(shuffled, "A001")
        assert again["findings"] == baseline["findings"]
        assert again["coverage"] == baseline["coverage"]


def test_observation_evaluation_separates_no_observation_incomparable_and_disagreement():
    scope = {
        "entity_id": "A001", "period_start": "2025-01-01", "period_end": "2025-02-01",
        "currency": "USD", "basis": "INFLOW", "aggregation": "total",
    }
    no_obs = evaluate_scoped_observation("No numbers mentioned here.", document_id="D1",
                                         doc_scope=scope, ledger_total=Decimal("5000"), ledger_scope=scope)
    assert no_obs["verdict"] == "NO_OBSERVATION"

    incomp = evaluate_scoped_observation("Deposit of $5,000 USD", document_id="D2",
                                         doc_scope={**scope, "entity_id": "OTHER"},
                                         ledger_total=Decimal("5000"), ledger_scope=scope)
    assert incomp["verdict"] == "NOT_COMPARABLE"

    disagree = evaluate_scoped_observation("Deposit of $5,500 USD", document_id="D3",
                                           doc_scope=scope, ledger_total=Decimal("5000"), ledger_scope=scope)
    assert disagree["verdict"] == "DISAGREEMENT"
    assert "neither proof" in disagree["interpretation_notice"]
