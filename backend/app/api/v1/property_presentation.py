import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.property_interest import PropertyInterest
from app.schemas.property_interest import (
    PropertyInterestResponse,
    PropertyInterestListResponse,
    PropertyInterestUpdateManualRequest,
    PropertyPresentationResult,
    TenantInterestProcessRequest,
    TenantInterestProcessResult,
)
from app.services.tenant_property_presentation_service import TenantPropertyPresentationService
from app.services.tenant_property_interest_understanding_service import (
    TenantPropertyInterestUnderstandingService,
)

router = APIRouter()


# 1. Present a single shortlisted match candidate to tenant
@router.post(
    "/property-matches/{match_id}/present-to-tenant",
    response_model=PropertyInterestResponse,
    status_code=status.HTTP_200_OK,
    summary="Present a specific shortlisted property candidate to tenant via WhatsApp",
)
def present_property_match_to_tenant(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        interest = TenantPropertyPresentationService.present_single_match(
            db=db,
            match_id=match_id,
            actor_id="operator",
            force_re_present=True,
        )
        resp = PropertyInterestResponse.model_validate(interest)
        if interest.property_match:
            resp.property_summary = TenantPropertyPresentationService.format_tenant_safe_summary(
                interest.property_match
            )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 2. Present shortlist to tenant (start presentation workflow)
@router.post(
    "/leads/{lead_id}/property-presentation/start",
    response_model=PropertyPresentationResult,
    status_code=status.HTTP_200_OK,
    summary="Initialize or progress property shortlist presentation to tenant",
)
def start_property_presentation(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        result = TenantPropertyPresentationService.present_shortlist(
            db=db,
            lead_id=lead_id,
            actor_id="operator",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 3. List all property interests for a lead
@router.get(
    "/leads/{lead_id}/property-interests",
    response_model=PropertyInterestListResponse,
    summary="List all presented properties and tenant interest statuses for a lead",
)
def list_lead_property_interests(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    items = TenantPropertyPresentationService.list_interests_for_lead(db, lead_id)
    return PropertyInterestListResponse(total=len(items), items=items)


# 4. Get specific property interest details
@router.get(
    "/property-interests/{interest_id}",
    response_model=PropertyInterestResponse,
    summary="Get detailed property interest information",
)
def get_property_interest_detail(
    interest_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    interest = db.query(PropertyInterest).filter(PropertyInterest.id == interest_id).first()
    if not interest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PropertyInterest not found.")

    resp = PropertyInterestResponse.model_validate(interest)
    if interest.property_match:
        resp.property_summary = TenantPropertyPresentationService.format_tenant_safe_summary(
            interest.property_match
        )
    return resp


# 5. Manually update interest status (operator override with audit)
@router.patch(
    "/property-interests/{interest_id}",
    response_model=PropertyInterestResponse,
    summary="Manually update property interest status by authorized operator",
)
def update_property_interest_manual(
    interest_id: uuid.UUID,
    payload: PropertyInterestUpdateManualRequest,
    db: Session = Depends(get_db),
):
    try:
        updated = TenantPropertyPresentationService.update_interest_status_manual(
            db=db,
            interest_id=interest_id,
            new_status=payload.status,
            tenant_notes=payload.tenant_notes,
            actor_id=payload.actor_id or "operator",
        )
        resp = PropertyInterestResponse.model_validate(updated)
        if updated.property_match:
            resp.property_summary = TenantPropertyPresentationService.format_tenant_safe_summary(
                updated.property_match
            )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 6. Process inbound tenant message / response to presented properties
@router.post(
    "/leads/{lead_id}/tenant-message/process-interest",
    response_model=TenantInterestProcessResult,
    summary="Process tenant response, classify interest, and trigger viewing workflow if requested",
)
def process_tenant_interest_message(
    lead_id: uuid.UUID,
    payload: TenantInterestProcessRequest,
    db: Session = Depends(get_db),
):
    try:
        result = TenantPropertyInterestUnderstandingService.process_tenant_response(
            db=db,
            lead_id=lead_id,
            message_content=payload.message_content,
            interactive_payload=payload.interactive_payload,
            inbound_message_id=payload.inbound_message_id,
            actor_id="tenant",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
