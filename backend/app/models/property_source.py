import uuid
from sqlalchemy import Column, String, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertySourceType, PropertySourceStatus


class PropertySource(Base):
    __tablename__ = "property_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    source_type = Column(
        SAEnum(PropertySourceType, name="property_source_type_enum"),
        nullable=False,
        default=PropertySourceType.MANUAL,
        index=True,
    )
    external_system_name = Column(String(255), nullable=True)
    status = Column(
        SAEnum(PropertySourceStatus, name="property_source_status_enum"),
        nullable=False,
        default=PropertySourceStatus.ACTIVE,
        index=True,
    )
    configuration_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listings = relationship("PropertyListing", back_populates="source")
    agents = relationship("PropertyAgent", back_populates="source")
