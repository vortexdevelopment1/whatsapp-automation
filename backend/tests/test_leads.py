import uuid
import pytest
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
    LeadSourceType,
    LeadSourceStatus,
    ImportBatchStatus,
)
from app.models.lead_import import LeadImportBatch
from app.models.lead_routing import LeadRoutingDecision


def test_lead_source_lifecycle(client):
    # 1. Create a lead source
    payload = {
        "name": "PropertyGuru Singapore",
        "source_type": LeadSourceType.PORTAL if hasattr(LeadSourceType, "PORTAL") else LeadSourceType.PARTNER.value,
        "description": "Inbound listing inquiries from PropertyGuru",
        "status": LeadSourceStatus.ACTIVE.value,
    }
    res = client.post("/api/lead-sources", json=payload)
    assert res.status_code == 201
    source = res.json()
    assert source["name"] == "PropertyGuru Singapore"
    assert source["status"] == LeadSourceStatus.ACTIVE.value
    source_id = source["id"]

    # 2. Prevent duplicate name creation
    dup_res = client.post("/api/lead-sources", json=payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 3. Update lead source
    update_res = client.patch(
        f"/api/lead-sources/{source_id}",
        json={"description": "Updated description", "status": LeadSourceStatus.INACTIVE.value},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["description"] == "Updated description"
    assert updated["status"] == LeadSourceStatus.INACTIVE.value

    # 4. List lead sources
    list_res = client.get("/api/lead-sources")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(s["id"] == source_id for s in items)


def test_lead_creation_and_phone_normalization(client):
    # Test normalization of varied valid formats
    phone_test_cases = [
        ("+65 9123 4567", "+6591234567"),
        ("6591234567", "+6591234567"),
        ("+6591234567", "+6591234567"),
        ("91234567", "+6591234567"),
        ("+1 650 253 0000", "+16502530000"),
    ]

    for raw_phone, expected_normalized in phone_test_cases:
        res = client.post(
            "/api/leads",
            json={
                "full_name": f"Test Tenant {raw_phone}",
                "phone": raw_phone,
                "email": "tenant@example.com",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["phone"] == raw_phone.strip()
        assert data["phone_normalized"] == expected_normalized
        assert data["status"] == LeadStatus.NEW.value
        assert data["consent_status"] == ConsentStatus.UNKNOWN.value
        assert data["opt_out_status"] == OptOutStatus.ACTIVE.value
        assert data["contact_eligibility"] == ContactEligibility.UNKNOWN.value


def test_invalid_phone_handling(client):
    invalid_phones = [
        "123",
        "abcdef",
        "",
        "   ",
        "+99999999999",
    ]

    for bad_phone in invalid_phones:
        res = client.post(
            "/api/leads",
            json={
                "full_name": "Invalid Phone Lead",
                "phone": bad_phone,
            },
        )
        assert res.status_code in (400, 422)


def test_lead_update_and_phone_re_normalization(client):
    # Create lead
    create_res = client.post(
        "/api/leads",
        json={
            "full_name": "Original Name",
            "phone": "+65 9123 4567",
            "email": "original@example.com",
        },
    )
    assert create_res.status_code == 201
    lead_id = create_res.json()["id"]

    # Update with new phone, name, and consent
    update_res = client.patch(
        f"/api/leads/{lead_id}",
        json={
            "full_name": "Updated Name",
            "phone": "98765432",
            "consent_status": ConsentStatus.CONSENTED.value,
            "opt_out_status": OptOutStatus.ACTIVE.value,
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["full_name"] == "Updated Name"
    assert updated["phone"] == "98765432"
    assert updated["phone_normalized"] == "+6598765432"
    assert updated["consent_status"] == ConsentStatus.CONSENTED.value


def test_lead_foreign_key_relations(client):
    # 1. Create lead source
    src_res = client.post(
        "/api/lead-sources",
        json={"name": f"Source {uuid.uuid4().hex[:6]}", "source_type": LeadSourceType.WEBSITE.value},
    )
    source_id = src_res.json()["id"]

    # 2. Create agent (Module 1)
    agent_res = client.post(
        "/api/agents",
        json={"full_name": "Assigned Agent", "agency_name": "OrangeTee & Tie"},
    )
    agent_id = agent_res.json()["id"]

    # Get agent's auto-created WhatsApp profile
    wa_res = client.get(f"/api/agents/{agent_id}/whatsapp")
    whatsapp_profile_id = wa_res.json()["id"]

    # 3. Create lead linked to source, agent, and whatsapp profile
    lead_res = client.post(
        "/api/leads",
        json={
            "full_name": "Linked Lead",
            "phone": "+65 9111 2222",
            "source_id": source_id,
            "assigned_agent_id": agent_id,
            "assigned_whatsapp_profile_id": whatsapp_profile_id,
        },
    )
    assert lead_res.status_code == 201
    lead = lead_res.json()
    assert lead["source_id"] == source_id
    assert lead["assigned_agent_id"] == agent_id
    assert lead["assigned_whatsapp_profile_id"] == whatsapp_profile_id
    assert lead["source"]["name"] == src_res.json()["name"]

    # Test invalid foreign key rejects
    invalid_lead_res = client.post(
        "/api/leads",
        json={
            "full_name": "Bad FK Lead",
            "phone": "+65 9111 2222",
            "assigned_agent_id": str(uuid.uuid4()),
        },
    )
    assert invalid_lead_res.status_code == 404


def test_lead_validate_and_archive(client):
    # Create lead
    lead_res = client.post(
        "/api/leads",
        json={"full_name": "Action Lead", "phone": "91234567"},
    )
    lead_id = lead_res.json()["id"]

    # Call /validate
    val_res = client.post(f"/api/leads/{lead_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["valid"] is True
    assert val_data["phone_normalized"] == "+6591234567"

    # Status updated to VALIDATING
    get_res = client.get(f"/api/leads/{lead_id}")
    assert get_res.json()["status"] == LeadStatus.VALIDATING.value

    # Archive lead
    arch_res = client.post(f"/api/leads/{lead_id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["status"] == LeadStatus.ARCHIVED.value

    # Lead still retrievable (not hard-deleted)
    get_after_arch = client.get(f"/api/leads/{lead_id}")
    assert get_after_arch.status_code == 200
    assert get_after_arch.json()["status"] == LeadStatus.ARCHIVED.value


def test_routing_and_outreach_endpoints_empty_state(client, db):
    # Create lead
    lead_res = client.post(
        "/api/leads",
        json={"full_name": "History Lead", "phone": "+65 9333 4444"},
    )
    lead_id = uuid.UUID(lead_res.json()["id"])

    # Routing history should initially be empty
    rh_res = client.get(f"/api/leads/{lead_id}/routing-history")
    assert rh_res.status_code == 200
    assert rh_res.json() == []

    # Add a routing decision record directly in db to verify endpoint serialization
    decision = LeadRoutingDecision(
        lead_id=lead_id,
        route_name="SPACE_SCOUT",
        reason={"rule": "campaign_space_scout", "version": "v1"},
        rule_version="v1",
        manual_override=False,
    )
    db.add(decision)
    db.commit()

    rh_res2 = client.get(f"/api/leads/{lead_id}/routing-history")
    assert rh_res2.status_code == 200
    items = rh_res2.json()
    assert len(items) == 1
    assert items[0]["route_name"] == "SPACE_SCOUT"
    assert items[0]["reason"]["rule"] == "campaign_space_scout"

    # Outreach history initially empty
    outreach_res = client.get(f"/api/leads/{lead_id}/outreach")
    assert outreach_res.status_code == 200
    assert outreach_res.json() == []


def test_lead_import_batch_model(db):
    batch = LeadImportBatch(
        file_name="leads_oct_2026.csv",
        total_rows=100,
        valid_rows=95,
        invalid_rows=3,
        duplicate_rows=2,
        status=ImportBatchStatus.COMPLETED,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    assert batch.id is not None
    assert batch.file_name == "leads_oct_2026.csv"
    assert batch.valid_rows == 95
    assert batch.status == ImportBatchStatus.COMPLETED
