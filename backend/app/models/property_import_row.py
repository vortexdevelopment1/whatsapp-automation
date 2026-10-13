import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyImportRowStatus


class PropertyImportRow(Base):
    __tablename__ = "property_import_rows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number = Column(Integer, nullable=False, index=True)

    raw_payload = Column(JSONB, nullable=False)
    normalized_payload = Column(JSONB, nullable=True)

    status = Column(
        SAEnum(PropertyImportRowStatus, name="property_import_row_status_enum"),
        nullable=False,
        default=PropertyImportRowStatus.PENDING,
        index=True,
    )

    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    error_codes = Column(JSONB, nullable=True)
    deduplication_result = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    batch = relationship("PropertyImportBatch", back_populates="rows")
    property = relationship("Property")
    listing = relationship("PropertyListing")
