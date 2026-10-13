import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.enums import PropertyListingStatus, ListingAvailabilityStatus


class PropertyListingBase(BaseModel):
    source_id: uuid.UUID
    source_listing_id: Optional[str] = Field(None, max_length=255)
    source_url: Optional[str] = Field(None, max_length=1024)
    listing_reference: Optional[str] = Field(None, max_length=255)
    agent_id: Optional[uuid.UUID] = None

    asking_price: Optional[Decimal] = None
    currency: str = Field("SGD", max_length=10)

    availability_status: ListingAvailabilityStatus = ListingAvailabilityStatus.UNKNOWN
    available_from: Optional[date] = None
    lease_min_months: Optional[int] = None
    lease_max_months: Optional[int] = None

    listing_status: PropertyListingStatus = PropertyListingStatus.ACTIVE
    source_last_updated_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("asking_price")
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Asking price cannot be negative.")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned or len(cleaned) > 10:
            raise ValueError("Invalid currency code.")
        return cleaned

    @field_validator("lease_min_months")
    @classmethod
    def validate_min_lease(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Minimum lease duration must be greater than 0.")
        return v

    @field_validator("lease_max_months")
    @classmethod
    def validate_max_lease(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Maximum lease duration must be greater than 0.")
        return v

    @model_validator(mode="after")
    def validate_lease_range(self):
        if self.lease_min_months is not None and self.lease_max_months is not None:
            if self.lease_min_months > self.lease_max_months:
                raise ValueError("Minimum lease cannot exceed maximum lease duration.")
        return self


class PropertyListingCreate(PropertyListingBase):
    property_id: Optional[uuid.UUID] = None


class PropertyListingUpdate(BaseModel):
    source_id: Optional[uuid.UUID] = None
    source_listing_id: Optional[str] = Field(None, max_length=255)
    source_url: Optional[str] = Field(None, max_length=1024)
    listing_reference: Optional[str] = Field(None, max_length=255)
    agent_id: Optional[uuid.UUID] = None

    asking_price: Optional[Decimal] = None
    currency: Optional[str] = Field(None, max_length=10)

    availability_status: Optional[ListingAvailabilityStatus] = None
    available_from: Optional[date] = None
    lease_min_months: Optional[int] = None
    lease_max_months: Optional[int] = None

    listing_status: Optional[PropertyListingStatus] = None
    source_last_updated_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("asking_price")
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Asking price cannot be negative.")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().upper()
            if not cleaned or len(cleaned) > 10:
                raise ValueError("Invalid currency code.")
            return cleaned
        return v

    @field_validator("lease_min_months")
    @classmethod
    def validate_min_lease(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Minimum lease duration must be greater than 0.")
        return v

    @field_validator("lease_max_months")
    @classmethod
    def validate_max_lease(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Maximum lease duration must be greater than 0.")
        return v

    @model_validator(mode="after")
    def validate_lease_range(self):
        if self.lease_min_months is not None and self.lease_max_months is not None:
            if self.lease_min_months > self.lease_max_months:
                raise ValueError("Minimum lease cannot exceed maximum lease duration.")
        return self


class PropertyListingResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    source_id: uuid.UUID
    source_listing_id: Optional[str] = None
    source_url: Optional[str] = None
    listing_reference: Optional[str] = None
    agent_id: Optional[uuid.UUID] = None

    asking_price: Optional[Decimal] = None
    currency: str = "SGD"

    availability_status: ListingAvailabilityStatus
    available_from: Optional[date] = None
    lease_min_months: Optional[int] = None
    lease_max_months: Optional[int] = None

    listing_status: PropertyListingStatus
    source_last_updated_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(None, validation_alias="listing_metadata")

    source_name: Optional[str] = None
    agent_name: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PropertyDetailResponse(BaseModel):
    id: uuid.UUID
    canonical_name: Optional[str] = None
    building_name: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    unit_number: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    district: Optional[str] = None
    country: str = "Singapore"

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    property_type: Any
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    size_sqft: Optional[Decimal] = None
    furnishing: Optional[Any] = None
    status: Any

    listings: list[PropertyListingResponse] = []
    listings_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
