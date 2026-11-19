"""Review lifecycle, approval envelopes, freshness guards, and immutable byte export.

Every protected action enforces the strict 4-level PostgreSQL lock order:
  1. auth_guard (FOR SHARE)
  2. dataset (ordered by id, FOR SHARE)
  3. case_record (ordered by id, FOR UPDATE)
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import (
    Approval, Artifact, AuditEvent, AuthGuard, CaseAssignment,
    CaseContributor, CaseFindingDisposition, CaseObservation, CaseRecord,
    Dataset, DatasetGrant, Export, ImportBatch, Job, LedgerRecord, Snapshot,
    SnapshotRecord, SourceFile, User, set_transaction_identity, utcnow,
)
from .drafting_service import (
    VALIDATOR_VERSION, build_draft_package, compute_envelope_digest,
)
from .intake_service import Conflict, Forbidden, IntakeError
from .observation_service import add_material_contributor


@dataclass(frozen=True)
class ExportPayload:
    export_id: str
    artifact_id: str
    export_kind: str  # "CURRENT" or "HISTORICAL"
    banner: str
    payload_digest: str
    narrative_bytes: bytes
    manifest_bytes: bytes
    approval_envelope: dict[str, Any]
    envelope_digest: str
    dataset_generation_at_export: int
    evidence_generation: int


def _lock_case_context(
    session: Session,
    case_id: str,
    actor_id: str,
    required_roles: set[str],
    *,
    require_assignment: bool = True,
) -> tuple[User, Dataset, CaseRecord, Snapshot]:
    """Acquire strict lock order: 1. AuthGuard FOR SHARE -> 2. Dataset FOR SHARE -> 3. Case FOR UPDATE."""
    session.scalar(select(AuthGuard).where(AuthGuard.id == 1).with_for_update(read=True))
    actor = session.get(User, actor_id, populate_existing=True)
    if not actor or not actor.enabled or not required_roles.intersection(actor.roles):
        raise Forbidden("Authorized role required")
    set_transaction_identity(session, actor.id, actor.roles)

    # Resolve dataset_id first (non-locking peek), then lock Dataset -> Case in strict order
    ds_id = session.scalar(select(CaseRecord.dataset_id).where(CaseRecord.id == case_id))
    if ds_id is None:
        raise IntakeError("Case not found")

    dataset = session.scalar(
        select(Dataset).where(Dataset.id == ds_id).with_for_update(read=True).execution_options(populate_existing=True)
    )
    if dataset is None:
        raise IntakeError("Dataset not found")

    is_privileged = bool({"administrator", "auditor"}.intersection(actor.roles))
    grant = session.get(DatasetGrant, (actor.id, dataset.id), populate_existing=True)
    if not is_privileged and grant is None:
        raise Forbidden("Dataset entitlement required")

    case = session.scalar(
        select(CaseRecord).where(CaseRecord.id == case_id).with_for_update().execution_options(populate_existing=True)
    )
    if case is None:
        raise IntakeError("Case not found")

    if require_assignment and not is_privileged:
        assigned = session.get(CaseAssignment, (case.id, actor.id), populate_existing=True)
        if assigned is None:
            raise Forbidden("Case assignment required")

    snapshot = session.get(Snapshot, case.snapshot_id, populate_existing=True)
    if snapshot is None:
        raise IntakeError("Pinned snapshot not found")

    return actor, dataset, case, snapshot


def _collect_contributor_ancestry(session: Session, case_id: str, artifact: Artifact) -> set[str]:
    """Return every material contributor across case history and artifact revision ancestry."""
    contributors = set(
        session.scalars(select(CaseContributor.user_id).where(CaseContributor.case_id == case_id)).all()
    )
    cursor: Artifact | None = artifact
    seen_ids: set[str] = set()
    while cursor is not None and cursor.id not in seen_ids:
        seen_ids.add(cursor.id)
        contributors.add(cursor.created_by)
        for cid in (cursor.contributors_snapshot or []):
            contributors.add(str(cid))
        cursor = session.get(Artifact, cursor.parent_artifact_id) if cursor.parent_artifact_id else None
    return contributors


def create_draft_revision(
    session: Session,
    case_id: str,
    actor_id: str,
    *,
    analyst_interpretations: list[dict[str, Any]] | None = None,
    parent_artifact_id: str | None = None,
) -> Artifact:
    """Create a deterministic DRAFT artifact (or new revision after edits/changes requested)."""
    actor, dataset, case, snapshot = _lock_case_context(
        session, case_id, actor_id, {"analyst", "administrator"},
    )
    if case.status == "CLOSED_NO_EXPORT":
        raise Conflict("Cannot draft on a closed case")

    # Find latest completed analysis job on the pinned snapshot
    job = session.scalar(
        select(Job)
        .where(Job.case_id == case.id, Job.snapshot_id == snapshot.id, Job.status == "COMPLETE")
        .order_by(Job.finished_at.desc())
    )
    analysis_result = (job.result if job and job.result else {
        "analysis_code_version": "none",
        "policy": {},
        "scope": {"subject_id": case.subject_id},
        "findings": [],
        "coverage": {"status": "NOT_RUN", "considered_events": 0, "excluded_events_count": 0, "limitations": []},
    })

    # Load pinned ledger records & source files referenced by this snapshot
    cited_rows = session.execute(
        select(
            LedgerRecord.id, LedgerRecord.kind, LedgerRecord.external_id,
            LedgerRecord.digest, LedgerRecord.source_file_id, LedgerRecord.row_number,
            LedgerRecord.payload,
        )
        .join(SnapshotRecord, SnapshotRecord.record_id == LedgerRecord.id)
        .where(SnapshotRecord.snapshot_id == snapshot.id)
    ).all()

    cited_event_ids = {
        eid for f in (analysis_result.get("findings") or []) for eid in f.get("cited_event_ids", [])
    }
    scoped_accounts = set((analysis_result.get("scope") or {}).get("subject_accounts") or [])
    for f in (analysis_result.get("findings") or []):
        scoped_accounts.update(f.get("accounts") or [])

    selected_records: list[dict[str, Any]] = []
    source_file_ids: set[str] = set()
    rel_entities: set[str] = {case.subject_id}
    for rec_id, kind, ext_id, digest, sf_id, row_num, payload in cited_rows:
        if kind == "relationships" and payload.get("account_id") in scoped_accounts:
            rel_entities.add(payload["entity_id"])

    for rec_id, kind, ext_id, digest, sf_id, row_num, payload in cited_rows:
        include = (
            (kind == "transactions" and (ext_id in cited_event_ids or (not cited_event_ids and (
                payload.get("source_account_id") in scoped_accounts or payload.get("target_account_id") in scoped_accounts
            ))))
            or (kind == "accounts" and ext_id in scoped_accounts)
            or (kind == "entities" and ext_id in rel_entities)
        )
        if include:
            source_file_ids.add(sf_id)
            selected_records.append({
                "record_id": rec_id,
                "kind": kind,
                "external_id": ext_id,
                "digest": digest,
                "source_file_id": sf_id,
                "row_number": row_num,
                "payload": payload,
            })

    sf_rows = (
        session.scalars(select(SourceFile).where(SourceFile.id.in_(source_file_ids))).all()
        if source_file_ids
        else []
    )
    source_files = [
        {"id": sf.id, "kind": sf.kind, "sha256": sf.sha256, "size": sf.size,
         "extract_id": sf.extract_id, "filename": sf.filename}
        for sf in sf_rows
    ]

    batch = session.get(ImportBatch, snapshot.batch_id) if snapshot.batch_id else None
    reconciliation = batch.reconciliation if batch else {"status": "UNVERIFIED", "reason": "no_batch"}

    observations = [
        {
            "observation_id": o.id, "source_kind": o.source_kind, "source_ref": o.source_ref,
            "scope": o.scope_json, "comparison_json": o.comparison_json, "created_by": o.created_by,
        }
        for o in session.scalars(select(CaseObservation).where(CaseObservation.case_id == case.id).order_by(CaseObservation.created_at)).all()
    ]
    dispositions = [
        {
            "disposition_id": d.id, "finding_id": d.finding_id, "disposition": d.disposition,
            "rationale": d.rationale, "benign_alternative": d.benign_alternative, "actor_id": d.actor_id,
        }
        for d in session.scalars(select(CaseFindingDisposition).where(CaseFindingDisposition.case_id == case.id).order_by(CaseFindingDisposition.created_at)).all()
    ]

    # Record material contribution for the drafting analyst BEFORE freezing contributor list
    add_material_contributor(session, case.id, actor.id)
    session.flush()

    max_rev = session.scalar(select(func.max(Artifact.revision_number)).where(Artifact.case_id == case.id)) or 0
    parent_art = None
    if parent_artifact_id:
        parent_art = session.get(Artifact, parent_artifact_id)
        if parent_art is None or parent_art.case_id != case.id:
            raise IntakeError("Invalid parent_artifact_id")
    revision_number = max_rev + 1

    contributors = set(
        session.scalars(select(CaseContributor.user_id).where(CaseContributor.case_id == case.id)).all()
    )
    if parent_art:
        contributors.update(_collect_contributor_ancestry(session, case.id, parent_art))
    contributors.add(actor.id)

    stamped_interpretations = [
        {**item, "author_id": actor.id}
        for item in (analyst_interpretations or [])
    ]

    case.version += 1
    draft_pkg = build_draft_package(
        case_meta={"id": case.id, "title": case.title, "subject_id": case.subject_id, "version": case.version},
        dataset_meta={"id": dataset.id, "namespace": dataset.namespace},
        snapshot_meta={"id": snapshot.id, "generation": snapshot.generation},
        reconciliation=reconciliation,
        analysis_result=analysis_result,
        cited_records=selected_records,
        source_files=source_files,
        observations=observations,
        dispositions=dispositions,
        analyst_interpretations=stamped_interpretations,
        material_contributors=sorted(contributors),
        parent_artifact_id=parent_artifact_id,
        revision_number=revision_number,
    )

    artifact = Artifact(
        dataset_id=dataset.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        case_version=case.version,
        parent_artifact_id=parent_artifact_id,
        revision_number=revision_number,
        policy_version=str((analysis_result.get("policy") or {}).get("policy_version", "policy-v1")),
        validator_version=VALIDATOR_VERSION,
        narrative=draft_pkg.narrative_bytes,
        manifest=draft_pkg.manifest_bytes,
        narrative_sha256=draft_pkg.narrative_sha256,
        manifest_sha256=draft_pkg.manifest_sha256,
        payload_digest=draft_pkg.payload_digest,
        validation=draft_pkg.validation,
        contributors_snapshot=sorted(contributors),
        status="DRAFT",
        created_by=actor.id,
        created_at=utcnow(),
    )
    session.add(artifact)
    session.flush()
    case.status = "DRAFT"
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="ARTIFACT_DRAFT_CREATED",
        resource_id=artifact.id,
        detail={
            "case_id": case.id,
            "revision_number": revision_number,
            "payload_digest": artifact.payload_digest,
            "validation_status": draft_pkg.validation["status"],
        },
    ))
    session.flush()
    return artifact


def freeze_artifact_for_review(session: Session, artifact_id: str, actor_id: str) -> Artifact:
    """Transition validated DRAFT artifact to IN_REVIEW (bytes already frozen at creation)."""
    case_id = session.scalar(select(Artifact.case_id).where(Artifact.id == artifact_id))
    if case_id is None:
        raise IntakeError("Artifact not found")
    actor, dataset, case, snapshot = _lock_case_context(
        session, case_id, actor_id, {"analyst", "administrator"},
    )
    artifact = session.get(Artifact, artifact_id, populate_existing=True)
    if artifact is None or artifact.status != "DRAFT":
        raise Conflict("Only DRAFT artifacts can be frozen for review")
    if not (artifact.validation or {}).get("passed", False):
        raise Conflict("Cannot submit an artifact that failed factual source checks")
    if dataset.generation != snapshot.generation:
        raise Conflict("Dataset has newer evidence; refresh case snapshot before submitting for review")

    artifact.status = "IN_REVIEW"
    case.status = "IN_REVIEW"
    case.version += 1
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="ARTIFACT_FROZEN_FOR_REVIEW",
        resource_id=artifact.id,
        detail={"case_id": case.id, "payload_digest": artifact.payload_digest},
    ))
    session.flush()
    return artifact


def review_artifact(
    session: Session,
    artifact_id: str,
    reviewer_id: str,
    *,
    decision: str,
    review_note: str | None = None,
) -> Approval:
    """Independently review an IN_REVIEW artifact (APPROVED or CHANGES_REQUESTED).

    Enforces reviewer independence across ALL material contributors in revision ancestry
    and blocks approval when newer dataset evidence has arrived.
    """
    if decision not in ("APPROVED", "CHANGES_REQUESTED"):
        raise IntakeError("Review decision must be APPROVED or CHANGES_REQUESTED")
    case_id = session.scalar(select(Artifact.case_id).where(Artifact.id == artifact_id))
    if case_id is None:
        raise IntakeError("Artifact not found")

    reviewer, dataset, case, snapshot = _lock_case_context(
        session, case_id, reviewer_id, {"reviewer", "administrator"},
    )
    artifact = session.get(Artifact, artifact_id, populate_existing=True)
    if artifact is None or artifact.status != "IN_REVIEW":
        raise Conflict("Artifact must be IN_REVIEW to record a review decision")

    contributors = _collect_contributor_ancestry(session, case.id, artifact)
    if reviewer.id in contributors:
        raise Forbidden("Independent review denied: reviewer is a material contributor in revision ancestry")

    if decision == "APPROVED" and dataset.generation != snapshot.generation:
        raise Conflict(
            f"Evidence stale: artifact reviewed generation {snapshot.generation}, "
            f"current dataset generation is {dataset.generation}. Refresh and re-review required."
        )

    now = utcnow()
    envelope = {
        "envelope_version": "argus-approval-v1",
        "filing_status": "REVIEWED_PACKAGE_NOT_FILED",
        "artifact_id": artifact.id,
        "case_id": case.id,
        "revision_number": artifact.revision_number,
        "payload_digest": artifact.payload_digest,
        "decision": decision,
        "reviewer_id": reviewer.id,
        "reviewed_at": now.isoformat(),
        "evidence_generation": snapshot.generation,
        "dataset_generation_at_review": dataset.generation,
        "freshness_status_at_review": (
            "CURRENT" if dataset.generation == snapshot.generation else "STALE"
        ),
        "material_contributors": sorted(contributors),
        "review_note": review_note or "",
    }
    env_digest = compute_envelope_digest(envelope)

    approval = Approval(
        artifact_id=artifact.id,
        reviewer_id=reviewer.id,
        payload_digest=artifact.payload_digest,
        evidence_generation=snapshot.generation,
        decision=decision,
        review_note=review_note,
        envelope_json=envelope,
        envelope_digest=env_digest,
        created_at=now,
    )
    session.add(approval)
    artifact.status = "APPROVED" if decision == "APPROVED" else "CHANGES_REQUESTED"
    case.status = artifact.status
    case.version += 1
    session.add(AuditEvent(
        actor_id=reviewer.id,
        event_type="ARTIFACT_REVIEWED",
        resource_id=artifact.id,
        detail={
            "case_id": case.id,
            "decision": decision,
            "payload_digest": artifact.payload_digest,
            "envelope_digest": env_digest,
            "evidence_generation": snapshot.generation,
        },
    ))
    session.flush()
    return approval


def close_case_without_export(
    session: Session,
    case_id: str,
    actor_id: str,
    *,
    closed_reason: str = "NO_FILING_WARRANTED",
    closure_memo: str | None = None,
) -> CaseRecord:
    """Close a case without export; closure memo follows institutional policy (optional)."""
    actor, _, case, _ = _lock_case_context(
        session, case_id, actor_id, {"analyst", "reviewer", "administrator"},
    )
    case.status = "CLOSED_NO_EXPORT"
    case.closed_reason = closed_reason[:64]
    case.closure_memo = closure_memo[:4000] if closure_memo else None
    case.version += 1
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="CASE_CLOSED_NO_EXPORT",
        resource_id=case.id,
        detail={"closed_reason": case.closed_reason, "has_memo": bool(case.closure_memo)},
    ))
    session.flush()
    return case


def export_approved_artifact(
    session: Session,
    artifact_id: str,
    actor_id: str,
    *,
    allow_historical: bool = False,
) -> ExportPayload:
    """Serve stored immutable bytes of an approved package after re-checking auth & freshness."""
    case_id = session.scalar(select(Artifact.case_id).where(Artifact.id == artifact_id))
    if case_id is None:
        raise IntakeError("Artifact not found")

    actor, dataset, case, snapshot = _lock_case_context(
        session, case_id, actor_id, {"analyst", "reviewer", "administrator", "auditor"},
    )
    artifact = session.get(Artifact, artifact_id, populate_existing=True)
    if artifact is None or artifact.status not in ("APPROVED", "APPROVED_HISTORICAL"):
        raise Conflict("Only approved artifacts can be exported")

    approval = session.scalar(select(Approval).where(Approval.artifact_id == artifact.id))
    if approval is None or approval.decision != "APPROVED":
        raise Conflict("Approved review envelope missing")

    is_stale = dataset.generation > snapshot.generation
    if is_stale:
        if artifact.status == "APPROVED":
            artifact.status = "APPROVED_HISTORICAL"
            case.status = "APPROVED_HISTORICAL"
        if not allow_historical:
            session.flush()
            raise Conflict(
                f"Package is APPROVED_HISTORICAL (reviewed generation {snapshot.generation}, "
                f"current dataset generation {dataset.generation}). Refresh and re-review for a "
                "current export, or request an explicitly labelled historical export."
            )
        export_kind = "HISTORICAL"
        banner = (
            f"HISTORICAL APPROVED PACKAGE — SUPERSEDED BY DATASET GENERATION {dataset.generation} — NOT FILED"
        )
    else:
        export_kind = "CURRENT"
        banner = "REVIEWED PACKAGE — NOT FILED"

    exp = Export(
        artifact_id=artifact.id,
        created_by=actor.id,
        export_kind=export_kind,
        dataset_generation_at_export=dataset.generation,
        created_at=utcnow(),
    )
    session.add(exp)
    session.flush()
    session.add(AuditEvent(
        actor_id=actor.id,
        event_type="ARTIFACT_EXPORTED",
        resource_id=artifact.id,
        detail={
            "export_id": exp.id,
            "export_kind": export_kind,
            "payload_digest": artifact.payload_digest,
            "evidence_generation": snapshot.generation,
            "dataset_generation": dataset.generation,
        },
    ))
    session.flush()

    return ExportPayload(
        export_id=exp.id,
        artifact_id=artifact.id,
        export_kind=export_kind,
        banner=banner,
        payload_digest=artifact.payload_digest,
        narrative_bytes=bytes(artifact.narrative),
        manifest_bytes=bytes(artifact.manifest),
        approval_envelope=dict(approval.envelope_json),
        envelope_digest=approval.envelope_digest,
        dataset_generation_at_export=dataset.generation,
        evidence_generation=snapshot.generation,
    )
