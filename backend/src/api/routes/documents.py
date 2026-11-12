import uuid

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from src.api.dependencies import CurrentPrincipal, DbSession, Principal
from src.api.schemas.documents import DeleteResponse, DocumentListResponse, DocumentOut, ReprocessResponse
from src.services.document_service import delete_document, get_document, list_documents, reprocess_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents_route(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    document_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = DbSession,
    principal: Principal = CurrentPrincipal,
) -> DocumentListResponse:
    return list_documents(db, principal, page, page_size, document_type, status)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document_route(
    document_id: uuid.UUID, db: Session = DbSession, principal: Principal = CurrentPrincipal
) -> DocumentOut:
    return get_document(db, principal, document_id)


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document_route(
    document_id: uuid.UUID, db: Session = DbSession, principal: Principal = CurrentPrincipal
) -> DeleteResponse:
    return delete_document(db, principal, document_id)


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document_route(
    document_id: uuid.UUID, db: Session = DbSession, principal: Principal = CurrentPrincipal
) -> ReprocessResponse:
    return reprocess_document(db, principal, document_id)
