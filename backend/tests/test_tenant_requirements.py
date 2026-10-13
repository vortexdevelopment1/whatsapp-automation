import uuid
from datetime import date, timedelta
import pytest
from app.models.tenant_requirement import TenantRequirement
from app.models.qualification_rule import QualificationRule
from app.models.enums import (
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
    FurnishingType,
)
from app.services.tenant_requirement_service import TenantRequirementService


def test_tenant_requirement_database_and_one_to_one(client):
    # 1. Create a lead
    lead_res = client.post("/api/leads", json={"full_name": "Req Tenant", "phone": "+65 9123 4567"})
    assert lead_res.status_code == 201
    lead_id = lead_res.json()["id"]

    # 2. Create requirement profile
    req_payload = {
        "preferred_locations": ["Novena", "Newton"],
        "budget_min": 3000,
        "budget_max": 3500,
        "currency": "SGD",
        "property_type": "Condo",
        "bedrooms": 2,
        "move_in_date": str(date.today() + timedelta(days=30)),
        "lease_duration_months": 12,
        "occupants": 2,
        "furnishing": FurnishingType.FURNISHED.value,
        "special_requirements": {"pets": True},
    }
    create_res = client.post(f"/api/leads/{lead_id}/requirements", json=req_payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["lead_id"] == lead_id
    assert data["property_type"] == "Condo"
    assert data["preferred_locations"] == ["Novena", "Newton"]
    assert data["qualification_status"] == QualificationStatus.NOT_STARTED.value
    # All 6 required fields are provided
    assert data["completion_percentage"] == 100

    # 3. Attempting to create duplicate requirement profile for same lead must fail
    dup_res = client.post(f"/api/leads/{lead_id}/requirements", json=req_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()


def test_validation_rules(client):
    lead_res = client.post("/api/leads", json={"full_name": "Validation Tenant", "phone": "+65 9234 5678"})
    lead_id = lead_res.json()["id"]

    # 1. Negative budget rejected
    bad_budget = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_max": -100, "phone": "+65 9234 5678"},
    )
    assert bad_budget.status_code == 422

    # 2. Budget min > max rejected
    min_gt_max = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_min": 4000, "budget_max": 3000},
    )
    assert min_gt_max.status_code == 422

    # 3. Invalid occupants count (<= 0) rejected
    bad_occupants = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"occupants": 0},
    )
    assert bad_occupants.status_code == 422

    # 4. Invalid lease duration (<= 0) rejected
    bad_lease = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"lease_duration_months": -6},
    )
    assert bad_lease.status_code == 422

    # 5. Invalid furnishing value rejected
    bad_furnishing = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"furnishing": "SUPER_LUXURY_CUSTOM"},
    )
    assert bad_furnishing.status_code == 422

    # 6. Valid multiple locations accepted and optional fields allowed blank
    valid_res = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={
            "preferred_locations": ["Orchard", "Somerset", "Dhoby Ghaut"],
            "budget_max": 4500,
        },
    )
    assert valid_res.status_code == 201
    assert valid_res.json()["preferred_locations"] == ["Orchard", "Somerset", "Dhoby Ghaut"]
    assert valid_res.json()["property_type"] is None
    assert valid_res.json()["bedrooms"] is None


def test_field_provenance_and_history_supersession(client):
    lead_res = client.post("/api/leads", json={"full_name": "History Tenant", "phone": "+65 9345 6789"})
    lead_id = lead_res.json()["id"]

    # Step 1: Initial budget = 3000
    create_res = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_max": 3000, "preferred_locations": ["Novena"]},
    )
    assert create_res.status_code == 201

    # Check history after initial creation
    hist_res1 = client.get(f"/api/leads/{lead_id}/requirements/history")
    assert hist_res1.status_code == 200
    hist1 = hist_res1.json()
    budget_entries1 = [h for h in hist1 if h["field_name"] == "budget_max"]
    assert len(budget_entries1) == 1
    assert float(budget_entries1[0]["value"]) == 3000.0
    assert budget_entries1[0]["status"] == RequirementFieldStatus.CONFIRMED.value
    assert budget_entries1[0]["source_type"] == RequirementSourceType.HUMAN_OPERATOR.value

    # Step 2: Tenant updates budget to 3500
    update_res = client.patch(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_max": 3500},
    )
    assert update_res.status_code == 200
    assert float(update_res.json()["budget_max"]) == 3500.0

    # Step 3: Check history after update
    hist_res2 = client.get(f"/api/leads/{lead_id}/requirements/history")
    assert hist_res2.status_code == 200
    hist2 = hist_res2.json()
    budget_entries2 = [h for h in hist2 if h["field_name"] == "budget_max"]
    assert len(budget_entries2) == 2

    # Verify no history is silently deleted: 3000 is SUPERSEDED, 3500 is CONFIRMED
    current_entry = next(h for h in budget_entries2 if float(h["value"]) == 3500.0)
    superseded_entry = next(h for h in budget_entries2 if float(h["value"]) == 3000.0)

    assert current_entry["status"] == RequirementFieldStatus.CONFIRMED.value
    assert superseded_entry["status"] == RequirementFieldStatus.SUPERSEDED.value



def test_missing_field_engine_and_completion_percentage(client):
    lead_res = client.post("/api/leads", json={"full_name": "Progress Tenant", "phone": "+65 9456 7890"})
    lead_id = lead_res.json()["id"]

    # 1. Create with 0 required fields filled
    create_res = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"currency": "SGD"},
    )
    assert create_res.status_code == 201
    assert create_res.json()["completion_percentage"] == 0

    # Check missing fields
    missing_res1 = client.get(f"/api/leads/{lead_id}/requirements/missing")
    assert missing_res1.status_code == 200
    missing1 = missing_res1.json()
    assert set(missing1) == {
        "preferred_locations",
        "budget_max",
        "property_type",
        "move_in_date",
        "lease_duration_months",
        "occupants",
    }

    # Check progress endpoint
    prog_res1 = client.get(f"/api/leads/{lead_id}/qualification-progress")
    assert prog_res1.status_code == 200
    prog1 = prog_res1.json()
    assert prog1["completion_percentage"] == 0
    assert prog1["ready"] is False
    assert len(prog1["completed_fields"]) == 0

    # 2. Complete 3 of 6 required fields: locations, budget_max, property_type
    update_res1 = client.patch(
        f"/api/leads/{lead_id}/requirements",
        json={
            "preferred_locations": ["Bishan", "Toa Payoh"],
            "budget_max": 3200,
            "property_type": "HDB",
            # Optional field added: bedrooms should NOT alter required completion percentage
            "bedrooms": 3,
        },
    )
    assert update_res1.status_code == 200
    assert update_res1.json()["completion_percentage"] == 50
    assert update_res1.json()["qualification_status"] == QualificationStatus.IN_PROGRESS.value

    missing_res2 = client.get(f"/api/leads/{lead_id}/requirements/missing")
    missing2 = missing_res2.json()
    assert sorted(missing2) == sorted(["move_in_date", "lease_duration_months", "occupants"])

    prog_res2 = client.get(f"/api/leads/{lead_id}/qualification-progress")
    prog2 = prog_res2.json()
    assert prog2["completion_percentage"] == 50
    assert prog2["ready"] is False
    assert set(prog2["completed_fields"]) == {"preferred_locations", "budget_max", "property_type"}

    # 3. Complete remaining 3 required fields
    update_res2 = client.patch(
        f"/api/leads/{lead_id}/requirements",
        json={
            "move_in_date": str(date.today() + timedelta(days=14)),
            "lease_duration_months": 24,
            "occupants": 3,
        },
    )
    assert update_res2.status_code == 200
    assert update_res2.json()["completion_percentage"] == 100

    prog_res3 = client.get(f"/api/leads/{lead_id}/qualification-progress")
    prog3 = prog_res3.json()
    assert prog3["completion_percentage"] == 100
    assert prog3["ready"] is True
    assert len(prog3["missing_fields"]) == 0


def test_qualification_rules_api(client):
    # 1. List qualification rules
    rules_res = client.get("/api/qualification-rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()
    assert len(rules) >= 1
    default_rule = rules[0]
    assert "preferred_locations" in default_rule["required_fields"]

    # 2. Get qualification rule by ID
    get_res = client.get(f"/api/qualification-rules/{default_rule['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == default_rule["name"]

    # 3. Create custom route qualification rule
    custom_rule_payload = {
        "name": "Luxury Coliving Qualification Rule",
        "route": "COLIVING_LUXURY",
        "required_fields": ["preferred_locations", "budget_max", "move_in_date"],
        "optional_fields": ["special_requirements"],
        "question_order": ["preferred_locations", "budget_max", "move_in_date", "special_requirements"],
        "active": True,
        "version": "v1.1",
    }
    create_rule_res = client.post("/api/qualification-rules", json=custom_rule_payload)
    assert create_rule_res.status_code == 201
    assert create_rule_res.json()["route"] == "COLIVING_LUXURY"


def test_api_error_handling_and_audit_logging(client):
    # 1. Non-existent lead returns 404
    fake_lead_id = uuid.uuid4()
    not_found = client.get(f"/api/leads/{fake_lead_id}/requirements")
    assert not_found.status_code == 404

    # 2. Create lead and test audit logs
    lead_res = client.post("/api/leads", json={"full_name": "Audit Tenant", "phone": "+65 9567 8901"})
    lead_id = lead_res.json()["id"]

    create_req = client.post(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_max": 2800, "property_type": "Studio"},
    )
    req_id = create_req.json()["id"]

    client.patch(
        f"/api/leads/{lead_id}/requirements",
        json={"budget_max": 3100},
    )

    # Verify audit logs for TenantRequirement
    audit_res = client.get(f"/api/audit-logs?entity_type=TenantRequirement&entity_id={req_id}")
    assert audit_res.status_code == 200
    actions = [a["action"] for a in audit_res.json()]
    assert "TENANT_REQUIREMENT_CREATED" in actions
    assert "TENANT_REQUIREMENT_UPDATED" in actions
