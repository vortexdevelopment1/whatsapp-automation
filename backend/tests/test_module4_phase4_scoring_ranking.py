import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import pytest
from fastapi.testclient import TestClient

from app.models.enums import (
    LeadStatus,
    QualificationStatus,
    PropertyType,
    FurnishingType,
    PropertyStatus,
    PropertyListingStatus,
    PropertySourceType,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    ScoringReasonCode,
)


@pytest.fixture
def qualified_tenant_setup(client: TestClient) -> Dict[str, Any]:
    # 1. Create Lead with unique valid Singapore phone
    unique_phone = f"+6591{uuid.uuid4().int % 1000000:06d}"
    lead_res = client.post(
        "/api/leads",
        json={
            "full_name": "Phase 4 Tenant Scoring Test",
            "phone": unique_phone,
            "email": f"tenant_{uuid.uuid4().hex[:6]}@example.com",
        },
        headers={"X-User-Role": "operator"},
    )
    assert lead_res.status_code == 201, lead_res.text
    lead_id = lead_res.json()["id"]

    # 2. Set Lead Requirements
    req_payload = {
        "preferred_locations": ["Novena", "Newton"],
        "budget_min": 3000,
        "budget_max": 4000,
        "currency": "SGD",
        "property_type": "CONDO",
        "bedrooms": 2,
        "move_in_date": "2026-12-01",
        "lease_duration_months": 12,
        "furnishing": "FURNISHED",
    }
    req_res = client.post(
        f"/api/leads/{lead_id}/requirements",
        json=req_payload,
        headers={"X-User-Role": "operator"},
    )
    assert req_res.status_code == 201, req_res.text

    # 3. Qualify the Lead in Module 3
    dec_res = client.post(
        f"/api/leads/{lead_id}/qualification/evaluate",
        json={
            "apply": True,
            "override_decision": "QUALIFIED",
            "override_reason": "Operator verified requirements for Phase 4 scoring",
        },
        headers={"X-User-Role": "operator"},
    )
    assert dec_res.status_code == 200, dec_res.text

    # 4. Create Active Source
    source_res = client.post(
        "/api/property-sources",
        json={
            "name": "Phase 4 Source Feed",
            "source_type": "APPROVED_API",
            "external_system_name": f"P4_SRC_{uuid.uuid4().hex[:6]}",
            "status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    assert source_res.status_code == 201
    source_id = source_res.json()["id"]

    return {
        "lead_id": lead_id,
        "source_id": source_id,
    }


def create_candidate(
    client: TestClient,
    source_id: str,
    property_name: str,
    address_1: str,
    property_type: str = "CONDO",
    bedrooms: int = 2,
    bathrooms: float = 2.0,
    furnishing: str = "FURNISHED",
    asking_price: float = 3800.0,
    currency: str = "SGD",
    available_from: str = "2026-12-01",
    lease_min: int = 12,
    lease_max: int = 24,
    availability_status: str = "AVAILABLE",
) -> Tuple[str, str]:
    # 1. Create Property
    prop_res = client.post(
        "/api/properties",
        json={
            "canonical_name": property_name,
            "building_name": property_name,
            "address_line_1": address_1,
            "unit_number": "#10-01",
            "postal_code": "307683",
            "city": "Singapore",
            "country": "Singapore",
            "property_type": property_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "furnishing": furnishing,
            "status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    assert prop_res.status_code == 201, prop_res.text
    prop_id = prop_res.json()["id"]

    # 2. Create Listing
    list_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={
            "source_id": source_id,
            "source_listing_id": f"LST-{uuid.uuid4().hex[:8]}",
            "asking_price": asking_price,
            "currency": currency,
            "availability_status": availability_status,
            "available_from": available_from,
            "lease_min_months": lease_min,
            "lease_max_months": lease_max,
            "listing_status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    assert list_res.status_code == 201, list_res.text
    listing_id = list_res.json()["id"]

    return prop_id, listing_id


# ==============================================================================
# TESTS
# ==============================================================================

def test_strong_match_high_score(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Listing matches all tenant criteria
    p_id, l_id = create_candidate(
        client,
        source_id,
        "Novena Prime Residences",
        "120 Thomson Road, Novena",
        asking_price=3750,
        availability_status="AVAILABLE",
    )

    # 1. Run Phase 3 Hard Filters
    run_res = client.post(f"/api/leads/{lead_id}/property-matching/run")
    assert run_res.status_code == 200
    assert run_res.json()["eligible_candidates"] >= 1

    # 2. Run Phase 4 Scoring
    score_res = client.post(f"/api/leads/{lead_id}/property-matching/score")
    assert score_res.status_code == 200
    score_data = score_res.json()
    assert score_data["scored"] >= 1
    assert score_data["top_score"] >= 90.0
    assert score_data["ready_for_agent_verification"] >= 1

    # Check match detail
    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=READY_FOR_AGENT_VERIFICATION")
    matches = matches_res.json()
    match = [m for m in matches if m["listing_id"] == l_id][0]
    assert match["rank"] == 1
    assert match["match_score"] >= 90.0
    assert "EXACT_LOCATION_MATCH" in match["score_breakdown"]["reason_codes"]
    assert "STRONG_BUDGET_FIT" in match["score_breakdown"]["reason_codes"]
    assert len(match["score_breakdown"]["positive_factors"]) >= 3


def test_budget_edge_scores(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Candidate 1: 3950 (within budget 4000)
    p1, l1 = create_candidate(client, source_id, "Budget Fit Condo", "150 Thomson Road, Novena", asking_price=3950)

    # Candidate 2: 4150 (above budget 4000, within 5% tolerance 4200)
    p2, l2 = create_candidate(client, source_id, "Tolerance Edge Condo", "152 Thomson Road, Novena", asking_price=4150)

    # Run matching with 5% tolerance
    client.post(
        f"/api/leads/{lead_id}/property-matching/run",
        json={"config": {"budget_tolerance_percent": 5.0}},
    )

    # Score
    client.post(f"/api/leads/{lead_id}/property-matching/score")

    matches = client.get(f"/api/leads/{lead_id}/property-matches?sort_by=score&sort_order=desc").json()
    m1 = [m for m in matches if m["listing_id"] == l1][0]
    m2 = [m for m in matches if m["listing_id"] == l2][0]

    # m1 within budget must have a higher budget raw score than m2 above budget
    assert m1["score_breakdown"]["dimensions"]["budget"]["raw_score"] > m2["score_breakdown"]["dimensions"]["budget"]["raw_score"]
    assert "NEAR_BUDGET_LIMIT" in m2["score_breakdown"]["reason_codes"]
    assert any("near upper budget tolerance" in r for r in m2["score_breakdown"]["risks"])


def test_location_vs_budget_tradeoff(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Candidate A: Exact Location (Novena), higher price (3950)
    pa, la = create_candidate(client, source_id, "Novena High Rent", "10 Novena Road", asking_price=3950)

    # Candidate B: Secondary Location (Newton), much lower price (3100)
    pb, lb = create_candidate(client, source_id, "Newton Low Rent", "50 Newton Road", asking_price=3100)

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    # Score with Location Heavy weights (Location: 50, Budget: 10, other weights adjusted to sum 100)
    cfg_loc = {
        "location_weight": 50.0,
        "budget_weight": 10.0,
        "property_type_weight": 10.0,
        "bedrooms_weight": 10.0,
        "move_in_weight": 8.0,
        "lease_weight": 5.0,
        "furnishing_weight": 4.0,
        "availability_weight": 3.0,
    }
    client.post(f"/api/leads/{lead_id}/property-matching/score", json={"config": cfg_loc})

    matches_loc = client.get(f"/api/leads/{lead_id}/property-matches?sort_by=rank").json()
    cand_a_loc = [m for m in matches_loc if m["listing_id"] == la][0]
    cand_b_loc = [m for m in matches_loc if m["listing_id"] == lb][0]
    # Candidate A ranks ahead of Candidate B under location-heavy weights
    assert cand_a_loc["rank"] < cand_b_loc["rank"]

    # Now re-score with Budget Heavy weights (Location: 10, Budget: 50)
    cfg_budget = {
        "location_weight": 10.0,
        "budget_weight": 50.0,
        "property_type_weight": 10.0,
        "bedrooms_weight": 10.0,
        "move_in_weight": 8.0,
        "lease_weight": 5.0,
        "furnishing_weight": 4.0,
        "availability_weight": 3.0,
    }
    client.post(f"/api/leads/{lead_id}/property-matching/score", json={"config": cfg_budget})

    matches_budget = client.get(f"/api/leads/{lead_id}/property-matches?sort_by=rank").json()
    cand_a_budget = [m for m in matches_budget if m["listing_id"] == la][0]
    cand_b_budget = [m for m in matches_budget if m["listing_id"] == lb][0]
    # Candidate B ranks ahead of Candidate A under budget-heavy weights
    assert cand_b_budget["rank"] < cand_a_budget["rank"]


def test_unknown_availability_shows_risk_warning(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Candidate with UNKNOWN availability
    p_id, l_id = create_candidate(
        client,
        source_id,
        "Novena Unverified Condo",
        "20 Novena Road",
        availability_status="UNKNOWN",
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")
    client.post(f"/api/leads/{lead_id}/property-matching/score")

    matches = client.get(f"/api/leads/{lead_id}/property-matches").json()
    match = [m for m in matches if m["listing_id"] == l_id][0]

    assert "AVAILABILITY_UNVERIFIED" in match["score_breakdown"]["reason_codes"]
    assert any("not yet verified" in r for r in match["score_breakdown"]["risks"])
    assert "Warning" in match["scoring_explanation"]
    assert "not yet verified" in match["scoring_explanation"]


def test_missing_optional_data_policy_neutral(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Furnishing is UNKNOWN
    p_id, l_id = create_candidate(
        client,
        source_id,
        "Novena Furnishing Unknown",
        "30 Novena Road",
        furnishing="UNKNOWN",
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")
    # Score with NEUTRAL policy
    client.post(
        f"/api/leads/{lead_id}/property-matching/score",
        json={"config": {"missing_data_policy": "NEUTRAL"}},
    )

    matches = client.get(f"/api/leads/{lead_id}/property-matches").json()
    match = [m for m in matches if m["listing_id"] == l_id][0]
    furn_dim = match["score_breakdown"]["dimensions"]["furnishing"]
    assert furn_dim["raw_score"] == 0.5
    assert furn_dim["weighted_score"] == 2.0  # 0.5 * 4.0 weight


def test_multiple_listings_on_same_property_scored_independently(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Canonical Property
    prop_res = client.post(
        "/api/properties",
        json={
            "canonical_name": "Novena Dual Listing Property",
            "building_name": "Novena Tower",
            "address_line_1": "100 Novena Rise",
            "unit_number": "#12-01",
            "postal_code": "307999",
            "city": "Singapore",
            "country": "Singapore",
            "property_type": "CONDO",
            "bedrooms": 2,
            "bathrooms": 2.0,
            "furnishing": "FURNISHED",
            "status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    prop_id = prop_res.json()["id"]

    # Listing 1: Cheaper price 3500
    l1_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={
            "source_id": source_id,
            "source_listing_id": "P4-L1",
            "asking_price": 3500,
            "currency": "SGD",
            "availability_status": "AVAILABLE",
            "available_from": "2026-12-01",
            "lease_min_months": 12,
            "listing_status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    l1_id = l1_res.json()["id"]

    # Listing 2: More expensive price 3950
    l2_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={
            "source_id": source_id,
            "source_listing_id": "P4-L2",
            "asking_price": 3950,
            "currency": "SGD",
            "availability_status": "AVAILABLE",
            "available_from": "2026-12-01",
            "lease_min_months": 12,
            "listing_status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    l2_id = l2_res.json()["id"]

    client.post(f"/api/leads/{lead_id}/property-matching/run")
    client.post(f"/api/leads/{lead_id}/property-matching/score")

    matches = client.get(f"/api/leads/{lead_id}/property-matches").json()
    m1 = [m for m in matches if m["listing_id"] == l1_id][0]
    m2 = [m for m in matches if m["listing_id"] == l2_id][0]

    # Both refer to same canonical property
    assert m1["property_id"] == prop_id
    assert m2["property_id"] == prop_id
    # But have distinct scores due to pricing difference
    assert m1["match_score"] > m2["match_score"]


def test_scoring_weights_validation(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]

    # Negative weight rejected
    bad_cfg_negative = {
        "location_weight": -10.0,
        "budget_weight": 40.0,
    }
    res_neg = client.post(
        f"/api/leads/{lead_id}/property-matching/score",
        json={"config": bad_cfg_negative},
    )
    assert res_neg.status_code == 422

    # Weights sum != 100 rejected
    bad_cfg_sum = {
        "location_weight": 30.0,
        "budget_weight": 20.0,  # Sum = 70.0 instead of 100.0
        "property_type_weight": 10.0,
        "bedrooms_weight": 5.0,
        "move_in_weight": 5.0,
    }
    res_sum = client.post(
        f"/api/leads/{lead_id}/property-matching/score",
        json={"config": bad_cfg_sum},
    )
    assert res_sum.status_code == 422


def test_threshold_and_top_n_capping(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Create 3 candidates:
    # C1: Novena (Exact), 3600 (High score)
    p1, l1 = create_candidate(client, source_id, "Candidate C1", "10 Novena Road", asking_price=3600)
    # C2: Newton (Secondary), 3700 (Good score)
    p2, l2 = create_candidate(client, source_id, "Candidate C2", "20 Newton Road", asking_price=3700)
    # C3: Secondary location with later move-in date
    p3, l3 = create_candidate(client, source_id, "Candidate C3", "30 Newton Road", asking_price=3800, available_from="2026-12-10")

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    # Score with top-N limit = 1 and threshold = 80.0
    cfg = {
        "minimum_score_for_outreach": 80.0,
        "maximum_candidates_for_agent_verification": 1,
    }
    score_res = client.post(f"/api/leads/{lead_id}/property-matching/score", json={"config": cfg})
    assert score_res.status_code == 200
    res_data = score_res.json()
    assert res_data["ready_for_agent_verification"] == 1

    matches = client.get(f"/api/leads/{lead_id}/property-matches?sort_by=rank").json()
    # Rank 1 gets READY_FOR_AGENT_VERIFICATION
    assert matches[0]["rank"] == 1
    assert matches[0]["match_status"] == "READY_FOR_AGENT_VERIFICATION"
    # Rank 2 also passed 80.0 threshold, but capped by Top-1 -> SCORED
    assert matches[1]["rank"] == 2
    assert matches[1]["match_status"] == "SCORED"


def test_failed_hard_filter_never_scored(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    # Property type HDB when tenant requires CONDO -> Filtered out in Phase 3
    p_hdb, l_hdb = create_candidate(client, source_id, "Novena HDB", "100 HDB Lane", property_type="HDB")

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_phase3 = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT").json()
    m_hdb = [m for m in matches_phase3 if m["listing_id"] == l_hdb][0]
    assert m_hdb["hard_filter_passed"] is False

    # Score
    client.post(f"/api/leads/{lead_id}/property-matching/score")

    # Check that HDB record is NEVER given a score and remains FILTERED_OUT
    m_hdb_post = client.get(f"/api/property-matches/{m_hdb['id']}").json()
    assert m_hdb_post["match_score"] is None
    assert m_hdb_post["rank"] is None
    assert m_hdb_post["match_status"] == "FILTERED_OUT"


def test_stale_score_handling_and_rescore(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    p_id, l_id = create_candidate(client, source_id, "Stale Test Condo", "88 Thomson Road, Novena", asking_price=3700)

    client.post(f"/api/leads/{lead_id}/property-matching/run")
    client.post(f"/api/leads/{lead_id}/property-matching/score")

    matches = client.get(f"/api/leads/{lead_id}/property-matches").json()
    m = [m for m in matches if m["listing_id"] == l_id][0]
    assert m["match_score"] is not None
    assert m["is_stale"] is False

    # Mark stale
    stale_res = client.post(
        f"/api/property-matches/{m['id']}/mark-stale",
        json={"reason": "Asking price updated in external feed"},
    )
    assert stale_res.status_code == 200
    assert stale_res.json()["is_stale"] is True
    assert stale_res.json()["stale_reason"] == "Asking price updated in external feed"

    # Re-score clears staleness
    client.post(f"/api/leads/{lead_id}/property-matching/score")
    m_fresh = client.get(f"/api/property-matches/{m['id']}").json()
    assert m_fresh["is_stale"] is False
    assert m_fresh["stale_reason"] is None


def test_manual_forward_override_with_audit(client: TestClient, qualified_tenant_setup: Dict[str, Any]):
    lead_id = qualified_tenant_setup["lead_id"]
    source_id = qualified_tenant_setup["source_id"]

    p_id, l_id = create_candidate(client, source_id, "Below Threshold Condo", "99 Thomson Road, Novena", asking_price=3990)

    client.post(f"/api/leads/{lead_id}/property-matching/run")
    # Score with strict 99.5 threshold so candidate ends up BELOW_OUTREACH_THRESHOLD
    client.post(f"/api/leads/{lead_id}/property-matching/score", json={"config": {"minimum_score_for_outreach": 99.5}})

    matches = client.get(f"/api/leads/{lead_id}/property-matches?status=BELOW_OUTREACH_THRESHOLD").json()
    m = [m for m in matches if m["listing_id"] == l_id][0]
    orig_score = m["match_score"]

    # Operator manually promotes candidate to READY_FOR_AGENT_VERIFICATION
    ov_res = client.post(
        f"/api/property-matches/{m['id']}/override",
        json={
            "target_status": "READY_FOR_AGENT_VERIFICATION",
            "reason": "Operator confirmed tenant is very interested in this specific building",
        },
        headers={"X-User-Role": "operator"},
    )
    assert ov_res.status_code == 200
    ov_data = ov_res.json()
    assert ov_data["match_status"] == "READY_FOR_AGENT_VERIFICATION"
    assert ov_data["manual_override"] is True
    assert ov_data["manual_override_reason"] == "Operator confirmed tenant is very interested in this specific building"
    # System match score must NOT be modified
    assert ov_data["match_score"] == orig_score
