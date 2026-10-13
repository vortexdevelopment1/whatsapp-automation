import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogCreate


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(self, data: AuditLogCreate) -> AuditLog:
        entry = AuditLog(
            actor_id=data.actor_id,
            action=data.action,
            entity_type=data.entity_type,
            entity_id=str(data.entity_id),
            old_value=data.old_value,
            new_value=data.new_value,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        query = self.db.query(AuditLog)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
