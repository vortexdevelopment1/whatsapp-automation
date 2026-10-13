import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import FAQStatus
from app.schemas.faq import (
    FAQCreateRequest,
    FAQUpdateRequest,
    FAQResponse,
    FAQMatchResult,
)
from app.services.faq_service import FAQService

router = APIRouter(prefix="/faqs", tags=["faqs"])


class FAQMatchTestRequest(BaseModel):
    query: str
    category: Optional[str] = None


@router.get("", response_model=List[FAQResponse])
def list_faqs(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[FAQStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List approved FAQ entries."""
    service = FAQService(db)
    return service.list_faqs(category=category, status=status, limit=limit, offset=skip)


@router.post("", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(
    data: FAQCreateRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Create a new FAQ entry."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = FAQService(db)
    return service.create_faq(data, actor_id=x_admin_id)


@router.get("/{faq_id}", response_model=FAQResponse)
def get_faq(
    faq_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve an FAQ entry by ID."""
    service = FAQService(db)
    faq = service.get_faq(faq_id)
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"FAQ with ID '{faq_id}' not found.")
    return faq


@router.put("/{faq_id}", response_model=FAQResponse)
def update_faq(
    faq_id: uuid.UUID,
    data: FAQUpdateRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Update an FAQ entry."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = FAQService(db)
    try:
        return service.update_faq(faq_id, data, actor_id=x_admin_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{faq_id}/status", response_model=FAQResponse)
def set_faq_status(
    faq_id: uuid.UUID,
    new_status: FAQStatus = Query(..., description="Target FAQ status"),
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Activate or deactivate an FAQ entry."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = FAQService(db)
    try:
        return service.set_status(faq_id, new_status, actor_id=x_admin_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/match", response_model=FAQMatchResult)
def match_faq(
    payload: FAQMatchTestRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """Test matching query against active FAQ entries."""
    service = FAQService(db)
    return service.match_faq(query_text=payload.query, category=payload.category, actor_id=x_admin_id)
