import uuid
import pytest
from app.models.lead import Lead
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
)


def test_exact_duplicate(client):
    # 1. Create original lead
    res1 = client.post(
        "/api/leads",
        json={"full_name": "Original Lead", "phone": "+65 9123 4567"},
    )
    assert res1.status_code == 201
    lead1_id = res1.json()["id"]

    # 2. Create second lead with exact same phone
    res2 = client.post(
        "/api/leads",
        json={"full_name": "Duplicate Lead", "phone": "+65 9123 4567"},
    )
    assert res2.status_code == 201
    lead2_id = res2.json()["id"]

    # 3. Check duplicate on second lead
    dup_res = client.post(f"/api/leads/{lead2_id}/check-duplicate")
    assert dup_res.status_code == 200
    data = dup_res.json()
    assert data["duplicate"] is True
    assert data["existing_lead_id"] == lead1_id
    assert "normalized_phone_match" in data["match_reasons"]
    assert data["existing_lead"]["full_name"] == "Original Lead"

    # Status of lead 2 should be DUPLICATE
    get_res = client.get(f"/api/leads/{lead2_id}")
    assert get_res.json()["status"] == LeadStatus.DUPLICATE.value


def test_formatting_variation_duplicate(client):
    # Create original lead with formatted phone
    res1 = client.post(
        "/api/leads",
        json={"full_name": "Formatted Lead", "phone": "+65 9123 4567"},
    )
    lead1_id = res1.json()["id"]

    # Create second lead with unformatted local number
    res2 = client.post(
        "/api/leads",
        json={"full_name": "Unformatted Lead", "phone": "91234567"},
    )
    lead2_id = res2.json()["id"]

    # Check duplicate
    dup_res = client.post(f"/api/leads/{lead2_id}/check-duplicate")
    assert dup_res.status_code == 200
    data = dup_res.json()
    assert data["duplicate"] is True
    assert data["existing_lead_id"] == lead1_id
    assert "normalized_phone_match" in data["match_reasons"]


def test_non_duplicate(client):
    res1 = client.post(
        "/api/leads",
        json={"full_name": "Alice", "phone": "+65 9111 0001"},
    )
    res2 = client.post(
        "/api/leads",
        json={"full_name": "Bob", "phone": "+65 9222 0002"},
    )
    lead2_id = res2.json()["id"]

    dup_res = client.post(f"/api/leads/{lead2_id}/check-duplicate")
    assert dup_res.status_code == 200
    data = dup_res.json()
    assert data["duplicate"] is False
    assert data["existing_lead_id"] is None
    assert data["match_reasons"] == []


def test_self_match_excluded(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "Solo Lead", "phone": "+65 9333 0003"},
    )
    lead_id = res.json()["id"]

    # Checking duplicate on self when no other leads match must return duplicate=False
    dup_res = client.post(f"/api/leads/{lead_id}/check-duplicate")
    assert dup_res.status_code == 200
    assert dup_res.json()["duplicate"] is False


def test_duplicate_override_requires_reason(client):
    # Setup duplicate
    res1 = client.post("/api/leads", json={"full_name": "Lead A", "phone": "+65 9444 0004"})
    res2 = client.post("/api/leads", json={"full_name": "Lead B", "phone": "+65 9444 0004"})
    lead2_id = res2.json()["id"]

    client.post(f"/api/leads/{lead2_id}/check-duplicate")

    # 1. Reject empty reason
    empty_res = client.post(f"/api/leads/{lead2_id}/duplicate-override", json={"reason": ""})
    assert empty_res.status_code == 400
    assert "reason is required" in empty_res.json()["detail"].lower()

    # 2. Reject whitespace-only reason
    ws_res = client.post(f"/api/leads/{lead2_id}/duplicate-override", json={"reason": "   "})
    assert ws_res.status_code == 400

    # 3. Accept valid reason
    ok_res = client.post(
        f"/api/leads/{lead2_id}/duplicate-override",
        json={"reason": "Customer inquiring for different unit at Marina Bay Suites"},
    )
    assert ok_res.status_code == 200
    data = ok_res.json()
    assert data["duplicate_override"] is True
    assert data["duplicate_override_reason"] == "Customer inquiring for different unit at Marina Bay Suites"
    assert data["status"] == LeadStatus.VALIDATING.value


def test_opted_out_blocked(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "OptOut Lead", "phone": "+65 9555 0005", "consent_status": ConsentStatus.CONSENTED.value},
    )
    lead_id = res.json()["id"]

    # Mark opt-out
    opt_res = client.post(f"/api/leads/{lead_id}/mark-opt-out", json={"reason": "Customer requested STOP"})
    assert opt_res.status_code == 200
    assert opt_res.json()["opt_out_status"] == OptOutStatus.OPTED_OUT.value
    assert opt_res.json()["status"] == LeadStatus.OPTED_OUT.value

    # Check eligibility
    elig_res = client.post(f"/api/leads/{lead_id}/check-contact-eligibility")
    assert elig_res.status_code == 200
    data = elig_res.json()
    assert data["eligibility"] == ContactEligibility.INELIGIBLE.value
    assert "opted_out" in data["reasons"]


def test_not_consented_blocked(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "No Consent Lead", "phone": "+65 9666 0006", "consent_status": ConsentStatus.NOT_CONSENTED.value},
    )
    lead_id = res.json()["id"]

    elig_res = client.post(f"/api/leads/{lead_id}/check-contact-eligibility")
    assert elig_res.status_code == 200
    data = elig_res.json()
    assert data["eligibility"] == ContactEligibility.INELIGIBLE.value
    assert "not_consented" in data["reasons"]


def test_unknown_consent_not_automatically_eligible(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "Unknown Consent Lead", "phone": "+65 9777 0007"},
    )
    lead_id = res.json()["id"]

    elig_res = client.post(f"/api/leads/{lead_id}/check-contact-eligibility")
    assert elig_res.status_code == 200
    data = elig_res.json()
    # Must NOT be ELIGIBLE
    assert data["eligibility"] != ContactEligibility.ELIGIBLE.value
    assert data["eligibility"] == ContactEligibility.UNKNOWN.value
    assert "unknown_consent" in data["reasons"]


def test_invalid_phone_blocked(client, db):
    # Manually create lead with invalid normalized phone in DB
    lead = Lead(
        full_name="Bad Phone Lead",
        phone="invalid_phone",
        phone_normalized="invalid_phone",
        consent_status=ConsentStatus.CONSENTED,
        opt_out_status=OptOutStatus.ACTIVE,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    elig_res = client.post(f"/api/leads/{lead.id}/check-contact-eligibility")
    assert elig_res.status_code == 200
    data = elig_res.json()
    assert data["eligibility"] == ContactEligibility.INELIGIBLE.value
    assert "invalid_phone" in data["reasons"]


def test_archived_lead_blocked(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "Archived Lead", "phone": "+65 9888 0008", "consent_status": ConsentStatus.CONSENTED.value},
    )
    lead_id = res.json()["id"]

    # Archive
    client.post(f"/api/leads/{lead_id}/archive")

    # Check eligibility
    elig_res = client.post(f"/api/leads/{lead_id}/check-contact-eligibility")
    assert elig_res.status_code == 200
    data = elig_res.json()
    assert data["eligibility"] == ContactEligibility.INELIGIBLE.value
    assert "archived_lead" in data["reasons"]


def test_restore_contact_requires_authorization(client):
    res = client.post(
        "/api/leads",
        json={"full_name": "Restore Lead", "phone": "+65 9876 5432"},
    )
    assert res.status_code == 201
    lead_id = res.json()["id"]

    client.post(f"/api/leads/{lead_id}/mark-opt-out")

    # 1. Attempt to restore without authorization -> 403 Forbidden
    unauth_res = client.post(f"/api/leads/{lead_id}/restore-contact", json={})
    assert unauth_res.status_code == 403

    # 2. Restore with authorization in payload
    auth_res = client.post(
        f"/api/leads/{lead_id}/restore-contact",
        json={"authorized_by": "compliance_officer_1", "reason": "Customer called to re-subscribe"},
    )
    assert auth_res.status_code == 200
    data = auth_res.json()
    assert data["opt_out_status"] == OptOutStatus.ACTIVE.value

    # 3. Test with Authorization header
    client.post(f"/api/leads/{lead_id}/mark-opt-out")
    header_res = client.post(
        f"/api/leads/{lead_id}/restore-contact",
        headers={"Authorization": "Bearer admin_token_123"},
        json={"reason": "Customer email confirmation"},
    )
    assert header_res.status_code == 200
    assert header_res.json()["opt_out_status"] == OptOutStatus.ACTIVE.value


def test_audit_logs_generated(client):
    res1 = client.post("/api/leads", json={"full_name": "Audit Lead 1", "phone": "+65 8111 0001"})
    lead1_id = res1.json()["id"]

    res2 = client.post("/api/leads", json={"full_name": "Audit Lead 2", "phone": "+65 8111 0001"})
    lead2_id = res2.json()["id"]

    # Trigger duplicate detection
    client.post(f"/api/leads/{lead2_id}/check-duplicate")

    # Trigger duplicate override
    client.post(f"/api/leads/{lead2_id}/duplicate-override", json={"reason": "Audit test override"})

    # Trigger eligibility check
    client.post(f"/api/leads/{lead2_id}/check-contact-eligibility")

    # Trigger opt-out
    client.post(f"/api/leads/{lead2_id}/mark-opt-out", json={"reason": "Audit opt-out"})

    # Trigger restore contact
    client.post(
        f"/api/leads/{lead2_id}/restore-contact",
        json={"authorized_by": "admin", "reason": "Audit restore"},
    )

    # Fetch audit logs
    audit_res = client.get(f"/api/audit-logs?entity_id={lead2_id}")
    assert audit_res.status_code == 200
    actions = [log["action"] for log in audit_res.json()]

    assert "LEAD_CREATED" in actions
    assert "LEAD_DUPLICATE_DETECTED" in actions
    assert "DUPLICATE_OVERRIDE" in actions
    assert "CONTACT_ELIGIBILITY_CHECKED" in actions
    assert "LEAD_OPTED_OUT" in actions
    assert "LEAD_CONTACT_RESTORED" in actions
