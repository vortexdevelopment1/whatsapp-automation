import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PropertySourceType, PropertySourceStatus


class PropertySourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: PropertySourceType = PropertySourceType.MANUAL
    external_system_name: Optional[str] = Field(None, max_length=255)
    status: PropertySourceStatus = PropertySourceStatus.ACTIVE
    configuration_reference: Optional[str] = Field(None, max_length=255)


class PropertySourceCreate(PropertySourceBase):
    pass


class PropertySourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    source_type: Optional[PropertySourceType] = None
    external_system_name: Optional[str] = Field(None, max_length=255)
    status: Optional[PropertySourceStatus] = None
    configuration_reference: Optional[str] = Field(None, max_length=255)


class PropertySourceResponse(PropertySourceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
