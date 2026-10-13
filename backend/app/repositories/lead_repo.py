import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.lead import Lead
from app.models.lead_routing import LeadRoutingDecision
from app.models.lead_outreach import LeadOutreach
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.schemas.lead import LeadCreate
from app.schemas.lead_routing import LeadRoutingDecisionCreate


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, lead_id: uuid.UUID) -> Optional[Lead]:
        return self.db.query(Lead).filter(Lead.id == lead_id).first()

    def get_by_phone_normalized(self, phone_normalized: str) -> Optional[Lead]:
        return (
            self.db.query(Lead)
            .filter(Lead.phone_normalized == phone_normalized)
            .order_by(Lead.created_at.desc())
            .first()
        )

    def list_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[LeadStatus] = None,
        source_id: Optional[uuid.UUID] = None,
        assigned_agent_id: Optional[uuid.UUID] = None,
        consent_status: Optional[ConsentStatus] = None,
        opt_out_status: Optional[OptOutStatus] = None,
        contact_eligibility: Optional[ContactEligibility] = None,
        search: Optional[str] = None,
    ) -> List[Lead]:
        query = self.db.query(Lead)

        if status:
            query = query.filter(Lead.status == status)
        if source_id:
            query = query.filter(Lead.source_id == source_id)
        if assigned_agent_id:
            query = query.filter(Lead.assigned_agent_id == assigned_agent_id)
        if consent_status:
            query = query.filter(Lead.consent_status == consent_status)
        if opt_out_status:
            query = query.filter(Lead.opt_out_status == opt_out_status)
        if contact_eligibility:
            query = query.filter(Lead.contact_eligibility == contact_eligibility)
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Lead.full_name.ilike(search_term),
                    Lead.phone.ilike(search_term),
                    Lead.phone_normalized.ilike(search_term),
                    Lead.email.ilike(search_term),
                )
            )

        return query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()

    def create(self, data: LeadCreate, phone_normalized: str) -> Lead:
        lead = Lead(
            full_name=data.full_name.strip() if data.full_name else None,
            phone=data.phone.strip(),
            phone_normalized=phone_normalized,
            email=data.email.strip().lower() if data.email else None,
            source_id=data.source_id,
            status=LeadStatus.NEW,
            consent_status=data.consent_status,
            opt_out_status=data.opt_out_status,
            contact_eligibility=data.contact_eligibility,
            assigned_agent_id=data.assigned_agent_id,
            assigned_whatsapp_profile_id=data.assigned_whatsapp_profile_id,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def update(self, lead: Lead, update_dict: Dict[str, Any]) -> Lead:
        for field, value in update_dict.items():
            setattr(lead, field, value)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def list_routing_history(self, lead_id: uuid.UUID) -> List[LeadRoutingDecision]:
        return (
            self.db.query(LeadRoutingDecision)
            .filter(LeadRoutingDecision.lead_id == lead_id)
            .order_by(LeadRoutingDecision.created_at.desc())
            .all()
        )

    def record_routing_decision(self, data: LeadRoutingDecisionCreate) -> LeadRoutingDecision:
        decision = LeadRoutingDecision(
            lead_id=data.lead_id,
            route_name=data.route_name,
            reason=data.reason,
            rule_version=data.rule_version,
            manual_override=data.manual_override,
            overridden_by=data.overridden_by,
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def list_outreach(self, lead_id: uuid.UUID) -> List[LeadOutreach]:
        return (
            self.db.query(LeadOutreach)
            .filter(LeadOutreach.lead_id == lead_id)
            .order_by(LeadOutreach.created_at.desc())
            .all()
        )
