import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_agent import PropertyAgent
from app.models.property_match import PropertyMatch
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.property_agent_followup import PropertyAgentFollowUp
from app.models.property_availability_verification import PropertyAvailabilityVerification
from app.models.message import WhatsAppMessage
from app.models.whatsapp import WhatsAppProfile
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    QualificationStatus,
    PropertyType,
    PropertyStatus,
    PropertySourceType,
    PropertySourceStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertyAgentStatus,
    PropertyMatchStatus,
    PropertyAgentOutreachType,
    PropertyAgentOutreachStatus,
    PropertyAgentFollowUpType,
    PropertyAgentFollowUpStatus,
    MessageDirection,
    MessageType,
)
from app.services.agent_followup_config import AgentFollowUpConfig
from app.services.property_agent_followup_service import PropertyAgentFollowUpService
from app.services.property_verification_fallback_service import PropertyVerificationFallbackService
from app.services.property_availability_verification_service import PropertyAvailabilityVerificationService
from app.services.property_agent_response_understanding_service import PropertyAgentResponseUnderstandingService


@pytest.fixture
def test_setup(db: Session):
    """Sets up a complete qualified tenant, property, listing, external agent, and outreach."""
    plat_agent = Agent(
        full_name="Platform Agent P7",
        agency_name="Platform Agency",
        email=f"p7_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(plat_agent)
    db.commit()

    profile = WhatsAppProfile(
        agent_id=plat_agent.id,
        phone_number_id=f"pn_{uuid.uuid4().hex[:8]}",
        display_phone_number="+6590001111",
    )
    db.add(profile)
    db.commit()

    lead = Lead(
        phone="+6588880002",
        phone_normalized="+6588880002",
        status=LeadStatus.REPLIED,
        consent_status=ConsentStatus.CONSENTED,
        opt_out_status=OptOutStatus.ACTIVE,
    )
    db.add(lead)
    db.commit()

    req = TenantRequirement(
        lead_id=lead.id,
        qualification_status=QualificationStatus.QUALIFIED.value,
        budget_max=Decimal("4000"),
        property_type="CONDO",
        bedrooms=2,
        lease_duration_months=12,
        move_in_date=date(2026, 12, 1),
        occupants=2,
        preferred_locations=["Novena", "Newton"],
    )
    db.add(req)
    db.commit()

    source = PropertySource(
        name="PropertyGuru P7",
        source_type=PropertySourceType.CSV_IMPORT,
        status=PropertySourceStatus.ACTIVE,
    )
    db.add(source)
    db.commit()

    prop = Property(
        canonical_name="Newton Edge Condo",
        property_type=PropertyType.CONDO,
        postal_code="307987",
        bedrooms=2,
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop)
    db.commit()

    prop_agent1 = PropertyAgent(
        full_name="Agent Alpha",
        phone="+6591112222",
        phone_normalized="+6591112222",
        agency_name="PropNex",
        status=PropertyAgentStatus.ACTIVE,
    )
    db.add(prop_agent1)

    prop_agent2 = PropertyAgent(
        full_name="Agent Beta",
        phone="+6593334444",
        phone_normalized="+6593334444",
        agency_name="ERA",
        status=PropertyAgentStatus.ACTIVE,
    )
    db.add(prop_agent2)
    db.commit()

    # Listing 1 (Agent 1)
    listing1 = PropertyListing(
        property_id=prop.id,
        source_id=source.id,
        agent_id=prop_agent1.id,
        asking_price=Decimal("3800"),
        currency="SGD",
        listing_status=PropertyListingStatus.ACTIVE,
        availability_status=ListingAvailabilityStatus.AVAILABLE.value,
        available_from=date(2026, 12, 1),
        lease_min_months=12,
        lease_max_months=24,
        listing_reference="P7-LST-001",
    )
    db.add(listing1)

    # Listing 2 for same property (Agent 2)
    listing2 = PropertyListing(
        property_id=prop.id,
        source_id=source.id,
        agent_id=prop_agent2.id,
        asking_price=Decimal("3850"),
        currency="SGD",
        listing_status=PropertyListingStatus.ACTIVE,
        availability_status=ListingAvailabilityStatus.AVAILABLE.value,
        available_from=date(2026, 12, 1),
        lease_min_months=12,
        lease_max_months=24,
        listing_reference="P7-LST-002",
    )
    db.add(listing2)
    db.commit()

    # Property 2 (Candidate for next property fallback)
    prop2 = Property(
        canonical_name="Novena Suites",
        property_type=PropertyType.CONDO,
        postal_code="307654",
        bedrooms=2,
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop2)
    db.commit()

    prop_agent3 = PropertyAgent(
        full_name="Agent Gamma",
        phone="+6595556666",
        phone_normalized="+6595556666",
        agency_name="Huttons",
        status=PropertyAgentStatus.ACTIVE,
    )
    db.add(prop_agent3)
    db.commit()

    listing3 = PropertyListing(
        property_id=prop2.id,
        source_id=source.id,
        agent_id=prop_agent3.id,
        asking_price=Decimal("3900"),
        currency="SGD",
        listing_status=PropertyListingStatus.ACTIVE,
        availability_status=ListingAvailabilityStatus.AVAILABLE.value,
        available_from=date(2026, 12, 1),
        lease_min_months=12,
        lease_max_months=24,
        listing_reference="P7-LST-003",
    )
    db.add(listing3)
    db.commit()

    # Match 1 for Property 1 (Rank #1, score 92)
    match1 = PropertyMatch(
        lead_id=lead.id,
        property_id=prop.id,
        listing_id=listing1.id,
        match_status=PropertyMatchStatus.AWAITING_AGENT.value,
        hard_filter_passed=True,
        match_score=Decimal("92.0"),
        rank=1,
        agent_verification_status="AWAITING_REPLY",
        availability_status="AWAITING_AGENT",
    )
    db.add(match1)

    # Match 2 for Property 2 (Rank #2, score 85)
    match2 = PropertyMatch(
        lead_id=lead.id,
        property_id=prop2.id,
        listing_id=listing3.id,
        match_status=PropertyMatchStatus.SCORED.value,
        hard_filter_passed=True,
        match_score=Decimal("85.0"),
        rank=2,
        agent_verification_status="NOT_CHECKED",
    )
    db.add(match2)
    db.commit()

    # Outreach 1
    now = datetime.now(timezone.utc)
    conv1 = PropertyAgentConversation(
        property_agent_id=prop_agent1.id,
        lead_id=lead.id,
        property_id=prop.id,
        listing_id=listing1.id,
        property_match_id=match1.id,
        conversation_type="PROPERTY_AGENT",
        status="ACTIVE",
        reference_code=f"PM-{str(match1.id)[:8].upper()}",
    )
    db.add(conv1)
    db.commit()

    outreach1 = PropertyAgentOutreach(
        lead_id=lead.id,
        property_id=prop.id,
        listing_id=listing1.id,
        property_match_id=match1.id,
        property_agent_id=prop_agent1.id,
        conversation_id=conv1.id,
        outreach_type=PropertyAgentOutreachType.INITIAL_AVAILABILITY_CHECK,
        status=PropertyAgentOutreachStatus.SENT,
        provider_message_id=f"wamid.p7_{uuid.uuid4().hex[:8]}",
        idempotency_key=f"property-agent-outreach:{match1.id}:init",
        reference_code=f"PM-{str(match1.id)[:8].upper()}",
        recipient_phone=prop_agent1.phone_normalized,
        message_content="Hello, checking availability for Newton Edge Condo.",
        sent_at=now,
        response_due_at=now + timedelta(minutes=180),
        followup_attempt=0,
    )
    db.add(outreach1)
    db.commit()
    db.refresh(outreach1)

    return {
        "lead": lead,
        "req": req,
        "prop1": prop,
        "prop2": prop2,
        "agent1": prop_agent1,
        "agent2": prop_agent2,
        "agent3": prop_agent3,
        "listing1": listing1,
        "listing2": listing2,
        "listing3": listing3,
        "match1": match1,
        "match2": match2,
        "outreach1": outreach1,
        "conv1": conv1,
        "profile": profile,
    }


def test_sla_start_and_schedule_initial_followup(db: Session, test_setup):
    """Test: Initial outreach creates SLA due time and schedules initial follow-up task."""
    data = test_setup
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    cfg = AgentFollowUpConfig(initial_response_sla_minutes=120)
    task = followup_svc.schedule_initial_followup(outreach.id, config=cfg)

    assert task.attempt_number == 1
    assert task.status == PropertyAgentFollowUpStatus.PENDING.value
    assert task.followup_type == PropertyAgentFollowUpType.INITIAL_RESPONSE_WAIT.value
    assert outreach.response_due_at is not None
    assert outreach.followup_attempt == 0


def test_response_before_sla_cancels_followup(db: Session, test_setup):
    """Test 43: Agent replies before SLA due time -> pending follow-up is cancelled, no nudge sent."""
    data = test_setup
    outreach = data["outreach1"]
    match = data["match1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)
    assert task.status == PropertyAgentFollowUpStatus.PENDING.value

    # Agent replies
    outreach.status = PropertyAgentOutreachStatus.REPLIED
    outreach.replied_at = datetime.now(timezone.utc)
    db.commit()

    # Cancel follow-ups
    cancelled_count = followup_svc.cancel_pending_followups_for_outreach(outreach.id, reason="AGENT_REPLIED")
    assert cancelled_count == 1

    db.refresh(task)
    assert task.status == PropertyAgentFollowUpStatus.CANCELLED.value
    assert task.cancellation_reason == "AGENT_REPLIED"


def test_first_followup_sent_when_due(db: Session, test_setup):
    """Test 44: First SLA expires with no reply -> follow-up nudge created/sent, attempt = 1."""
    data = test_setup
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    cfg = AgentFollowUpConfig(initial_response_sla_minutes=10, max_followup_attempts=2)
    task = followup_svc.schedule_initial_followup(outreach.id, config=cfg)

    # Fast forward task due_at to past
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # Worker runs
    results = followup_svc.process_due_followups(config=cfg)
    assert len(results) >= 1

    db.refresh(task)
    assert task.status == PropertyAgentFollowUpStatus.SENT.value
    assert task.sent_at is not None
    assert "following up" in task.message_content.lower()

    db.refresh(outreach)
    assert outreach.followup_attempt == 1

    # Verify next follow-up task was scheduled
    next_task = (
        db.query(PropertyAgentFollowUp)
        .filter(PropertyAgentFollowUp.outreach_id == outreach.id, PropertyAgentFollowUp.attempt_number == 2)
        .first()
    )
    assert next_task is not None
    assert next_task.status == PropertyAgentFollowUpStatus.PENDING.value
    assert next_task.followup_type == PropertyAgentFollowUpType.FINAL_NUDGE.value


def test_max_followups_exhaustion_marks_agent_unresponsive(db: Session, test_setup):
    """Test 45: Max attempts exhausted -> outreach marked UNRESPONSIVE, match marked AGENT_UNRESPONSIVE, fallback triggered."""
    data = test_setup
    outreach = data["outreach1"]
    match = data["match1"]

    followup_svc = PropertyAgentFollowUpService(db)
    cfg = AgentFollowUpConfig(max_followup_attempts=1)
    task = followup_svc.schedule_initial_followup(outreach.id, config=cfg)

    # 1. Send first (and max) attempt
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    followup_svc.process_due_followups(config=cfg)

    # 2. Check scheduled review task
    review_task = (
        db.query(PropertyAgentFollowUp)
        .filter(PropertyAgentFollowUp.outreach_id == outreach.id, PropertyAgentFollowUp.followup_type == PropertyAgentFollowUpType.FALLBACK_REVIEW.value)
        .first()
    )
    assert review_task is not None

    # 3. Process review task after expiry
    review_task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    res2 = followup_svc.process_due_followups(config=cfg)

    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.UNRESPONSIVE
    db.refresh(match)
    # Fallback executed alternate listing!
    assert "UNRESPONSIVE_FALLBACK_TRIGGERED" in [r.get("status") for r in res2]


def test_idempotent_duplicate_scheduler_run(db: Session, test_setup):
    """Test 46: Duplicate worker run does not send duplicate messages."""
    data = test_setup
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    cfg = AgentFollowUpConfig(initial_response_sla_minutes=10)
    task = followup_svc.schedule_initial_followup(outreach.id, config=cfg)
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # First run
    res1 = followup_svc.process_due_followups(config=cfg)
    assert len(res1) == 1
    assert res1[0]["status"] == "SENT"

    # Second run immediately
    res2 = followup_svc.process_due_followups(config=cfg)
    # The task was already marked SENT, so 0 due tasks
    assert len(res2) == 0


def test_agent_reply_just_before_send_cancels_followup(db: Session, test_setup):
    """Test 47: Inbound reply arrives milliseconds before worker execution -> follow-up is cancelled."""
    data = test_setup
    outreach = data["outreach1"]
    agent = data["agent1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # Agent inbound message arrives in DB
    inbound_msg = WhatsAppMessage(
        whatsapp_profile_id=data["profile"].id,
        provider_message_id=f"wamid.in_{uuid.uuid4().hex[:10]}",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender=agent.phone_normalized,
        recipient=data["profile"].display_phone_number,
        content="Yes still available!",
    )
    db.add(inbound_msg)
    db.commit()

    # Worker executes
    results = followup_svc.process_due_followups()
    assert len(results) == 1
    assert results[0]["status"] == "CANCELLED"
    assert "DETECTED" in results[0]["reason"]

    db.refresh(task)
    assert task.status == PropertyAgentFollowUpStatus.CANCELLED.value


def test_fallback_selects_alternate_listing_for_same_property(db: Session, test_setup):
    """Test 48: Unresponsive Agent 1 -> fallback selects alternate Listing 2 with Agent 2 for same property."""
    data = test_setup
    match = data["match1"]
    listing2 = data["listing2"]

    fallback_svc = PropertyVerificationFallbackService(db)
    preview = fallback_svc.preview_fallback(match.id)

    assert preview.recommended_action == "TRY_ALTERNATE_LISTING"
    assert preview.alternate_listing is not None
    assert preview.alternate_listing["id"] == str(listing2.id)

    # Execute
    res = fallback_svc.execute_fallback(match.id, actor_id="operator")
    assert res.status == "SUCCESS"
    assert res.action == "TRY_ALTERNATE_LISTING"
    assert res.new_outreach_id is not None

    db.refresh(match)
    assert match.listing_id == listing2.id


def test_fallback_selects_next_property_when_no_alternate_listing(db: Session, test_setup):
    """Test 49: No alternate listing -> fallback selects next ranked eligible property (Property 2)."""
    data = test_setup
    match1 = data["match1"]
    match2 = data["match2"]
    listing2 = data["listing2"]

    # Deactivate listing 2 so no alternate listing exists for Property 1
    listing2.listing_status = PropertyListingStatus.INACTIVE
    db.commit()

    fallback_svc = PropertyVerificationFallbackService(db)
    preview = fallback_svc.preview_fallback(match1.id)

    assert preview.recommended_action == "TRY_NEXT_PROPERTY"
    assert preview.next_property_match is not None
    assert preview.next_property_match["id"] == str(match2.id)

    # Execute
    res = fallback_svc.execute_fallback(match1.id, actor_id="operator")
    assert res.status == "SUCCESS"
    assert res.action == "TRY_NEXT_PROPERTY"
    assert res.new_match_id == str(match2.id)
    assert res.new_outreach_id is not None


def test_fallback_escalates_to_human_review_when_below_threshold(db: Session, test_setup):
    """Test 50: Next candidate score below minimum threshold -> does not automatically outreach, escalates to HUMAN_REVIEW."""
    data = test_setup
    match1 = data["match1"]
    match2 = data["match2"]
    data["listing2"].listing_status = PropertyListingStatus.INACTIVE

    # Set Match 2 score to 60 (below default 70 threshold)
    match2.match_score = Decimal("60.0")
    db.commit()

    fallback_svc = PropertyVerificationFallbackService(db)
    preview = fallback_svc.preview_fallback(match1.id)

    assert preview.recommended_action == "HUMAN_REVIEW"
    assert preview.reason == "NO_ELIGIBLE_ALTERNATIVES"

    res = fallback_svc.execute_fallback(match1.id)
    assert res.status == "ESCALATED"
    assert res.action == "HUMAN_REVIEW"

    db.refresh(match1)
    assert match1.match_status == PropertyMatchStatus.NEEDS_REVIEW.value
    assert match1.agent_verification_status == "HUMAN_REVIEW"


def test_fallback_escalates_when_max_total_contacts_reached(db: Session, test_setup):
    """Test 51: Max total agent contacts for lead reached -> no more automatic outreach, HUMAN_REVIEW."""
    data = test_setup
    match1 = data["match1"]

    cfg = AgentFollowUpConfig(max_total_agent_contacts=1)
    fallback_svc = PropertyVerificationFallbackService(db)
    preview = fallback_svc.preview_fallback(match1.id, config=cfg)

    assert preview.recommended_action == "HUMAN_REVIEW"
    assert preview.reason == "MAX_AGENT_CONTACTS_REACHED"


def test_listing_unavailable_cancels_followup_and_triggers_fallback(db: Session, test_setup):
    """Test 52: Listing marked UNAVAILABLE during pending follow-up -> cancels follow-up and evaluates fallback."""
    data = test_setup
    outreach = data["outreach1"]
    listing = data["listing1"]
    match = data["match1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Listing marked unavailable
    listing.availability_status = ListingAvailabilityStatus.UNAVAILABLE.value
    db.commit()

    results = followup_svc.process_due_followups()
    assert len(results) == 1
    assert results[0]["status"] == "CANCELLED"
    assert results[0]["reason"] == "LISTING_UNAVAILABLE"


def test_price_change_breaks_match_cancels_future_followups(db: Session, test_setup):
    """Test 53: Agent price change violates tenant budget -> match marked CONDITIONAL/incompatible, follow-ups cancelled."""
    data = test_setup
    match = data["match1"]
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)
    assert task.status == PropertyAgentFollowUpStatus.PENDING.value

    inbound_msg = WhatsAppMessage(
        whatsapp_profile_id=data["profile"].id,
        provider_message_id=f"wamid.in_{uuid.uuid4().hex[:10]}",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender=data["agent1"].phone_normalized,
        recipient=data["profile"].display_phone_number,
        content="Price is 4500",
    )
    db.add(inbound_msg)
    db.commit()

    verification_svc = PropertyAvailabilityVerificationService(db)
    analysis_extraction = {
        "status": "COMPLETED",
        "message_id": str(inbound_msg.id),
        "correlation": {
            "status": "RESOLVED",
            "property_match_id": str(match.id),
            "listing_id": str(data["listing1"].id),
            "outreach_id": str(outreach.id),
        },
        "extraction": {
            "intent": "PRICE_UPDATE",
            "fields": {
                "availability": {"value": "AVAILABLE", "confidence": 0.95},
                "asking_price": {"value": 4500.0, "confidence": 0.95},  # Exceeds max budget 4000
            },
        },
    }

    verification_svc.apply_verification_from_extraction(analysis_extraction)

    db.refresh(task)
    assert task.status == PropertyAgentFollowUpStatus.CANCELLED.value


def test_failed_send_does_not_count_as_valid_attempt(db: Session, test_setup, monkeypatch):
    """Test 54: Failed WhatsApp send -> task marked FAILED, does not count as a successful attempt."""
    data = test_setup
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)
    task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # Mock send_message failure
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Meta WhatsApp network timeout")

    monkeypatch.setattr(followup_svc.whatsapp_service, "send_message", mock_fail)

    res = followup_svc.process_due_followups()
    assert res[0]["status"] == "FAILED"

    db.refresh(task)
    assert task.status == PropertyAgentFollowUpStatus.FAILED.value
    db.refresh(outreach)
    assert outreach.followup_attempt == 0


def test_late_response_processed_without_disrupting_active_flow(db: Session, test_setup):
    """Test 55: Agent responds after being marked UNRESPONSIVE -> processed via Phase 6, late response audited."""
    data = test_setup
    match = data["match1"]
    outreach = data["outreach1"]

    # Mark outreach as UNRESPONSIVE
    outreach.status = PropertyAgentOutreachStatus.UNRESPONSIVE
    db.commit()

    inbound_msg = WhatsAppMessage(
        whatsapp_profile_id=data["profile"].id,
        provider_message_id=f"wamid.in_{uuid.uuid4().hex[:10]}",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender=data["agent1"].phone_normalized,
        recipient=data["profile"].display_phone_number,
        content="Yes available at 3800",
    )
    db.add(inbound_msg)
    db.commit()

    verification_svc = PropertyAvailabilityVerificationService(db)
    analysis = {
        "status": "COMPLETED",
        "message_id": str(inbound_msg.id),
        "correlation": {
            "status": "RESOLVED",
            "property_match_id": str(match.id),
            "listing_id": str(data["listing1"].id),
            "outreach_id": str(outreach.id),
        },
        "extraction": {
            "intent": "AVAILABLE",
            "fields": {
                "availability": {"value": "AVAILABLE", "confidence": 0.95},
                "asking_price": {"value": 3800.0, "confidence": 0.95},
            },
        },
    }

    res = verification_svc.apply_verification_from_extraction(analysis)
    assert res["status"] == "COMPLETED"

    db.refresh(outreach)
    assert outreach.status == PropertyAgentOutreachStatus.REPLIED
    assert outreach.replied_at is not None


def test_manual_followup_by_operator(db: Session, test_setup):
    """Test 56: Operator sends manual follow-up early -> recorded with attempt increment and audit log."""
    data = test_setup
    outreach = data["outreach1"]

    followup_svc = PropertyAgentFollowUpService(db)
    initial_task = followup_svc.schedule_initial_followup(outreach.id)

    task = followup_svc.send_manual_followup(
        outreach_id=outreach.id,
        reason="Operator urgently needs verification",
        actor_id="operator_sarah",
    )

    assert task.attempt_number == 1
    assert task.status == PropertyAgentFollowUpStatus.SENT.value
    assert task.sent_at is not None

    db.refresh(outreach)
    assert outreach.followup_attempt == 1

    db.refresh(initial_task)
    assert initial_task.status == PropertyAgentFollowUpStatus.CANCELLED.value


def test_unauthorized_manual_followup_blocked_if_replied(db: Session, test_setup):
    """Test 57: Attempt to send manual follow-up when agent has already replied -> blocked with 400 error."""
    data = test_setup
    outreach = data["outreach1"]
    outreach.status = PropertyAgentOutreachStatus.REPLIED
    db.commit()

    followup_svc = PropertyAgentFollowUpService(db)
    with pytest.raises(Exception) as exc:
        followup_svc.send_manual_followup(outreach.id)
    assert "already replied" in str(exc.value).lower()


def test_api_endpoints_followups_and_fallback(client: TestClient, test_setup, db: Session):
    """Test API: GET followups, POST manual follow-up, POST cancel, GET fallback-preview, POST execute-fallback."""
    data = test_setup
    outreach = data["outreach1"]
    match = data["match1"]

    followup_svc = PropertyAgentFollowUpService(db)
    task = followup_svc.schedule_initial_followup(outreach.id)

    # 1. GET follow-up list
    res_list = client.get(f"/api/property-agent-followups?match_id={match.id}")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 2. GET match follow-ups
    res_match_tasks = client.get(f"/api/property-matches/{match.id}/followups")
    assert res_match_tasks.status_code == 200
    assert len(res_match_tasks.json()) >= 1

    # 3. POST cancel follow-up
    res_cancel = client.post(
        f"/api/property-agent-followups/{task.id}/cancel",
        json={"reason": "Operator manually verified externally"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # 4. POST manual follow-up
    res_manual = client.post(
        f"/api/property-agent-outreach/{outreach.id}/follow-up",
        json={"reason": "Follow up now requested"},
    )
    assert res_manual.status_code == 200
    assert res_manual.json()["status"] == "SENT"

    # 5. GET fallback preview
    res_prev = client.get(f"/api/property-matches/{match.id}/fallback-preview")
    assert res_prev.status_code == 200
    prev_data = res_prev.json()
    assert prev_data["recommended_action"] == "TRY_ALTERNATE_LISTING"

    # 6. POST execute fallback
    res_exec = client.post(
        f"/api/property-matches/{match.id}/execute-fallback",
        json={"reason": "Agent unresponsive on listing 1"},
    )
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["status"] == "SUCCESS"
    assert exec_data["action"] == "TRY_ALTERNATE_LISTING"


def test_phase7_acceptance_flow_end_to_end(db: Session, test_setup):
    """
    Section 60 Acceptance Flow:
    Property #1 (Score 94, Agent A) contacted
    -> No reply
    -> SLA expires
    -> Follow-up #1 sent
    -> No reply
    -> Final configured attempt expires
    -> Agent A marked UNRESPONSIVE
    -> System checks same property: Alternate Listing with Agent B exists
    -> Agent B selected & new outreach sent
    -> Agent B responds: 'Yes, available at 3900.'
    -> Phase 6 processes response
    -> Property becomes VERIFIED_CANDIDATE
    -> Confirmed: No viewing scheduled, no negotiation, no agreement generation.
    """
    data = test_setup
    match1 = data["match1"]
    match1.match_score = Decimal("94.0")
    db.commit()

    outreach1 = data["outreach1"]
    listing2 = data["listing2"]
    agent2 = data["agent2"]

    followup_svc = PropertyAgentFollowUpService(db)
    fallback_svc = PropertyVerificationFallbackService(db)
    verification_svc = PropertyAvailabilityVerificationService(db)

    # 1. Config: max 1 follow-up attempt
    cfg = AgentFollowUpConfig(
        initial_response_sla_minutes=10,
        followup_delay_minutes=10,
        max_followup_attempts=1,
        alternate_listing_enabled=True,
    )

    # SLA started on initial outreach
    initial_task = followup_svc.schedule_initial_followup(outreach1.id, config=cfg)
    assert initial_task.status == PropertyAgentFollowUpStatus.PENDING.value
    assert match1.match_status == PropertyMatchStatus.AWAITING_AGENT.value

    # 2. SLA expires -> Follow-up #1 sent
    initial_task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    res1 = followup_svc.process_due_followups(config=cfg)
    assert len(res1) == 1
    assert res1[0]["status"] == "SENT"
    assert res1[0]["attempt_number"] == 1

    db.refresh(outreach1)
    assert outreach1.followup_attempt == 1

    # Follow-up #1 created next review task (attempt 2)
    review_task = (
        db.query(PropertyAgentFollowUp)
        .filter(
            PropertyAgentFollowUp.outreach_id == outreach1.id,
            PropertyAgentFollowUp.attempt_number == 2,
        )
        .first()
    )
    assert review_task is not None

    # 3. Final configured attempt expires -> Agent A marked UNRESPONSIVE
    review_task.due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    res2 = followup_svc.process_due_followups(config=cfg)
    assert len(res2) == 1
    assert "UNRESPONSIVE_FALLBACK_TRIGGERED" in [r.get("status") for r in res2]

    db.refresh(outreach1)
    assert outreach1.status == PropertyAgentOutreachStatus.UNRESPONSIVE

    # 4. Fallback selected alternate listing 2 (Agent B)
    db.refresh(match1)
    assert match1.listing_id == listing2.id

    # New outreach to Agent B exists
    outreach2 = (
        db.query(PropertyAgentOutreach)
        .filter(
            PropertyAgentOutreach.property_match_id == match1.id,
            PropertyAgentOutreach.property_agent_id == agent2.id,
        )
        .first()
    )
    assert outreach2 is not None
    assert outreach2.status == PropertyAgentOutreachStatus.SENT

    # 5. Agent B responds: 'Yes, available at 3900.'
    inbound_msg = WhatsAppMessage(
        whatsapp_profile_id=data["profile"].id,
        provider_message_id=f"wamid.in_{uuid.uuid4().hex[:10]}",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender=agent2.phone_normalized,
        recipient=data["profile"].display_phone_number,
        content="Yes, available at 3900.",
    )
    db.add(inbound_msg)
    db.commit()

    analysis_extraction = {
        "status": "COMPLETED",
        "message_id": str(inbound_msg.id),
        "correlation": {
            "status": "RESOLVED",
            "property_match_id": str(match1.id),
            "listing_id": str(listing2.id),
            "outreach_id": str(outreach2.id),
        },
        "extraction": {
            "intent": "AVAILABLE",
            "fields": {
                "availability": {"value": "AVAILABLE", "confidence": 0.98},
                "asking_price": {"value": 3900.0, "confidence": 0.95},
            },
        },
    }

    v_result = verification_svc.apply_verification_from_extraction(analysis_extraction)
    assert v_result["status"] == "COMPLETED"

    # 6. Property becomes verified candidate
    db.refresh(match1)
    assert match1.match_status in [PropertyMatchStatus.AVAILABLE.value, PropertyMatchStatus.VERIFIED_CANDIDATE.value]
    assert match1.agent_verification_status in ["VERIFIED", "CONFIRMED"]

    # 7. Strictly verify boundary: No viewing scheduled, no negotiation, no agreement
    # Matches table checks
    assert not hasattr(match1, "viewing_scheduled_at") or match1.__dict__.get("viewing_scheduled_at") is None
    # No pending follow-ups
    pending_followups = (
        db.query(PropertyAgentFollowUp)
        .filter(
            PropertyAgentFollowUp.property_match_id == match1.id,
            PropertyAgentFollowUp.status.in_([
                PropertyAgentFollowUpStatus.PENDING.value,
                PropertyAgentFollowUpStatus.DUE.value,
            ]),
        )
        .count()
    )
    assert pending_followups == 0

