import uuid
from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import FAQStatus


class FAQEntry(Base):
    __tablename__ = "faq_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(String(500), nullable=False, index=True)
    answer = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, default="GENERAL", index=True)
    keywords = Column(JSONB, nullable=False, default=list)
    language = Column(String(10), nullable=False, default="en")
    status = Column(
        SAEnum(FAQStatus, name="faq_status_enum", native_enum=True),
        nullable=False,
        default=FAQStatus.ACTIVE,
        index=True,
    )
    version = Column(String(50), nullable=False, default="v1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
