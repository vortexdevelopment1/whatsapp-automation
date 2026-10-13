import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.property_agent import PropertyAgent
from app.models.message import WhatsAppMessage
from app.models.enums import PropertyAgentOutreachStatus, PropertyAgentOutreachType
from app.schemas.property_agent_outreach import (
    PropertyAgentOutreachCreate,
    PropertyAgentOutreachResponse,
    OutreachMessagePreview,
    BulkAgentOutreachRunRequest,
    BulkAgentOutreachRunResponse,
    PropertyAgentConversationDetail,
    PropertyAgentConversationMessageItem,
)
from app.services.property_agent_outreach_service import PropertyAgentOutreachService

router = APIRouter(tags=["property-agent-outreach"])


def to_outreach_response(outreach: PropertyAgentOutreach) -> PropertyAgentOutreachResponse:
    resp = PropertyAgentOutreachResponse.model_validate(outreach)
    if outreach.property_agent:
        resp.agent_name = outreach.property_agent.full_name
        resp.agency_name = outreach.property_agent.agency_name
    if outreach.property:
        resp.property_title = outreach.property.canonical_name or outreach.property.building_name
    return resp



@router.post(
    "/property-matches/{match_id}/agent-outreach/preview",
    response_model=OutreachMessagePreview,
    summary="Preview listing agent outreach message before sending",
)
def preview_agent_outreach(
    match_id: uuid.UUID,
    template_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    service = PropertyAgentOutreachService(db)
    try:
        return service.preview_outreach(match_id=match_id, template_id=template_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/property-matches/{match_id}/agent-outreach",
    response_model=PropertyAgentOutreachResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send or queue availability check outreach to listing agent",
)
def send_agent_outreach(
    match_id: uuid.UUID,
    payload: Optional[PropertyAgentOutreachCreate] = None,
    db: Session = Depends(get_db),
):
    service = PropertyAgentOutreachService(db)
    template_id = payload.template_id if payload else None
    outreach_type = payload.outreach_type if payload else PropertyAgentOutreachType.INITIAL_AVAILABILITY_CHECK
    manual_reason = payload.manual_reason if payload else None

    try:
        outreach = service.send_initial_outreach(
            match_id=match_id,
            template_id=template_id,
            outreach_type=outreach_type,
            manual_reason=manual_reason,
            actor_id="operator",
        )
        return to_outreach_response(outreach)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/leads/{lead_id}/property-agent-outreach/run",
    response_model=BulkAgentOutreachRunResponse,
    summary="Run bulk agent outreach for top ranked eligible candidate matches",
)
def run_bulk_agent_outreach(
    lead_id: uuid.UUID,
    payload: Optional[BulkAgentOutreachRunRequest] = None,
    db: Session = Depends(get_db),
):
    service = PropertyAgentOutreachService(db)
    max_c = payload.max_candidates if payload else None
    tpl_id = payload.template_id if payload else None

    try:
        return service.run_bulk_outreach_for_lead(
            lead_id=lead_id,
            max_candidates=max_c,
            template_id=tpl_id,
            actor_id="operator",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/property-matches/{match_id}/agent-outreach",
    response_model=List[PropertyAgentOutreachResponse],
    summary="List outreach history for a specific property match",
)
def list_match_outreach_history(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    records = (
        db.query(PropertyAgentOutreach)
        .filter(PropertyAgentOutreach.property_match_id == match_id)
        .order_by(PropertyAgentOutreach.created_at.desc())
        .all()
    )
    return [to_outreach_response(r) for r in records]


@router.get(
    "/property-agent-outreach",
    response_model=List[PropertyAgentOutreachResponse],
    summary="List property agent outreach records with filtering",
)
def list_property_agent_outreach(
    lead_id: Optional[uuid.UUID] = Query(None),
    property_id: Optional[uuid.UUID] = Query(None),
    listing_id: Optional[uuid.UUID] = Query(None),
    property_agent_id: Optional[uuid.UUID] = Query(None),
    property_match_id: Optional[uuid.UUID] = Query(None),
    outreach_status: Optional[PropertyAgentOutreachStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(PropertyAgentOutreach)
    if lead_id:
        query = query.filter(PropertyAgentOutreach.lead_id == lead_id)
    if property_id:
        query = query.filter(PropertyAgentOutreach.property_id == property_id)
    if listing_id:
        query = query.filter(PropertyAgentOutreach.listing_id == listing_id)
    if property_agent_id:
        query = query.filter(PropertyAgentOutreach.property_agent_id == property_agent_id)
    if property_match_id:
        query = query.filter(PropertyAgentOutreach.property_match_id == property_match_id)
    if outreach_status:
        query = query.filter(PropertyAgentOutreach.status == outreach_status)

    records = query.order_by(PropertyAgentOutreach.created_at.desc()).offset(skip).limit(limit).all()
    return [to_outreach_response(r) for r in records]


@router.get(
    "/property-agent-outreach/{outreach_id}",
    response_model=PropertyAgentOutreachResponse,
    summary="Get single property agent outreach record",
)
def get_property_agent_outreach(
    outreach_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    record = db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.id == outreach_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyAgentOutreach '{outreach_id}' not found.",
        )
    return to_outreach_response(record)


@router.get(
    "/property-agent-conversations/{conversation_id}",
    response_model=PropertyAgentConversationDetail,
    summary="Get property agent conversation details and message history",
)
def get_property_agent_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    conv = (
        db.query(PropertyAgentConversation)
        .filter(PropertyAgentConversation.id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyAgentConversation '{conversation_id}' not found.",
        )

    # Resolve message items from linked outreach records and WhatsAppMessages
    messages: List[PropertyAgentConversationMessageItem] = []
    agent_phone = conv.property_agent.phone_normalized or conv.property_agent.phone if conv.property_agent else None

    # Get outbound messages from outreach records
    for out in conv.outreach_records:
        if out.message_content:
            messages.append(
                PropertyAgentConversationMessageItem(
                    id=out.whatsapp_message_id or out.id,
                    direction="OUTBOUND",
                    content=out.message_content,
                    provider_status=out.status.value if out.status else "sent",
                    created_at=out.sent_at or out.created_at,
                )
            )

    # Also query any inbound messages from the agent's phone
    if agent_phone:
        inbound_msgs = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.direction == "INBOUND",
                or_(
                    WhatsAppMessage.sender == agent_phone,
                    WhatsAppMessage.sender == (conv.property_agent.phone if conv.property_agent else agent_phone),
                ),
            )
            .order_by(WhatsAppMessage.created_at.asc())
            .all()
        )
        for im in inbound_msgs:
            messages.append(
                PropertyAgentConversationMessageItem(
                    id=im.id,
                    direction="INBOUND",
                    content=im.content,
                    provider_status=im.provider_status or "delivered",
                    created_at=im.created_at,
                )
            )

    # Sort all messages chronologically
    messages.sort(key=lambda m: m.created_at)

    detail = PropertyAgentConversationDetail(
        id=conv.id,
        property_agent_id=conv.property_agent_id,
        lead_id=conv.lead_id,
        property_id=conv.property_id,
        listing_id=conv.listing_id,
        property_match_id=conv.property_match_id,
        conversation_type=conv.conversation_type,
        status=conv.status,
        reference_code=conv.reference_code,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
        agent_name=conv.property_agent.full_name if conv.property_agent else None,
        agency_name=conv.property_agent.agency_name if conv.property_agent else None,
        agent_phone=agent_phone,
        property_title=conv.property.canonical_name or conv.property.building_name if conv.property else None,
        messages=messages,
    )
    return detail

