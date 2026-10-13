import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.template import MessageTemplate
from app.models.enums import TemplateStatus
from app.schemas.template import TemplateCreate, TemplateUpdate


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, template_id: uuid.UUID) -> Optional[MessageTemplate]:
        return self.db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()

    def list_by_agent_id(self, agent_id: uuid.UUID) -> List[MessageTemplate]:
        return (
            self.db.query(MessageTemplate)
            .filter((MessageTemplate.agent_id == agent_id) | (MessageTemplate.agent_id.is_(None)))
            .order_by(MessageTemplate.created_at.desc())
            .all()
        )

    def create(self, agent_id: Optional[uuid.UUID], data: TemplateCreate) -> MessageTemplate:
        template = MessageTemplate(
            agent_id=agent_id,
            template_name=data.template_name,
            meta_template_name=data.meta_template_name,
            language=data.language,
            category=data.category,
            body=data.body,
            status=data.status or TemplateStatus.DRAFT,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def update(self, template: MessageTemplate, data: TemplateUpdate) -> MessageTemplate:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        self.db.commit()
        self.db.refresh(template)
        return template
