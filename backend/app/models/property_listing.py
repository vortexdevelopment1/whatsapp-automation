import uuid
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyListingStatus, ListingAvailabilityStatus


class PropertyListing(Base):
    __tablename__ = "property_listings"
    __table_args__ = (
        UniqueConstraint("source_id", "source_listing_id", name="uq_property_listings_source_listing"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_listing_id = Column(String(255), nullable=True, index=True)
    source_url = Column(String(1024), nullable=True)
    listing_reference = Column(String(255), nullable=True)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    asking_price = Column(Numeric(12, 2), nullable=True, index=True)
    currency = Column(String(10), nullable=False, default="SGD")

    availability_status = Column(
        SAEnum(ListingAvailabilityStatus, name="listing_availability_status_enum"),
        nullable=False,
        default=ListingAvailabilityStatus.UNKNOWN,
        index=True,
    )
    available_from = Column(Date, nullable=True)
    lease_min_months = Column(Integer, nullable=True)
    lease_max_months = Column(Integer, nullable=True)

    listing_status = Column(
        SAEnum(PropertyListingStatus, name="property_listing_status_enum"),
        nullable=False,
        default=PropertyListingStatus.ACTIVE,
        index=True,
    )

    source_last_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    listing_metadata = Column("metadata", JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    property = relationship("Property", back_populates="listings")
    source = relationship("PropertySource", back_populates="listings")
    agent = relationship("PropertyAgent", back_populates="listings")
    matches = relationship("PropertyMatch", back_populates="listing")
