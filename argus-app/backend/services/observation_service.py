"""Scoped observations, ledger comparisons, analyst dispositions, and non-authorship comments.

Strict separation:
  - CaseObservation: source-linked raw observations + scoped comparison result
    (NO_OBSERVATION / NOT_COMPARABLE / MATCH / DISAGREEMENT / INSUFFICIENT_DATA).
  - CaseFindingDisposition: human judgment & benign alternatives preserving raw findings.
  - CaseComment: discussion/review notes that do NOT confer authorship on CaseContributor.
"""
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tracer_agent.src.core.evidence_synthesizer import EvidenceSynthesizer

from ..database import (
    AuditEvent, CaseComment, CaseContributor, CaseFindingDisposition,
    CaseObservation, CaseRecord, LedgerRecord, SnapshotRecord, utcnow,
)
from ..models.ledger import analysis_eligibility, decimal_string, timestamp


class _ProductionSynthesizer(EvidenceSynthesizer):
    """Production wrapper that never loads spaCy or external NLP models."""

    def _get_nlp(self):
        return None


def compute_scoped_ledger_total(
    session: Session,
    snapshot_id: str,
    account_id: str,
    currency: str,
    interval_start: str,
    interval_end: str,
    basis: str,
) -> Decimal:
    """Compute exact pinned-snapshot Decimal sum for an explicit comparison scope."""
    start_dt = timestamp(interval_start)
    end_dt = timestamp(interval_end)
    rows = session.scalars(
        select(LedgerRecord)
        .join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id)
        .where(
            SnapshotRecord.snapshot_id == snapshot_id,
            LedgerRecord.kind == "transactions",
            LedgerRecord.currency == currency,
        )
    ).all()
    reversed_ids = {
        r.payload.get("related_event_id")
        for r in rows
        if r.payload.get("event_type") == "REVERSAL" and r.payload.get("status", "POSTED") == "POSTED"
    }
    amounts: list[Decimal] = []
    for rec in rows:
        eligible, _ = analysis_eligibility(rec.payload)
        if not eligible or rec.external_id in reversed_ids:
            continue
        ev_dt = timestamp(rec.payload["event_at"])
        if not (start_dt <= ev_dt < end_dt):
            continue
        if basis == "INFLOW" and rec.target_account_id == account_id:
            amounts.append(Decimal(rec.payload["amount"]))
        elif basis == "OUTFLOW" and rec.source_account_id == account_id:
            amounts.append(Decimal(rec.payload["amount"]))
        elif basis == "GROSS_ACTIVITY" and (rec.source_account_id == account_id or rec.target_account_id == account_id):
            amounts.append(Decimal(rec.payload["amount"]))
    if not amounts:
        return Decimal("0")
    return _ProductionSynthesizer._exact_sum(amounts)


def evaluate_scoped_observation(
    raw_text: str,
    *,
    document_id: str,
    doc_scope: dict[str, Any] | None,
    ledger_total: Decimal | None,
    ledger_scope: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract exact monetary observations and perform strict scope-matched comparison."""
    synth = _ProductionSynthesizer()
    ledger_data = (
        {"total_inflow": ledger_total, "scope": ledger_scope}
        if ledger_total is not None
        else {"scope": ledger_scope}
    )
    res = synth.synthesize(
        ledger_data,
        [{"id": document_id, "content": raw_text, "scope": doc_scope}],
    )
    return {
        "verdict": res.verdict,
        "reasoning": res.reasoning,
        "checked_count": res.checked_count,
        "eligible_count": res.eligible_count,
        "observations": [{**obs, "amount": decimal_string(obs["amount"])} for obs in res.observations],
        "comparisons": res.comparisons,
        "discrepancies": res.discrepancies,
        "interpretation_notice": (
            "A numerical disagreement is a question requiring scoped investigation, "
            "neither proof that the ledger is true nor proof of wrongdoing."
        ),
    }


def add_material_contributor(session: Session, case_id: str, actor_id: str) -> None:
    """Record a material contributor across case revision ancestry (idempotent)."""
    existing = session.get(CaseContributor, (case_id, actor_id))
    if existing is None:
        session.add(CaseContributor(case_id=case_id, user_id=actor_id))


def record_case_observation(
    session: Session,
    case: CaseRecord,
    actor_id: str,
    *,
    source_kind: str,
    source_ref: str,
    raw_text: str,
    scope: dict[str, Any] | None = None,
    ledger_scope: dict[str, Any] | None = None,
    ledger_total: Decimal | None = None,
) -> CaseObservation:
    """Persist an immutable source-linked observation (counts as material contribution)."""
    if not raw_text or len(raw_text) > 8000:
        raise ValueError("Observation text must be 1..8000 characters")
    comparison = evaluate_scoped_observation(
        raw_text,
        document_id=source_ref,
        doc_scope=scope,
        ledger_total=ledger_total,
        ledger_scope=ledger_scope or scope,
    )
    first_obs = comparison["observations"][0] if comparison["observations"] else {}
    obs = CaseObservation(
        case_id=case.id,
        dataset_id=case.dataset_id,
        snapshot_id=case.snapshot_id,
        source_kind=source_kind,
        source_ref=source_ref,
        span_start=first_obs.get("start"),
        span_end=first_obs.get("end"),
        entity_id=(scope or {}).get("entity_id"),
        account_id=(scope or {}).get("account_id") or (scope or {}).get("entity_id"),
        currency=first_obs.get("currency") or (scope or {}).get("currency"),
        interval_start=(scope or {}).get("period_start"),
        interval_end=(scope or {}).get("period_end"),
        accounting_basis=(scope or {}).get("basis"),
        aggregation=(scope or {}).get("aggregation"),
        amount_str=first_obs.get("amount"),
        raw_text=raw_text,
        scope_json=scope or {},
        comparison_json=comparison,
        created_by=actor_id,
        created_at=utcnow(),
    )
    session.add(obs)
    add_material_contributor(session, case.id, actor_id)
    case.version += 1
    session.add(AuditEvent(
        actor_id=actor_id,
        event_type="OBSERVATION_RECORDED",
        resource_id=case.id,
        detail={"observation_id": obs.id, "verdict": comparison["verdict"]},
    ))
    session.flush()
    return obs


def record_finding_disposition(
    session: Session,
    case: CaseRecord,
    actor_id: str,
    *,
    finding_id: str,
    disposition: str,
    rationale: str,
    benign_alternative: str | None = None,
    job_id: str | None = None,
) -> CaseFindingDisposition:
    """Append human disposition while preserving the raw finding intact."""
    if disposition not in ("OPEN", "ESCALATED", "DISMISSED", "NEEDS_INFO"):
        raise ValueError("Invalid disposition state")
    if not rationale or not rationale.strip():
        raise ValueError("Disposition rationale is required")
    entry = CaseFindingDisposition(
        case_id=case.id,
        dataset_id=case.dataset_id,
        job_id=job_id,
        finding_id=finding_id,
        disposition=disposition,
        rationale=rationale.strip(),
        benign_alternative=benign_alternative.strip() if benign_alternative else None,
        actor_id=actor_id,
        created_at=utcnow(),
    )
    session.add(entry)
    add_material_contributor(session, case.id, actor_id)
    case.version += 1
    session.add(AuditEvent(
        actor_id=actor_id,
        event_type="FINDING_DISPOSITION_RECORDED",
        resource_id=case.id,
        detail={"finding_id": finding_id, "disposition": disposition},
    ))
    session.flush()
    return entry


def record_case_comment(
    session: Session,
    case: CaseRecord,
    actor_id: str,
    *,
    body: str,
    artifact_id: str | None = None,
) -> CaseComment:
    """Add a review comment — explicitly does NOT add actor to CaseContributor."""
    if not body or not body.strip() or len(body) > 4000:
        raise ValueError("Comment must be 1..4000 characters")
    comment = CaseComment(
        case_id=case.id,
        dataset_id=case.dataset_id,
        artifact_id=artifact_id,
        author_id=actor_id,
        body=body.strip(),
        created_at=utcnow(),
    )
    session.add(comment)
    session.add(AuditEvent(
        actor_id=actor_id,
        event_type="CASE_COMMENT_ADDED",
        resource_id=case.id,
        detail={"comment_id": comment.id, "artifact_id": artifact_id},
    ))
    session.flush()
    return comment
