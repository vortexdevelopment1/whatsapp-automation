from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import (
    PropertyImportType,
    PropertyImportBatchStatus,
    PropertyImportRowStatus,
    DuplicateReviewStatus,
    DuplicateConfidenceLevel,
)

# ---------------------------------------------------------
# IMPORT BATCH SCHEMAS
# ---------------------------------------------------------

class PropertyImportBatchBase(BaseModel):
    source_id: UUID
    import_type: PropertyImportType = PropertyImportType.CSV
    file_name: Optional[str] = None

class PropertyImportBatchResponse(BaseModel):
    id: UUID
    source_id: UUID
    file_name: Optional[str] = None
    import_type: PropertyImportType
    status: PropertyImportBatchStatus
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_listing_rows: int
    matched_existing_property_rows: int
    new_property_rows: int
    manual_review_rows: int
    created_by: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# IMPORT ROW SCHEMAS
# ---------------------------------------------------------

class PropertyImportRowResponse(BaseModel):
    id: UUID
    batch_id: UUID
    row_number: int
    raw_payload: Dict[str, Any]
    normalized_payload: Optional[Dict[str, Any]] = None
    status: PropertyImportRowStatus
    property_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    error_codes: Optional[List[Any]] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# PREVIEW SCHEMAS
# ---------------------------------------------------------

class PreviewRowItem(BaseModel):
    row_number: int
    raw_payload: Dict[str, Any]
    normalized_payload: Optional[Dict[str, Any]] = None
    status: PropertyImportRowStatus
    dedup_verdict: Optional[str] = None
    dedup_confidence: Optional[str] = None
    dedup_reasons: Optional[List[str]] = None
    target_property_id: Optional[UUID] = None
    target_listing_id: Optional[UUID] = None
    errors: Optional[List[Any]] = None


class PropertyImportPreviewResponse(BaseModel):
    batch_id: UUID
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_listing_rows: int
    matched_existing_property_rows: int
    new_property_rows: int
    manual_review_rows: int
    sample_rows: List[PreviewRowItem] = Field(default_factory=list)


# ---------------------------------------------------------
# DUPLICATE REVIEW SCHEMAS
# ---------------------------------------------------------

class CandidatePropertySummary(BaseModel):
    id: UUID
    canonical_name: str
    building_name: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    unit_number: Optional[str] = None
    postal_code: Optional[str] = None
    property_type: Optional[Any] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    size_sqft: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PropertyDuplicateReviewResponse(BaseModel):
    id: UUID
    import_row_id: Optional[UUID] = None
    candidate_property_id: Optional[UUID] = None
    incoming_normalized_data: Dict[str, Any]
    match_reasons: List[str] = Field(default_factory=list)
    confidence_level: DuplicateConfidenceLevel
    status: DuplicateReviewStatus
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Additional joined data if present
    candidate_property: Optional[CandidatePropertySummary] = None

    model_config = ConfigDict(from_attributes=True)


class AttachReviewRequest(BaseModel):
    target_property_id: Optional[UUID] = None
    reason: Optional[str] = "Attached to existing canonical property by operator"

class CreateNewPropertyReviewRequest(BaseModel):
    reason: Optional[str] = "Operator confirmed separate physical property"

class IgnoreReviewRequest(BaseModel):
    reason: Optional[str] = "Operator rejected / ignored duplicate candidate"
