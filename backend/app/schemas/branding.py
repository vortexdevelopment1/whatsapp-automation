import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from app.models.enums import BrandingStatus


class BrandingBase(BaseModel):
    business_description: Optional[str] = None
    office_address: Optional[str] = None
    website: Optional[str] = Field(None, max_length=512)
    profile_photo_url: Optional[str] = Field(None, max_length=1024)
    digital_name_card_url: Optional[str] = Field(None, max_length=1024)
    lanyard_artwork_url: Optional[str] = Field(None, max_length=1024)
    branding_status: Optional[BrandingStatus] = BrandingStatus.NOT_STARTED


class BrandingUpdate(BrandingBase):
    pass


class BrandingResponse(BrandingBase):
    id: uuid.UUID
    agent_id: uuid.UUID
    branding_status: BrandingStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
