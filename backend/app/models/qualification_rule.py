import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class QualificationRule(Base):
    __tablename__ = "qualification_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    route = Column(String(100), nullable=True, index=True)
    required_fields = Column(JSONB, nullable=False, default=list)
    optional_fields = Column(JSONB, nullable=False, default=list)
    question_order = Column(JSONB, nullable=False, default=list)
    disqualification_rules = Column(JSONB, nullable=False, default=list)
    human_review_rules = Column(JSONB, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True, index=True)
    version = Column(String(50), nullable=False, default="v1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
