import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.lead_source import LeadSource
from app.models.enums import LeadSourceStatus
from app.repositories.lead_source_repo import LeadSourceRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.lead_source import LeadSourceCreate, LeadSourceUpdate
from app.schemas.audit import AuditLogCreate


class LeadSourceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LeadSourceRepository(db)
        self.audit_repo = AuditRepository(db)

    def get_source_or_404(self, source_id: uuid.UUID) -> LeadSource:
        source = self.repo.get_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead source with id '{source_id}' not found.",
            )
        return source

    def list_sources(
        self,
        status: Optional[LeadSourceStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[LeadSource]:
        return self.repo.list_sources(status=status, skip=skip, limit=limit)

    def create_source(self, data: LeadSourceCreate, actor_id: str = "system") -> LeadSource:
        # Check name uniqueness
        existing = self.repo.get_by_name(data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead source with name '{data.name.strip()}' already exists.",
            )

        source = self.repo.create(data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_SOURCE_CREATED",
                entity_type="LeadSource",
                entity_id=str(source.id),
                new_value={
                    "name": source.name,
                    "source_type": source.source_type.value,
                    "status": source.status.value,
                },
            )
        )
        return source

    def update_source(
        self, source_id: uuid.UUID, data: LeadSourceUpdate, actor_id: str = "system"
    ) -> LeadSource:
        source = self.get_source_or_404(source_id)

        if data.name and data.name.strip().lower() != source.name.lower():
            existing = self.repo.get_by_name(data.name)
            if existing and existing.id != source.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lead source with name '{data.name.strip()}' already exists.",
                )

        old_values = {
            "name": source.name,
            "source_type": source.source_type.value,
            "status": source.status.value,
            "description": source.description,
        }

        updated = self.repo.update(source, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_SOURCE_UPDATED",
                entity_type="LeadSource",
                entity_id=str(updated.id),
                old_value=old_values,
                new_value=data.model_dump(exclude_unset=True),
            )
        )
        return updated
