import uuid
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import FAQStatus


class FAQCreateRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    answer: str = Field(..., min_length=1)
    category: str = Field(default="GENERAL", max_length=100)
    keywords: List[str] = Field(default_factory=list)
    language: str = Field(default="en", max_length=10)
    status: FAQStatus = Field(default=FAQStatus.ACTIVE)
    version: str = Field(default="v1", max_length=50)


class FAQUpdateRequest(BaseModel):
    question: Optional[str] = Field(default=None, min_length=3, max_length=500)
    answer: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, max_length=100)
    keywords: Optional[List[str]] = None
    language: Optional[str] = Field(default=None, max_length=10)
    status: Optional[FAQStatus] = None
    version: Optional[str] = Field(default=None, max_length=50)


class FAQResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    category: str
    keywords: List[str]
    language: str
    status: FAQStatus
    version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    def __getitem__(self, item: str):
        val = getattr(self, item)
        if hasattr(val, "value"):
            return val.value
        return val


class FAQMatchResult(BaseModel):
    matched: bool
    faq: Optional[FAQResponse] = None
    confidence: float = 0.0
    fallback_message: Optional[str] = None
