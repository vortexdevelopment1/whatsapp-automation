import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import TemplateStatus


class TemplateBase(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=255)
    meta_template_name: Optional[str] = Field(None, max_length=255)
    language: str = Field("en_US", min_length=2, max_length=20)
    category: Optional[str] = Field(None, max_length=50)
    body: str = Field(..., min_length=1)
    status: Optional[TemplateStatus] = TemplateStatus.DRAFT


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    meta_template_name: Optional[str] = Field(None, max_length=255)
    language: Optional[str] = Field(None, min_length=2, max_length=20)
    category: Optional[str] = Field(None, max_length=50)
    body: Optional[str] = Field(None, min_length=1)
    status: Optional[TemplateStatus] = None


class TemplateResponse(TemplateBase):
    id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    status: TemplateStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
