import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.schemas import DocumentOut
from backend.core.prerequisites import resolve_prerequisites
from backend.db import get_db
from backend.models import Document

router = APIRouter(prefix="/documents", tags=["documents"])


def _with_resolved_prerequisites(doc: Document, db: Session) -> dict:
    """Adds `prerequisite_links` to a course's metadata (worked out on every read)."""
    metadata = dict(doc.doc_metadata)
    if doc.type != "course" or not metadata.get("accreditations"):
        return metadata

    accreditations = []
    for acc in metadata["accreditations"]:
        acc = dict(acc)
        prereq_text = acc.get("Предуслов")
        if prereq_text:
            acc["prerequisite_links"] = resolve_prerequisites(db, prereq_text)
        accreditations.append(acc)
    metadata["accreditations"] = accreditations
    return metadata


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    """A full document, for the frontend's document page."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found") from None

    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentOut(
        id=str(doc.id),
        source=doc.source,
        type=doc.type,
        title=doc.title,
        url=doc.url,
        published_at=doc.published_at,
        content=doc.content,
        doc_metadata=_with_resolved_prerequisites(doc, db),
    )
