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
    PropertySourceStatus,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    HardFilterReasonCode,
    UnknownDataPolicy,
)


@pytest.fixture
def qualified_lead_setup(client: TestClient) -> Dict[str, Any]:
    # 1. Create Lead with unique phone
    unique_phone = f"+6591{uuid.uuid4().int % 1000000:06d}"
    lead_res = client.post(
        "/api/leads",
        json={
            "full_name": "Qualified Tenant Test",
            "phone": unique_phone,
            "email": f"tenant_{uuid.uuid4().hex[:6]}@example.com",
        },
        headers={"X-User-Role": "operator"},
    )
    assert lead_res.status_code == 201, lead_res.text
    lead_id = lead_res.json()["id"]

    # 2. Set Lead Status & Requirements to QUALIFIED
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


    # 3. Simulate Qualified decision in Module 3
    dec_res = client.post(
        f"/api/leads/{lead_id}/qualification/evaluate",
        json={
            "apply": True,
            "override_decision": "QUALIFIED",
            "override_reason": "Operator manually verified all requirements",
        },
        headers={"X-User-Role": "operator"},
    )
    assert dec_res.status_code == 200, dec_res.text

    # 4. Create Active Source
    source_res = client.post(
        "/api/property-sources",
        json={
            "name": "Phase 3 Test Feed",
            "source_type": "APPROVED_API",
            "external_system_name": f"P3_SRC_{uuid.uuid4().hex[:6]}",
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


def create_test_property_with_listing(
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
    property_status: str = "ACTIVE",
    listing_status: str = "ACTIVE",
) -> Tuple[str, str]:
    # 1. Create Property
    prop_res = client.post(
        "/api/properties",
        json={
            "canonical_name": property_name,
            "building_name": property_name,
            "address_line_1": address_1,
            "address_line_2": "#10-01",
            "unit_number": "#10-01",
            "postal_code": "307683",
            "city": "Singapore",
            "country": "Singapore",
            "property_type": property_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "furnishing": furnishing,
            "status": property_status,
        },
        headers={"X-User-Role": "operator"},
    )
    assert prop_res.status_code == 201
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
            "listing_status": listing_status,
        },
        headers={"X-User-Role": "operator"},
    )
    assert list_res.status_code == 201
    listing_id = list_res.json()["id"]

    return prop_id, listing_id


# ==============================================================================
# TESTS
# ==============================================================================

def test_qualification_gate_blocks_unqualified_lead(client: TestClient):
    phone = f"+6591{uuid.uuid4().int % 1000000:06d}"
    lead_res = client.post(
        "/api/leads",
        json={"full_name": "Unqualified Lead", "phone": phone},
        headers={"X-User-Role": "operator"},
    )
    assert lead_res.status_code == 201, lead_res.text
    lead_id = lead_res.json()["id"]


    # Matching run should fail
    run_res = client.post(f"/api/leads/{lead_id}/property-matching/run")
    assert run_res.status_code == 400
    assert "not QUALIFIED" in run_res.json()["detail"] or "tenant requirements" in run_res.json()["detail"]


def test_perfect_eligibility_and_filters(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # 1. Compatible Listing in Novena (3800 SGD, 2 BR, Condo, Available 1 Dec 2026, 12m, Furnished)
    p_id, l_id = create_test_property_with_listing(
        client,
        source_id=source_id,
        property_name="Novena Suites Luxury",
        address_1="100 Thomson Road, Novena",
        property_type="CONDO",
        bedrooms=2,
        furnishing="FURNISHED",
        asking_price=3800,
        currency="SGD",
        available_from="2026-12-01",
        lease_min=12,
        lease_max=24,
    )

    # 2. Run matching
    run_res = client.post(f"/api/leads/{lead_id}/property-matching/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "COMPLETED"
    assert run_data["eligible_candidates"] >= 1

    # Check match list
    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=ELIGIBLE_FOR_SCORING")
    assert matches_res.status_code == 200
    matches = matches_res.json()
    assert any(m["listing_id"] == l_id for m in matches)
    target_match = [m for m in matches if m["listing_id"] == l_id][0]
    assert target_match["hard_filter_passed"] is True
    assert target_match["match_status"] == "ELIGIBLE_FOR_SCORING"


def test_property_type_mismatch_filtered_out(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Tenant requires CONDO, create HDB flat
    p_id, l_id = create_test_property_with_listing(
        client,
        source_id=source_id,
        property_name="Novena HDB Flat",
        address_1="10 Thomson Road, Novena",
        property_type="HDB",
        bedrooms=2,
        asking_price=3500,
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    assert matches_res.status_code == 200
    matches = matches_res.json()
    target_match = [m for m in matches if m["listing_id"] == l_id][0]

    assert target_match["hard_filter_passed"] is False
    assert "PROPERTY_TYPE_MISMATCH" in target_match["hard_filter_result"]["reason_codes"]


def test_budget_filter_and_tolerance(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Listing 1: 4100 SGD (2.5% above 4000)
    p1, l1 = create_test_property_with_listing(
        client, source_id, "Novena Slightly Above", "102 Thomson Road, Novena", asking_price=4100
    )
    # Listing 2: 4500 SGD (12.5% above 4000)
    p2, l2 = create_test_property_with_listing(
        client, source_id, "Novena Far Above", "104 Thomson Road, Novena", asking_price=4500
    )

    # Run with 5% budget tolerance
    config_payload = {
        "config": {
            "budget_tolerance_percent": 5.0,
            "strict_property_type": True,
        }
    }
    client.post(f"/api/leads/{lead_id}/property-matching/run", json=config_payload)

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches")
    assert matches_res.status_code == 200
    matches = matches_res.json()

    # 4100 should be ELIGIBLE_FOR_SCORING (4100 <= 4000 * 1.05 = 4200)
    m1 = [m for m in matches if m["listing_id"] == l1][0]
    assert m1["match_status"] == "ELIGIBLE_FOR_SCORING"

    # 4500 should be FILTERED_OUT (4500 > 4200)
    m2 = [m for m in matches if m["listing_id"] == l2][0]
    assert m2["match_status"] == "FILTERED_OUT"
    assert "ABOVE_BUDGET_LIMIT" in m2["hard_filter_result"]["reason_codes"]


def test_bedroom_filter(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Listing with 1 bedroom (tenant requires 2)
    p_1bed, l_1bed = create_test_property_with_listing(
        client, source_id, "Novena 1BR", "106 Thomson Road, Novena", bedrooms=1, asking_price=3000
    )
    # Listing with 3 bedrooms (tenant requires 2, extra allowed)
    p_3bed, l_3bed = create_test_property_with_listing(
        client, source_id, "Novena 3BR", "108 Thomson Road, Novena", bedrooms=3, asking_price=3900
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches")
    matches = matches_res.json()

    m_1bed = [m for m in matches if m["listing_id"] == l_1bed][0]
    assert m_1bed["match_status"] == "FILTERED_OUT"
    assert "BELOW_REQUIRED_BEDROOMS" in m_1bed["hard_filter_result"]["reason_codes"]

    m_3bed = [m for m in matches if m["listing_id"] == l_3bed][0]
    assert m_3bed["match_status"] == "ELIGIBLE_FOR_SCORING"


def test_location_filter(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Listing in Jurong West (outside Novena / Newton)
    p_jurong, l_jurong = create_test_property_with_listing(
        client, source_id, "Jurong Lake Condo", "50 Boon Lay Way, Jurong", asking_price=3400
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_jurong = [m for m in matches if m["listing_id"] == l_jurong][0]
    assert "LOCATION_OUTSIDE_ALLOWED_AREA" in m_jurong["hard_filter_result"]["reason_codes"]


def test_move_in_date_filter(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Tenant move-in is 2026-12-01. Available 2027-02-01 (60 days late > 14 days tolerance)
    p_late, l_late = create_test_property_with_listing(
        client, source_id, "Novena Late Condo", "110 Thomson Road, Novena", available_from="2027-02-01"
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_late = [m for m in matches if m["listing_id"] == l_late][0]
    assert "AVAILABLE_TOO_LATE" in m_late["hard_filter_result"]["reason_codes"]


def test_lease_duration_filter(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Tenant requires 12 months. Listing minimum is 24 months.
    p_24m, l_24m = create_test_property_with_listing(
        client, source_id, "Novena 2YearMin", "112 Thomson Road, Novena", lease_min=24, lease_max=36
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_24m = [m for m in matches if m["listing_id"] == l_24m][0]
    assert "LEASE_TERM_INCOMPATIBLE" in m_24m["hard_filter_result"]["reason_codes"]


def test_furnishing_filter_strict_vs_flexible(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Unfurnished listing
    p_unfurn, l_unfurn = create_test_property_with_listing(
        client, source_id, "Novena Bare Unit", "114 Thomson Road, Novena", furnishing="UNFURNISHED"
    )

    # 1. Run with strict_furnishing = True
    config_strict = {"config": {"strict_furnishing": True}}
    client.post(f"/api/leads/{lead_id}/property-matching/run", json=config_strict)

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_unfurn = [m for m in matches if m["listing_id"] == l_unfurn][0]
    assert "FURNISHING_MISMATCH" in m_unfurn["hard_filter_result"]["reason_codes"]


def test_unavailable_listing_filtered(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Rented / UNAVAILABLE listing
    p_unavail, l_unavail = create_test_property_with_listing(
        client, source_id, "Novena Taken Condo", "116 Thomson Road, Novena", availability_status="UNAVAILABLE"
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_unavail = [m for m in matches if m["listing_id"] == l_unavail][0]
    assert "LISTING_UNAVAILABLE" in m_unavail["hard_filter_result"]["reason_codes"]


def test_currency_mismatch_filtered(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Currency is AED instead of SGD
    p_aed, l_aed = create_test_property_with_listing(
        client, source_id, "Dubai Marina Gate", "Al Reshaas Street, Novena", currency="AED", asking_price=3800
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_aed = [m for m in matches if m["listing_id"] == l_aed][0]
    assert "CURRENCY_MISMATCH" in m_aed["hard_filter_result"]["reason_codes"]


def test_inactive_property_or_listing_excluded(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Inactive property
    p_inact, l_inact = create_test_property_with_listing(
        client, source_id, "Archived Property", "118 Thomson Road, Novena", property_status="ACTIVE"
    )
    archive_res = client.post(
        f"/api/properties/{p_inact}/archive",
        headers={"X-User-Role": "operator"},
    )
    assert archive_res.status_code == 200

    # Inactive listing
    p_exp, l_exp = create_test_property_with_listing(
        client, source_id, "Expired Listing Property", "120 Thomson Road, Novena", listing_status="EXPIRED"
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    # Inactive base records are completely excluded from participating
    matches_res = client.get(f"/api/leads/{lead_id}/property-matches")
    matches = matches_res.json()
    assert not any(m["listing_id"] == l_inact for m in matches)
    assert not any(m["listing_id"] == l_exp for m in matches)


def test_manual_override_with_audit(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Create listing that fails on budget (4600 SGD)
    p_high, l_high = create_test_property_with_listing(
        client, source_id, "Novena High Price", "122 Thomson Road, Novena", asking_price=4600
    )

    client.post(f"/api/leads/{lead_id}/property-matching/run")

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches?status=FILTERED_OUT")
    matches = matches_res.json()
    m_high = [m for m in matches if m["listing_id"] == l_high][0]
    match_id = m_high["id"]

    # Perform manual override by operator
    override_payload = {
        "target_status": "ELIGIBLE_FOR_SCORING",
        "reason": "Tenant indicated willingness to stretch budget for high floor unit",
    }
    over_res = client.post(
        f"/api/property-matches/{match_id}/override",
        json=override_payload,
        headers={"X-Admin-Id": "senior-agent-bob"},
    )
    assert over_res.status_code == 200
    over_data = over_res.json()
    assert over_data["match_status"] == "ELIGIBLE_FOR_SCORING"
    assert over_data["manual_override"] is True
    assert over_data["manual_override_by"] == "senior-agent-bob"
    assert "stretch budget" in over_data["manual_override_reason"]
    # Hard filter evaluation result must remain intact for auditability
    assert over_data["hard_filter_passed"] is False
    assert "ABOVE_BUDGET_LIMIT" in over_data["hard_filter_result"]["reason_codes"]


def test_multiple_listings_on_same_property_preserved(client: TestClient, qualified_lead_setup: Dict[str, Any]):
    lead_id = qualified_lead_setup["lead_id"]
    source_id = qualified_lead_setup["source_id"]

    # Canonical Property
    prop_res = client.post(
        "/api/properties",
        json={
            "canonical_name": "Novena Regency Shared",
            "building_name": "Novena Regency",
            "address_line_1": "275 Thomson Road, Novena",
            "unit_number": "#05-01",
            "postal_code": "307645",
            "city": "Singapore",
            "country": "Singapore",
            "property_type": "CONDO",
            "bedrooms": 2,
            "furnishing": "FURNISHED",
            "status": "ACTIVE",
        },
        headers={"X-User-Role": "operator"},
    )
    prop_id = prop_res.json()["id"]

    # Listing 1 by Agent A: 3500 SGD
    l1_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={
            "source_id": source_id,
            "source_listing_id": "REG-01",
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

    # Listing 2 by Agent B: 3700 SGD
    l2_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={
            "source_id": source_id,
            "source_listing_id": "REG-02",
            "asking_price": 3700,
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

    matches_res = client.get(f"/api/leads/{lead_id}/property-matches")
    matches = matches_res.json()

    # Both listing matches exist for the SAME canonical property
    prop_matches = [m for m in matches if m["property_id"] == prop_id]
    assert len(prop_matches) == 2
    listing_ids = {m["listing_id"] for m in prop_matches}
    assert l1_id in listing_ids
    assert l2_id in listing_ids
