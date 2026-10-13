import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyAgentStatus


class PropertyAgent(Base):
    __tablename__ = "property_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=True)
    agency_name = Column(String(255), nullable=True, index=True)
    registration_number = Column(String(100), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    phone_normalized = Column(String(50), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    status = Column(
        SAEnum(PropertyAgentStatus, name="property_agent_status_enum"),
        nullable=False,
        default=PropertyAgentStatus.ACTIVE,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    source = relationship("PropertySource", back_populates="agents")
    listings = relationship("PropertyListing", back_populates="agent")
