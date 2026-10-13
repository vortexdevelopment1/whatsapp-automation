import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.models.enums import (
    PropertyType,
    PropertyStatus,
    FurnishingType,
    PropertySourceType,
    PropertySourceStatus,
    PropertyAgentStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
)
from app.db.seeds.property_seeds import seed_property_inventory


def test_property_source_crud_and_validation(client: TestClient):
    # 1. Create Source
    source_payload = {
        "name": "Test Agency Source",
        "source_type": "CSV_IMPORT",
        "external_system_name": "AgencyCSV_v1",
        "status": "ACTIVE",
        "configuration_reference": "config/agency_csv.json",
    }
    res = client.post("/api/property-sources", json=source_payload, headers={"X-User-Role": "operator"})
    assert res.status_code == 201
    source_data = res.json()
    assert source_data["name"] == "Test Agency Source"
    assert source_data["source_type"] == "CSV_IMPORT"
    assert source_data["status"] == "ACTIVE"
    source_id = source_data["id"]

    # 2. Get Source
    res_get = client.get(f"/api/property-sources/{source_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == source_id

    # 3. List Sources
    res_list = client.get("/api/property-sources?source_type=CSV_IMPORT")
    assert res_list.status_code == 200
    assert any(s["id"] == source_id for s in res_list.json())

    # 4. Deactivate Source
    res_deact = client.post(f"/api/property-sources/{source_id}/deactivate", headers={"X-User-Role": "operator"})
    assert res_deact.status_code == 200
    assert res_deact.json()["status"] == "INACTIVE"

    # 5. Activate Source
    res_act = client.post(f"/api/property-sources/{source_id}/activate", headers={"X-User-Role": "operator"})
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIVE"

    # 6. Invalid source type
    res_inv = client.post(
        "/api/property-sources",
        json={"name": "Bad Type", "source_type": "NON_EXISTENT_TYPE"},
        headers={"X-User-Role": "operator"},
    )
    assert res_inv.status_code == 422


def test_property_agent_crud_and_phone_normalization(client: TestClient):
    # 1. Create Property Agent
    agent_payload = {
        "full_name": "Kelvin Tan",
        "agency_name": "PropNex Singapore",
        "registration_number": "R099887Z",
        "phone": "+65 9111 2233",
        "email": "kelvin.tan@propnex-example.sg",
        "status": "ACTIVE",
    }
    res = client.post("/api/property-agents", json=agent_payload, headers={"X-User-Role": "operator"})
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Kelvin Tan"
    assert data["phone_normalized"] == "+6591112233"
    agent_id = data["id"]

    # 2. Read Agent
    res_get = client.get(f"/api/property-agents/{agent_id}")
    assert res_get.status_code == 200
    assert res_get.json()["registration_number"] == "R099887Z"

    # 3. Update Agent
    res_upd = client.patch(
        f"/api/property-agents/{agent_id}",
        json={"phone": "+65 8222 3344", "agency_name": "PropNex Prime"},
        headers={"X-User-Role": "operator"},
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["phone_normalized"] == "+6582223344"
    assert res_upd.json()["agency_name"] == "PropNex Prime"

    # 4. Archive Agent
    res_arch = client.post(f"/api/property-agents/{agent_id}/archive", headers={"X-User-Role": "operator"})
    assert res_arch.status_code == 200
    assert res_arch.json()["status"] == "ARCHIVED"


def test_property_crud_and_validations(client: TestClient):
    # 1. Create Canonical Property
    prop_payload = {
        "canonical_name": "Novena Suites #12-05",
        "building_name": "Novena Suites",
        "address_line_1": "100 Thomson Road",
        "unit_number": "#12-05",
        "postal_code": "307591",
        "district": "D11 - Novena / Newton",
        "city": "Singapore",
        "country": "Singapore",
        "latitude": 1.3182,
        "longitude": 103.8440,
        "property_type": "CONDO",
        "bedrooms": 2,
        "bathrooms": 2.0,
        "size_sqft": 820.0,
        "furnishing": "FURNISHED",
        "status": "ACTIVE",
    }
    res = client.post("/api/properties", json=prop_payload, headers={"X-User-Role": "operator"})
    assert res.status_code == 201
    prop_data = res.json()
    assert prop_data["canonical_name"] == "Novena Suites #12-05"
    assert prop_data["bedrooms"] == 2
    assert prop_data["status"] == "ACTIVE"
    prop_id = prop_data["id"]

    # 2. Read Property Detail
    res_get = client.get(f"/api/properties/{prop_id}")
    assert res_get.status_code == 200
    detail = res_get.json()
    assert detail["canonical_name"] == "Novena Suites #12-05"
    assert detail["listings_count"] == 0
    assert detail["listings"] == []

    # 3. Update Property
    res_patch = client.patch(
        f"/api/properties/{prop_id}",
        json={"bedrooms": 3, "furnishing": "PARTIALLY_FURNISHED"},
        headers={"X-User-Role": "operator"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["bedrooms"] == 3
    assert res_patch.json()["furnishing"] == "PARTIALLY_FURNISHED"

    # 4. Archive Property
    res_arch = client.post(f"/api/properties/{prop_id}/archive", headers={"X-User-Role": "operator"})
    assert res_arch.status_code == 200
    assert res_arch.json()["status"] == "ARCHIVED"

    # 5. Validation: Negative bedrooms
    res_neg_bed = client.post(
        "/api/properties",
        json={"canonical_name": "Bad Bed", "bedrooms": -1, "country": "Singapore"},
        headers={"X-User-Role": "operator"},
    )
    assert res_neg_bed.status_code == 422

    # 6. Validation: Invalid coordinates
    res_bad_lat = client.post(
        "/api/properties",
        json={"canonical_name": "Bad Lat", "latitude": 95.0, "country": "Singapore"},
        headers={"X-User-Role": "operator"},
    )
    assert res_bad_lat.status_code == 422

    # 7. Validation: Invalid property type
    res_bad_type = client.post(
        "/api/properties",
        json={"canonical_name": "Bad Type", "property_type": "CASTLE", "country": "Singapore"},
        headers={"X-User-Role": "operator"},
    )
    assert res_bad_type.status_code == 422


def test_property_listings_provenance_multiple_listings_and_availability(client: TestClient):
    # Setup source and agent
    src_res = client.post(
        "/api/property-sources",
        json={"name": "Multi Listing Source A", "source_type": "APPROVED_API", "status": "ACTIVE"},
        headers={"X-User-Role": "operator"},
    )
    source_a_id = src_res.json()["id"]

    src_res_b = client.post(
        "/api/property-sources",
        json={"name": "Multi Listing Source B", "source_type": "MANUAL", "status": "ACTIVE"},
        headers={"X-User-Role": "operator"},
    )
    source_b_id = src_res_b.json()["id"]

    agt_res_a = client.post(
        "/api/property-agents",
        json={"full_name": "Agent Arthur", "agency_name": "Agency A", "phone": "+65 9876 5432"},
        headers={"X-User-Role": "operator"},
    )
    agent_a_id = agt_res_a.json()["id"]

    agt_res_b = client.post(
        "/api/property-agents",
        json={"full_name": "Agent Beatrice", "agency_name": "Agency B", "phone": "+65 9765 4321"},
        headers={"X-User-Role": "operator"},
    )
    agent_b_id = agt_res_b.json()["id"]

    # Create canonical property
    prop_res = client.post(
        "/api/properties",
        json={
            "canonical_name": "Duo Residences #20-01",
            "building_name": "Duo Residences",
            "postal_code": "189767",
            "property_type": "CONDO",
            "bedrooms": 2,
            "country": "Singapore",
        },
        headers={"X-User-Role": "operator"},
    )
    prop_id = prop_res.json()["id"]

    # 1. Attach Listing 1 (SGD 3500, Agent Arthur, UNKNOWN availability default)
    listing_1_payload = {
        "source_id": source_a_id,
        "source_listing_id": "DUO-PORTAL-101",
        "source_url": "https://portal.sg/duo-101",
        "agent_id": agent_a_id,
        "asking_price": 3500.0,
        "currency": "SGD",
        "lease_min_months": 12,
        "lease_max_months": 24,
        "available_from": "2026-12-01",
        "metadata": {"raw_views": 150, "features": ["high-floor", "pool-view"]},
    }
    l1_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json=listing_1_payload,
        headers={"X-User-Role": "operator"},
    )
    assert l1_res.status_code == 201
    l1_data = l1_res.json()
    assert l1_data["property_id"] == prop_id
    assert float(l1_data["asking_price"]) == 3500.0
    # Crucial Requirement: Listing creation does NOT automatically imply AVAILABLE!
    assert l1_data["availability_status"] == "UNKNOWN"
    assert l1_data["metadata"]["features"] == ["high-floor", "pool-view"]
    listing_1_id = l1_data["id"]

    # 2. Attach Listing 2 to the EXACT SAME property (SGD 3650, Agent Beatrice, AVAILABLE)
    listing_2_payload = {
        "source_id": source_b_id,
        "source_listing_id": "MANUAL-DUO-202",
        "source_url": "https://agencyb.sg/duo-202",
        "agent_id": agent_b_id,
        "asking_price": 3650.0,
        "currency": "SGD",
        "availability_status": "AVAILABLE",
        "lease_min_months": 12,
        "metadata": {"origin": "landlord_direct"},
    }
    l2_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json=listing_2_payload,
        headers={"X-User-Role": "operator"},
    )
    assert l2_res.status_code == 201
    l2_data = l2_res.json()
    assert l2_data["property_id"] == prop_id
    assert float(l2_data["asking_price"]) == 3650.0
    assert l2_data["availability_status"] == "AVAILABLE"
    listing_2_id = l2_data["id"]

    # 3. Verify Property Detail now shows ONE property with TWO distinct listings
    prop_detail_res = client.get(f"/api/properties/{prop_id}")
    assert prop_detail_res.status_code == 200
    prop_detail = prop_detail_res.json()
    assert prop_detail["listings_count"] == 2
    listing_ids = [l["id"] for l in prop_detail["listings"]]
    assert listing_1_id in listing_ids
    assert listing_2_id in listing_ids

    # 4. Provenance preservation: Update listing 1 price and ensure provenance fields intact
    upd_res = client.patch(
        f"/api/property-listings/{listing_1_id}",
        json={"asking_price": 3450.0},
        headers={"X-User-Role": "operator"},
    )
    assert upd_res.status_code == 200
    upd_data = upd_res.json()
    assert float(upd_data["asking_price"]) == 3450.0

    assert upd_data["source_listing_id"] == "DUO-PORTAL-101"
    assert upd_data["source_url"] == "https://portal.sg/duo-101"
    assert upd_data["metadata"]["features"] == ["high-floor", "pool-view"]

    # 5. Availability state update endpoint
    avail_res = client.patch(
        f"/api/property-listings/{listing_1_id}/availability",
        json={"availability_status": "AWAITING_VERIFICATION", "available_from": "2026-12-15"},
        headers={"X-User-Role": "operator"},
    )
    assert avail_res.status_code == 200
    assert avail_res.json()["availability_status"] == "AWAITING_VERIFICATION"
    assert avail_res.json()["available_from"] == "2026-12-15"

    # 6. Negative price validation
    neg_price_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={"source_id": source_a_id, "asking_price": -500.0},
        headers={"X-User-Role": "operator"},
    )
    assert neg_price_res.status_code == 422

    # 7. Invalid lease range validation: min > max
    bad_lease_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={"source_id": source_a_id, "lease_min_months": 24, "lease_max_months": 12},
        headers={"X-User-Role": "operator"},
    )
    assert bad_lease_res.status_code == 422

    # 8. Duplicate (source_id, source_listing_id) validation
    dup_res = client.post(
        f"/api/properties/{prop_id}/listings",
        json={"source_id": source_a_id, "source_listing_id": "DUO-PORTAL-101"},
        headers={"X-User-Role": "operator"},
    )
    assert dup_res.status_code == 400


def test_rbac_and_audit_logging(client: TestClient):
    # Setup test source
    src = client.post(
        "/api/property-sources",
        json={"name": "RBAC Source", "source_type": "MANUAL", "status": "ACTIVE"},
        headers={"X-User-Role": "admin"},
    ).json()

    # 1. Viewer cannot create property
    res_viewer_prop = client.post(
        "/api/properties",
        json={"canonical_name": "Forbidden Tower", "country": "Singapore"},
        headers={"X-User-Role": "viewer"},
    )
    assert res_viewer_prop.status_code == 403

    # 2. Viewer cannot create source
    res_viewer_src = client.post(
        "/api/property-sources",
        json={"name": "Forbidden Source", "source_type": "MANUAL"},
        headers={"X-User-Role": "viewer"},
    )
    assert res_viewer_src.status_code == 403

    # 3. Viewer cannot create agent
    res_viewer_agt = client.post(
        "/api/property-agents",
        json={"full_name": "Forbidden Agent"},
        headers={"X-User-Role": "viewer"},
    )
    assert res_viewer_agt.status_code == 403

    # 4. Operator can create property and audit log is recorded
    res_op = client.post(
        "/api/properties",
        json={"canonical_name": "Audited Residence", "country": "Singapore", "bedrooms": 1},
        headers={"X-User-Role": "operator", "X-Admin-Id": "operator_test_user"},
    )
    assert res_op.status_code == 201
    prop_id = res_op.json()["id"]

    # Check audit log
    res_audit = client.get(f"/api/audit-logs?entity_type=property&entity_id={prop_id}")
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "PROPERTY_CREATED"
    assert logs[0]["actor_id"] == "operator_test_user"


def test_seed_demo_inventory(client: TestClient):
    res = client.post("/api/dev/module4/seed-inventory", headers={"X-User-Role": "admin"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["seeded"]["properties_count"] >= 5
    assert data["seeded"]["listings_count"] >= 6
    assert data["seeded"]["sources_count"] >= 3
    assert data["seeded"]["agents_count"] >= 4

    # Verify Novena Regency has multiple listings in the database
    res_props = client.get("/api/properties?search=Novena Regency")
    assert res_props.status_code == 200
    props = res_props.json()
    assert len(props) >= 1
    novena_prop = props[0]
    assert novena_prop["listings_count"] >= 2
