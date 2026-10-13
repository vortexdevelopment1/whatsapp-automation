import uuid
import pytest
from datetime import date
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.lead import Lead
from app.models.agent import Agent
from app.models.whatsapp import WhatsAppProfile
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.models.qualification_rule import QualificationRule
from app.models.qualification_decision import QualificationDecision
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
)
from app.services.qualification_decision_service import QualificationDecisionService


@pytest.fixture
def setup_lead_and_rule(db: Session):
    agent = Agent(
        full_name="Agent Marcus",
        phone="+6591112222",
        email=f"marcus_{uuid.uuid4().hex[:6]}@example.com",
        registration_number=f"R{uuid.uuid4().hex[:6].upper()}",
        agency_name="ERA Realty",
    )
    db.add(agent)
    db.commit()

    lead = Lead(
        phone="+6591234567",
        phone_normalized="+6591234567",
        full_name="Alex Tan",
        status=LeadStatus.CONTACTED,
        consent_status=ConsentStatus.CONSENTED,
        opt_out_status=OptOutStatus.ACTIVE,
        contact_eligibility=ContactEligibility.ELIGIBLE,
        assigned_agent_id=agent.id,
    )
    db.add(lead)
    db.commit()

    # Create active rule v1
    rule = QualificationRule(
        name="Standard Rental Qualification",
        version="qualification-v1",
        active=True,
        required_fields=[
            "preferred_locations",
            "budget_max",
            "property_type",
            "move_in_date",
            "lease_duration_months",
            "occupants",
        ],
        optional_fields=["furnishing", "bedrooms", "pet_details"],
        disqualification_rules=[],
        human_review_rules=["UNRESOLVED_CONFLICT", "MAX_CLARIFICATION_ATTEMPTS_EXCEEDED"],
    )
    db.add(rule)
    db.commit()

    return lead, rule


def create_complete_requirement(db: Session, lead_id: uuid.UUID) -> TenantRequirement:
    req = TenantRequirement(
        lead_id=lead_id,
        preferred_locations=["Novena"],
        budget_min=3000,
        budget_max=3500,
        currency="SGD",
        property_type="Condo",
        bedrooms=2,
        move_in_date="2026-11-01",
        lease_duration_months=12,
        occupants=2,
        furnishing="FURNISHED",
        qualification_status=QualificationStatus.IN_PROGRESS,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# Test 31 — Fully complete tenant -> QUALIFIED
def test_31_fully_complete_tenant(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True, evaluated_by="system")

    assert result["decision"] == "QUALIFIED"
    assert "ALL_REQUIRED_FIELDS_COMPLETE" in result["reason_codes"]
    assert "ALL_REQUIRED_FIELDS_VALID" in result["reason_codes"]
    assert "NO_BLOCKING_CLARIFICATIONS" in result["reason_codes"]
    assert result["missing_fields"] == []
    assert result["blocking_fields"] == []
    assert result["completion_percentage"] == 100
    assert result["rule_version"] == "qualification-v1"

    # Verify requirement updated
    db.refresh(lead)
    req = db.query(TenantRequirement).filter_by(lead_id=lead.id).first()
    assert req.qualification_status == QualificationStatus.QUALIFIED


# Test 32 — Missing required field -> NOT QUALIFIED
def test_32_missing_required_field(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = TenantRequirement(
        lead_id=lead.id,
        preferred_locations=["Novena"],
        budget_max=3500,
        property_type="Condo",
        move_in_date="2026-11-01",
        lease_duration_months=12,
        occupants=None,  # Missing
        qualification_status=QualificationStatus.IN_PROGRESS,
    )
    db.add(req)
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    assert result["decision"] == "IN_PROGRESS"
    assert "MISSING_REQUIRED_FIELDS" in result["reason_codes"]
    assert "occupants" in result["missing_fields"]
    assert result["completion_percentage"] < 100

    db.refresh(req)
    assert req.qualification_status == QualificationStatus.IN_PROGRESS


# Test 33 — Unresolved clarification -> NOT QUALIFIED
def test_33_unresolved_clarification(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = create_complete_requirement(db, lead.id)
    # Add history entry for move_in_date with PROPOSED status (needs confirmation)
    hist = TenantRequirementHistory(
        tenant_requirement_id=req.id,
        field_name="move_in_date",
        value="2026-11-01",
        status=RequirementFieldStatus.PROPOSED,
        source_type=RequirementSourceType.TENANT_MESSAGE,
    )
    db.add(hist)
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    assert result["decision"] != "QUALIFIED"
    assert "PENDING_CLARIFICATION" in result["reason_codes"]
    assert "move_in_date" in result["blocking_fields"]


# Test 34 — Conflict -> NEEDS_HUMAN_REVIEW
def test_34_conflict_needs_human_review(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = create_complete_requirement(db, lead.id)
    # Malformed conflict: budget_min > budget_max
    req.budget_min = 5000
    req.budget_max = 3000
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    assert result["decision"] == "NEEDS_HUMAN_REVIEW"
    assert "UNRESOLVED_REQUIREMENT_CONFLICT" in result["reason_codes"]
    assert "budget_min" in result["blocking_fields"]

    db.refresh(req)
    assert req.qualification_status == QualificationStatus.NEEDS_HUMAN_REVIEW


# Test 35 — Opted out -> DISQUALIFIED
def test_35_opted_out_lead(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)
    # Mark lead as opted out
    lead.opt_out_status = OptOutStatus.OPTED_OUT
    lead.contact_eligibility = ContactEligibility.INELIGIBLE
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    assert result["decision"] == "DISQUALIFIED"
    assert "CONTACT_NOT_ELIGIBLE" in result["reason_codes"]
    assert "LEAD_OPTED_OUT" in result["reason_codes"]

    db.refresh(lead)
    req = db.query(TenantRequirement).filter_by(lead_id=lead.id).first()
    assert req.qualification_status == QualificationStatus.DISQUALIFIED


# Test 36 — Archived lead -> Apply blocked
def test_36_archived_lead_blocked(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)
    lead.status = LeadStatus.ARCHIVED
    db.commit()

    service = QualificationDecisionService(db)
    # Preview should return DISQUALIFIED with LEAD_ARCHIVED
    preview = service.evaluate_qualification(lead.id, apply=False)
    assert preview["decision"] == "DISQUALIFIED"
    assert "LEAD_ARCHIVED" in preview["reason_codes"]

    # Apply should raise ValueError or block state transition
    with pytest.raises(ValueError, match="Cannot update qualification for an ARCHIVED lead"):
        service.evaluate_qualification(lead.id, apply=True)


# Test 37 — Configured disqualification rule
def test_37_configured_disqualification_rule(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = create_complete_requirement(db, lead.id)
    req.lease_duration_months = 3  # 3 months
    db.commit()

    # Add business rule: lease_duration_months minimum 6
    rule.disqualification_rules = [
        {
            "field": "lease_duration_months",
            "operator": "lt",
            "value": 6,
            "reason_code": "LEASE_DURATION_BELOW_MINIMUM",
        }
    ]
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    assert result["decision"] == "DISQUALIFIED"
    assert "LEASE_DURATION_BELOW_MINIMUM" in result["reason_codes"]
    assert "lease_duration_months" in result["blocking_fields"]


# Test 38 — No disqualification configured
def test_38_no_disqualification_configured(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = create_complete_requirement(db, lead.id)
    req.lease_duration_months = 3
    # Default rule has empty disqualification_rules
    rule.disqualification_rules = []
    db.commit()

    service = QualificationDecisionService(db)
    result = service.evaluate_qualification(lead.id, apply=True)

    # System should NOT invent a disqualification!
    assert result["decision"] != "DISQUALIFIED"
    assert result["decision"] == "QUALIFIED"


# Test 39 — State transition validation
def test_39_state_transitions(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    service = QualificationDecisionService(db)

    # Valid transition: IN_PROGRESS -> QUALIFIED (via authorized evaluation)
    assert service.validate_qualification_transition(
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFIED,
        is_authorized_override=True,
    ) is True

    # Forbidden transition: QUALIFIED -> NOT_STARTED without authorized reset
    with pytest.raises(ValueError, match="Invalid qualification transition"):
        service.validate_qualification_transition(
            QualificationStatus.QUALIFIED,
            QualificationStatus.NOT_STARTED,
            is_authorized_override=False,
        )


# Test 40 — Rule versioning
def test_40_rule_versioning(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)
    service = QualificationDecisionService(db)

    # First evaluation under rule v1
    res1 = service.evaluate_qualification(lead.id, apply=True)
    assert res1["rule_version"] == "qualification-v1"

    # Create active rule v2 and deactivate v1
    rule.active = False
    db.commit()

    rule_v2 = QualificationRule(
        name="Standard Rental Qualification v2",
        version="qualification-v2",
        active=True,
        required_fields=rule.required_fields,
        optional_fields=rule.optional_fields,
        disqualification_rules=[],
        human_review_rules=[],
    )
    db.add(rule_v2)
    db.commit()

    # Second evaluation records rule-v2
    res2 = service.evaluate_qualification(lead.id, apply=True)
    assert res2["rule_version"] == "qualification-v2"

    # Check decision history has both versions preserved
    history = service.get_decision_history(lead.id)
    versions = [h.rule_version for h in history]
    assert "qualification-v1" in versions
    assert "qualification-v2" in versions


# Test 41 — Idempotency
def test_41_idempotency(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)
    service = QualificationDecisionService(db)

    res1 = service.evaluate_qualification(lead.id, apply=True)
    res2 = service.evaluate_qualification(lead.id, apply=True)

    assert res1["decision"] == res2["decision"]
    assert res1["rule_version"] == res2["rule_version"]
    assert res1["completion_percentage"] == res2["completion_percentage"]

    # Requirement status remains QUALIFIED
    req = db.query(TenantRequirement).filter_by(lead_id=lead.id).first()
    assert req.qualification_status == QualificationStatus.QUALIFIED


# Test 42 — Human override
def test_42_human_override(db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    req = create_complete_requirement(db, lead.id)
    service = QualificationDecisionService(db)

    # Missing reason -> ValueError
    with pytest.raises(ValueError, match="Override reason is required"):
        service.evaluate_qualification(
            lead.id,
            apply=True,
            human_override_status="NEEDS_HUMAN_REVIEW",
            override_reason="",
        )

    # Valid authorized override
    res = service.evaluate_qualification(
        lead.id,
        apply=True,
        human_override_status="NEEDS_HUMAN_REVIEW",
        override_reason="Tenant requires specialized lease terms requiring senior manager approval.",
        evaluated_by="senior_manager",
    )

    assert res["decision"] == "NEEDS_HUMAN_REVIEW"
    assert "HUMAN_OVERRIDE" in res["reason_codes"]
    assert res["evaluation_source"] == "HUMAN"
    assert res["evaluated_by"] == "senior_manager"

    db.refresh(req)
    assert req.qualification_status == QualificationStatus.NEEDS_HUMAN_REVIEW

    # History record stores human source
    history = service.get_decision_history(lead.id)
    assert history[0].evaluation_source == "HUMAN"
    assert history[0].evaluated_by == "senior_manager"


# Integration test with FastAPI endpoint
def test_qualification_evaluate_api(client: TestClient, db: Session, setup_lead_and_rule):
    lead, rule = setup_lead_and_rule
    create_complete_requirement(db, lead.id)

    # 1. Preview mode (apply=False)
    resp = client.post(f"/api/leads/{lead.id}/qualification/evaluate", json={"apply": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "QUALIFIED"
    assert data["rule_version"] == "qualification-v1"

    # Status not yet updated in DB
    req = db.query(TenantRequirement).filter_by(lead_id=lead.id).first()
    assert req.qualification_status == QualificationStatus.IN_PROGRESS

    # 2. Apply mode (apply=True)
    resp = client.post(f"/api/leads/{lead.id}/qualification/evaluate", json={"apply": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "QUALIFIED"

    # Status now updated in DB
    db.refresh(req)
    assert req.qualification_status == QualificationStatus.QUALIFIED

    # 3. Decision history endpoint
    resp = client.get(f"/api/leads/{lead.id}/qualification/decision-history")
    assert resp.status_code == 200
    hist = resp.json()
    assert len(hist) >= 1
    assert hist[0]["decision"] == "QUALIFIED"

    # 4. Status endpoint
    resp = client.get(f"/api/leads/{lead.id}/qualification/status")
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["latest_decision"] is not None
    assert status_data["latest_decision"]["decision"] == "QUALIFIED"
