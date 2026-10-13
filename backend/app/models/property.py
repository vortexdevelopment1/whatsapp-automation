import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyType, PropertyStatus, FurnishingType


class Property(Base):
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name = Column(String(255), nullable=True, index=True)
    building_name = Column(String(255), nullable=True, index=True)
    address_line_1 = Column(String(255), nullable=True)
    address_line_2 = Column(String(255), nullable=True)
    unit_number = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    state_region = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    country = Column(String(100), nullable=False, default="Singapore", index=True)
    address_normalized = Column(String(500), nullable=True, index=True)
    property_fingerprint = Column(String(255), nullable=True, index=True)


    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)

    property_type = Column(
        SAEnum(PropertyType, name="property_type_enum"),
        nullable=False,
        default=PropertyType.CONDO,
        index=True,
    )
    bedrooms = Column(Integer, nullable=True, index=True)
    bathrooms = Column(Numeric(3, 1), nullable=True)
    size_sqft = Column(Numeric(10, 2), nullable=True)
    furnishing = Column(
        SAEnum(FurnishingType, name="furnishing_type_enum"),
        nullable=True,
        default=FurnishingType.UNKNOWN,
        index=True,
    )
    status = Column(
        SAEnum(PropertyStatus, name="property_status_enum"),
        nullable=False,
        default=PropertyStatus.ACTIVE,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listings = relationship("PropertyListing", back_populates="property", cascade="all, delete-orphan")
    matches = relationship("PropertyMatch", back_populates="property", cascade="all, delete-orphan")
