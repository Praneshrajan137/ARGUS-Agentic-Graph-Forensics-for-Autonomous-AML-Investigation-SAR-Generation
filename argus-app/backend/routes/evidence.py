"""Evidence routes — 1 endpoint for querying evidence documents."""
from fastapi import APIRouter, HTTPException, Query

from ..models.state import get_state
from ..models.schemas import EvidenceListResponse, EvidenceDocumentResponse

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    subject_id: str | None = None,
    entity_id: str | None = None,
    crime_type: str | None = None,
    type: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return evidence documents with optional filtering by subject, crime type, or keyword."""
    state = get_state()
    if state.graph is None:
        raise HTTPException(status_code=400, detail="No graph loaded. Generate first.")

    # Accept both param names (entity_id is alias for subject_id, type is alias for crime_type)
    effective_subject = subject_id or entity_id
    effective_crime_type = crime_type or type

    docs = []
    for idx, doc in enumerate(state.evidence_documents):
        if effective_subject and str(doc.get("subject_id", "")) != effective_subject:
            continue
        if effective_crime_type and doc.get("crime_type", "") != effective_crime_type:
            continue
        # Keyword search on content
        if keyword:
            content = doc.get("body", doc.get("narrative", doc.get("content", "")))
            if keyword.lower() not in content.lower():
                continue

        ts = doc.get("timestamp", doc.get("date", 0))
        if hasattr(ts, "timestamp"):
            ts = int(ts.timestamp())
        elif isinstance(ts, str):
            ts = 0
        elif not isinstance(ts, int):
            ts = 0

        docs.append(EvidenceDocumentResponse(
            id=doc.get("document_id", f"ev_{idx}"),
            source_type=doc.get("document_type", doc.get("source_type", "memo")),
            content=doc.get("body", doc.get("narrative", doc.get("content", ""))),
            subject_id=str(doc.get("subject_id", "")),
            associated_entity=str(doc.get("associated_entity", doc.get("subject_id", ""))),
            timestamp=ts,
            crime_type=doc.get("crime_type", ""),
        ))

        if len(docs) >= limit:
            break

    return EvidenceListResponse(documents=docs, total=len(docs))
