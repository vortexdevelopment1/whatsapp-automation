import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyImportType, PropertyImportBatchStatus


class PropertyImportBatch(Base):
    __tablename__ = "property_import_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name = Column(String(255), nullable=True)
    import_type = Column(
        SAEnum(PropertyImportType, name="property_import_type_enum"),
        nullable=False,
        default=PropertyImportType.CSV,
        index=True,
    )
    status = Column(
        SAEnum(PropertyImportBatchStatus, name="property_import_batch_status_enum"),
        nullable=False,
        default=PropertyImportBatchStatus.UPLOADED,
        index=True,
    )

    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    duplicate_listing_rows = Column(Integer, nullable=False, default=0)
    matched_existing_property_rows = Column(Integer, nullable=False, default=0)
    new_property_rows = Column(Integer, nullable=False, default=0)
    manual_review_rows = Column(Integer, nullable=False, default=0)

    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    error_summary = Column(JSONB, nullable=True)

    source = relationship("PropertySource")
    rows = relationship("PropertyImportRow", back_populates="batch", cascade="all, delete-orphan")
    reviews = relationship("PropertyDuplicateReview", back_populates="batch")
