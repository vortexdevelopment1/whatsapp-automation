import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.models.enums import (
    PropertyType,
    FurnishingType,
    ListingAvailabilityStatus,
    PropertyImportBatchStatus,
    PropertyImportRowStatus,
    DuplicateReviewStatus,
    DuplicateConfidenceLevel,
)
from app.services.property_normalizer import PropertyNormalizer
from app.services.demo_property_source_adapter import DemoPropertySourceAdapter


# ==============================================================================
# 1. NORMALIZATION UNIT TESTS
# ==============================================================================

def test_property_type_normalization():
    assert PropertyNormalizer.normalize_property_type("condo") == PropertyType.CONDO
    assert PropertyNormalizer.normalize_property_type("Condominium") == PropertyType.CONDO
    assert PropertyNormalizer.normalize_property_type("private condo") == PropertyType.CONDO
    assert PropertyNormalizer.normalize_property_type("apt") == PropertyType.APARTMENT
    assert PropertyNormalizer.normalize_property_type("apartment") == PropertyType.APARTMENT
    assert PropertyNormalizer.normalize_property_type("HDB flat") == PropertyType.HDB
    assert PropertyNormalizer.normalize_property_type("hdb") == PropertyType.HDB
    assert PropertyNormalizer.normalize_property_type("landed house") == PropertyType.LANDED
    assert PropertyNormalizer.normalize_property_type("unknown-type-xyz") == PropertyType.OTHER


def test_furnishing_normalization():
    assert PropertyNormalizer.normalize_furnishing("fully furnished") == FurnishingType.FURNISHED
    assert PropertyNormalizer.normalize_furnishing("full furnished") == FurnishingType.FURNISHED
    assert PropertyNormalizer.normalize_furnishing("Furnished") == FurnishingType.FURNISHED
    assert PropertyNormalizer.normalize_furnishing("semi furnished") == FurnishingType.PARTIALLY_FURNISHED
    assert PropertyNormalizer.normalize_furnishing("partially furnished") == FurnishingType.PARTIALLY_FURNISHED
    assert PropertyNormalizer.normalize_furnishing("unfurnished") == FurnishingType.UNFURNISHED
    assert PropertyNormalizer.normalize_furnishing("bare") == FurnishingType.UNFURNISHED
    assert PropertyNormalizer.normalize_furnishing("random-xyz") == FurnishingType.UNKNOWN


def test_currency_and_price_normalization():
    curr, defaulted = PropertyNormalizer.normalize_currency("S$")
    assert curr == "SGD" and not defaulted

    curr, defaulted = PropertyNormalizer.normalize_currency("Singapore Dollar")
    assert curr == "SGD" and not defaulted

    curr, defaulted = PropertyNormalizer.normalize_currency("AED")
    assert curr == "AED" and not defaulted

    curr, defaulted = PropertyNormalizer.normalize_currency("Dhs")
    assert curr == "AED" and not defaulted

    curr, defaulted = PropertyNormalizer.normalize_currency(None, default="SGD")
    assert curr == "SGD" and defaulted

    # Price normalization
    assert PropertyNormalizer.normalize_price(3500) == Decimal("3500.00")
    assert PropertyNormalizer.normalize_price("3,500") == Decimal("3500.00")
    assert PropertyNormalizer.normalize_price("$3500") == Decimal("3500.00")
    assert PropertyNormalizer.normalize_price("S$ 3,500") == Decimal("3500.00")
    assert PropertyNormalizer.normalize_price("AED 140,000") == Decimal("140000.00")

    with pytest.raises(ValueError):
        PropertyNormalizer.normalize_price("-500")
    with pytest.raises(ValueError):
        PropertyNormalizer.normalize_price("free")


def test_bedroom_bathroom_normalization():
    assert PropertyNormalizer.normalize_bedrooms("2 bed") == 2
    assert PropertyNormalizer.normalize_bedrooms("2BR") == 2
    assert PropertyNormalizer.normalize_bedrooms("2 Bedroom") == 2
    assert PropertyNormalizer.normalize_bedrooms("studio") == 0
    assert PropertyNormalizer.normalize_bedrooms(3) == 3

    assert PropertyNormalizer.normalize_bathrooms("2") == Decimal("2.0")
    assert PropertyNormalizer.normalize_bathrooms("1.5 bath") == Decimal("1.5")


def test_lease_term_normalization():
    min_m, max_m = PropertyNormalizer.normalize_lease_terms("12 months", "24 months")
    assert min_m == 12 and max_m == 24

    min_m, max_m = PropertyNormalizer.normalize_lease_terms("1 year", None)
    assert min_m == 12 and max_m is None

    min_m, max_m = PropertyNormalizer.normalize_lease_terms("6 months", "12")
    assert min_m == 6 and max_m == 12

    # Inverted range error
    with pytest.raises(ValueError):
        PropertyNormalizer.normalize_lease_terms(24, 12)


def test_availability_normalization():
    assert PropertyNormalizer.normalize_availability("available") == ListingAvailabilityStatus.AVAILABLE
    assert PropertyNormalizer.normalize_availability("taken") == ListingAvailabilityStatus.UNAVAILABLE
    assert PropertyNormalizer.normalize_availability("rented") == ListingAvailabilityStatus.UNAVAILABLE
    assert PropertyNormalizer.normalize_availability("check with agent") == ListingAvailabilityStatus.AWAITING_VERIFICATION
    assert PropertyNormalizer.normalize_availability(None) == ListingAvailabilityStatus.UNKNOWN


def test_address_normalization_and_fingerprint():
    addr1 = PropertyNormalizer.normalize_address(
        address_line_1="3 Central Blvd",
        address_line_2="#15-02",
        postal_code="018965",
        city="Singapore",
        country="Singapore",
    )
    assert addr1["postal_code_normalized"] == "018965"
    assert addr1["unit_normalized"] == "#15-02"
    assert "central boulevard" in addr1["address_normalized"]

    addr2 = PropertyNormalizer.normalize_address(
        address_line_1="3 Central Boulevard",
        address_line_2="#15-2",  # Should format to #15-02
        postal_code="18965",    # Should zero-pad to 018965
        city="Singapore",
        country="Singapore",
    )
    assert addr2["postal_code_normalized"] == "018965"
    assert addr2["unit_normalized"] == "#15-02"
    assert addr1["property_fingerprint"] == addr2["property_fingerprint"]


def test_agent_normalization():
    agent1 = PropertyNormalizer.normalize_agent(
        name="Alice Tan",
        phone="+65 9123 4567",
        email="Alice.Tan@Example.com",
        agency="propnex realty",
        reg_no="r012345a",
    )
    assert agent1["phone_normalized"] == "+6591234567"
    assert agent1["email"] == "alice.tan@example.com"
    assert agent1["registration_number"] == "R012345A"

    agent2 = PropertyNormalizer.normalize_agent(
        name="Alice Tan",
        phone="6591234567",
    )
    assert agent2["phone_normalized"] == "+6591234567"


# ==============================================================================
# 2. INTEGRATION TESTS (API & DEDUPLICATION)
# ==============================================================================

@pytest.fixture
def active_source_id(client: TestClient) -> str:
    res = client.post(
        "/api/property-sources",
        json={
            "name": "Integration Test Source",
            "source_type": "CSV_IMPORT",
            "status": "ACTIVE",
            "external_system_name": f"SRC_{uuid.uuid4().hex[:6].upper()}",
        },
        headers={"X-User-Role": "operator"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_csv_upload_validation_and_preview(client: TestClient, active_source_id: str):
    csv_data = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "TEST-01,Test Condo 2BR,Test Towers,100 Anson Rd,#08-01,079903,Singapore,Singapore,Condominium,2,2,950,Fully Furnished,4500,SGD,2026-11-01,12,24,available,ACTIVE,John Agent,PropNex,R111222A,+65 9111 2222,john@propnex.sg,2026-10-01T00:00:00Z\n"
        "TEST-02,Invalid Row Listing,Bad Towers,100 Anson Rd,#08-02,079903,Singapore,Singapore,Condo,2,2,950,Furnished,-500,SGD,2026-11-01,12,24,available,ACTIVE,John Agent,PropNex,R111222A,+65 9111 2222,john@propnex.sg,2026-10-01T00:00:00Z\n"
    )


    files = {"file": ("test_import.csv", csv_data, "text/csv")}
    data = {"source_id": active_source_id}
    res = client.post("/api/property-imports/upload", data=data, files=files)
    assert res.status_code == 201
    batch = res.json()
    batch_id = batch["id"]

    assert batch["status"] == "UPLOADED"
    assert batch["total_rows"] == 2
    assert batch["valid_rows"] == 1
    assert batch["invalid_rows"] == 1

    # Preview batch
    res_prev = client.post(f"/api/property-imports/{batch_id}/preview")
    assert res_prev.status_code == 200
    prev_data = res_prev.json()
    assert prev_data["total_rows"] == 2
    assert prev_data["valid_rows"] == 1
    assert prev_data["invalid_rows"] == 1
    assert len(prev_data["sample_rows"]) == 2

    # Row 1 should be VALID and NEW_PROPERTY_CREATED candidate
    assert prev_data["sample_rows"][0]["status"] == "NEW_PROPERTY_CREATED"
    # Row 2 should be INVALID with error
    assert prev_data["sample_rows"][1]["status"] == "INVALID"
    assert len(prev_data["sample_rows"][1]["errors"]) > 0


def test_deduplication_exact_listing_and_canonical_property(client: TestClient, active_source_id: str):
    # Step 1: Initial upload with 1 property listing
    csv_1 = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "PROP-101,Marina Bay 2BR,Marina Bay Tower,1 Marina Blvd,#10-01,018989,Singapore,Singapore,Condominium,2,2,1000,Furnished,5000,SGD,2026-11-01,12,24,available,ACTIVE,Agent A,ERA,R123456A,+65 9123 4567,agenta@era.sg,2026-10-01T00:00:00Z\n"
    )
    f1 = {"file": ("batch1.csv", csv_1, "text/csv")}
    res1 = client.post("/api/property-imports/upload", data={"source_id": active_source_id}, files=f1)
    assert res1.status_code == 201
    batch1_id = res1.json()["id"]

    res_commit1 = client.post(f"/api/property-imports/{batch1_id}/commit")
    assert res_commit1.status_code == 200
    b1_comm = res_commit1.json()
    assert b1_comm["new_property_rows"] == 1
    assert b1_comm["duplicate_listing_rows"] == 0

    # Step 2: Upload same exact source listing with updated price (5200) + a second listing for SAME property by Agent B
    csv_2 = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "PROP-101,Marina Bay 2BR (Price Up),Marina Bay Tower,1 Marina Blvd,#10-01,018989,Singapore,Singapore,Condominium,2,2,1000,Furnished,5200,SGD,2026-11-01,12,24,available,ACTIVE,Agent A,ERA,R123456A,+65 9123 4567,agenta@era.sg,2026-10-05T00:00:00Z\n"
        "PROP-102,Marina Bay High Floor 2BR,Marina Bay Tower,1 Marina Boulevard,#10-01,018989,Singapore,Singapore,condo,2,2,1000,Furnished,5300,SGD,2026-11-01,12,24,available,ACTIVE,Agent B,PropNex,R789012B,+65 9234 5678,agentb@propnex.sg,2026-10-05T00:00:00Z\n"
    )
    f2 = {"file": ("batch2.csv", csv_2, "text/csv")}
    res2 = client.post("/api/property-imports/upload", data={"source_id": active_source_id}, files=f2)
    assert res2.status_code == 201
    batch2_id = res2.json()["id"]

    # Preview batch 2
    res_prev2 = client.post(f"/api/property-imports/{batch2_id}/preview")
    assert res_prev2.status_code == 200
    p2 = res_prev2.json()
    assert p2["duplicate_listing_rows"] == 1
    assert p2["matched_existing_property_rows"] == 1
    assert p2["new_property_rows"] == 0

    # Commit batch 2
    res_commit2 = client.post(f"/api/property-imports/{batch2_id}/commit")
    assert res_commit2.status_code == 200
    b2_comm = res_commit2.json()
    assert b2_comm["duplicate_listing_rows"] == 1
    assert b2_comm["matched_existing_property_rows"] == 1
    assert b2_comm["new_property_rows"] == 0

    # Verify canonical property has 2 separate listings attached to it
    res_rows = client.get(f"/api/property-imports/{batch2_id}/rows")
    assert res_rows.status_code == 200
    rows = res_rows.json()
    prop_id = rows[0]["property_id"]
    assert prop_id is not None
    assert rows[1]["property_id"] == prop_id

    # Check listing details via property detail endpoint
    res_prop = client.get(f"/api/properties/{prop_id}")
    assert res_prop.status_code == 200
    prop_data = res_prop.json()
    assert len(prop_data["listings"]) == 2
    prices = {float(l["asking_price"]) for l in prop_data["listings"]}
    assert 5200.0 in prices
    assert 5300.0 in prices


def test_different_unit_creates_distinct_property(client: TestClient, active_source_id: str):
    csv_data = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "UNIT-01,Clementi Park #02-01,Clementi Park,10 Sunset Way,#02-01,597040,Singapore,Singapore,Condominium,3,2,1300,Furnished,4200,SGD,2026-11-01,12,24,available,ACTIVE,Agent C,ERA,R333444C,+65 9333 4444,agentc@era.sg,2026-10-01T00:00:00Z\n"
        "UNIT-02,Clementi Park #05-01,Clementi Park,10 Sunset Way,#05-01,597040,Singapore,Singapore,Condominium,3,2,1300,Furnished,4400,SGD,2026-11-01,12,24,available,ACTIVE,Agent C,ERA,R333444C,+65 9333 4444,agentc@era.sg,2026-10-01T00:00:00Z\n"
    )
    files = {"file": ("units.csv", csv_data, "text/csv")}
    res = client.post("/api/property-imports/upload", data={"source_id": active_source_id}, files=files)
    batch_id = res.json()["id"]

    res_commit = client.post(f"/api/property-imports/{batch_id}/commit")
    assert res_commit.status_code == 200
    b_comm = res_commit.json()
    # Distinct units must create distinct properties
    assert b_comm["new_property_rows"] == 2


def test_uncertain_duplicate_triggers_manual_review_and_resolution(client: TestClient, active_source_id: str):
    # Step 1: Create an established property with known unit
    csv_1 = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "ESTAB-01,Rivergate 3BR,Rivergate,93 Robertson Quay,#18-05,238255,Singapore,Singapore,Condo,3,3,1500,Furnished,8500,SGD,2026-11-01,12,24,available,ACTIVE,Agent R,SRI,R555666R,+65 9555 6666,agentr@sri.sg,2026-10-01T00:00:00Z\n"
    )
    res1 = client.post("/api/property-imports/upload", data={"source_id": active_source_id}, files={"file": ("estab.csv", csv_1, "text/csv")})
    b1_id = res1.json()["id"]
    client.post(f"/api/property-imports/{b1_id}/commit")

    # Step 2: Upload incoming listing with matching building and bedrooms, but NO unit number
    csv_2 = (
        "source_listing_id,property_name,building_name,address_line_1,address_line_2,postal_code,city,country,property_type,bedrooms,bathrooms,size_sqft,furnishing,asking_price,currency,available_from,lease_min_months,lease_max_months,availability_status,listing_status,agent_name,agent_agency,agent_registration_number,agent_phone,agent_email,source_last_updated_at\n"
        "UNCERT-02,Rivergate 3-Bedroom High Floor,Rivergate,93 Robertson Quay,,238255,Singapore,Singapore,Condo,3,3,1500,Furnished,8600,SGD,2026-11-01,12,24,available,ACTIVE,Agent S,PropNex,R777888S,+65 9777 8888,agents@propnex.sg,2026-10-02T00:00:00Z\n"
    )
    res2 = client.post("/api/property-imports/upload", data={"source_id": active_source_id}, files={"file": ("uncert.csv", csv_2, "text/csv")})
    b2_id = res2.json()["id"]

    res_commit2 = client.post(f"/api/property-imports/{b2_id}/commit")
    assert res_commit2.status_code == 200
    b2_data = res_commit2.json()
    assert b2_data["manual_review_rows"] == 1
    assert b2_data["status"] == "COMPLETED_WITH_WARNINGS"

    # Step 3: Check duplicate review item in review queue
    res_reviews = client.get("/api/property-duplicate-reviews?status=OPEN")
    assert res_reviews.status_code == 200
    reviews = res_reviews.json()
    assert len(reviews) >= 1
    target_rev = [r for r in reviews if r["incoming_normalized_data"].get("source_listing_id") == "UNCERT-02"][0]
    review_id = target_rev["id"]
    assert target_rev["status"] == "OPEN"
    assert "same_postal_code" in target_rev["match_reasons"]
    assert "incoming_unit_number_missing" in target_rev["match_reasons"]


    # Step 4: Resolve review by attaching to the candidate property
    candidate_id = target_rev["candidate_property_id"]
    res_attach = client.post(
        f"/api/property-duplicate-reviews/{review_id}/attach-existing",
        json={"target_property_id": candidate_id, "reason": "Operator confirmed after checking with agent S"},
    )
    assert res_attach.status_code == 200
    resolved_rev = res_attach.json()
    assert resolved_rev["status"] == "ATTACHED_EXISTING"

    # Verify listing is attached to candidate property
    res_cand_prop = client.get(f"/api/properties/{candidate_id}")
    assert res_cand_prop.status_code == 200
    cand_prop = res_cand_prop.json()
    assert any(l["source_listing_id"] == "UNCERT-02" for l in cand_prop["listings"])


def test_demo_seed_endpoint_and_batch_execution(client: TestClient):
    # Tests the synthetic demo adapter seeding 20 rows
    res = client.post("/api/property-imports/demo-seed?row_count=20", headers={"X-Admin-Id": "demo-admin"})
    assert res.status_code == 201
    batch = res.json()
    assert batch["import_type"] == "DEMO"
    assert batch["total_rows"] == 20
    assert batch["valid_rows"] >= 18  # includes the planned invalid test rows

    # Commit batch
    res_commit = client.post(f"/api/property-imports/{batch['id']}/commit", headers={"X-Admin-Id": "demo-admin"})
    assert res_commit.status_code == 200
    committed = res_commit.json()
    assert committed["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
    assert committed["new_property_rows"] > 0
