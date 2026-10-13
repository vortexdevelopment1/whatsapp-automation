import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.property_source import PropertySource
from app.models.enums import PropertySourceType, PropertySourceStatus
from app.schemas.property_source import PropertySourceCreate, PropertySourceUpdate
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate


class PropertySourceService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def get_source_or_404(self, source_id: uuid.UUID) -> PropertySource:
        source = self.db.query(PropertySource).filter(PropertySource.id == source_id).first()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property source with ID '{source_id}' not found.",
            )
        return source

    def create_source(self, data: PropertySourceCreate, actor_id: str = "system") -> PropertySource:
        existing = (
            self.db.query(PropertySource)
            .filter(PropertySource.name == data.name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property source with name '{data.name}' already exists.",
            )

        source = PropertySource(
            name=data.name,
            source_type=data.source_type,
            external_system_name=data.external_system_name,
            status=data.status,
            configuration_reference=data.configuration_reference,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SOURCE_CREATED",
                entity_type="property_source",
                entity_id=str(source.id),
                new_value={
                    "name": source.name,
                    "source_type": source.source_type.value,
                    "status": source.status.value,
                },
            )
        )

        return source

    def list_sources(
        self,
        source_type: Optional[PropertySourceType] = None,
        source_status: Optional[PropertySourceStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PropertySource]:
        query = self.db.query(PropertySource)
        if source_type:
            query = query.filter(PropertySource.source_type == source_type)
        if source_status:
            query = query.filter(PropertySource.status == source_status)
        return query.order_by(PropertySource.created_at.desc()).offset(skip).limit(limit).all()

    def update_source(
        self, source_id: uuid.UUID, data: PropertySourceUpdate, actor_id: str = "system"
    ) -> PropertySource:
        source = self.get_source_or_404(source_id)
        old_val = {
            "name": source.name,
            "source_type": source.source_type.value,
            "status": source.status.value,
        }

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(source, key, value)

        self.db.commit()
        self.db.refresh(source)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SOURCE_UPDATED",
                entity_type="property_source",
                entity_id=str(source.id),
                old_value=old_val,
                new_value={
                    "name": source.name,
                    "source_type": source.source_type.value,
                    "status": source.status.value,
                },
            )
        )

        return source

    def activate_source(self, source_id: uuid.UUID, actor_id: str = "system") -> PropertySource:
        source = self.get_source_or_404(source_id)
        old_status = source.status.value
        source.status = PropertySourceStatus.ACTIVE
        self.db.commit()
        self.db.refresh(source)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SOURCE_ACTIVATED",
                entity_type="property_source",
                entity_id=str(source.id),
                old_value={"status": old_status},
                new_value={"status": source.status.value},
            )
        )
        return source

    def deactivate_source(self, source_id: uuid.UUID, actor_id: str = "system") -> PropertySource:
        source = self.get_source_or_404(source_id)
        old_status = source.status.value
        source.status = PropertySourceStatus.INACTIVE
        self.db.commit()
        self.db.refresh(source)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SOURCE_DEACTIVATED",
                entity_type="property_source",
                entity_id=str(source.id),
                old_value={"status": old_status},
                new_value={"status": source.status.value},
            )
        )
        return source
