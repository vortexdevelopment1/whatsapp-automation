import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from app.models.enums import (
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
    FurnishingType,
)


class TenantRequirementBase(BaseModel):
    preferred_locations: Optional[List[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency: str = "SGD"
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    move_in_date: Optional[date] = None
    lease_duration_months: Optional[int] = None
    occupants: Optional[int] = None
    furnishing: Optional[str] = None
    special_requirements: Optional[Dict[str, Any]] = None

    @field_validator("budget_min")
    @classmethod
    def validate_budget_min(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("budget_min must be greater than or equal to 0")
        return v

    @field_validator("budget_max")
    @classmethod
    def validate_budget_max(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("budget_max must be greater than or equal to 0")
        return v

    @field_validator("bedrooms")
    @classmethod
    def validate_bedrooms(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("bedrooms must be greater than or equal to 0")
        return v

    @field_validator("occupants")
    @classmethod
    def validate_occupants(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("occupants must be greater than 0")
        return v

    @field_validator("lease_duration_months")
    @classmethod
    def validate_lease_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("lease_duration_months must be greater than 0")
        return v

    @field_validator("furnishing")
    @classmethod
    def validate_furnishing(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_upper = v.upper()
            allowed = {f.value for f in FurnishingType}
            if v_upper not in allowed:
                raise ValueError(f"furnishing must be one of: {', '.join(sorted(allowed))}")
            return v_upper
        return v

    @model_validator(mode="after")
    def validate_budget_range(self):
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min cannot be greater than budget_max")
        return self


class TenantRequirementCreate(TenantRequirementBase):
    source_type: RequirementSourceType = RequirementSourceType.HUMAN_OPERATOR
    source_message_id: Optional[uuid.UUID] = None


class TenantRequirementUpdate(BaseModel):
    preferred_locations: Optional[List[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    move_in_date: Optional[date] = None
    lease_duration_months: Optional[int] = None
    occupants: Optional[int] = None
    furnishing: Optional[str] = None
    special_requirements: Optional[Dict[str, Any]] = None
    source_type: RequirementSourceType = RequirementSourceType.HUMAN_OPERATOR
    source_message_id: Optional[uuid.UUID] = None

    @field_validator("budget_min")
    @classmethod
    def validate_budget_min(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("budget_min must be greater than or equal to 0")
        return v

    @field_validator("budget_max")
    @classmethod
    def validate_budget_max(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("budget_max must be greater than or equal to 0")
        return v

    @field_validator("bedrooms")
    @classmethod
    def validate_bedrooms(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("bedrooms must be greater than or equal to 0")
        return v

    @field_validator("occupants")
    @classmethod
    def validate_occupants(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("occupants must be greater than 0")
        return v

    @field_validator("lease_duration_months")
    @classmethod
    def validate_lease_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("lease_duration_months must be greater than 0")
        return v

    @field_validator("furnishing")
    @classmethod
    def validate_furnishing(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_upper = v.upper()
            allowed = {f.value for f in FurnishingType}
            if v_upper not in allowed:
                raise ValueError(f"furnishing must be one of: {', '.join(sorted(allowed))}")
            return v_upper
        return v

    @model_validator(mode="after")
    def validate_budget_range(self):
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min cannot be greater than budget_max")
        return self


class TenantRequirementHistoryResponse(BaseModel):
    id: uuid.UUID
    tenant_requirement_id: uuid.UUID
    field_name: str
    value: Any
    confidence: Optional[Decimal] = None
    source_message_id: Optional[uuid.UUID] = None
    status: RequirementFieldStatus
    source_type: RequirementSourceType
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantRequirementResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    preferred_locations: Optional[List[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency: str
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    move_in_date: Optional[date] = None
    lease_duration_months: Optional[int] = None
    occupants: Optional[int] = None
    furnishing: Optional[str] = None
    special_requirements: Optional[Dict[str, Any]] = None
    qualification_status: QualificationStatus
    completion_percentage: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualificationProgressResponse(BaseModel):
    lead_id: uuid.UUID
    qualification_status: QualificationStatus
    completion_percentage: int
    ready: bool
    missing_fields: List[str]
    completed_fields: List[str]
    required_fields: List[str]
    optional_fields: List[str]


class QualificationRuleBase(BaseModel):
    name: str
    route: Optional[str] = None
    required_fields: List[str]
    optional_fields: List[str]
    question_order: List[str]
    active: bool = True
    version: str = "v1"


class QualificationRuleCreate(QualificationRuleBase):
    pass


class QualificationRuleResponse(QualificationRuleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
