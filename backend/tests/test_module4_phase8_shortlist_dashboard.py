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
from app.models.property_matching_run import PropertyMatchingRun
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_followup import PropertyAgentFollowUp
from app.models.property_availability_verification import PropertyAvailabilityVerification
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
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
    PropertyShortlistStatus,
    ShortlistItemStatus,
    ShortlistReasonCode,
    AvailabilityVerificationStatus,
    AvailabilityVerificationSource,
)
from app.services.shortlist_config import ShortlistConfig
from app.services.property_shortlist_service import PropertyShortlistService


@pytest.fixture
def setup_lead_and_agent(db: Session):
    plat_agent = Agent(
        full_name="Platform Agent P8",
        agency_name="Platform Agency",
        email=f"p8_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(plat_agent)
    db.commit()

    profile = WhatsAppProfile(
        agent_id=plat_agent.id,
        phone_number_id=f"pn_{uuid.uuid4().hex[:8]}",
        display_phone_number="+6590008888",
    )
    db.add(profile)
    db.commit()

    lead = Lead(
        phone="+6588880008",
        phone_normalized="+6588880008",
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

    source = PropertySource(
        name="Source P8",
        source_type=PropertySourceType.CSV_IMPORT,
        status=PropertySourceStatus.ACTIVE,
    )
    db.add(source)
    db.commit()

    ext_agent = PropertyAgent(
        full_name="Agent Tan P8",
        agency_name="ERA P8",
        phone="+6591112222",
        status=PropertyAgentStatus.ACTIVE,
    )
    db.add(ext_agent)
    db.commit()


    matching_run = PropertyMatchingRun(
        lead_id=lead.id,
        config_version="1.0.0",
    )
    db.add(matching_run)
    db.commit()

    return {
        "lead": lead,
        "req": req,
        "source": source,
        "ext_agent": ext_agent,
        "matching_run": matching_run,
    }


def create_candidate(
    db: Session,
    lead_id: uuid.UUID,
    matching_run_id: uuid.UUID,
    source_id: uuid.UUID,
    ext_agent_id: uuid.UUID,
    name: str,
    price: Decimal,
    avail_status: str = "AVAILABLE",
    verif_status: str = "CONFIRMED",
    score: Decimal = Decimal("90.0"),
    rank: int = 1,
    available_from: date = date(2026, 12, 1),
    is_stale: bool = False,
    listing_status: str = "ACTIVE",
    prop_status: str = "ACTIVE",
    hard_filter_passed: bool = True,
):
    prop = Property(
        canonical_name=name,
        building_name=name,
        address_line_1=f"123 {name} Road",
        address_normalized=f"123 {name} Road, Singapore",
        district="Novena",
        property_type="CONDO",
        bedrooms=2,
        bathrooms=2,
        status=prop_status,
    )
    db.add(prop)
    db.commit()


    listing = PropertyListing(
        property_id=prop.id,
        source_id=source_id,
        agent_id=ext_agent_id,
        asking_price=price,
        currency="SGD",
        available_from=available_from,
        lease_min_months=12,
        listing_status=listing_status,
        availability_status=avail_status,
    )
    db.add(listing)
    db.commit()


    match = PropertyMatch(
        lead_id=lead_id,
        property_id=prop.id,
        listing_id=listing.id,
        matching_run_id=matching_run_id,
        match_status=PropertyMatchStatus.AVAILABLE.value if avail_status == "AVAILABLE" else PropertyMatchStatus.CANDIDATE.value,
        hard_filter_passed=hard_filter_passed,
        match_score=score,
        rank=rank,
        is_stale=is_stale,
        agent_verification_status=verif_status,
        availability_status=avail_status,
    )
    db.add(match)
    db.commit()

    if verif_status == "CONFIRMED":
        verif = PropertyAvailabilityVerification(
            property_match_id=match.id,
            listing_id=listing.id,
            property_agent_id=ext_agent_id,
            verification_status=AvailabilityVerificationStatus.CONFIRMED.value,
            availability_status=avail_status,
            verification_source=AvailabilityVerificationSource.AGENT_REPLY.value,
            asking_price=price,
            available_from=available_from,
            minimum_lease_months=12,
        )
        db.add(verif)
        db.commit()


    return match


# 1. Test Verified Candidate
def test_verified_candidate_readiness(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Novena Suites #08-01", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("94.0"), rank=1
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.VERIFIED_CANDIDATE.value
    assert res.eligible is True
    assert ShortlistReasonCode.AGENT_CONFIRMED_AVAILABLE.value in res.reasons
    assert ShortlistReasonCode.PRICE_WITHIN_BUDGET.value in res.reasons
    assert ShortlistReasonCode.LEASE_COMPATIBLE.value in res.reasons


# 2. Test High Score but Unverified
def test_high_score_unverified(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Newton Grand #10-02", price=Decimal("3800"), avail_status="UNKNOWN", verif_status="NOT_CHECKED", score=Decimal("98.0"), rank=1
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.PENDING_VERIFICATION.value
    assert ShortlistReasonCode.AGENT_NOT_VERIFIED.value in res.reasons


# 3. Test Available but Price Too High
def test_available_but_price_too_high(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Orchard Luxury #12-05", price=Decimal("4600"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("95.0"), rank=1
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value
    assert res.eligible is False
    assert ShortlistReasonCode.PRICE_ABOVE_LIMIT.value in res.reasons


# 4. Test Conditional Candidate (Move-in Date Slightly Late)
def test_conditional_candidate_move_in(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Move-in preferred Dec 1, available Dec 10 (9 days late -> <= 14 days conditional)
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Novena Regency #04-03", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("88.0"), rank=1, available_from=date(2026, 12, 10)
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.CONDITIONAL_CANDIDATE.value
    assert ShortlistReasonCode.AVAILABILITY_DATE_SLIGHTLY_LATE.value in res.warnings


# 5. Test Unavailable Candidate
def test_unavailable_candidate(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Marina Bay #20-01", price=Decimal("3800"), avail_status="UNAVAILABLE", verif_status="REJECTED", score=Decimal("92.0"), rank=1
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value
    assert res.eligible is False
    assert ShortlistReasonCode.LISTING_UNAVAILABLE.value in res.reasons


# 6. Test Stale Score Candidate
def test_stale_score_candidate(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Balestier Point #05-02", price=Decimal("3700"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("91.0"), rank=1, is_stale=True
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.requires_score_refresh is True
    assert ShortlistReasonCode.SCORE_STALE.value in res.reasons


# 7. Test Inactive Listing Candidate
def test_inactive_listing_candidate(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    match = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Thomson V #02-01", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("89.0"), rank=1, listing_status="INACTIVE"
    )
    res = PropertyShortlistService.evaluate_candidate_readiness(match, data["req"])
    assert res.shortlist_status == ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value
    assert ShortlistReasonCode.LISTING_INACTIVE.value in res.reasons


# 8. Test Max Shortlist Size Top-N
def test_max_shortlist_size(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Create 8 verified candidates
    for i in range(8):
        create_candidate(
            db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
            name=f"Condo {i+1}", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED",
            score=Decimal(str(80 + i)), rank=i+1
        )
    config = ShortlistConfig(max_shortlist_size=5)
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id, config=config)
    assert len(shortlist.items) == 5
    # Highest score (87.0) should be position 1
    assert shortlist.items[0].score_at_selection == Decimal("87.0")
    assert shortlist.items[0].position == 1


# 9. Test Conditional Sorting Preference
def test_conditional_sorting_preference(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Verified candidate score 85.0
    m_verif = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Verified Lower Score", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("85.0"), rank=2
    )
    # Conditional candidate score 95.0 (late move-in)
    m_cond = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Conditional Higher Score", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("95.0"), rank=1, available_from=date(2026, 12, 10)
    )
    config = ShortlistConfig(prefer_verified_over_conditional=True)
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id, config=config)
    assert len(shortlist.items) == 2
    # Verified should be position 1 despite lower score
    assert shortlist.items[0].property_match_id == m_verif.id
    assert shortlist.items[1].property_match_id == m_cond.id


# 10. Test Manual Add Candidate
def test_manual_add_candidate(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Auto Candidate 1", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("90.0")
    )
    m2 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Manual Add Candidate", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("85.0")
    )
    config = ShortlistConfig(max_shortlist_size=1)
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id, config=config)
    assert len(shortlist.items) == 1

    item = PropertyShortlistService.add_item_to_shortlist(
        db, shortlist.id, m2.id, user_email="operator@agency.com", manual_override_reason="Client requested this unit"
    )
    assert item.position == 2
    assert item.manual_override is True
    assert item.manual_override_reason == "Client requested this unit"


# 11. Test Unsafe Manual Add Blocked
def test_unsafe_manual_add_blocked(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m_unavail = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Unavailable Unit", price=Decimal("3800"), avail_status="UNAVAILABLE", verif_status="REJECTED", score=Decimal("85.0")
    )
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    with pytest.raises(ValueError, match="Cannot shortlist an UNAVAILABLE property candidate"):
        PropertyShortlistService.add_item_to_shortlist(db, shortlist.id, m_unavail.id)


# 12. Test Reorder Shortlist Items
def test_reorder_shortlist_items(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Unit A", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("95.0"), rank=1
    )
    m2 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Unit B", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("90.0"), rank=2
    )
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    assert shortlist.items[0].property_match_id == m1.id
    assert shortlist.items[1].property_match_id == m2.id

    # Reorder m2 to pos 1, m1 to pos 2
    updated = PropertyShortlistService.reorder_shortlist_items(db, shortlist.id, [m2.id, m1.id])
    assert updated.items[0].property_match_id == m2.id
    assert updated.items[0].position == 1
    assert updated.items[1].property_match_id == m1.id
    assert updated.items[1].position == 2
    # System rank on match itself is preserved
    db.refresh(m1)
    db.refresh(m2)
    assert m1.rank == 1
    assert m2.rank == 2


# 13. Test Tenant Requirement Change Marks Stale
def test_tenant_requirement_change_marks_stale(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Unit A", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("90.0")
    )
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    assert shortlist.status == PropertyShortlistStatus.READY.value

    # Tenant changes requirement budget to 3500 (below 3900)
    data["req"].budget_max = Decimal("3500")
    db.commit()

    refreshed = PropertyShortlistService.refresh_shortlist(db, data["lead"].id)
    assert refreshed.status == PropertyShortlistStatus.STALE.value


# 14. Test Late Agent Response Handling
def test_late_agent_response_handling(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Candidate starts pending
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Late Unit", price=Decimal("3800"), avail_status="UNKNOWN", verif_status="NOT_CHECKED", score=Decimal("92.0")
    )
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    # Pending is not in verified shortlist
    assert len(shortlist.items) == 0

    # Late response arrives and confirms AVAILABLE
    m1.agent_verification_status = AvailabilityVerificationStatus.CONFIRMED.value
    m1.availability_status = ListingAvailabilityStatus.AVAILABLE.value
    m1.listing.availability_status = ListingAvailabilityStatus.AVAILABLE.value
    db.commit()

    # Re-build shortlist picks up verified candidate
    updated = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    assert len(updated.items) == 1
    assert updated.items[0].property_match_id == m1.id
    assert updated.status == PropertyShortlistStatus.READY.value


# 15. Test Dashboard Summary Counts
def test_dashboard_summary_counts(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # 1 verified, 1 conditional, 1 awaiting, 1 unavailable
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Verified 1", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("94.0")
    )
    m2 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Conditional 1", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("88.0"), available_from=date(2026, 12, 10)
    )
    m3 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Awaiting 1", price=Decimal("3800"), avail_status="UNKNOWN", verif_status="NOT_CHECKED", score=Decimal("85.0")
    )
    m4 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Unavailable 1", price=Decimal("3800"), avail_status="UNAVAILABLE", verif_status="REJECTED", score=Decimal("80.0")
    )
    PropertyShortlistService.build_shortlist(db, data["lead"].id)
    dash = PropertyShortlistService.get_lead_matching_dashboard(db, data["lead"].id)
    assert dash.summary.total_candidates == 4
    assert dash.summary.verified_available == 1
    assert dash.summary.conditional == 1
    assert dash.summary.unavailable == 1
    assert dash.summary.shortlisted == 2


# 16. Test Module 5 Handoff Contract
def test_module5_handoff_contract(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Handoff Unit 1", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("95.0")
    )
    PropertyShortlistService.build_shortlist(db, data["lead"].id)
    handoff = PropertyShortlistService.generate_module5_handoff(db, data["lead"].id)
    assert handoff.lead_id == data["lead"].id
    assert handoff.handoff_status == "READY_FOR_VIEWING_COORDINATION"
    assert len(handoff.properties) == 1
    p = handoff.properties[0]
    assert p.property_match_id == m1.id
    assert p.asking_price == Decimal("3900")
    assert p.currency == "SGD"
    assert p.availability == "AVAILABLE"
    assert p.shortlist_position == 1


# 17. Test API Endpoints
def test_property_shortlist_apis(client: TestClient, db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    m1 = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="API Unit 1", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("93.0")
    )
    # 1. Build Shortlist API
    res = client.post(f"/api/leads/{data['lead'].id}/property-shortlist/build")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["status"] == "READY"
    assert len(json_data["items"]) == 1

    # 2. Get Dashboard API
    dash_res = client.get(f"/api/leads/{data['lead'].id}/property-matching/dashboard")
    assert dash_res.status_code == 200
    dash_json = dash_res.json()
    assert dash_json["module5_ready"] is True
    assert dash_json["summary"]["shortlisted"] == 1

    # 3. Module 5 Handoff API
    ho_res = client.get(f"/api/leads/{data['lead'].id}/property-shortlist/module5-handoff")
    assert ho_res.status_code == 200
    ho_json = ho_res.json()
    assert ho_json["handoff_status"] == "READY_FOR_VIEWING_COORDINATION"


# 18. Test Full Phase 8 Acceptance Flow
def test_phase8_full_acceptance_flow(db: Session, setup_lead_and_agent):
    data = setup_lead_and_agent
    # Candidate A: 94 score, AVAILABLE, 3900 -> VERIFIED
    mA = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Novena Suites #08-01", price=Decimal("3900"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("94.0"), rank=1
    )
    # Candidate B: 91 score, AVAILABLE, 3800 -> VERIFIED
    mB = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Newton Residence #05-02", price=Decimal("3800"), avail_status="AVAILABLE", verif_status="CONFIRMED", score=Decimal("91.0"), rank=2
    )
    # Candidate C: 88 score, AVAILABLE Dec 10 -> CONDITIONAL
    mC = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Novena Regency #04-03", price=Decimal("3850"), avail_status="AVAILABLE", verif_status="CONFIRMED",
        score=Decimal("88.0"), rank=3, available_from=date(2026, 12, 10)
    )
    # Candidate D: 86 score, UNAVAILABLE -> NOT_SHORTLIST_ELIGIBLE
    mD = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Newton Suites #02-01", price=Decimal("3700"), avail_status="UNAVAILABLE", verif_status="REJECTED", score=Decimal("86.0"), rank=4
    )
    # Candidate E: 83 score, AWAITING AGENT -> PENDING_VERIFICATION
    mE = create_candidate(
        db, data["lead"].id, data["matching_run"].id, data["source"].id, data["ext_agent"].id,
        name="Balestier Plaza #11-04", price=Decimal("3600"), avail_status="UNKNOWN", verif_status="NOT_CHECKED", score=Decimal("83.0"), rank=5
    )

    # Build shortlist
    shortlist = PropertyShortlistService.build_shortlist(db, data["lead"].id)
    assert shortlist.status == PropertyShortlistStatus.READY.value
    assert len(shortlist.items) == 3

    # Shortlist items order
    assert shortlist.items[0].property_match_id == mA.id
    assert shortlist.items[0].shortlist_status == ShortlistItemStatus.VERIFIED_CANDIDATE.value

    assert shortlist.items[1].property_match_id == mB.id
    assert shortlist.items[1].shortlist_status == ShortlistItemStatus.VERIFIED_CANDIDATE.value

    assert shortlist.items[2].property_match_id == mC.id
    assert shortlist.items[2].shortlist_status == ShortlistItemStatus.CONDITIONAL_CANDIDATE.value

    # Check dashboard
    dash = PropertyShortlistService.get_lead_matching_dashboard(db, data["lead"].id)
    assert dash.module5_ready is True
    assert dash.summary.verified_available == 2
    assert dash.summary.conditional == 1
    assert dash.summary.unavailable == 1
    assert dash.summary.shortlisted == 3

    # Handoff to Module 5
    handoff = PropertyShortlistService.generate_module5_handoff(db, data["lead"].id)
    assert handoff.handoff_status == "READY_FOR_VIEWING_COORDINATION"
    assert len(handoff.properties) == 3
