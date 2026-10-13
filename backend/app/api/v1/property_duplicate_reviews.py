import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import DuplicateReviewStatus
from app.schemas.property_import import (
    PropertyDuplicateReviewResponse,
    AttachReviewRequest,
    CreateNewPropertyReviewRequest,
    IgnoreReviewRequest,
)
from app.services.property_import_service import PropertyImportService

router = APIRouter(prefix="/property-duplicate-reviews", tags=["property-duplicate-reviews"])


@router.get("", response_model=List[PropertyDuplicateReviewResponse])
def list_duplicate_reviews(
    status_filter: Optional[DuplicateReviewStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List uncertain duplicate reviews pending manual resolution or resolved history.
    """
    service = PropertyImportService(db)
    reviews = service.list_duplicate_reviews(status_filter=status_filter, skip=skip, limit=limit)
    return [PropertyDuplicateReviewResponse.model_validate(rev) for rev in reviews]


@router.get("/{review_id}", response_model=PropertyDuplicateReviewResponse)
def get_duplicate_review(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get detailed duplicate review item with candidate property comparison.
    """
    service = PropertyImportService(db)
    rev = service.get_duplicate_review_or_404(review_id)
    return PropertyDuplicateReviewResponse.model_validate(rev)



@router.post("/{review_id}/attach-existing", response_model=PropertyDuplicateReviewResponse)
def attach_to_existing_property(
    review_id: uuid.UUID,
    payload: AttachReviewRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Operator confirms that the incoming listing belongs to candidate/target property.
    Attaches a new listing to that canonical property.
    """
    service = PropertyImportService(db)
    review = service.get_duplicate_review_or_404(review_id)

    target_id = payload.target_property_id or review.candidate_property_id
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target property ID must be provided or present on review candidate.",
        )

    updated_review = service.resolve_review_attach(
        review_id=review_id,
        property_id=target_id,
        actor_id=x_admin_id,
    )
    return updated_review


@router.post("/{review_id}/create-new", response_model=PropertyDuplicateReviewResponse)
def create_new_property_from_review(
    review_id: uuid.UUID,
    payload: CreateNewPropertyReviewRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Operator confirms that the incoming listing is a distinct physical property.
    Creates a new canonical property and attaches the listing.
    """
    service = PropertyImportService(db)
    updated_review = service.resolve_review_create_new(
        review_id=review_id,
        actor_id=x_admin_id,
    )
    return updated_review


@router.post("/{review_id}/ignore", response_model=PropertyDuplicateReviewResponse)
def ignore_review_candidate(
    review_id: uuid.UUID,
    payload: IgnoreReviewRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Operator marks candidate review as ignored/dismissed.
    """
    service = PropertyImportService(db)
    reason = payload.reason or "Operator dismissed duplicate review"
    updated_review = service.resolve_review_ignore(
        review_id=review_id,
        reason=reason,
        actor_id=x_admin_id,
    )
    return updated_review
