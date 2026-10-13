import uuid
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.lead import Lead
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_match import PropertyMatch
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.tenant_requirement import TenantRequirement
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
    QualificationStatus,
    PropertyType,
    PropertyStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertyAgentStatus,
    PropertyMatchStatus,
    PropertyAgentOutreachStatus,
    PropertyAgentOutreachType,
    AgentMappingStatus,
    MessageDirection,
)
from app.services.property_agent_mapping_service import PropertyAgentMappingService
from app.services.property_agent_verification_selection_service import PropertyAgentVerificationSelectionService
from app.services.property_agent_outreach_service import PropertyAgentOutreachService


@pytest.fixture
def setup_lead_and_agent(db: Session):
    # Ensure internal platform agent exists
    from app.models.agent import Agent
    internal_agent = db.query(Agent).first()
    if not internal_agent:
        internal_agent = Agent(
            full_name="Platform Outreach Agent",
            email=f"platform_agent_{uuid.uuid4().hex[:6]}@agency.sg",
            phone=f"+658{uuid.uuid4().int % 10000000:07d}",
            agency_name="Platform Agency",
            registration_number="R123456B",
        )
        db.add(internal_agent)
        db.commit()
        db.refresh(internal_agent)

    # Create WhatsApp profile
    profile = db.query(WhatsAppProfile).first()
    if not profile:
        profile = WhatsAppProfile(
            agent_id=internal_agent.id,
            phone_number_id="pn_test_outreach",
            display_phone_number="+6590000000",
            business_display_name="Concierge Test",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)


    # 1. Create qualified lead
    lead = Lead(
        phone="+6591234567",
        phone_normalized="+6591234567",
        status=LeadStatus.REPLIED,
        consent_status=ConsentStatus.CONSENTED,
        opt_out_status=OptOutStatus.ACTIVE,
        contact_eligibility=ContactEligibility.ELIGIBLE,
        assigned_whatsapp_profile_id=profile.id,
    )
    db.add(lead)

    db.commit()
    db.refresh(lead)

    # Tenant requirement
    req = TenantRequirement(
        lead_id=lead.id,
        qualification_status=QualificationStatus.QUALIFIED,
        preferred_locations=["Novena"],
        budget_max=Decimal("4000.00"),
        property_type="CONDO",
        bedrooms=2,
        lease_duration_months=12,
        occupants=2,
        move_in_date="2026-12-01",
    )
    db.add(req)



    # 2. Create property agent
    agent = PropertyAgent(
        full_name="Agent Evelyn Tan",
        agency_name="ERA Singapore",
        phone="+6598765432",
        phone_normalized="+6598765432",
        status=PropertyAgentStatus.ACTIVE,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # 3. Create physical property & listing
    prop = Property(
        canonical_name="Novena Suites",
        property_type=PropertyType.CONDO,
        status=PropertyStatus.ACTIVE,
        bedrooms=2,
    )
    db.add(prop)

    db.commit()
    db.refresh(prop)

    from app.models.property_source import PropertySource
    from app.models.enums import PropertySourceType, PropertySourceStatus
    source = db.query(PropertySource).first()
    if not source:
        source = PropertySource(
            name="Direct Listing Portal",
            source_type=PropertySourceType.MANUAL,
            status=PropertySourceStatus.ACTIVE,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    listing = PropertyListing(
        property_id=prop.id,
        source_id=source.id,
        agent_id=agent.id,
        listing_reference="Novena Suites 2BR High Floor",
        asking_price=Decimal("3800.00"),
        availability_status=ListingAvailabilityStatus.AVAILABLE,
        listing_status=PropertyListingStatus.ACTIVE,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)


    # 4. Create eligible candidate match
    match = PropertyMatch(
        lead_id=lead.id,
        property_id=prop.id,
        listing_id=listing.id,
        hard_filter_passed=True,
        match_status=PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value,
        match_score=Decimal("92.50"),
        rank=1,
        agent_verification_status="NOT_CHECKED",
        is_stale=False,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "lead": lead,
        "requirement": req,
        "agent": agent,
        "property": prop,
        "listing": listing,
        "match": match,
    }



def test_agent_mapping_service_success(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    mapping_svc = PropertyAgentMappingService(db)
    result = mapping_svc.resolve_agent_for_match(data["match"])

    assert result.mapping_status == AgentMappingStatus.READY
    assert result.property_agent_id == data["agent"].id
    assert result.phone_normalized == "+6598765432"
    assert result.agent_name == "Agent Evelyn Tan"


def test_agent_mapping_service_missing_agent(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Detach agent from listing
    data["listing"].agent_id = None
    db.commit()

    mapping_svc = PropertyAgentMappingService(db)
    result = mapping_svc.resolve_agent_for_match(data["match"])
    assert result.mapping_status == AgentMappingStatus.MISSING_AGENT


def test_agent_mapping_service_inactive_agent(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["agent"].status = PropertyAgentStatus.INACTIVE
    db.commit()

    mapping_svc = PropertyAgentMappingService(db)
    result = mapping_svc.resolve_agent_for_match(data["match"])
    assert result.mapping_status == AgentMappingStatus.AGENT_INACTIVE


def test_agent_mapping_service_invalid_phone(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["agent"].phone = "invalid_phone_123"
    data["agent"].phone_normalized = None
    db.commit()

    mapping_svc = PropertyAgentMappingService(db)
    result = mapping_svc.resolve_agent_for_match(data["match"])
    assert result.mapping_status == AgentMappingStatus.INVALID_CONTACT


def test_outreach_send_valid(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    outreach_svc = PropertyAgentOutreachService(db)

    outreach = outreach_svc.send_initial_outreach(
        match_id=data["match"].id,
        actor_id="test_admin",
    )

    assert outreach.status == PropertyAgentOutreachStatus.SENT
    assert outreach.recipient_phone == "+6598765432"
    assert outreach.provider_message_id is not None
    assert outreach.reference_code.startswith("PM-")
    assert outreach.conversation_id is not None

    # Check match status transitioned to AWAITING_AGENT
    db.refresh(data["match"])
    assert data["match"].match_status == PropertyMatchStatus.AWAITING_AGENT.value
    assert data["match"].agent_verification_status == "AWAITING_REPLY"

    # Check PropertyAgentConversation created
    conv = db.query(PropertyAgentConversation).filter(PropertyAgentConversation.id == outreach.conversation_id).first()
    assert conv is not None
    assert conv.conversation_type == "PROPERTY_AGENT"
    assert conv.property_agent_id == data["agent"].id


def test_outreach_minimum_data_sharing(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    outreach_svc = PropertyAgentOutreachService(db)

    outreach = outreach_svc.send_initial_outreach(match_id=data["match"].id)
    content = outreach.message_content

    # Disclosed rental context
    assert "Novena Suites" in content
    assert "2-bed" in content
    assert "12 months" in content

    # STRICT DATA MINIMIZATION: Never disclose tenant private info
    assert data["lead"].phone not in content
    assert "92.5" not in content  # no internal score
    assert "qualification" not in content.lower()
    assert "tenant notes" not in content.lower()


def test_outreach_idempotency_duplicate_send(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    outreach_svc = PropertyAgentOutreachService(db)

    # First send
    outreach1 = outreach_svc.send_initial_outreach(match_id=data["match"].id)
    # Second send attempt
    outreach2 = outreach_svc.send_initial_outreach(match_id=data["match"].id)

    assert outreach1.id == outreach2.id
    assert outreach1.idempotency_key == outreach2.idempotency_key

    # Exactly 1 outreach record exists in DB
    total = db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.property_match_id == data["match"].id).count()
    assert total == 1


def test_outreach_blocked_for_below_threshold(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["match"].match_status = PropertyMatchStatus.BELOW_OUTREACH_THRESHOLD.value
    db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    with pytest.raises(ValueError, match="not in READY_FOR_AGENT_VERIFICATION"):
        outreach_svc.send_initial_outreach(match_id=data["match"].id)


def test_outreach_allowed_with_manual_override(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["match"].match_status = PropertyMatchStatus.BELOW_OUTREACH_THRESHOLD.value
    data["match"].manual_override = True
    data["match"].manual_override_reason = "Operator manual inspection passed"
    db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    outreach = outreach_svc.send_initial_outreach(
        match_id=data["match"].id,
        manual_reason="Operator manual inspection passed",
    )
    assert outreach.status == PropertyAgentOutreachStatus.SENT


def test_outreach_blocked_for_failed_hard_filter(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["match"].hard_filter_passed = False
    db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    with pytest.raises(ValueError, match="failed Phase 3 hard filters"):
        outreach_svc.send_initial_outreach(match_id=data["match"].id)


def test_outreach_blocked_for_inactive_listing(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["listing"].listing_status = PropertyListingStatus.ARCHIVED
    db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    with pytest.raises(ValueError, match="Listing is inactive"):
        outreach_svc.send_initial_outreach(match_id=data["match"].id)


def test_outreach_blocked_for_unqualified_lead(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    data["requirement"].qualification_status = QualificationStatus.DISQUALIFIED
    db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    with pytest.raises(ValueError, match="not in QUALIFIED status"):
        outreach_svc.send_initial_outreach(match_id=data["match"].id)



def test_bulk_outreach_selection_and_run(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    lead = data["lead"]
    agent = data["agent"]
    source_id = data["listing"].source_id

    # Create additional 2 properties & matches
    for i in range(2, 4):
        p = Property(canonical_name=f"Condo {i}", property_type=PropertyType.CONDO, status=PropertyStatus.ACTIVE)
        db.add(p)

        db.commit()
        l = PropertyListing(
            property_id=p.id,
            source_id=source_id,
            agent_id=agent.id,
            listing_reference=f"Condo {i} Unit",
            asking_price=Decimal("3900.00"),
            availability_status=ListingAvailabilityStatus.AVAILABLE,
            listing_status=PropertyListingStatus.ACTIVE,
        )
        db.add(l)
        db.commit()

        m = PropertyMatch(
            lead_id=lead.id,
            property_id=p.id,
            listing_id=l.id,
            hard_filter_passed=True,
            match_status=PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value,
            match_score=Decimal(80 - i),
            rank=i,
            is_stale=False,
        )
        db.add(m)
        db.commit()

    outreach_svc = PropertyAgentOutreachService(db)
    # Run bulk outreach with max_candidates = 2
    bulk_res = outreach_svc.run_bulk_outreach_for_lead(lead_id=lead.id, max_candidates=2)

    assert bulk_res.selected == 2
    assert bulk_res.sent == 2
    assert len(bulk_res.outreach_records) == 2


def test_webhook_delivery_status_callbacks(client, db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    outreach_svc = PropertyAgentOutreachService(db)
    outreach = outreach_svc.send_initial_outreach(match_id=data["match"].id)

    provider_id = outreach.provider_message_id

    # 1. Simulate DELIVERED status webhook callback
    resp = client.post(
        "/api/webhook/whatsapp",
        json={
            "provider_message_id": provider_id,
            "status": "delivered",
        },
    )
    assert resp.status_code == 200
    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.DELIVERED
    assert outreach.delivered_at is not None

    # 2. Simulate READ status webhook callback
    resp = client.post(
        "/api/webhook/whatsapp",
        json={
            "provider_message_id": provider_id,
            "status": "read",
        },
    )
    assert resp.status_code == 200
    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.READ
    assert outreach.read_at is not None


def test_webhook_inbound_property_agent_reply(client, db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    outreach_svc = PropertyAgentOutreachService(db)
    outreach = outreach_svc.send_initial_outreach(match_id=data["match"].id)

    # Agent replies from their phone
    resp = client.post(
        "/api/webhook/whatsapp?async_processing=false",
        json={
            "sender": data["agent"].phone_normalized,
            "content": f"Yes, the unit is still available! Ref: {outreach.reference_code}",
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "property_agent_reply_received"
    assert res_data["matched_outreach_id"] == str(outreach.id)

    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.REPLIED
    assert outreach.replied_at is not None
    db.refresh(data["match"])
    assert data["match"].agent_verification_status in ["REPLIED", "VERIFIED"]

    # Verify late delivery callback does NOT overwrite REPLIED status
    client.post(
        "/api/webhook/whatsapp",
        json={
            "provider_message_id": outreach.provider_message_id,
            "status": "delivered",
        },
    )
    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.REPLIED


def test_api_preview_and_send_outreach(client, db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match_id = str(data["match"].id)

    # 1. Preview
    prev_resp = client.post(f"/api/property-matches/{match_id}/agent-outreach/preview")
    assert prev_resp.status_code == 200, prev_resp.text


    prev_data = prev_resp.json()
    assert "Novena Suites" in prev_data["message_content"]
    assert prev_data["recipient_phone"] == "+6598765432"

    # 2. Send
    send_resp = client.post(f"/api/property-matches/{match_id}/agent-outreach")
    assert send_resp.status_code == 201
    send_data = send_resp.json()
    assert send_data["status"] == "SENT"
    assert send_data["property_match_id"] == match_id

    # 3. Match outreach history
    hist_resp = client.get(f"/api/property-matches/{match_id}/agent-outreach")
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 1
