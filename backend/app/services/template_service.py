import uuid
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.template import MessageTemplate
from app.repositories.template_repo import TemplateRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.schemas.audit import AuditLogCreate
from app.services.agent_service import AgentService


class TemplateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TemplateRepository(db)
        self.agent_service = AgentService(db)
        self.audit_repo = AuditRepository(db)

    def get_template_or_404(self, template_id: uuid.UUID) -> MessageTemplate:
        template = self.repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id {template_id} not found"
            )
        return template

    def list_templates_for_agent(self, agent_id: uuid.UUID) -> List[MessageTemplate]:
        self.agent_service.get_agent_or_404(agent_id)
        return self.repo.list_by_agent_id(agent_id)

    def create_template(
        self, agent_id: uuid.UUID, data: TemplateCreate, actor_id: str = "system"
    ) -> MessageTemplate:
        self.agent_service.get_agent_or_404(agent_id)
        template = self.repo.create(agent_id, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TEMPLATE_CREATED",
                entity_type="MessageTemplate",
                entity_id=str(template.id),
                new_value={"template_name": template.template_name, "language": template.language},
            )
        )
        return template

    def update_template(
        self, template_id: uuid.UUID, data: TemplateUpdate, actor_id: str = "system"
    ) -> MessageTemplate:
        template = self.get_template_or_404(template_id)
        old_data = {
            "template_name": template.template_name,
            "status": template.status.value if template.status else None,
        }
        updated = self.repo.update(template, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TEMPLATE_UPDATED",
                entity_type="MessageTemplate",
                entity_id=str(updated.id),
                old_value=old_data,
                new_value=data.model_dump(exclude_unset=True),
            )
        )
        return updated
