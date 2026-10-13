import pytest
from datetime import datetime, timedelta, timezone
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
from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.enums import (
    LeadStatus,
    QualificationStatus,
    PropertyType,
    PropertyStatus,
    PropertyListingStatus,
    PropertySourceType,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    PropertyShortlistStatus,
    ShortlistItemStatus,
    ViewingStatus,
    ViewingConfirmationStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingLocationType,
)
from app.services.viewing_service import ViewingService
from app.services.viewing_slot_service import ViewingSlotService
from app.services.viewing_state_machine import ViewingStateMachine


@pytest.fixture
def base_fixtures(db):
    lead = Lead(
        id=uuid.uuid4(),
        full_name="Alex Chen",
        phone="+6591234567",
        phone_normalized="+6591234567",
        status=LeadStatus.REPLIED,
    )
    db.add(lead)

    req = TenantRequirement(
        lead_id=lead.id,
        qualification_status=QualificationStatus.QUALIFIED.value,
        budget_max=Decimal("4000.00"),
        preferred_locations=["Novena"],
        bedrooms=2,
        property_type="CONDO",
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
        district="D11",
        bedrooms=2,
        property_type=PropertyType.CONDO,
        status=PropertyStatus.ACTIVE,
    )
    prop_b = Property(
        id=uuid.uuid4(),
        canonical_name="Newton Suites #14-05",
        district="D11",
        bedrooms=2,
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
        availability_status=ListingAvailabilityStatus.AVAILABLE,
        listing_status=PropertyListingStatus.ACTIVE,
    )
    listing_b = PropertyListing(
        id=uuid.uuid4(),
        property_id=prop_b.id,
        source_id=source.id,
        agent_id=agent_b.id,
        asking_price=Decimal("3750.00"),
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
        status=PropertyShortlistStatus.READY.value,
        version=1,
    )
    db.add(shortlist)
    db.flush()

    item_a = PropertyShortlistItem(
        id=uuid.uuid4(),
        shortlist_id=shortlist.id,
        property_match_id=match_a.id,
        position=1,
        shortlist_status=ShortlistItemStatus.VERIFIED_CANDIDATE.value,
    )
    item_b = PropertyShortlistItem(
        id=uuid.uuid4(),
        shortlist_id=shortlist.id,
        property_match_id=match_b.id,
        position=2,
        shortlist_status=ShortlistItemStatus.VERIFIED_CANDIDATE.value,
    )
    db.add_all([item_a, item_b])
    db.commit()

    return {
        "lead": lead,
        "req": req,
        "prop_a": prop_a,
        "prop_b": prop_b,
        "listing_a": listing_a,
        "listing_b": listing_b,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "match_a": match_a,
        "match_b": match_b,
        "shortlist": shortlist,
        "item_a": item_a,
        "item_b": item_b,
    }


# ==============================================================================
# TEST 1: VALID VIEWING CREATION
# ==============================================================================
def test_valid_viewing_creation(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(
        db=db,
        match_id=f["match_a"].id,
        created_by="operator_john",
    )
    assert viewing.id is not None
    assert viewing.lead_id == f["lead"].id
    assert viewing.property_match_id == f["match_a"].id
    assert viewing.property_id == f["prop_a"].id
    assert viewing.listing_id == f["listing_a"].id
    assert viewing.property_agent_id == f["agent_a"].id
    assert viewing.status == ViewingStatus.DRAFT
    assert viewing.tenant_confirmation_status == ViewingConfirmationStatus.NOT_REQUIRED
    assert viewing.agent_confirmation_status == ViewingConfirmationStatus.NOT_REQUIRED
    assert viewing.timezone == "Asia/Singapore"
    assert viewing.duration_minutes == 30
    assert len(viewing.events) >= 1
    assert viewing.events[0].event_type == ViewingEventType.VIEWING_CREATED


# ==============================================================================
# TEST 2: INVALID PROPERTY BLOCKED
# ==============================================================================
def test_invalid_property_blocked(db, base_fixtures):
    f = base_fixtures
    # Mark listing unavailable
    f["listing_a"].availability_status = ListingAvailabilityStatus.UNAVAILABLE
    db.commit()

    with pytest.raises(ValueError, match="marked UNAVAILABLE"):
        ViewingService.create_viewing_from_match(
            db=db,
            match_id=f["match_a"].id,
        )


# ==============================================================================
# TEST 3: STALE SHORTLIST BLOCKED
# ==============================================================================
def test_stale_shortlist_blocked(db, base_fixtures):
    f = base_fixtures
    f["shortlist"].status = PropertyShortlistStatus.STALE.value
    db.commit()

    with pytest.raises(ValueError, match="is STALE"):
        ViewingService.create_viewing_from_match(
            db=db,
            match_id=f["match_a"].id,
        )


# ==============================================================================
# TEST 4: UNQUALIFIED TENANT BLOCKED
# ==============================================================================
def test_unqualified_tenant_blocked(db, base_fixtures):
    f = base_fixtures
    f["req"].qualification_status = QualificationStatus.QUALIFYING.value
    db.commit()

    with pytest.raises(ValueError, match="not QUALIFIED"):
        ViewingService.create_viewing_from_match(
            db=db,
            match_id=f["match_a"].id,
        )


# ==============================================================================
# TEST 5: MULTIPLE VIEWINGS ACROSS DIFFERENT PROPERTIES ALLOWED
# ==============================================================================
def test_multiple_viewings_allowed(db, base_fixtures):
    f = base_fixtures
    viewing_a = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)
    viewing_b = ViewingService.create_viewing_from_match(db=db, match_id=f["match_b"].id)

    assert viewing_a.id != viewing_b.id
    assert viewing_a.property_id == f["prop_a"].id
    assert viewing_b.property_id == f["prop_b"].id

    lead_viewings = ViewingService.list_viewings(db=db, lead_id=f["lead"].id)
    assert len(lead_viewings) == 2


# ==============================================================================
# TEST 6: DUPLICATE VIEWING FOR SAME PROPERTY IDEMPOTENT
# ==============================================================================
def test_duplicate_same_property_idempotent(db, base_fixtures):
    f = base_fixtures
    v1 = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)
    v2 = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    # Must return existing active viewing rather than creating duplicate
    assert v1.id == v2.id
    all_viewings = ViewingService.list_viewings(db=db, lead_id=f["lead"].id)
    assert len(all_viewings) == 1


# ==============================================================================
# TEST 7: ADD MULTIPLE SLOTS
# ==============================================================================
def test_add_multiple_slots(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    t1 = datetime(2026, 10, 17, 3, 0, tzinfo=timezone.utc)  # Sat 11am SGT
    t2 = datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc)  # Sat 3pm SGT
    t3 = datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)  # Sun 10am SGT

    s1 = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t1)
    s2 = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t2)
    s3 = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t3)

    assert s1.id != s2.id != s3.id
    slots = ViewingSlotService.list_slots(db=db, viewing_id=viewing.id)
    assert len(slots) == 3
    assert [s.start_at for s in slots] == [t1, t2, t3]


# ==============================================================================
# TEST 8: SELECT SLOT & AT MOST ONE SELECTED INVARIANT
# ==============================================================================
def test_select_slot_enforces_single_selection(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    t1 = datetime(2026, 10, 17, 3, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc)

    s1 = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t1)
    s2 = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t2)

    # 1. Select s1
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=s1.id)
    db.refresh(viewing)
    db.refresh(s1)
    assert s1.status == ViewingSlotStatus.SELECTED
    assert viewing.scheduled_start_at == t1

    # 2. Select s2 -> s1 must be reverted to AVAILABLE
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=s2.id)
    db.refresh(viewing)
    db.refresh(s1)
    db.refresh(s2)
    assert s2.status == ViewingSlotStatus.SELECTED
    assert s1.status == ViewingSlotStatus.AVAILABLE
    assert viewing.scheduled_start_at == t2


# ==============================================================================
# TEST 9: INVALID SLOT DURATION (end <= start)
# ==============================================================================
def test_invalid_slot_duration(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    t_start = datetime(2026, 10, 17, 5, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 10, 17, 4, 0, tzinfo=timezone.utc)  # 1 hour prior

    with pytest.raises(ValueError, match="strictly greater than start_at"):
        ViewingSlotService.add_slot(
            db=db,
            viewing_id=viewing.id,
            start_at=t_start,
            end_at=t_end,
        )


# ==============================================================================
# TEST 10: CROSS-VIEWING SLOT SELECTION REJECTED
# ==============================================================================
def test_cross_viewing_slot_rejected(db, base_fixtures):
    f = base_fixtures
    va = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)
    vb = ViewingService.create_viewing_from_match(db=db, match_id=f["match_b"].id)

    slot_b = ViewingSlotService.add_slot(
        db=db,
        viewing_id=vb.id,
        start_at=datetime(2026, 10, 17, 5, 0, tzinfo=timezone.utc),
    )

    # Attempt to select slot_b on viewing va
    with pytest.raises(ValueError, match="not found for viewing"):
        ViewingSlotService.select_slot(db=db, viewing_id=va.id, slot_id=slot_b.id)


# ==============================================================================
# TEST 11: INVALID STATE TRANSITION REJECTED
# ==============================================================================
def test_invalid_state_transition_rejected(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    # DRAFT -> COMPLETED is illegal
    with pytest.raises(ValueError, match="Invalid viewing state transition"):
        ViewingService.transition_viewing(
            db=db,
            viewing_id=viewing.id,
            target_status=ViewingStatus.COMPLETED,
        )

    # CANCELLED -> CONFIRMED is illegal
    ViewingService.cancel_viewing(db=db, viewing_id=viewing.id, reason="Changed mind")
    with pytest.raises(ValueError, match="Invalid viewing state transition"):
        ViewingService.transition_viewing(
            db=db,
            viewing_id=viewing.id,
            target_status=ViewingStatus.CONFIRMED,
        )


# ==============================================================================
# TEST 12: VALID WORKFLOW TRANSITION SEQUENCE
# ==============================================================================
def test_valid_state_transition_sequence(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)
    assert viewing.status == ViewingStatus.DRAFT

    # DRAFT -> SLOTS_AVAILABLE
    v1 = ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOTS_AVAILABLE)
    assert v1.status == ViewingStatus.SLOTS_AVAILABLE

    # SLOTS_AVAILABLE -> SLOT_PROPOSED
    v2 = ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOT_PROPOSED)
    assert v2.status == ViewingStatus.SLOT_PROPOSED

    # Add slot & select it before confirming
    t_slot = datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc)
    s = ViewingSlotService.add_slot(db=db, viewing_id=viewing.id, start_at=t_slot)
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=s.id)

    # SLOT_PROPOSED -> CONFIRMED
    v3 = ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.CONFIRMED)
    assert v3.status == ViewingStatus.CONFIRMED
    assert v3.tenant_confirmation_status == ViewingConfirmationStatus.CONFIRMED
    assert v3.agent_confirmation_status == ViewingConfirmationStatus.CONFIRMED

    # CONFIRMED -> RESCHEDULE_REQUESTED
    v4 = ViewingService.transition_viewing(
        db=db,
        viewing_id=viewing.id,
        target_status=ViewingStatus.RESCHEDULE_REQUESTED,
        reason="Agent requested later time",
    )
    assert v4.status == ViewingStatus.RESCHEDULE_REQUESTED
    assert v4.reschedule_count == 1
    assert v4.previous_scheduled_start_at == t_slot


# ==============================================================================
# TEST 13: CANCELLATION WORKFLOW
# ==============================================================================
def test_cancel_viewing_workflow(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    slot = ViewingSlotService.add_slot(
        db=db,
        viewing_id=viewing.id,
        start_at=datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc),
    )
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=slot.id)

    cancelled = ViewingService.cancel_viewing(
        db=db,
        viewing_id=viewing.id,
        reason="Tenant found alternate condo",
        cancelled_by="TENANT",
    )

    assert cancelled.status == ViewingStatus.CANCELLED
    assert cancelled.cancellation_reason == "Tenant found alternate condo"
    assert cancelled.cancelled_by == "TENANT"
    assert cancelled.cancelled_at is not None

    db.refresh(slot)
    assert slot.status == ViewingSlotStatus.CANCELLED


# ==============================================================================
# TEST 14: COMPLETION WORKFLOW
# ==============================================================================
def test_complete_viewing_workflow(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    slot = ViewingSlotService.add_slot(
        db=db,
        viewing_id=viewing.id,
        start_at=datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc),
    )
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=slot.id)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOTS_AVAILABLE)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOT_PROPOSED)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.CONFIRMED)

    completed = ViewingService.complete_viewing(
        db=db,
        viewing_id=viewing.id,
        notes="Tenant attended viewing on time with agent",
    )
    assert completed.status == ViewingStatus.COMPLETED
    assert completed.completed_at is not None
    assert "Tenant attended" in completed.outcome_notes


# ==============================================================================
# TEST 15: NO-SHOW RECORDING
# ==============================================================================
def test_no_show_workflow(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(db=db, match_id=f["match_a"].id)

    slot = ViewingSlotService.add_slot(
        db=db,
        viewing_id=viewing.id,
        start_at=datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc),
    )
    ViewingSlotService.select_slot(db=db, viewing_id=viewing.id, slot_id=slot.id)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOTS_AVAILABLE)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.SLOT_PROPOSED)
    ViewingService.transition_viewing(db=db, viewing_id=viewing.id, target_status=ViewingStatus.CONFIRMED)

    noshow = ViewingService.record_no_show(
        db=db,
        viewing_id=viewing.id,
        actor="PROPERTY_AGENT",
        notes="Agent did not arrive at guardhouse",
    )
    assert noshow.status == ViewingStatus.NO_SHOW
    assert "No show by PROPERTY_AGENT" in noshow.outcome_notes


# ==============================================================================
# TEST 16: TIMEZONE VALIDATION
# ==============================================================================
def test_timezone_validation(db, base_fixtures):
    f = base_fixtures
    viewing = ViewingService.create_viewing_from_match(
        db=db,
        match_id=f["match_a"].id,
        timezone="Asia/Singapore",
    )
    assert viewing.timezone == "Asia/Singapore"

    with pytest.raises(ValueError, match="Invalid timezone identifier"):
        ViewingService.create_viewing_from_match(
            db=db,
            match_id=f["match_b"].id,
            timezone="Mars/Olympus_Mons",
        )


# ==============================================================================
# TEST 17: FASTAPI HTTP REST ENDPOINTS
# ==============================================================================
def test_viewings_api_endpoints(client, base_fixtures):
    f = base_fixtures

    # 1. Create viewing via API
    resp = client.post(
        f"/api/property-matches/{f['match_a'].id}/viewings",
        json={"duration_minutes": 45, "timezone": "Asia/Singapore"},
    )
    assert resp.status_code == 201
    v_data = resp.json()
    viewing_id = v_data["id"]
    assert v_data["status"] == "DRAFT"
    assert v_data["duration_minutes"] == 45
    assert v_data["property_summary"]["canonical_name"] == "Novena Residence #08-02"

    # 2. List lead viewings
    resp = client.get(f"/api/leads/{f['lead'].id}/viewings")
    assert resp.status_code == 200
    list_data = resp.json()
    assert list_data["total"] >= 1

    # 3. Add slot via API
    slot_start = "2026-10-17T11:00:00Z"
    resp = client.post(
        f"/api/viewings/{viewing_id}/slots",
        json={"start_at": slot_start, "timezone": "Asia/Singapore"},
    )
    assert resp.status_code == 201
    s_data = resp.json()
    slot_id = s_data["id"]

    # 4. Select slot via API
    resp = client.post(f"/api/viewings/{viewing_id}/slots/{slot_id}/select")
    assert resp.status_code == 200
    assert resp.json()["status"] == "SELECTED"

    # 5. Detail view via API
    resp = client.get(f"/api/viewings/{viewing_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["slots"]) == 1
    assert len(detail["events"]) >= 2

    # 6. Cancel via API
    resp = client.post(
        f"/api/viewings/{viewing_id}/cancel",
        json={"reason": "Testing cancellation API"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"
