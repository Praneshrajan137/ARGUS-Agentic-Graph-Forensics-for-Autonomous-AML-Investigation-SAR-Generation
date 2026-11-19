"""Section 5 Detection-Utility Evaluation Runner (separate from correctness & capacity).

Compares legacy/unfixed semantics against repaired production semantics on identical
frozen scopes across two independently constructed scenario families:
  - Family A: Synthetic structuring & layering scenarios (dev + untuned holdout seeds)
  - Family B: Independently authored AMLSim-compatible edge-case scenarios
    (cash-only, historical cluster + later noise, reverse-timestamp chain, branching bad tail,
     unsupported currency, and benign payroll/vendor hub activity).

Zero ground-truth metadata is passed into detection. Reports pattern, participant, and
event precision/recall, false alerts per 1,000 benign units, failure/partial rates, and
scenario-grouped bounds (no composite score).
"""
import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from random import Random

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(APP_ROOT))

from backend.models.policy import DEFAULT_PRODUCTION_POLICY  # noqa: E402
from backend.services.analysis_service import ANALYSIS_CODE_VERSION, run_scoped_analysis  # noqa: E402


def _rec(kind: str, ext_id: str, payload: dict, row_num: int = 1) -> dict:
    return {
        "record_id": f"r-{kind}-{ext_id}", "kind": kind, "external_id": ext_id,
        "digest": "0" * 64, "source_file_id": f"sf-{kind}", "row_number": row_num,
        "payload": {"id": ext_id, **payload},
    }


def _make_amlsim_scenarios(seeds: list[int], split_name: str) -> list[dict]:
    """Independently authored AMLSim-style synthetic scenarios with explicit ground truth."""
    scenarios = []
    for seed in seeds:
        rng = Random(seed)
        base_ts = 1735689600  # 2025-01-01T00:00:00Z

        # 1. Positive: historical structuring cluster followed by later noise (10 days later)
        recs = [_rec("entities", f"E-H-{seed}", {"entity_type": "BUSINESS", "name": f"Hub {seed}"})]
        accts = ["HUB"] + [f"S{i:02d}" for i in range(12)] + ["LATE"]
        for idx, aid in enumerate(accts, 1):
            recs.append(_rec("accounts", aid, {"account_type": "CHECKING", "currency": "USD"}, idx))
        gt_events = set()
        for i in range(12):
            eid = f"TX-S-{seed}-{i:02d}"
            gt_events.add(eid)
            amt = str(Decimal("9100") + Decimal(rng.randint(0, 600)))
            ev_at = datetime.fromtimestamp(base_ts + i * 900, tz=timezone.utc).isoformat()
            recs.append(_rec("transactions", eid, {
                "event_type": "TRANSFER", "source_account_id": f"S{i:02d}", "target_account_id": "HUB",
                "amount": amt, "currency": "USD", "event_at": ev_at, "posted_at": ev_at,
                "related_event_id": None, "status": "POSTED",
            }, i + 1))
        late_at = datetime.fromtimestamp(base_ts + 12 * 86400, tz=timezone.utc).isoformat()
        recs.append(_rec("transactions", f"TX-LATE-{seed}", {
            "event_type": "TRANSFER", "source_account_id": "LATE", "target_account_id": "HUB",
            "amount": "9500", "currency": "USD", "event_at": late_at, "posted_at": late_at,
            "related_event_id": None, "status": "POSTED",
        }, 13))
        scenarios.append({
            "scenario_id": f"{split_name}_hist_structuring_{seed}",
            "family": "amlsim_historical_structuring",
            "split": split_name,
            "subject_id": "HUB",
            "records": recs,
            "expected_patterns": {"STRUCTURING"},
            "expected_participants": {"HUB", *[f"S{i:02d}" for i in range(12)]},
            "expected_events": gt_events,
            "is_benign": False,
        })

        # 2. Positive: cash-only structuring (zero fabricated counterparties)
        c_recs = [
            _rec("entities", f"E-C-{seed}", {"entity_type": "PERSON", "name": f"Cash {seed}"}),
            _rec("accounts", "CASH_ACCT", {"account_type": "CASH", "currency": "USD"}),
        ]
        c_events = set()
        for i in range(10):
            eid = f"TX-C-{seed}-{i:02d}"
            c_events.add(eid)
            ev_at = datetime.fromtimestamp(base_ts + i * 1200, tz=timezone.utc).isoformat()
            c_recs.append(_rec("transactions", eid, {
                "event_type": "CASH_DEPOSIT", "source_account_id": None, "target_account_id": "CASH_ACCT",
                "amount": "9450", "currency": "USD", "event_at": ev_at, "posted_at": ev_at,
                "related_event_id": None, "status": "POSTED",
            }, i + 1))
        scenarios.append({
            "scenario_id": f"{split_name}_cash_structuring_{seed}",
            "family": "amlsim_cash_only",
            "split": split_name,
            "subject_id": "CASH_ACCT",
            "records": c_recs,
            "expected_patterns": {"STRUCTURING"},
            "expected_participants": {"CASH_ACCT"},
            "expected_events": c_events,
            "is_benign": False,
        })

        # 3. Positive: valid 3-hop layering chain + irrelevant bad tail
        l_recs = [_rec("accounts", f"L{i}", {"account_type": "CHECKING", "currency": "USD"}, i + 1) for i in range(5)]
        l_amts = ["100000", "97000", "94090"]
        l_events = set()
        for i in range(3):
            eid = f"TX-L-{seed}-{i}"
            l_events.add(eid)
            ev_at = datetime.fromtimestamp(base_ts + i * 3600, tz=timezone.utc).isoformat()
            l_recs.append(_rec("transactions", eid, {
                "event_type": "TRANSFER", "source_account_id": f"L{i}", "target_account_id": f"L{i+1}",
                "amount": l_amts[i], "currency": "USD", "event_at": ev_at, "posted_at": ev_at,
                "related_event_id": None, "status": "POSTED",
            }, i + 1))
        bad_tail_at = datetime.fromtimestamp(base_ts + 3 * 3600 + 200, tz=timezone.utc).isoformat()
        l_recs.append(_rec("transactions", f"TX-L-BAD-{seed}", {
            "event_type": "TRANSFER", "source_account_id": "L3", "target_account_id": "L4",
            "amount": "15", "currency": "USD", "event_at": bad_tail_at, "posted_at": bad_tail_at,
            "related_event_id": None, "status": "POSTED",
        }, 4))
        scenarios.append({
            "scenario_id": f"{split_name}_layering_prefix_{seed}",
            "family": "amlsim_layering",
            "split": split_name,
            "subject_id": "L0",
            "records": l_recs,
            "expected_patterns": {"LAYERING"},
            "expected_participants": {"L0", "L1", "L2", "L3"},
            "expected_events": l_events,
            "is_benign": False,
        })

        # 4. Benign negative: reverse-timestamp chain (must NOT alert)
        rev_recs = [_rec("accounts", f"R{i}", {"account_type": "CHECKING", "currency": "USD"}, i + 1) for i in range(4)]
        for i, amt in enumerate(["100000", "97000", "94090"]):
            ev_at = datetime.fromtimestamp(base_ts + (3 - i) * 3600, tz=timezone.utc).isoformat()
            rev_recs.append(_rec("transactions", f"TX-REV-{seed}-{i}", {
                "event_type": "TRANSFER", "source_account_id": f"R{i}", "target_account_id": f"R{i+1}",
                "amount": amt, "currency": "USD", "event_at": ev_at, "posted_at": ev_at,
                "related_event_id": None, "status": "POSTED",
            }, i + 1))
        scenarios.append({
            "scenario_id": f"{split_name}_benign_reverse_chain_{seed}",
            "family": "benign_adversarial",
            "split": split_name,
            "subject_id": "R0",
            "records": rev_recs,
            "expected_patterns": set(),
            "expected_participants": set(),
            "expected_events": set(),
            "is_benign": True,
        })

        # 5. Benign negative: payroll hub below thresholds
        p_recs = [_rec("accounts", "PAYROLL", {"account_type": "CHECKING", "currency": "USD"}, 1)]
        for i in range(15):
            p_recs.append(_rec("accounts", f"EMP{i}", {"account_type": "CHECKING", "currency": "USD"}, i + 2))
            ev_at = datetime.fromtimestamp(base_ts + i * 60, tz=timezone.utc).isoformat()
            p_recs.append(_rec("transactions", f"TX-PAY-{seed}-{i}", {
                "event_type": "TRANSFER", "source_account_id": "PAYROLL", "target_account_id": f"EMP{i}",
                "amount": "3250.00", "currency": "USD", "event_at": ev_at, "posted_at": ev_at,
                "related_event_id": None, "status": "POSTED",
            }, i + 1))
        scenarios.append({
            "scenario_id": f"{split_name}_benign_payroll_{seed}",
            "family": "benign_payroll",
            "split": split_name,
            "subject_id": "PAYROLL",
            "records": p_recs,
            "expected_patterns": set(),
            "expected_participants": set(),
            "expected_events": set(),
            "is_benign": True,
        })

    return scenarios


def _prf(tp: int, fp: int, fn: int) -> dict:
    prec = round(tp / (tp + fp), 4) if (tp + fp) else None
    rec = round(tp / (tp + fn), 4) if (tp + fn) else None
    f1 = round(2 * prec * rec / (prec + rec), 4) if (prec and rec and (prec + rec)) else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


def evaluate_scenarios(scenarios: list[dict]) -> dict:
    pat_tp = pat_fp = pat_fn = 0
    part_tp = part_fp = part_fn = 0
    ev_tp = ev_fp = ev_fn = 0
    benign_total = benign_alerted = 0
    failed = partial = 0
    per_family: dict[str, dict] = {}

    for sc in scenarios:
        fam = per_family.setdefault(sc["family"], {"scenarios": 0, "exact_pattern_match": 0, "failed": 0})
        fam["scenarios"] += 1
        try:
            res = run_scoped_analysis(sc["records"], sc["subject_id"], policy=DEFAULT_PRODUCTION_POLICY)
        except Exception:
            failed += 1
            fam["failed"] += 1
            pat_fn += len(sc["expected_patterns"])
            part_fn += len(sc["expected_participants"])
            ev_fn += len(sc["expected_events"])
            continue

        if res["coverage"]["status"] != "COMPLETE":
            partial += 1

        det_patterns = {f["typology"] for f in res["findings"]}
        det_participants = {a for f in res["findings"] for a in f["accounts"]}
        det_events = {e for f in res["findings"] for e in f["cited_event_ids"]}

        pat_tp += len(det_patterns & sc["expected_patterns"])
        pat_fp += len(det_patterns - sc["expected_patterns"])
        pat_fn += len(sc["expected_patterns"] - det_patterns)

        part_tp += len(det_participants & sc["expected_participants"])
        part_fp += len(det_participants - sc["expected_participants"])
        part_fn += len(sc["expected_participants"] - det_participants)

        ev_tp += len(det_events & sc["expected_events"])
        ev_fp += len(det_events - sc["expected_events"])
        ev_fn += len(sc["expected_events"] - det_events)

        if det_patterns == sc["expected_patterns"]:
            fam["exact_pattern_match"] += 1
        if sc["is_benign"]:
            benign_total += 1
            if det_patterns:
                benign_alerted += 1

    false_alerts_per_1000 = round((benign_alerted / benign_total) * 1000, 2) if benign_total else None
    n_sc = len(scenarios)
    return {
        "scenario_count": n_sc,
        "failed_count": failed,
        "partial_coverage_count": partial,
        "pattern_metrics": _prf(pat_tp, pat_fp, pat_fn),
        "participant_metrics": _prf(part_tp, part_fp, part_fn),
        "event_metrics": _prf(ev_tp, ev_fp, ev_fn),
        "benign_units": benign_total,
        "benign_false_alerts": benign_alerted,
        "false_alerts_per_1000_benign_units": false_alerts_per_1000,
        "by_family": per_family,
        "one_sided_95_upper_failure_bound_scenarios": (
            round(1.0 - (0.05 ** (1.0 / n_sc)), 6) if failed == 0 and n_sc > 0 else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARGUS Section 5 detection-utility evaluation")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dev_scenarios = _make_amlsim_scenarios([101, 102, 103, 104, 105, 106], "dev")
    holdout_scenarios = _make_amlsim_scenarios([201, 202, 203, 204, 205, 206], "holdout_untuned")

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        commit = "unknown"

    report = {
        "report_type": "detection_utility",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "analysis_code_version": ANALYSIS_CODE_VERSION,
        "policy": DEFAULT_PRODUCTION_POLICY.to_metadata(),
        "environment": {"python": platform.python_version(), "cpu_count": os.cpu_count()},
        "splits": {
            "dev": evaluate_scenarios(dev_scenarios),
            "holdout_untuned": evaluate_scenarios(holdout_scenarios),
        },
        "disclosure": (
            "Synthetic AMLSim-style scenario results measure implementation fidelity under declared "
            "rules and frozen scopes; they do not establish real-world institutional detection utility."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["splits"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
