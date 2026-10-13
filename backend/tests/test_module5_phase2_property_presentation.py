import pytest
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_source import PropertySource
from app.models.property_match import PropertyMatch
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.property_interest import PropertyInterest
from app.models.viewing import Viewing
from app.models.whatsapp import WhatsAppProfile
from app.models.agent import Agent
from app.models.enums import (
    LeadStatus,
    QualificationStatus,
    QualificationMode,
    OptOutStatus,
    ContactEligibility,
    PropertyType,
    PropertyStatus,
    PropertyListingStatus,
    PropertySourceType,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    PropertyShortlistStatus,
    PropertyInterestStatus,
    TenantInterestIntent,
    ViewingStatus,
    WhatsAppConnectionStatus,
)
from app.services.tenant_property_presentation_service import TenantPropertyPresentationService
from app.services.tenant_property_interest_understanding_service import (
    TenantPropertyInterestUnderstandingService,
)


@pytest.fixture
def presentation_fixtures(db):
    # Setup internal Agent and WhatsAppProfile
    agent = Agent(
        id=uuid.uuid4(),
        full_name="Rental Ops Desk",
        agency_name="Rental Operations",
        phone="+6590000000",
    )
    db.add(agent)

    wa_profile = WhatsAppProfile(
        id=uuid.uuid4(),
        agent_id=agent.id,
        phone_number_id="pn_test_123",
        display_phone_number="+6590000000",
        connection_status=WhatsAppConnectionStatus.CONNECTED,
    )
    db.add(wa_profile)

    lead = Lead(
        id=uuid.uuid4(),
        full_name="Alex Chen",
        phone="+6591234567",
        phone_normalized="+6591234567",
        status=LeadStatus.REPLIED,
        assigned_whatsapp_profile_id=wa_profile.id,
    )
    db.add(lead)

    req = TenantRequirement(
        lead_id=lead.id,
        qualification_status=QualificationStatus.QUALIFIED.value,
        budget_max=Decimal("4000.00"),
        preferred_locations=["Novena"],
        bedrooms=2,
        property_type="CONDO",
        ai_paused=False,
    )
    db.add(req)

    source = PropertySource(
        id=uuid.uuid4(),
        name="PropertyGuru Demo",
        source_type=PropertySourceType.DEMO,
    )
    db.add(source)

    agent_a = PropertyAgent(
        id=uuid.uuid4(),
        full_name="Agent Tan",
        agency_name="PropNex",
        phone="+6582345678",
    )
    agent_b = PropertyAgent(
        id=uuid.uuid4(),
        full_name="Agent Lim",
        agency_name="ERA",
        phone="+6583456789",
    )
    db.add_all([agent_a, agent_b])

    prop_a = Property(
        id=uuid.uuid4(),
        canonical_name="Novena Residence #08-02",
        building_name="Novena Residence",
        district="D11",
        bedrooms=2,
        bathrooms=Decimal("2.0"),
        size_sqft=Decimal("850.00"),
        property_type=PropertyType.CONDO,
        status=PropertyStatus.ACTIVE,
    )
    prop_b = Property(
        id=uuid.uuid4(),
        canonical_name="Newton Suites #14-05",
        building_name="Newton Suites",
        district="D11",
        bedrooms=2,
        bathrooms=Decimal("2.0"),
        size_sqft=Decimal("900.00"),
        property_type=PropertyType.CONDO,
        status=PropertyStatus.ACTIVE,
    )
    db.add_all([prop_a, prop_b])

    listing_a = PropertyListing(
        id=uuid.uuid4(),
        property_id=prop_a.id,
        source_id=source.id,
        agent_id=agent_a.id,
        asking_price=Decimal("3900.00"),
        currency="SGD",
        availability_status=ListingAvailabilityStatus.AVAILABLE,
        listing_status=PropertyListingStatus.ACTIVE,
    )
    listing_b = PropertyListing(
        id=uuid.uuid4(),
        property_id=prop_b.id,
        source_id=source.id,
        agent_id=agent_b.id,
        asking_price=Decimal("3750.00"),
        currency="SGD",
        availability_status=ListingAvailabilityStatus.AVAILABLE,
        listing_status=PropertyListingStatus.ACTIVE,
    )
    db.add_all([listing_a, listing_b])

    match_a = PropertyMatch(
        id=uuid.uuid4(),
        lead_id=lead.id,
        property_id=prop_a.id,
        listing_id=listing_a.id,
        match_score=Decimal("94.0"),
        match_status=PropertyMatchStatus.AVAILABLE.value,
        availability_status=ListingAvailabilityStatus.AVAILABLE.value,
        hard_filter_passed=True,
    )
    match_b = PropertyMatch(
        id=uuid.uuid4(),
        lead_id=lead.id,
        property_id=prop_b.id,
        listing_id=listing_b.id,
        match_score=Decimal("90.0"),
        match_status=PropertyMatchStatus.AVAILABLE.value,
        availability_status=ListingAvailabilityStatus.AVAILABLE.value,
        hard_filter_passed=True,
    )
    db.add_all([match_a, match_b])

    shortlist = PropertyShortlist(
        id=uuid.uuid4(),
        lead_id=lead.id,
        version=1,
        status=PropertyShortlistStatus.READY.value,
    )
    db.add(shortlist)

    item_a = PropertyShortlistItem(
        id=uuid.uuid4(),
        shortlist_id=shortlist.id,
        property_match_id=match_a.id,
        position=1,
        shortlist_status="VERIFIED_CANDIDATE",
        score_at_selection=Decimal("94.0"),
    )
    item_b = PropertyShortlistItem(
        id=uuid.uuid4(),
        shortlist_id=shortlist.id,
        property_match_id=match_b.id,
        position=2,
        shortlist_status="VERIFIED_CANDIDATE",
        score_at_selection=Decimal("90.0"),
    )
    db.add_all([item_a, item_b])
    db.commit()

    return {
        "lead": lead,
        "req": req,
        "shortlist": shortlist,
        "match_a": match_a,
        "match_b": match_b,
        "prop_a": prop_a,
        "prop_b": prop_b,
        "listing_a": listing_a,
        "listing_b": listing_b,
        "item_a": item_a,
        "item_b": item_b,
    }


# ==============================================================================
# TEST 1: PRESENT FIRST PROPERTY
# ==============================================================================
def test_present_first_property(db, presentation_fixtures):
    f = presentation_fixtures
    interest = TenantPropertyPresentationService.present_single_match(
        db=db,
        match_id=f["match_a"].id,
    )
    assert interest.status == PropertyInterestStatus.PRESENTED
    assert interest.presented_at is not None
    assert interest.presented_price == Decimal("3900.00")
    assert interest.source_message_id is not None

    # Verify safe summary excludes internal scores
    summary = TenantPropertyPresentationService.format_tenant_safe_summary(f["match_a"])
    assert "94.0" not in summary.summary_text
    assert "score" not in summary.summary_text.lower()
    assert "Novena Residence" in summary.summary_text


# ==============================================================================
# TEST 2: TENANT INTERESTED (WITHOUT EXPLICIT VIEWING REQUEST)
# ==============================================================================
def test_tenant_interested(db, presentation_fixtures):
    f = presentation_fixtures
    # Present property first
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="I like this one! Looks like a great place.",
    )
    assert res.intent == TenantInterestIntent.INTERESTED
    assert res.viewing_created is False
    assert res.property_interest.status == PropertyInterestStatus.INTERESTED
    assert "arrange an in-person or virtual viewing" in res.response_text


# ==============================================================================
# TEST 3: VIEWING REQUEST CREATES MODULE 5 VIEWING
# ==============================================================================
def test_viewing_request(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="I'd like to schedule a viewing for this property please.",
    )
    assert res.intent == TenantInterestIntent.REQUEST_VIEWING
    assert res.viewing_created is True
    assert res.viewing_id is not None
    assert res.property_interest.status == PropertyInterestStatus.VIEWING_REQUESTED

    # Verify Viewing entity created in DRAFT status
    viewing = db.query(Viewing).filter(Viewing.id == res.viewing_id).first()
    assert viewing is not None
    assert viewing.status == ViewingStatus.DRAFT
    assert viewing.lead_id == f["lead"].id
    assert viewing.property_match_id == f["match_a"].id


# ==============================================================================
# TEST 4: NOT INTERESTED
# ==============================================================================
def test_not_interested(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="No, skip this property. It is not suitable.",
    )
    assert res.intent == TenantInterestIntent.NOT_INTERESTED
    assert res.viewing_created is False
    assert res.property_interest.status == PropertyInterestStatus.NOT_INTERESTED


# ==============================================================================
# TEST 5: REQUEST NEXT PROPERTY
# ==============================================================================
def test_next_property(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Show me another option from the list.",
    )
    assert res.intent == TenantInterestIntent.REQUEST_NEXT_OPTION
    assert res.property_interest is not None
    # Second property (Newton Suites) was presented
    assert res.property_interest.property_match_id == f["match_b"].id


# ==============================================================================
# TEST 6: MORE DETAILS
# ==============================================================================
def test_more_details(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Can you share more details and photos?",
    )
    assert res.intent == TenantInterestIntent.REQUEST_MORE_DETAILS
    assert res.property_interest.status == PropertyInterestStatus.WANTS_MORE_DETAILS
    assert "Novena Residence" in res.response_text


# ==============================================================================
# TEST 7: AMBIGUOUS REFERENCE REQUIRES CLARIFICATION
# ==============================================================================
def test_ambiguous_reference(db, presentation_fixtures):
    f = presentation_fixtures
    # Present both properties
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_b"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Tell me about that one.",
    )
    assert res.needs_clarification is True
    assert res.intent == TenantInterestIntent.UNCLEAR
    assert "clarify which property" in res.clarification_question.lower()


# ==============================================================================
# TEST 8: INTERACTIVE BUTTON SELECTION
# ==============================================================================
def test_interactive_reply(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_b"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Clicked button",
        interactive_payload=f"view_property:{f['match_b'].id}",
    )
    assert res.intent == TenantInterestIntent.REQUEST_VIEWING
    assert res.correlated_property_match_id == f["match_b"].id
    assert res.viewing_created is True
    assert res.property_interest.status == PropertyInterestStatus.VIEWING_REQUESTED


# ==============================================================================
# TEST 9: DUPLICATE VIEWING REQUEST IDEMPOTENT
# ==============================================================================
def test_duplicate_viewing_request(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    # First viewing request
    res1 = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="I'd like to view this property.",
    )
    # Second identical viewing request
    res2 = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Can I schedule a viewing for this?",
    )

    assert res1.viewing_id == res2.viewing_id
    total_viewings = db.query(Viewing).filter(
        Viewing.lead_id == f["lead"].id,
        Viewing.property_match_id == f["match_a"].id,
    ).count()
    assert total_viewings == 1


# ==============================================================================
# TEST 10: PROPERTY BECOMES UNAVAILABLE AFTER PRESENTATION
# ==============================================================================
def test_property_becomes_unavailable(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    # Now property match becomes UNAVAILABLE
    f["match_a"].availability_status = "UNAVAILABLE"
    db.commit()

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="I want to view Novena Residence please.",
    )
    assert res.viewing_created is False
    assert "no longer available" in res.response_text.lower()


# ==============================================================================
# TEST 11: SHORTLIST BECOMES STALE
# ==============================================================================
def test_shortlist_becomes_stale(db, presentation_fixtures):
    f = presentation_fixtures
    f["shortlist"].status = PropertyShortlistStatus.STALE.value
    db.commit()

    with pytest.raises(ValueError, match="expected READY"):
        TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)


# ==============================================================================
# TEST 12: HUMAN TAKEOVER BLOCKS AUTOMATED PRESENTATION
# ==============================================================================
def test_human_takeover_blocks_automated_presentation(db, presentation_fixtures):
    f = presentation_fixtures
    f["req"].qualification_mode = QualificationMode.HUMAN_REVIEW
    db.commit()

    with pytest.raises(ValueError, match="HUMAN_TAKEOVER mode"):
        TenantPropertyPresentationService.present_shortlist(db=db, lead_id=f["lead"].id)


# ==============================================================================
# TEST 13: OPT-OUT BLOCKS PRESENTATION
# ==============================================================================
def test_opt_out_blocks_presentation(db, presentation_fixtures):
    f = presentation_fixtures
    f["lead"].opt_out_status = OptOutStatus.OPTED_OUT
    db.commit()

    with pytest.raises(ValueError, match="opted out"):
        TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)


# ==============================================================================
# TEST 14: PROPERTY Q&A GROUNDED AND UNKNOWN AMENITIES
# ==============================================================================
def test_property_question_grounded_and_unknown(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)

    # 1. Structured attribute question: Rent
    res_rent = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="How much is the rent for Novena Residence?",
    )
    assert res_rent.intent == TenantInterestIntent.ASK_PROPERTY_QUESTION
    assert "3,900" in res_rent.response_text

    # 2. Unknown amenity question: Parking
    res_parking = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Does Novena Residence have parking?",
    )
    assert res_parking.intent == TenantInterestIntent.ASK_PROPERTY_QUESTION
    assert "not currently confirmed" in res_parking.response_text.lower()


# ==============================================================================
# TEST 15: COMPARE PROPERTIES
# ==============================================================================
def test_compare_properties(db, presentation_fixtures):
    f = presentation_fixtures
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_a"].id)
    TenantPropertyPresentationService.present_single_match(db=db, match_id=f["match_b"].id)

    res = TenantPropertyInterestUnderstandingService.process_tenant_response(
        db=db,
        lead_id=f["lead"].id,
        message_content="Which is cheaper and can you compare them?",
    )
    assert res.intent == TenantInterestIntent.COMPARE_PROPERTIES
    assert "Novena Residence" in res.response_text
    assert "Newton Suites" in res.response_text
    assert "3,900" in res.response_text
    assert "3,750" in res.response_text
    # Internal score must not be exposed
    assert "94.0" not in res.response_text


# ==============================================================================
# TEST 16: REST API ENDPOINTS
# ==============================================================================
def test_rest_api_endpoints(client, presentation_fixtures):
    f = presentation_fixtures

    # 1. Present single match via API
    resp = client.post(f"/api/property-matches/{f['match_a'].id}/present-to-tenant")
    assert resp.status_code == 200
    data = resp.json()
    interest_id = data["id"]
    assert data["status"] == "PRESENTED"
    assert data["property_summary"]["name"] == "Novena Residence #08-02"

    # 2. List interests for lead
    resp = client.get(f"/api/leads/{f['lead'].id}/property-interests")
    assert resp.status_code == 200
    interests_list = resp.json()
    assert interests_list["total"] >= 1

    # 3. Get single interest detail
    resp = client.get(f"/api/property-interests/{interest_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == interest_id

    # 4. Manual update by operator
    resp = client.patch(
        f"/api/property-interests/{interest_id}",
        json={"status": "INTERESTED", "tenant_notes": "Tenant called operator directly"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "INTERESTED"
    assert "called operator" in resp.json()["tenant_notes"]

    # 5. Process inbound message via API
    resp = client.post(
        f"/api/leads/{f['lead'].id}/tenant-message/process-interest",
        json={"message_content": "I would love to view this property on Saturday"},
    )
    assert resp.status_code == 200
    process_data = resp.json()
    assert process_data["intent"] == "REQUEST_VIEWING"
    assert process_data["viewing_created"] is True
