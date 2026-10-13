import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.lead_source import LeadSource
from app.models.enums import LeadSourceStatus
from app.schemas.lead_source import LeadSourceCreate, LeadSourceUpdate


class LeadSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, source_id: uuid.UUID) -> Optional[LeadSource]:
        return self.db.query(LeadSource).filter(LeadSource.id == source_id).first()

    def get_by_name(self, name: str) -> Optional[LeadSource]:
        return self.db.query(LeadSource).filter(LeadSource.name.ilike(name.strip())).first()

    def list_sources(
        self,
        status: Optional[LeadSourceStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[LeadSource]:
        query = self.db.query(LeadSource)
        if status:
            query = query.filter(LeadSource.status == status)
        return query.order_by(LeadSource.name.asc()).offset(skip).limit(limit).all()

    def create(self, data: LeadSourceCreate) -> LeadSource:
        source = LeadSource(
            name=data.name.strip(),
            source_type=data.source_type,
            description=data.description,
            status=data.status,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def update(self, source: LeadSource, data: LeadSourceUpdate) -> LeadSource:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(source, field, value)
        self.db.commit()
        self.db.refresh(source)
        return source
