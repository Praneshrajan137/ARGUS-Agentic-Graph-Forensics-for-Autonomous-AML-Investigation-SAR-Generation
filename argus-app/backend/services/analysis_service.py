"""Explicit production analysis pipeline: validate scope -> load pinned snapshot -> detect -> persist.

Zero external AI, zero research confidence gates hiding findings, zero synthetic
counterparties for cash events, and zero silent USD fallback for unsupported currencies.
"""
import hashlib
import time
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tracer_agent.src.core.graph_reasoner import GraphReasoner
from tracer_agent.src.core.heuristics.layering import detect_layering
from tracer_agent.src.core.heuristics.structuring import (
    find_structuring_patterns,
    find_structuring_windows,
)

from ..database import LedgerRecord, Snapshot, SnapshotRecord
from ..models.ledger import analysis_eligibility, decimal_string, timestamp
from ..models.policy import DEFAULT_PRODUCTION_POLICY, RulePolicy
from .intake_service import canonical_payload

ANALYSIS_CODE_VERSION = "argus-analysis-v1"


def _finding_id(kind: str, scope_key: tuple, cited_event_ids: list[str]) -> str:
    payload = {
        "kind": kind,
        "scope": [str(item) for item in scope_key],
        "events": sorted(cited_event_ids),
    }
    return hashlib.sha256(canonical_payload(payload)).hexdigest()[:24]


def _resolve_subject_accounts(
    subject_id: str,
    accounts: dict[str, dict],
    relationships: list[dict],
) -> list[str]:
    """Resolve subject_id as either a direct account ID or an entity owning accounts."""
    if subject_id in accounts:
        return [subject_id]
    owned = sorted({
        rel["account_id"] for rel in relationships
        if rel["entity_id"] == subject_id and rel["account_id"] in accounts
    })
    return owned


def _owners_at_time(account_id: str, event_dt: datetime, relationships_by_acct: dict[str, list[dict]]) -> list[str]:
    """Return party IDs with an effective relationship covering event_dt (never retrospective)."""
    owners = []
    for rel in relationships_by_acct.get(account_id, []):
        start = timestamp(rel["valid_from"])
        end = timestamp(rel["valid_to"]) if rel.get("valid_to") else None
        if start <= event_dt and (end is None or event_dt < end):
            owners.append(rel["entity_id"])
    return sorted(set(owners))


def _window_events_with_policy(
    events: list[dict],
    account_id: str,
    currency: str,
    mode: str,
    policy: RulePolicy,
) -> list[dict]:
    """Run structuring window detection under ROLLING_SECONDS or INSTITUTION_BUSINESS_DAY."""
    threshold = policy.threshold_for(currency)
    if threshold is None:
        return []

    if policy.business_day.mode == "INSTITUTION_BUSINESS_DAY":
        # Map each event timestamp to its configured institution business-day ordinal
        # so the shared sliding-window algorithm operates on exact business days
        # without ever silently grouping by UTC calendar date.
        mapped = []
        orig_ts_by_id: dict[str, int] = {}
        for ev in events:
            ev_dt = ev["event_dt"]
            orig_ts_by_id[ev["tx_id"]] = ev["timestamp"]
            mapped.append({
                **ev,
                "timestamp": policy.business_day.business_day_index(ev_dt),
            })
        window_span = max(0, policy.business_day.business_days_window - 1)
        results = find_structuring_windows(
            mapped,
            account_id,
            currency=currency,
            mode=mode,
            thresholds=(threshold.min_amount, threshold.max_amount, threshold.min_count, window_span),
            strict_currency=True,
        )
        out = []
        for res in results:
            actual_times = [orig_ts_by_id[tx["tx_id"]] for tx in res.qualifying_transactions]
            out.append({
                "result": res,
                "window_start": min(actual_times),
                "window_end": max(actual_times),
                "window_mode": "INSTITUTION_BUSINESS_DAY",
            })
        return out

    results = find_structuring_windows(
        events,
        account_id,
        currency=currency,
        mode=mode,
        thresholds=(threshold.min_amount, threshold.max_amount, threshold.min_count, threshold.window_seconds),
        strict_currency=True,
    )
    return [
        {
            "result": res,
            "window_start": res.window_start,
            "window_end": res.window_end,
            "window_mode": "ROLLING_SECONDS",
        }
        for res in results
    ]


def run_scoped_analysis(
    records: list[dict[str, Any]],
    subject_id: str,
    *,
    hop_depth: int = 3,
    policy: RulePolicy = DEFAULT_PRODUCTION_POLICY,
    interval_start: str | None = None,
    interval_end: str | None = None,
    max_events: int = 20_000,
    max_accounts: int = 5_000,
    deadline_seconds: float = 60.0,
) -> dict[str, Any]:
    """Execute deterministic scoped analysis on pinned snapshot records.

    Each item in `records` is a dict containing:
      kind, external_id, record_id, digest, source_file_id, row_number, payload
    """
    if not 1 <= hop_depth <= 6:
        raise ValueError("hop_depth must be between 1 and 6")

    deadline_mono = time.monotonic() + max(0.001, deadline_seconds)
    start_dt = timestamp(interval_start) if interval_start else None
    end_dt = timestamp(interval_end) if interval_end else None
    if start_dt and end_dt and start_dt >= end_dt:
        raise ValueError("interval_start must precede interval_end")

    entities: dict[str, dict] = {}
    accounts: dict[str, dict] = {}
    relationships: list[dict] = []
    relationships_by_acct: dict[str, list[dict]] = {}
    transactions: list[dict] = []

    for item in records:
        kind = item["kind"]
        payload = item["payload"]
        ext_id = item["external_id"]
        if kind == "entities":
            entities[ext_id] = {**payload, "_meta": item}
        elif kind == "accounts":
            accounts[ext_id] = {**payload, "_meta": item}
        elif kind == "relationships":
            relationships.append(payload)
            relationships_by_acct.setdefault(payload["account_id"], []).append(payload)
        elif kind == "transactions":
            transactions.append(item)

    subject_accounts = _resolve_subject_accounts(subject_id, accounts, relationships)
    if not subject_accounts:
        raise ValueError(f"Subject '{subject_id}' has no accounts in pinned snapshot")

    # Identify transactions explicitly reversed by a POSTED REVERSAL event
    reversed_event_ids: set[str] = {
        item["payload"]["related_event_id"]
        for item in transactions
        if item["payload"].get("event_type") == "REVERSAL"
        and item["payload"].get("status", "POSTED") == "POSTED"
        and item["payload"].get("related_event_id")
    }

    limitations: list[dict[str, Any]] = []
    excluded_events: list[dict[str, Any]] = []
    excluded_breakdown: dict[str, int] = {}

    def record_exclusion(item: dict, reason: str) -> None:
        excluded_breakdown[reason] = excluded_breakdown.get(reason, 0) + 1
        if len(excluded_events) < 500:
            p = item["payload"]
            excluded_events.append({
                "event_id": item["external_id"],
                "record_id": item.get("record_id"),
                "source_file_id": item.get("source_file_id"),
                "row_number": item.get("row_number"),
                "reason": reason,
                "event_type": p.get("event_type"),
                "status": p.get("status", "POSTED"),
                "currency": p.get("currency"),
                "amount": p.get("amount"),
                "event_at": p.get("event_at"),
            })

    # Partition transactions into known-endpoint transfers vs cash events vs exclusions
    transfer_adj: dict[str, set[str]] = {}
    all_transfer_items: list[dict] = []
    cash_by_account: dict[tuple[str, str, str], list[dict]] = {}
    considered_count = 0

    for item in sorted(transactions, key=lambda r: r["external_id"]):
        p = item["payload"]
        ev_dt = timestamp(p["event_at"])
        if start_dt and ev_dt < start_dt:
            record_exclusion(item, "OUTSIDE_INTERVAL")
            continue
        if end_dt and ev_dt >= end_dt:
            record_exclusion(item, "OUTSIDE_INTERVAL")
            continue

        eligible, excl_reason = analysis_eligibility(p)
        if not eligible:
            record_exclusion(item, excl_reason or "INELIGIBLE")
            continue
        if item["external_id"] in reversed_event_ids:
            record_exclusion(item, "REVERSED_ORIGINAL_EVENT")
            continue

        ev_type = p["event_type"]
        if ev_type == "TRANSFER":
            src, dst = p["source_account_id"], p["target_account_id"]
            if not src or not dst:
                record_exclusion(item, "MISSING_TRANSFER_ENDPOINT")
                continue
            transfer_adj.setdefault(src, set()).add(dst)
            transfer_adj.setdefault(dst, set()).add(src)
            all_transfer_items.append(item)
        elif ev_type in ("CASH_DEPOSIT", "CASH_WITHDRAWAL"):
            acct = p["target_account_id"] if ev_type == "CASH_DEPOSIT" else p["source_account_id"]
            mode = "FAN_IN" if ev_type == "CASH_DEPOSIT" else "FAN_OUT"
            cash_by_account.setdefault((acct, p["currency"], mode), []).append({
                "tx_id": item["external_id"],
                "source_node": "",  # Unknown external counterparty — NEVER fabricated
                "target_node": "",
                "amount": Decimal(p["amount"]),
                "currency": p["currency"],
                "timestamp": int(ev_dt.timestamp()),
                "event_dt": ev_dt,
                "tx_type": ev_type,
                "record_id": item.get("record_id"),
            })
        else:
            record_exclusion(item, "UNSUPPORTED_EVENT_TYPE")

    # Bounded BFS over known-endpoint transfer graph from subject_accounts
    scoped_accounts: set[str] = set(subject_accounts)
    queue: deque[tuple[str, int]] = deque((acct, 0) for acct in subject_accounts)
    while queue:
        acct, depth = queue.popleft()
        if depth >= hop_depth:
            continue
        for nbr in sorted(transfer_adj.get(acct, ())):
            if nbr not in scoped_accounts:
                if len(scoped_accounts) >= max_accounts:
                    limitations.append({"reason": "MAX_GRAPH_ACCOUNTS", "node": acct, "limit": max_accounts})
                    queue.clear()
                    break
                scoped_accounts.add(nbr)
                queue.append((nbr, depth + 1))

    # Filter transfer events to scoped_accounts within max_events budget
    scoped_transfers: list[dict] = []
    for item in all_transfer_items:
        p = item["payload"]
        if p["source_account_id"] in scoped_accounts and p["target_account_id"] in scoped_accounts:
            if len(scoped_transfers) >= max_events:
                limitations.append({"reason": "MAX_GRAPH_EVENTS", "node": subject_id, "limit": max_events})
                break
            scoped_transfers.append(item)

    # Track unsupported-currency structuring exclusions explicitly (NEVER coerce to USD)
    supported_structuring_currencies = set(policy.structuring_thresholds.keys())
    currencies_in_scope: set[str] = set()

    graph_txs: list[dict] = []
    for item in scoped_transfers:
        p = item["payload"]
        ev_dt = timestamp(p["event_at"])
        cur = p["currency"]
        currencies_in_scope.add(cur)
        if cur not in supported_structuring_currencies:
            record_exclusion(item, "UNSUPPORTED_STRUCTURING_CURRENCY")
        graph_txs.append({
            "id": item["external_id"],
            "source_node": p["source_account_id"],
            "target_node": p["target_account_id"],
            "amount": Decimal(p["amount"]),
            "currency": cur,
            "timestamp": int(ev_dt.timestamp()),
            "event_dt": ev_dt,
            "type": p["event_type"],
            "record_id": item.get("record_id"),
        })
        considered_count += 1

    # Also account for scoped cash events
    scoped_cash_keys = sorted(
        key for key in cash_by_account if key[0] in scoped_accounts
    )
    for acct, cur, mode in scoped_cash_keys:
        currencies_in_scope.add(cur)
        events = cash_by_account[(acct, cur, mode)]
        if cur not in supported_structuring_currencies:
            for ev in events:
                excluded_breakdown["UNSUPPORTED_STRUCTURING_CURRENCY"] = (
                    excluded_breakdown.get("UNSUPPORTED_STRUCTURING_CURRENCY", 0) + 1
                )
        considered_count += len(events)

    findings_by_id: dict[str, dict[str, Any]] = {}
    subject_acct_set = set(subject_accounts)

    # 1. Graph-based transfer detection (structuring + constraint-pruned layering)
    reasoner = GraphReasoner()
    if graph_txs:
        nodes_dict = {
            acct_id: {
                "id": acct_id,
                "account_type": accounts[acct_id].get("account_type", "UNKNOWN"),
                "currency": accounts[acct_id].get("currency"),
            }
            for acct_id in sorted(scoped_accounts)
            if acct_id in accounts
        }
        reasoner.load_from_dict({"transactions": graph_txs, "nodes": nodes_dict}, strict_currency=True)

        # Build event_dt map for business-day windowing if configured
        tx_dt_map = {tx["id"]: tx["event_dt"] for tx in graph_txs}

        for acct_id in sorted(scoped_accounts):
            if time.monotonic() >= deadline_mono:
                limitations.append({"reason": "DEADLINE_EXCEEDED", "node": acct_id, "limit": int(deadline_seconds)})
                break
            for cur in sorted(currencies_in_scope & supported_structuring_currencies):
                threshold = policy.threshold_for(cur)
                if threshold is None:
                    continue
                if policy.business_day.mode == "INSTITUTION_BUSINESS_DAY":
                    for mode, raw_edges in (
                        ("FAN_IN", reasoner.get_1hop_incoming(acct_id)),
                        ("FAN_OUT", reasoner.get_1hop_outgoing(acct_id)),
                    ):
                        enriched = [{**edge, "event_dt": tx_dt_map[edge["tx_id"]]} for edge in raw_edges]
                        for wrapped in _window_events_with_policy(enriched, acct_id, cur, mode, policy):
                            res = wrapped["result"]
                            cited = sorted(tx["tx_id"] for tx in res.qualifying_transactions)
                            fid = _finding_id("STRUCTURING_TRANSFER", (acct_id, cur, mode, wrapped["window_start"], wrapped["window_end"]), cited)
                            involved_accts = sorted({acct_id, *res.counterpart_nodes})
                            findings_by_id[fid] = {
                                "finding_id": fid,
                                "typology": "STRUCTURING",
                                "channel": "TRANSFER",
                                "mode": mode,
                                "focus_account": acct_id,
                                "accounts": involved_accts,
                                "subject_involved": bool(subject_acct_set.intersection(involved_accts)),
                                "currency": cur,
                                "total_amount": decimal_string(res.total_amount),
                                "event_count": res.transaction_count,
                                "known_counterparty_count": len(res.counterpart_nodes),
                                "window_start": wrapped["window_start"],
                                "window_end": wrapped["window_end"],
                                "window_mode": wrapped["window_mode"],
                                "cited_event_ids": cited,
                                "uncalibrated_priority_score": decimal_string(res.confidence),
                                "score_disclaimer": "Uncalibrated heuristic priority score; not a probability or filing decision.",
                                "reasoning": res.reasoning,
                            }
                else:
                    patterns = find_structuring_patterns(
                        reasoner,
                        acct_id,
                        currency=cur,
                        thresholds=(threshold.min_amount, threshold.max_amount, threshold.min_count, threshold.window_seconds),
                        strict_currency=True,
                    )
                    for res in patterns:
                        cited = sorted(tx["tx_id"] for tx in res.qualifying_transactions)
                        fid = _finding_id("STRUCTURING_TRANSFER", (acct_id, cur, res.mode, res.window_start, res.window_end), cited)
                        involved_accts = sorted({acct_id, *res.counterpart_nodes})
                        findings_by_id[fid] = {
                            "finding_id": fid,
                            "typology": "STRUCTURING",
                            "channel": "TRANSFER",
                            "mode": res.mode,
                            "focus_account": acct_id,
                            "accounts": involved_accts,
                            "subject_involved": bool(subject_acct_set.intersection(involved_accts)),
                            "currency": cur,
                            "total_amount": decimal_string(res.total_amount),
                            "event_count": res.transaction_count,
                            "known_counterparty_count": len(res.counterpart_nodes),
                            "window_start": res.window_start,
                            "window_end": res.window_end,
                            "window_mode": "ROLLING_SECONDS",
                            "cited_event_ids": cited,
                            "uncalibrated_priority_score": decimal_string(res.confidence),
                            "score_disclaimer": "Uncalibrated heuristic priority score; not a probability or filing decision.",
                            "reasoning": res.reasoning,
                        }

            # Constraint-pruned layering search per currency
            for cur in sorted(currencies_in_scope):
                l_res = detect_layering(
                    reasoner,
                    acct_id,
                    max_depth=min(hop_depth, policy.layering_max_depth),
                    currency=cur,
                    min_chain_length=policy.layering_min_hops,
                    decay_min=policy.layering_decay_min,
                    decay_max=policy.layering_decay_max,
                    decay_tolerance=policy.layering_decay_tolerance,
                    max_hop_delay_seconds=policy.layering_max_hop_delay_seconds,
                    deadline_monotonic=deadline_mono,
                    prune_constraints=True,
                )
                for chain in l_res.chains:
                    cited = [tx["tx_id"] for tx in chain.chain_transactions]
                    fid = _finding_id("LAYERING_CHAIN", (chain.currency, tuple(chain.chain_nodes)), cited)
                    findings_by_id[fid] = {
                        "finding_id": fid,
                        "typology": "LAYERING",
                        "channel": "TRANSFER",
                        "mode": "CHAIN",
                        "focus_account": acct_id,
                        "accounts": list(chain.chain_nodes),
                        "subject_involved": bool(subject_acct_set.intersection(chain.chain_nodes)),
                        "currency": chain.currency,
                        "start_amount": decimal_string(chain.start_amount),
                        "end_amount": decimal_string(chain.end_amount),
                        "total_amount": decimal_string(chain.start_amount),
                        "avg_decay_rate": decimal_string(chain.avg_decay_rate),
                        "hop_count": chain.hop_count,
                        "event_count": chain.hop_count,
                        "window_start": chain.chain_transactions[0]["timestamp"],
                        "window_end": chain.chain_transactions[-1]["timestamp"],
                        "cited_event_ids": cited,
                        "uncalibrated_priority_score": decimal_string(l_res.confidence),
                        "score_disclaimer": (
                            "Uncalibrated heuristic priority score; a graph path does not establish "
                            "fungible-fund identity or criminal intent."
                        ),
                        "reasoning": l_res.reasoning,
                    }

        limitations.extend(reasoner.coverage["limitations"])

    # 2. Cash-account windowing (NEVER fabricates external graph accounts or diversity)
    for acct, cur, mode in scoped_cash_keys:
        if cur not in supported_structuring_currencies:
            continue
        events = cash_by_account[(acct, cur, mode)]
        for wrapped in _window_events_with_policy(events, acct, cur, mode, policy):
            res = wrapped["result"]
            cited = sorted(tx["tx_id"] for tx in res.qualifying_transactions)
            fid = _finding_id("STRUCTURING_CASH", (acct, cur, mode, wrapped["window_start"], wrapped["window_end"]), cited)
            findings_by_id[fid] = {
                "finding_id": fid,
                "typology": "STRUCTURING",
                "channel": "CASH",
                "mode": mode,
                "focus_account": acct,
                "accounts": [acct],
                "subject_involved": acct in subject_acct_set,
                "currency": cur,
                "total_amount": decimal_string(res.total_amount),
                "event_count": res.transaction_count,
                "known_counterparty_count": 0,  # Cash external counterparties are unknown
                "window_start": wrapped["window_start"],
                "window_end": wrapped["window_end"],
                "window_mode": wrapped["window_mode"],
                "cited_event_ids": cited,
                "uncalibrated_priority_score": decimal_string(res.confidence),
                "score_disclaimer": (
                    "Uncalibrated heuristic priority score; cash counterparties are unknown "
                    "and not synthesized."
                ),
                "reasoning": res.reasoning,
            }

    # Deduplicate limitations deterministically
    unique_limits = sorted(
        {(item["reason"], str(item.get("node", "")), int(item.get("limit", 0))) for item in limitations}
    )
    deduped_limitations = [
        {"reason": r, "node": n, "limit": lim} for r, n, lim in unique_limits
    ]
    coverage_status = "PARTIAL" if deduped_limitations else "COMPLETE"

    sorted_findings = sorted(
        findings_by_id.values(),
        key=lambda f: (-Decimal(f["uncalibrated_priority_score"]), f["typology"], f["finding_id"]),
    )

    # Compact graph/table view of scoped known-endpoint activity (temporal owners resolved per event)
    graph_nodes = [
        {
            "id": acct_id,
            "account_type": accounts[acct_id].get("account_type", "UNKNOWN"),
            "currency": accounts[acct_id].get("currency"),
            "is_subject": acct_id in subject_acct_set,
        }
        for acct_id in sorted(scoped_accounts)
        if acct_id in accounts
    ]
    graph_edges = [
        {
            "event_id": item["external_id"],
            "record_id": item.get("record_id"),
            "source_file_id": item.get("source_file_id"),
            "row_number": item.get("row_number"),
            "source": item["payload"]["source_account_id"],
            "target": item["payload"]["target_account_id"],
            "amount": item["payload"]["amount"],
            "currency": item["payload"]["currency"],
            "event_at": item["payload"]["event_at"],
            "event_type": item["payload"]["event_type"],
            "source_owners_at_event": _owners_at_time(
                item["payload"]["source_account_id"],
                timestamp(item["payload"]["event_at"]),
                relationships_by_acct,
            ),
            "target_owners_at_event": _owners_at_time(
                item["payload"]["target_account_id"],
                timestamp(item["payload"]["event_at"]),
                relationships_by_acct,
            ),
        }
        for item in scoped_transfers[:500]
    ]

    return {
        "analysis_code_version": ANALYSIS_CODE_VERSION,
        "policy": policy.to_metadata(),
        "scope": {
            "subject_id": subject_id,
            "subject_accounts": subject_accounts,
            "hop_depth": hop_depth,
            "interval_start": interval_start,
            "interval_end": interval_end,
            "max_events": max_events,
            "max_accounts": max_accounts,
            "deadline_seconds": int(deadline_seconds),
        },
        "findings": sorted_findings,
        "excluded_events": excluded_events,
        "coverage": {
            "status": coverage_status,
            "considered_events": considered_count,
            "excluded_events_count": sum(excluded_breakdown.values()),
            "excluded_breakdown": dict(sorted(excluded_breakdown.items())),
            "scoped_accounts_count": len(scoped_accounts),
            "limitations": deduped_limitations,
            "negative_scope_notice": (
                "No qualifying pattern found within this declared scope does not clear a customer. "
                "PARTIAL coverage indicates search/budget limits were reached."
            ),
        },
        "graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
            "edges_truncated": len(scoped_transfers) > len(graph_edges),
        },
    }


def analyze_snapshot(
    session: Session,
    snapshot_id: str,
    subject_id: str,
    *,
    hop_depth: int = 3,
    policy: RulePolicy = DEFAULT_PRODUCTION_POLICY,
    interval_start: str | None = None,
    interval_end: str | None = None,
    max_events: int = 20_000,
    max_accounts: int = 5_000,
    deadline_seconds: float = 60.0,
) -> dict[str, Any]:
    """Load exact pinned revisions from SnapshotRecord -> LedgerRecord and run analysis."""
    snapshot = session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot '{snapshot_id}' not found")

    rows = session.execute(
        select(
            LedgerRecord.id,
            LedgerRecord.kind,
            LedgerRecord.external_id,
            LedgerRecord.digest,
            LedgerRecord.source_file_id,
            LedgerRecord.row_number,
            LedgerRecord.payload,
        )
        .join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id)
        .where(SnapshotRecord.snapshot_id == snapshot_id)
    ).all()

    records = [
        {
            "record_id": rec_id,
            "kind": kind,
            "external_id": ext_id,
            "digest": digest,
            "source_file_id": src_id,
            "row_number": row_num,
            "payload": payload,
        }
        for rec_id, kind, ext_id, digest, src_id, row_num, payload in rows
    ]
    result = run_scoped_analysis(
        records,
        subject_id,
        hop_depth=hop_depth,
        policy=policy,
        interval_start=interval_start,
        interval_end=interval_end,
        max_events=max_events,
        max_accounts=max_accounts,
        deadline_seconds=deadline_seconds,
    )
    result["snapshot_id"] = snapshot.id
    result["dataset_id"] = snapshot.dataset_id
    result["snapshot_generation"] = snapshot.generation
    return result
