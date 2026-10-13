import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.enums import AgentStatus, AuthorizationStatus


def validate_phone_number(v: Optional[str]) -> Optional[str]:
    if v is None or v.strip() == "":
        return None
    cleaned = v.strip()
    # Basic international/national phone regex: optional '+' followed by 7 to 15 digits/spaces/dashes
    pattern = r"^\+?[0-9\s\-\(\)]{7,20}$"
    if not re.match(pattern, cleaned):
        raise ValueError("Invalid phone number format. Must contain 7 to 20 digits, spaces, or hyphens.")
    return cleaned


class AgentBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    agency_name: str = Field(..., min_length=1, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    profile_photo_url: Optional[str] = Field(None, max_length=1024)
    notes: Optional[str] = None

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_number(v)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip()


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    agency_name: Optional[str] = Field(None, min_length=1, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    profile_photo_url: Optional[str] = Field(None, max_length=1024)
    notes: Optional[str] = None
    authorization_status: Optional[AuthorizationStatus] = None

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_number(v)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip()


class AgentResponse(AgentBase):
    id: uuid.UUID
    status: AgentStatus
    authorization_status: AuthorizationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
