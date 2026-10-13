import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.faq_entry import FAQEntry
from app.models.enums import FAQStatus


class FAQRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, faq_id: uuid.UUID) -> Optional[FAQEntry]:
        return self.db.query(FAQEntry).filter(FAQEntry.id == faq_id).first()

    def list_all(
        self,
        category: Optional[str] = None,
        status: Optional[FAQStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FAQEntry]:
        q = self.db.query(FAQEntry)
        if category:
            q = q.filter(FAQEntry.category == category)
        if status:
            q = q.filter(FAQEntry.status == status)
        return q.order_by(desc(FAQEntry.created_at)).offset(offset).limit(limit).all()

    def list_active(self) -> List[FAQEntry]:
        return (
            self.db.query(FAQEntry)
            .filter(FAQEntry.status == FAQStatus.ACTIVE)
            .order_by(FAQEntry.category, FAQEntry.question)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> FAQEntry:
        faq = FAQEntry(
            id=data.get("id", uuid.uuid4()),
            question=data["question"],
            answer=data["answer"],
            category=data.get("category", "GENERAL"),
            keywords=data.get("keywords", []),
            language=data.get("language", "en"),
            status=data.get("status", FAQStatus.ACTIVE),
            version=data.get("version", "v1"),
        )
        self.db.add(faq)
        self.db.commit()
        self.db.refresh(faq)
        return faq

    def update(self, faq: FAQEntry, updates: Dict[str, Any]) -> FAQEntry:
        for k, v in updates.items():
            if hasattr(faq, k):
                setattr(faq, k, v)
        self.db.commit()
        self.db.refresh(faq)
        return faq

    def delete(self, faq: FAQEntry) -> None:
        self.db.delete(faq)
        self.db.commit()
