import uuid
from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import ImportBatchStatus


class LeadImportBatch(Base):
    __tablename__ = "lead_import_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String(255), nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    duplicate_rows = Column(Integer, nullable=False, default=0)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    status = Column(
        SAEnum(ImportBatchStatus, name="import_batch_status_enum", native_enum=True),
        nullable=False,
        default=ImportBatchStatus.UPLOADED,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
