import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.enums import PropertyAgentStatus


def validate_agent_phone(v: Optional[str]) -> Optional[str]:
    if v is None or v.strip() == "":
        return None
    cleaned = v.strip()
    pattern = r"^\+?[0-9\s\-\(\)]{7,20}$"
    if not re.match(pattern, cleaned):
        raise ValueError("Invalid phone number format. Must contain 7 to 20 digits, spaces, or hyphens.")
    return cleaned


class PropertyAgentBase(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    agency_name: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    status: PropertyAgentStatus = PropertyAgentStatus.ACTIVE
    source_id: Optional[uuid.UUID] = None
    external_reference: Optional[str] = Field(None, max_length=255)

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_agent_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip()


class PropertyAgentCreate(PropertyAgentBase):
    pass


class PropertyAgentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    agency_name: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    status: Optional[PropertyAgentStatus] = None
    source_id: Optional[uuid.UUID] = None
    external_reference: Optional[str] = Field(None, max_length=255)

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_agent_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip()


class PropertyAgentResponse(PropertyAgentBase):
    id: uuid.UUID
    phone_normalized: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
