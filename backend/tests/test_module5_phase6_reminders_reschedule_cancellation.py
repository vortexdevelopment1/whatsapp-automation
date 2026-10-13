"""
Module 5 Phase 6 - Comprehensive Test Suite:
Reminders + Reschedule + Cancellation
Tests:
51. Normal reminder creation and dispatch when due.
52. Duplicate reminder worker execution (idempotency key prevents duplicate sends).
53. Viewing cancelled before reminder fires (reminder skipped/not sent).
54. Reschedule before reminder (old reminder skipped/cancelled).
55. Reschedule success (old booking preserved in history, version incremented, new reminders scheduled).
56. Agent-requested reschedule (captured, requires tenant confirmation).
57. Tenant cancellation (viewing CANCELLED, reminders cancelled, agent notified).
58. Agent cancellation (viewing CANCELLED, reminders cancelled, tenant notified).
59. Property becomes unavailable (system cancellation path, both notified, reminders cancelled).
60. Duplicate cancellation idempotency (single state transition, single notification set).
61. Duplicate reschedule request idempotency (one active reschedule workflow).
62. Multiple viewings correlation & ambiguity clarification.
63. Reminder send failure & bounded retry (viewing remains CONFIRMED, failure recorded).
64. Race condition handling (pre-send revalidation prevents post-cancellation send).
65. Stale schedule version check (old version reminders skipped).
66. Invalid/Unauthorized reschedule state (blocked on CANCELLED/COMPLETED).
67. REST API endpoints for reminders, rebuild, reschedule, cancel, and schedule-history.
"""
import pytest
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import uuid
from unittest.mock import MagicMock

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_source import PropertySource
from app.models.property_match import PropertyMatch
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.viewing_reminder import ViewingReminder, ViewingScheduleHistory
from app.models.agent import Agent
from app.models.message import WhatsAppMessage
from app.models.whatsapp import WhatsAppProfile
from app.models.enums import (
    LeadStatus,
    QualificationStatus,
    PropertyType,
    PropertyStatus,
    PropertyListingStatus,
    PropertySourceType,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    ViewingStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingConfirmationStatus,
    ViewingReminderParty,
    ViewingReminderType,
    ViewingReminderStatus,
    ViewingOperationIntent,
    ContactEligibility,
    MessageDirection,
    MessageType,
    WhatsAppConnectionStatus,
)
from app.services.viewing_reminder_config import ViewingReminderConfig
from app.services.viewing_reminder_service import ViewingReminderService
from app.services.viewing_reschedule_service import ViewingRescheduleService
from app.services.viewing_cancellation_service import ViewingCancellationService
from app.services.viewing_operation_understanding_service import ViewingOperationUnderstandingService
from app.services.viewing_confirmation_service import ViewingConfirmationService


@pytest.fixture
def phase6_fixtures(db):
    lead = Lead(
        id=uuid.uuid4(),
        full_name="Alex Tan",
        phone="+6591234567",
        phone_normalized="+6591234567",
        status=LeadStatus.REPLIED,
        contact_eligibility=ContactEligibility.ELIGIBLE,
    )
    db.add(lead)

    source = PropertySource(
        id=uuid.uuid4(),
        name="PropertyGuru",
        source_type=PropertySourceType.DEMO,
    )
    db.add(source)

    prop = Property(
        id=uuid.uuid4(),
        canonical_name="Novena Residence",
        property_type=PropertyType.CONDO,
        address_line_1="100 Moulmein Road",
        postal_code="308123",
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop)

    agent_user = Agent(
        id=uuid.uuid4(),
        full_name="Platform Concierge Agent",
        email=f"agent_{uuid.uuid4().hex[:6]}@platform.sg",
        phone="+6590000000",
        agency_name="Platform Property",
    )
    db.add(agent_user)
    db.flush()

    wa_profile = WhatsAppProfile(
        id=uuid.uuid4(),
        agent_id=agent_user.id,
        phone_number_id="pn_platform_test",
        display_phone_number="+6590000000",
        business_display_name="Platform Concierge",
        connection_status=WhatsAppConnectionStatus.CONNECTED,
    )
    db.add(wa_profile)

    listing_agent = PropertyAgent(
        id=uuid.uuid4(),
        full_name="David Lim",
        phone="+6598889999",
        phone_normalized="+6598889999",
        agency_name="ERA Realty",
    )
    db.add(listing_agent)

    listing = PropertyListing(
        id=uuid.uuid4(),
        property_id=prop.id,
        source_id=source.id,
        agent_id=listing_agent.id,
        source_listing_id="REF-NOV-101",
        listing_reference="REF-NOV-101",
        asking_price=Decimal("4500.00"),
        listing_status=PropertyListingStatus.ACTIVE,
        availability_status=ListingAvailabilityStatus.AVAILABLE,
    )
    db.add(listing)

    shortlist = PropertyShortlist(
        id=uuid.uuid4(),
        lead_id=lead.id,
        status="ACTIVE",
    )
    db.add(shortlist)

    match = PropertyMatch(
        id=uuid.uuid4(),
        lead_id=lead.id,
        property_id=prop.id,
        listing_id=listing.id,
        match_status=PropertyMatchStatus.AVAILABLE.value,
        availability_status="AVAILABLE",
    )
    db.add(match)
    db.flush()

    shortlist_item = PropertyShortlistItem(
        id=uuid.uuid4(),
        shortlist_id=shortlist.id,
        property_match_id=match.id,
        position=1,
        shortlist_status="ACCEPTED",
    )
    db.add(shortlist_item)

    now = datetime.now(dt_timezone.utc)
    saturday_start = now + timedelta(days=2)  # In 2 days
    saturday_end = saturday_start + timedelta(minutes=45)

    viewing = Viewing(
        id=uuid.uuid4(),
        lead_id=lead.id,
        shortlist_id=shortlist.id,
        shortlist_item_id=shortlist_item.id,
        property_match_id=match.id,
        property_id=prop.id,
        listing_id=listing.id,
        property_agent_id=listing_agent.id,
        status=ViewingStatus.CONFIRMED,
        scheduled_start_at=saturday_start,
        scheduled_end_at=saturday_end,
        timezone="Asia/Singapore",
        duration_minutes=45,
        tenant_confirmation_status=ViewingConfirmationStatus.CONFIRMED,
        agent_confirmation_status=ViewingConfirmationStatus.CONFIRMED,
        schedule_version=1,
    )
    db.add(viewing)

    slot = ViewingSlot(
        id=uuid.uuid4(),
        viewing_id=viewing.id,
        source=ViewingSlotSource.PROPERTY_AGENT,
        start_at=saturday_start,
        end_at=saturday_end,
        timezone="Asia/Singapore",
        status=ViewingSlotStatus.BOOKED,
        is_mutual_match=True,
    )
    db.add(slot)
    db.commit()

    return {
        "lead": lead,
        "prop": prop,
        "listing": listing,
        "listing_agent": listing_agent,
        "viewing": viewing,
        "slot": slot,
        "match": match,
        "wa_profile": wa_profile,
    }


# 51. Normal reminder creation and dispatch when due
def test_normal_reminder(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_msg.provider_message_id = "meta_msg_123"
    mock_wa.send_message.return_value = mock_msg

    # Config with 24h and 2h offsets
    cfg = ViewingReminderConfig(reminder_offsets_minutes=[1440, 120])
    service = ViewingReminderService(db, mock_wa, cfg)

    reminders = service.schedule_reminders_for_viewing(viewing.id)
    assert len(reminders) == 4  # 2 offsets * 2 parties (tenant + agent)

    tenant_24h = [r for r in reminders if r.party == ViewingReminderParty.TENANT and r.offset_minutes == 1440][0]
    assert tenant_24h.status == ViewingReminderStatus.PENDING
    assert tenant_24h.booking_version == 1

    # Simulate reminder being due
    sent_reminder = service.send_reminder(tenant_24h.id)
    assert sent_reminder.status == ViewingReminderStatus.SENT
    assert sent_reminder.sent_at is not None
    assert mock_wa.send_message.called


# 52. Duplicate reminder worker (idempotency key prevents duplicate sends)
def test_duplicate_reminder_worker(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    cfg = ViewingReminderConfig(reminder_offsets_minutes=[120])
    service = ViewingReminderService(db, mock_wa, cfg)

    reminders = service.schedule_reminders_for_viewing(viewing.id)
    reminder = reminders[0]

    # First send
    r1 = service.send_reminder(reminder.id)
    assert r1.status == ViewingReminderStatus.SENT
    assert mock_wa.send_message.call_count == 1

    # Second send attempt on same reminder
    r2 = service.send_reminder(reminder.id)
    assert r2.status == ViewingReminderStatus.SENT
    # Mock should NOT have been called a second time
    assert mock_wa.send_message.call_count == 1


# 53. Viewing cancelled before reminder time -> reminder skipped
def test_cancel_before_reminder(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    service = ViewingReminderService(db, mock_wa)

    reminders = service.schedule_reminders_for_viewing(viewing.id)
    reminder = reminders[0]

    # Cancel viewing before reminder fires
    viewing.status = ViewingStatus.CANCELLED
    db.commit()

    # Pre-send validation must fail and mark reminder SKIPPED
    res = service.send_reminder(reminder.id)
    assert res.status == ViewingReminderStatus.SKIPPED
    assert "no longer CONFIRMED" in res.error_message
    assert mock_wa.send_message.call_count == 0


# 54. Reschedule before reminder -> old reminder skipped/cancelled
def test_reschedule_before_reminder(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reminder_svc = ViewingReminderService(db, mock_wa)
    reschedule_svc = ViewingRescheduleService(db, mock_wa)

    reminders = reminder_svc.schedule_reminders_for_viewing(viewing.id)
    old_reminder = reminders[0]
    assert old_reminder.booking_version == 1

    # Initiate reschedule
    reschedule_svc.request_reschedule(
        viewing_id=viewing.id,
        requested_by="TENANT",
        reason="Need to change date",
    )

    db.refresh(old_reminder)
    assert old_reminder.status == ViewingReminderStatus.CANCELLED

    # If old reminder worker runs anyway, pre-send revalidation prevents dispatch
    res = reminder_svc.send_reminder(old_reminder.id)
    assert res.status in [ViewingReminderStatus.CANCELLED, ViewingReminderStatus.SKIPPED]
    assert mock_wa.send_message.call_count == 0


# 55. Reschedule success: Sat 3pm -> Sun 11am; version incremented, history preserved
def test_reschedule_success(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    reschedule_svc = ViewingRescheduleService(db, mock_wa)

    old_start = viewing.scheduled_start_at
    old_version = viewing.schedule_version
    assert old_version == 1

    # Tenant requests reschedule
    rescheduled = reschedule_svc.request_reschedule(
        viewing_id=viewing.id,
        requested_by="TENANT",
        reason="Can we do Sunday instead?",
    )

    assert rescheduled.status in [
        ViewingStatus.RESCHEDULE_REQUESTED,
        ViewingStatus.AWAITING_AGENT_AVAILABILITY,
        ViewingStatus.AWAITING_TENANT_AVAILABILITY,
    ]
    assert rescheduled.schedule_version == 2
    assert rescheduled.reschedule_count == 1
    assert rescheduled.previous_scheduled_start_at == old_start

    # Verify history snapshot was saved
    history = reschedule_svc.get_schedule_history(viewing.id)
    assert len(history) == 1
    assert history[0].version == 1
    assert history[0].changed_by == "TENANT"
    assert "Sunday" in history[0].reason

    # Now agent provides new slot (Sunday 11am) and finalizes booking
    sunday_start = old_start + timedelta(days=1)
    new_slot = ViewingSlot(
        id=uuid.uuid4(),
        viewing_id=viewing.id,
        source=ViewingSlotSource.PROPERTY_AGENT,
        start_at=sunday_start,
        end_at=sunday_start + timedelta(minutes=45),
        timezone="Asia/Singapore",
        status=ViewingSlotStatus.PROPOSED,
    )
    db.add(new_slot)
    viewing.tenant_confirmation_status = ViewingConfirmationStatus.CONFIRMED
    viewing.agent_confirmation_status = ViewingConfirmationStatus.CONFIRMED
    viewing.status = ViewingStatus.SLOT_PROPOSED
    db.commit()

    conf_svc = ViewingConfirmationService(db, mock_wa)
    booking_res = conf_svc.finalize_booking(viewing.id)

    db.refresh(viewing)
    assert viewing.status == ViewingStatus.CONFIRMED
    assert viewing.scheduled_start_at == sunday_start
    assert viewing.schedule_version == 2

    # Verify new reminders created for version 2
    reminder_svc = ViewingReminderService(db, mock_wa)
    v2_reminders = (
        db.query(ViewingReminder)
        .filter(ViewingReminder.viewing_id == viewing.id, ViewingReminder.booking_version == 2)
        .all()
    )
    assert len(v2_reminders) > 0


# 56. Agent-requested reschedule: captured, requires tenant confirmation
def test_agent_reschedule(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reschedule_svc = ViewingRescheduleService(db, mock_wa)

    new_time = viewing.scheduled_start_at + timedelta(hours=2)

    # Agent requests reschedule
    rescheduled = reschedule_svc.request_reschedule(
        viewing_id=viewing.id,
        requested_by="PROPERTY_AGENT",
        reason="3pm no longer works. 5pm does.",
        candidate_slot_start=new_time,
        candidate_slot_end=new_time + timedelta(minutes=45),
    )

    db.refresh(viewing)
    # Viewing must NOT be automatically CONFIRMED; must be SLOTS_AVAILABLE or RESCHEDULE_REQUESTED
    assert viewing.status != ViewingStatus.CONFIRMED
    assert viewing.schedule_version == 2

    history = reschedule_svc.get_schedule_history(viewing.id)
    assert len(history) == 1
    assert history[0].changed_by == "PROPERTY_AGENT"


# 57. Tenant cancellation: CANCELLED, reminders cancelled, agent notified
def test_tenant_cancel(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    reminder_svc = ViewingReminderService(db, mock_wa)
    reminder_svc.schedule_reminders_for_viewing(viewing.id)

    cancel_svc = ViewingCancellationService(db, mock_wa)
    cancelled = cancel_svc.cancel_viewing(
        viewing_id=viewing.id,
        cancelling_party="TENANT",
        reason_code="TENANT_REQUEST",
        reason_text="I want to cancel the viewing.",
    )

    assert cancelled.status == ViewingStatus.CANCELLED
    assert cancelled.cancelled_by == "TENANT"

    # Pending reminders must be cancelled
    pending_reminders = (
        db.query(ViewingReminder)
        .filter(
            ViewingReminder.viewing_id == viewing.id,
            ViewingReminder.status == ViewingReminderStatus.PENDING,
        )
        .all()
    )
    assert len(pending_reminders) == 0

    # WhatsApp notifications sent to agent and tenant
    assert mock_wa.send_message.called


# 58. Agent cancellation: CANCELLED, reminders cancelled, tenant notified
def test_agent_cancel(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    cancel_svc = ViewingCancellationService(db, mock_wa)
    cancelled = cancel_svc.cancel_viewing(
        viewing_id=viewing.id,
        cancelling_party="PROPERTY_AGENT",
        reason_code="AGENT_REQUEST",
        reason_text="Owner cancelled the viewing.",
    )

    assert cancelled.status == ViewingStatus.CANCELLED
    assert cancelled.cancelled_by == "PROPERTY_AGENT"
    assert "AGENT_REQUEST" in cancelled.cancellation_reason
    assert mock_wa.send_message.called


# 59. Property unavailable: controlled system cancellation, both notified
def test_property_unavailable(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    cancel_svc = ViewingCancellationService(db, mock_wa)
    cancelled = cancel_svc.cancel_viewing(
        viewing_id=viewing.id,
        cancelling_party="SYSTEM",
        reason_code="PROPERTY_UNAVAILABLE",
        reason_text="Property no longer available",
    )

    assert cancelled.status == ViewingStatus.CANCELLED
    assert cancelled.cancelled_by == "SYSTEM"
    assert cancelled.cancellation_reason.startswith("PROPERTY_UNAVAILABLE")
    # Both tenant and agent notified
    assert mock_wa.send_message.call_count >= 2


# 60. Duplicate cancellation idempotency
def test_duplicate_cancel(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = uuid.uuid4()
    mock_wa.send_message.return_value = mock_msg

    cancel_svc = ViewingCancellationService(db, mock_wa)
    # First cancellation
    c1 = cancel_svc.cancel_viewing(
        viewing_id=viewing.id,
        cancelling_party="TENANT",
        reason_code="TENANT_REQUEST",
    )
    first_call_count = mock_wa.send_message.call_count

    # Second cancellation call
    c2 = cancel_svc.cancel_viewing(
        viewing_id=viewing.id,
        cancelling_party="TENANT",
        reason_code="TENANT_REQUEST",
    )
    assert c1.status == ViewingStatus.CANCELLED
    assert c2.status == ViewingStatus.CANCELLED
    # No duplicate notifications
    assert mock_wa.send_message.call_count == first_call_count


# 61. Duplicate reschedule request idempotency
def test_duplicate_reschedule_request(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reschedule_svc = ViewingRescheduleService(db, mock_wa)

    r1 = reschedule_svc.request_reschedule(
        viewing_id=viewing.id,
        requested_by="TENANT",
        reason="Change to Sunday",
    )
    v_num = r1.schedule_version

    # Repeated identical request
    r2 = reschedule_svc.request_reschedule(
        viewing_id=viewing.id,
        requested_by="TENANT",
        reason="Change to Sunday",
    )
    # Version should not increment twice for the same unconfirmed request
    assert r2.schedule_version == v_num


# 62. Multiple viewings: tenant with two confirmed viewings
@pytest.mark.asyncio
async def test_multiple_viewings_correlation(db, phase6_fixtures):
    lead = phase6_fixtures["lead"]
    v1 = phase6_fixtures["viewing"]
    mock_wa = MagicMock()

    # Create second confirmed viewing on another day for different property
    prop2 = Property(
        id=uuid.uuid4(),
        canonical_name="Newton Edge",
        property_type=PropertyType.CONDO,
        address_line_1="2 Newton Road",
        postal_code="307999",
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop2)
    db.flush()

    listing2 = PropertyListing(
        id=uuid.uuid4(),
        property_id=prop2.id,
        source_id=phase6_fixtures["listing"].source_id,
        agent_id=phase6_fixtures["listing_agent"].id,
        source_listing_id="REF-NEW-202",
        listing_reference="REF-NEW-202",
        asking_price=Decimal("5000.00"),
        listing_status=PropertyListingStatus.ACTIVE,
        availability_status=ListingAvailabilityStatus.AVAILABLE,
    )
    db.add(listing2)
    db.flush()

    match2 = PropertyMatch(
        id=uuid.uuid4(),
        lead_id=lead.id,
        property_id=prop2.id,
        listing_id=listing2.id,
        match_status=PropertyMatchStatus.AVAILABLE.value,
        availability_status="AVAILABLE",
    )
    db.add(match2)
    db.flush()

    sunday_start = v1.scheduled_start_at + timedelta(days=1)
    v2 = Viewing(
        id=uuid.uuid4(),
        lead_id=lead.id,
        property_match_id=match2.id,
        property_id=prop2.id,
        listing_id=listing2.id,
        property_agent_id=phase6_fixtures["listing_agent"].id,
        status=ViewingStatus.CONFIRMED,
        scheduled_start_at=sunday_start,
        scheduled_end_at=sunday_start + timedelta(minutes=30),
        schedule_version=1,
    )
    db.add(v2)
    db.commit()

    op_service = ViewingOperationUnderstandingService(db, wa_service=mock_wa)

    # Inbound message mentions "Novena" specifically
    v_match, needs_clar, _ = op_service.correlate_viewing_for_tenant(
        lead_id=lead.id,
        message_text="Can we cancel the Novena viewing?",
    )
    assert not needs_clar
    assert v_match.id == v1.id

    # Inbound message is ambiguous ("Cancel it")
    v_ambiguous, needs_clar2, question = op_service.correlate_viewing_for_tenant(
        lead_id=lead.id,
        message_text="Cancel it",
    )
    assert needs_clar2
    assert v_ambiguous is None
    assert "multiple upcoming viewings" in question


# 63. Reminder send failure & bounded retry
def test_reminder_send_failure_bounded_retry(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    mock_wa.send_message.side_effect = Exception("Meta API 500 Network Timeout")

    cfg = ViewingReminderConfig(reminder_offsets_minutes=[120], max_reminder_attempts=2)
    service = ViewingReminderService(db, mock_wa, cfg)

    reminders = service.schedule_reminders_for_viewing(viewing.id)
    reminder = reminders[0]

    # Attempt 1 fails: remains PENDING for retry
    r1 = service.send_reminder(reminder.id)
    assert r1.status == ViewingReminderStatus.PENDING
    assert r1.attempt_count == 1
    # Viewing status must NOT change
    db.refresh(viewing)
    assert viewing.status == ViewingStatus.CONFIRMED

    # Attempt 2 fails: exhausts max_attempts (2) -> FAILED
    r2 = service.send_reminder(reminder.id)
    assert r2.status == ViewingReminderStatus.FAILED
    assert r2.attempt_count == 2
    assert "Exhausted max attempts" in r2.error_message
    assert viewing.status == ViewingStatus.CONFIRMED


# 64. Race condition handling: cancellation committed before reminder worker runs
def test_race_condition_reminder_cancellation(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reminder_svc = ViewingReminderService(db, mock_wa)
    cancel_svc = ViewingCancellationService(db, mock_wa)

    reminders = reminder_svc.schedule_reminders_for_viewing(viewing.id)
    reminder = reminders[0]

    # Concurrent thread commits cancellation
    cancel_svc.cancel_viewing(viewing.id, cancelling_party="TENANT")
    calls_after_cancel = mock_wa.send_message.call_count

    # Worker executes pre-send validation
    r = reminder_svc.send_reminder(reminder.id)
    assert r.status in [ViewingReminderStatus.SKIPPED, ViewingReminderStatus.CANCELLED]
    assert mock_wa.send_message.call_count == calls_after_cancel


# 65. Stale schedule version check
def test_stale_schedule_version(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reminder_svc = ViewingReminderService(db, mock_wa)

    reminders = reminder_svc.schedule_reminders_for_viewing(viewing.id)
    v1_reminder = reminders[0]
    assert v1_reminder.booking_version == 1

    # Simulate schedule version bump
    viewing.schedule_version = 2
    db.commit()

    # Pre-send validation must detect stale schedule version
    res = reminder_svc.send_reminder(v1_reminder.id)
    assert res.status == ViewingReminderStatus.SKIPPED
    assert "Stale schedule version" in res.error_message


# 66. Unauthorized / invalid reschedule entry conditions
def test_unauthorized_reschedule(db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]
    mock_wa = MagicMock()
    reschedule_svc = ViewingRescheduleService(db, mock_wa)

    # Complete viewing
    viewing.status = ViewingStatus.COMPLETED
    db.commit()

    with pytest.raises(ValueError, match="Viewing must be CONFIRMED"):
        reschedule_svc.request_reschedule(viewing.id, requested_by="TENANT")


# 67. REST API Endpoints: Reminders, Rebuild, Reschedule, Cancel, Schedule-History
def test_security_and_rest_apis(client, db, phase6_fixtures):
    viewing = phase6_fixtures["viewing"]

    # 1. Schedule initial reminders
    service = ViewingReminderService(db)
    service.schedule_reminders_for_viewing(viewing.id)

    # 2. GET /reminders
    res_reminders = client.get(f"/api/viewings/{viewing.id}/reminders")
    assert res_reminders.status_code == 200
    reminders_data = res_reminders.json()
    assert len(reminders_data) > 0

    # 3. POST /reminders/rebuild
    res_rebuild = client.post(f"/api/viewings/{viewing.id}/reminders/rebuild")
    assert res_rebuild.status_code == 200
    rebuilt_data = res_rebuild.json()
    assert len(rebuilt_data) > 0

    # 4. POST /reschedule
    res_reschedule = client.post(
        f"/api/viewings/{viewing.id}/reschedule",
        json={"requested_by": "TENANT", "reason": "Moving to next week"},
    )
    assert res_reschedule.status_code == 200
    resched_data = res_reschedule.json()
    assert resched_data["schedule_version"] == 2

    # 5. GET /schedule-history
    res_history = client.get(f"/api/viewings/{viewing.id}/schedule-history")
    assert res_history.status_code == 200
    hist_data = res_history.json()
    assert len(hist_data) == 1
    assert hist_data[0]["version"] == 1
    assert hist_data[0]["changed_by"] == "TENANT"

    # 6. POST /cancel
    res_cancel = client.post(
        f"/api/viewings/{viewing.id}/cancel",
        json={"reason_code": "SCHEDULING_CONFLICT", "reason": "Tenant conflict"},
    )
    assert res_cancel.status_code == 200
    cancel_data = res_cancel.json()
    assert cancel_data["status"] == "CANCELLED"
