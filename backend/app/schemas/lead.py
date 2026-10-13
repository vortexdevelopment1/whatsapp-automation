import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.schemas.lead_source import LeadSourceResponse


class LeadBase(BaseModel):
    full_name: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    source_id: Optional[uuid.UUID] = None
    consent_status: ConsentStatus = ConsentStatus.UNKNOWN
    opt_out_status: OptOutStatus = OptOutStatus.ACTIVE
    contact_eligibility: ContactEligibility = ContactEligibility.UNKNOWN
    assigned_agent_id: Optional[uuid.UUID] = None
    assigned_whatsapp_profile_id: Optional[uuid.UUID] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    source_id: Optional[uuid.UUID] = None
    status: Optional[LeadStatus] = None
    consent_status: Optional[ConsentStatus] = None
    opt_out_status: Optional[OptOutStatus] = None
    contact_eligibility: Optional[ContactEligibility] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    assigned_whatsapp_profile_id: Optional[uuid.UUID] = None


class LeadValidateResponse(BaseModel):
    valid: bool
    phone_normalized: Optional[str] = None
    errors: List[str] = []


class LeadResponse(BaseModel):
    id: uuid.UUID
    full_name: Optional[str] = None
    phone: str
    phone_normalized: str
    email: Optional[str] = None
    source_id: Optional[uuid.UUID] = None
    status: LeadStatus
    consent_status: ConsentStatus
    opt_out_status: OptOutStatus
    contact_eligibility: ContactEligibility
    assigned_agent_id: Optional[uuid.UUID] = None
    assigned_whatsapp_profile_id: Optional[uuid.UUID] = None
    duplicate_override: bool = False
    duplicate_override_reason: Optional[str] = None
    duplicate_of_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    source: Optional[LeadSourceResponse] = None

    model_config = ConfigDict(from_attributes=True)


class LeadDuplicateSummary(BaseModel):
    id: uuid.UUID
    full_name: Optional[str] = None
    phone: str
    phone_normalized: str
    status: LeadStatus

    model_config = ConfigDict(from_attributes=True)


class LeadDuplicateCheckResponse(BaseModel):
    duplicate: bool
    existing_lead_id: Optional[uuid.UUID] = None
    match_reasons: List[str] = []
    existing_lead: Optional[LeadDuplicateSummary] = None


class LeadEligibilityCheckResponse(BaseModel):
    lead_id: uuid.UUID
    eligibility: ContactEligibility
    reasons: List[str] = []


class LeadDuplicateOverrideRequest(BaseModel):
    reason: str


class LeadMarkOptOutRequest(BaseModel):
    reason: Optional[str] = None


class LeadRestoreContactRequest(BaseModel):
    reason: Optional[str] = None
    authorized_by: Optional[str] = None

