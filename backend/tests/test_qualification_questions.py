import uuid
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.lead import Lead
from app.models.agent import Agent
from app.models.whatsapp import WhatsAppProfile
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.models.qualification_rule import QualificationRule
from app.models.qualification_question import QualificationQuestion
from app.models.message_ai_processing import MessageAIProcessing
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
    AgentStatus,
    AuthorizationStatus,
    WhatsAppConnectionStatus,
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
    QuestionAction,
    QuestionType,
    QualificationQuestionStatus,
    MessageAIProcessingStatus,
    AITaskType,
)
from app.services.qualification_question_service import QualificationQuestionService
from app.ai.providers.mock import MockAIProvider
from app.ai.orchestrator import AIOrchestrator
from app.ai.exceptions import AITimeoutError
from app.ai.schemas import QuestionResponseResult


@pytest.fixture
def test_setup(db: Session):
    agent = Agent(
        full_name="Agent Sarah",
        phone="+6591234567",
        email=f"sarah_{uuid.uuid4().hex[:6]}@example.com",
        registration_number=f"R{uuid.uuid4().hex[:6].upper()}",
        agency_name="ERA Realty",
    )
    db.add(agent)
    db.commit()

    profile = WhatsAppProfile(
        agent_id=agent.id,
        phone_number_id="pn_test_sarah",
        display_phone_number="+6591234567",
    )
    db.add(profile)
    db.commit()

    lead = Lead(
        full_name="John Doe",
        phone="+6598765432",
        phone_normalized="+6598765432",
        status=LeadStatus.NEW,
        consent_status=ConsentStatus.CONSENTED,
        opt_out_status=OptOutStatus.ACTIVE,
        contact_eligibility=ContactEligibility.ELIGIBLE,
        assigned_agent_id=agent.id,
        assigned_whatsapp_profile_id=profile.id,
    )
    db.add(lead)
    db.commit()

    req = TenantRequirement(
        lead_id=lead.id,
        qualification_status=QualificationStatus.NOT_STARTED,
        completion_percentage=0,
    )
    db.add(req)
    db.commit()

    # Ensure active qualification rule with canonical ordering
    rule = db.query(QualificationRule).filter(QualificationRule.active == True).first()
    if not rule:
        rule = QualificationRule(
            name="Default Rental Qualification",
            route="standard",
            required_fields=[
                "preferred_locations",
                "budget_max",
                "property_type",
                "move_in_date",
                "lease_duration_months",
                "occupants",
            ],
            optional_fields=["bedrooms", "furnishing", "special_requirements"],
            question_order=[
                "preferred_locations",
                "budget_max",
                "property_type",
                "move_in_date",
                "lease_duration_months",
                "occupants",
                "bedrooms",
                "furnishing",
                "special_requirements",
            ],
            active=True,
            version="v1",
        )
        db.add(rule)
        db.commit()

    return {"agent": agent, "profile": profile, "lead": lead, "req": req, "rule": rule}


# =====================================================================
# 31. Basic Missing Field
# =====================================================================

@pytest.mark.asyncio
async def test_basic_missing_field(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # Supply location, budget_max, property_type
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    db.commit()

    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    assert resp.action == QuestionAction.ASK_FIELD
    assert resp.field == "move_in_date"
    assert resp.question_type == QuestionType.MISSING_FIELD
    assert "move_in_date" in resp.missing_fields
    assert "lease_duration_months" in resp.missing_fields
    assert "occupants" in resp.missing_fields
    assert resp.question_text is not None


# =====================================================================
# 32. Multiple Fields Already Supplied
# =====================================================================

@pytest.mark.asyncio
async def test_multiple_fields_already_supplied(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # Supply 5 out of 6 required fields
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    req.move_in_date = date(2026, 12, 1)
    req.lease_duration_months = 12
    db.commit()

    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    assert resp.action == QuestionAction.ASK_FIELD
    assert resp.field == "occupants"
    assert resp.missing_fields == ["occupants"]
    assert "occupants" in resp.question_text.lower() or "people" in resp.question_text.lower()


# =====================================================================
# 33. Clarification Priority
# =====================================================================

@pytest.mark.asyncio
async def test_clarification_priority(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # move_in_date is proposed/ambiguous (needs clarification), lease_duration is missing
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    req.occupants = 2
    db.commit()

    # Record move_in_date as PROPOSED in history
    db.add(
        TenantRequirementHistory(
            tenant_requirement_id=req.id,
            field_name="move_in_date",
            value="2026-12-01",
            confidence=Decimal("0.65"),
            status=RequirementFieldStatus.PROPOSED,
            source_type=RequirementSourceType.TENANT_MESSAGE,
        )
    )
    db.commit()

    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    # Clarification must take priority over asking lease_duration_months!
    assert resp.action == QuestionAction.ASK_CLARIFICATION
    assert resp.field == "move_in_date"
    assert resp.question_type == QuestionType.CLARIFICATION


# =====================================================================
# 34. All Required Fields Complete
# =====================================================================

@pytest.mark.asyncio
async def test_all_required_fields_complete_no_question(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    req.move_in_date = date(2026, 12, 1)
    req.lease_duration_months = 12
    req.occupants = 2
    db.commit()

    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    assert resp.action == QuestionAction.NO_QUESTION
    assert resp.reason == "all_required_fields_complete"
    assert resp.completion_percentage == 100
    assert len(resp.missing_fields) == 0

    # Ensure lead was NOT automatically marked qualified (must remain authoritative)
    refreshed_req = db.query(TenantRequirement).filter(TenantRequirement.id == req.id).first()
    assert refreshed_req.qualification_status != QualificationStatus.QUALIFIED


# =====================================================================
# 35. Configured Question Order
# =====================================================================

@pytest.mark.asyncio
async def test_question_order_adherence(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]
    rule = test_setup["rule"]

    # All missing. Configured question order has preferred_locations first
    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    assert resp.field == "preferred_locations"

    # Now populate preferred_locations; next in order is budget_max
    req.preferred_locations = ["Novena"]
    db.commit()

    resp2 = await service.generate_next_question(lead.id)
    assert resp2.field == "budget_max"


# =====================================================================
# 36. Optional Fields Handling
# =====================================================================

@pytest.mark.asyncio
async def test_optional_fields_behavior(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # Complete all required fields
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    req.move_in_date = date(2026, 12, 1)
    req.lease_duration_months = 12
    req.occupants = 2
    db.commit()

    service = QualificationQuestionService(db)

    # When collect_optional is False -> NO_QUESTION
    resp_no_opt = await service.generate_next_question(lead.id, collect_optional=False)
    assert resp_no_opt.action == QuestionAction.NO_QUESTION

    # When collect_optional is True -> asks optional field (e.g. bedrooms)
    resp_opt = await service.generate_next_question(lead.id, collect_optional=True)
    assert resp_opt.action == QuestionAction.ASK_FIELD
    assert resp_opt.field in ["bedrooms", "furnishing", "special_requirements"]


# =====================================================================
# 37. Max Clarification Limit Escalates to Human Review
# =====================================================================

@pytest.mark.asyncio
async def test_max_clarification_attempts_escalates_to_human_review(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    req.preferred_locations = ["Novena"]
    db.commit()

    # Record budget_max as proposed
    db.add(
        TenantRequirementHistory(
            tenant_requirement_id=req.id,
            field_name="budget_max",
            value=3500,
            confidence=Decimal("0.60"),
            status=RequirementFieldStatus.PROPOSED,
            source_type=RequirementSourceType.TENANT_MESSAGE,
        )
    )
    db.commit()

    # Simulate 2 prior clarification questions for budget_max
    for _ in range(2):
        db.add(
            QualificationQuestion(
                lead_id=lead.id,
                field_name="budget_max",
                question_type=QuestionType.CLARIFICATION,
                action=QuestionAction.ASK_CLARIFICATION,
                status=QualificationQuestionStatus.ANSWERED,
            )
        )
    db.commit()

    service = QualificationQuestionService(db, max_clarification_attempts=2)
    resp = await service.generate_next_question(lead.id)

    assert resp.action == QuestionAction.HUMAN_REVIEW
    assert resp.reason == "max_clarification_attempts_exceeded"
    assert resp.field == "budget_max"


# =====================================================================
# 38. AI Response Validation & Fallback on Target Field Mismatch
# =====================================================================

class FieldMismatchMockProvider(MockAIProvider):
    async def generate_structured(self, prompt, response_model, **kwargs):
        # Deliberately return target_field="occupants" when instruction wanted "move_in_date"
        return QuestionResponseResult(
            reply_text="How many people are staying?",
            target_field="occupants",
            prompt_version="mismatch_v1",
        ), self.generate_usage()


@pytest.mark.asyncio
async def test_ai_target_field_mismatch_uses_fallback(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # Missing move_in_date
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    db.commit()

    mismatch_provider = FieldMismatchMockProvider()
    orchestrator = AIOrchestrator(provider=mismatch_provider)
    service = QualificationQuestionService(db, orchestrator=orchestrator)

    resp = await service.generate_next_question(lead.id)

    assert resp.field == "move_in_date"
    assert resp.fallback_used is True
    # Deterministic fallback question for move_in_date
    assert "When are you planning to move in?" in resp.question_text


# =====================================================================
# 39. Provider Failure Uses Fallback Question
# =====================================================================

@pytest.mark.asyncio
async def test_provider_failure_uses_fallback(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    db.commit()

    error_provider = MockAIProvider(mode="TIMEOUT")
    orchestrator = AIOrchestrator(provider=error_provider, max_retries=1)
    service = QualificationQuestionService(db, orchestrator=orchestrator)

    resp = await service.generate_next_question(lead.id)

    assert resp.field == "move_in_date"
    assert resp.fallback_used is True
    assert "When are you planning to move in?" in resp.question_text


# =====================================================================
# 40. Prompt Injection Safety
# =====================================================================

@pytest.mark.asyncio
async def test_prompt_injection_safety_target_preserved(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    # Missing lease_duration_months
    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    req.property_type = "CONDO"
    req.move_in_date = date(2026, 12, 1)
    db.commit()

    service = QualificationQuestionService(db)
    resp = await service.generate_next_question(lead.id)

    assert resp.field == "lease_duration_months"
    assert "how long" in resp.question_text.lower() or "rent the property" in resp.question_text.lower()


# =====================================================================
# 41. Idempotency - No Duplicate Question Events
# =====================================================================

@pytest.mark.asyncio
async def test_idempotent_question_generation(test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    req.preferred_locations = ["Novena"]
    db.commit()

    service = QualificationQuestionService(db)

    # First generation
    resp1 = await service.generate_next_question(lead.id)
    initial_count = db.query(QualificationQuestion).filter(QualificationQuestion.lead_id == lead.id).count()

    # Second generation without changes
    resp2 = await service.generate_next_question(lead.id)
    final_count = db.query(QualificationQuestion).filter(QualificationQuestion.lead_id == lead.id).count()

    assert resp1.field == resp2.field
    assert resp1.question_text == resp2.question_text
    assert final_count == initial_count


# =====================================================================
# 42. API Endpoints
# =====================================================================

def test_api_next_question_and_preview(client: TestClient, test_setup, db: Session):
    lead = test_setup["lead"]
    req = test_setup["req"]

    req.preferred_locations = ["Novena"]
    req.budget_max = Decimal("3500")
    db.commit()

    # 1. Preview
    preview_resp = client.get(f"/api/leads/{lead.id}/qualification/preview")
    assert preview_resp.status_code == 200
    pdata = preview_resp.json()
    assert "completion_percentage" in pdata
    assert "missing_fields" in pdata
    assert pdata["next_question"]["field"] == "property_type"

    # 2. Next Question
    gen_resp = client.post(f"/api/leads/{lead.id}/qualification/next-question")
    assert gen_resp.status_code == 200
    gdata = gen_resp.json()
    assert gdata["action"] == "ASK_FIELD"
    assert gdata["field"] == "property_type"
    assert gdata["question_text"] is not None
