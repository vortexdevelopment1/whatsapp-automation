import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import PropertyType, PropertyStatus, FurnishingType


class PropertyBase(BaseModel):
    canonical_name: Optional[str] = Field(None, max_length=255)
    building_name: Optional[str] = Field(None, max_length=255)
    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    unit_number: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    country: str = Field("Singapore", max_length=100)

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    property_type: PropertyType = PropertyType.CONDO
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    size_sqft: Optional[Decimal] = None
    furnishing: Optional[FurnishingType] = FurnishingType.UNKNOWN
    status: PropertyStatus = PropertyStatus.ACTIVE

    @field_validator("bedrooms")
    @classmethod
    def validate_bedrooms(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Bedrooms cannot be negative.")
        return v

    @field_validator("bathrooms")
    @classmethod
    def validate_bathrooms(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Bathrooms cannot be negative.")
        return v

    @field_validator("size_sqft")
    @classmethod
    def validate_size_sqft(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Size (sqft) cannot be negative.")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180 degrees.")
        return v


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    canonical_name: Optional[str] = Field(None, max_length=255)
    building_name: Optional[str] = Field(None, max_length=255)
    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    unit_number: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    property_type: Optional[PropertyType] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    size_sqft: Optional[Decimal] = None
    furnishing: Optional[FurnishingType] = None
    status: Optional[PropertyStatus] = None

    @field_validator("bedrooms")
    @classmethod
    def validate_bedrooms(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Bedrooms cannot be negative.")
        return v

    @field_validator("bathrooms")
    @classmethod
    def validate_bathrooms(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Bathrooms cannot be negative.")
        return v

    @field_validator("size_sqft")
    @classmethod
    def validate_size_sqft(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Size (sqft) cannot be negative.")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180 degrees.")
        return v


class PropertyResponse(PropertyBase):
    id: uuid.UUID
    listings_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
