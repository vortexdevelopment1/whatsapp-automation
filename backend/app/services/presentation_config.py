"""
Configuration settings for Module 5 Phase 2: Tenant Property Presentation & Interest Capture
"""
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import PropertyPresentationMode


class PresentationConfig(BaseModel):
    mode: PropertyPresentationMode = PropertyPresentationMode.SEQUENTIAL
    max_properties_per_batch: int = Field(default=3, ge=1, le=10)
    include_property_media: bool = True
    include_availability: bool = True
    include_lease_terms: bool = True
    allow_compare: bool = True
    enable_interactive_buttons: bool = True
    currency_default: str = "SGD"
    revalidation_grace_period_hours: int = 24


# Default shared singleton instance
presentation_config = PresentationConfig()
