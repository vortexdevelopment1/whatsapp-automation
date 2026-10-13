import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import DuplicateReviewStatus, DuplicateConfidenceLevel


class PropertyDuplicateReview(Base):
    __tablename__ = "property_duplicate_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    import_row_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_import_rows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    candidate_property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    incoming_normalized_data = Column(JSONB, nullable=False)
    match_reasons = Column(JSONB, nullable=False)
    confidence_level = Column(
        SAEnum(DuplicateConfidenceLevel, name="duplicate_confidence_level_enum"),
        nullable=False,
        default=DuplicateConfidenceLevel.MEDIUM,
        index=True,
    )
    status = Column(
        SAEnum(DuplicateReviewStatus, name="duplicate_review_status_enum"),
        nullable=False,
        default=DuplicateReviewStatus.OPEN,
        index=True,
    )

    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    batch = relationship("PropertyImportBatch", back_populates="reviews")
    import_row = relationship("PropertyImportRow")
    candidate_property = relationship("Property")
