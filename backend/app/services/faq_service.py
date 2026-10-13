import re
import uuid
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.faq_entry import FAQEntry
from app.models.enums import FAQStatus
from app.repositories.faq_repo import FAQRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.faq import FAQCreateRequest, FAQUpdateRequest, FAQResponse, FAQMatchResult


class FAQService:
    """
    Module 3 Phase 7: Controlled FAQ Service.
    The approved FAQ database is the absolute source of truth.
    The AI/system NEVER hallucinates or invents business policies, fees, or legal terms.
    """

    FALLBACK_MESSAGE = "I'm not confident I have the correct information for that. I can have a team member assist you."

    def __init__(self, db: Session):
        self.db = db
        self.faq_repo = FAQRepository(db)
        self.audit_repo = AuditRepository(db)

    def list_faqs(
        self,
        category: Optional[str] = None,
        status: Optional[FAQStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FAQResponse]:
        entries = self.faq_repo.list_all(category=category, status=status, limit=limit, offset=offset)
        return [FAQResponse.model_validate(e) for e in entries]

    def get_faq(self, faq_id: uuid.UUID) -> Optional[FAQResponse]:
        entry = self.faq_repo.get_by_id(faq_id)
        return FAQResponse.model_validate(entry) if entry else None

    def create_faq(self, req: FAQCreateRequest, actor_id: str = "system") -> FAQResponse:
        created = self.faq_repo.create(req.model_dump())
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="FAQ_CREATED",
                entity_type="FAQEntry",
                entity_id=str(created.id),
                new_value={"question": created.question, "category": created.category},
            )
        )
        return FAQResponse.model_validate(created)

    def update_faq(self, faq_id: uuid.UUID, req: FAQUpdateRequest, actor_id: str = "system") -> FAQResponse:
        entry = self.faq_repo.get_by_id(faq_id)
        if not entry:
            raise ValueError(f"FAQ with ID '{faq_id}' not found.")
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        updated = self.faq_repo.update(entry, updates)
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="FAQ_UPDATED",
                entity_type="FAQEntry",
                entity_id=str(updated.id),
                new_value=updates,
            )
        )
        return FAQResponse.model_validate(updated)

    def set_status(self, faq_id: uuid.UUID, new_status: FAQStatus, actor_id: str = "system") -> FAQResponse:
        entry = self.faq_repo.get_by_id(faq_id)
        if not entry:
            raise ValueError(f"FAQ with ID '{faq_id}' not found.")
        entry.status = new_status
        self.db.commit()
        self.db.refresh(entry)
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="FAQ_ACTIVATED" if new_status == FAQStatus.ACTIVE else "FAQ_DEACTIVATED",
                entity_type="FAQEntry",
                entity_id=str(entry.id),
                new_value={"status": new_status.value},
            )
        )
        return FAQResponse.model_validate(entry)

    def match_faq(
        self, query_text: str, category: Optional[str] = None, actor_id: str = "system"
    ) -> FAQMatchResult:
        """
        Matches tenant query against active approved FAQ entries.
        Uses normalized tokenization, keyword overlap, and question similarity.
        """
        if not query_text or not query_text.strip():
            return FAQMatchResult(matched=False, fallback_message=self.FALLBACK_MESSAGE)

        active_faqs = self.faq_repo.list_active()
        if not active_faqs:
            self._log_not_found(query_text, actor_id)
            return FAQMatchResult(matched=False, fallback_message=self.FALLBACK_MESSAGE)

        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return FAQMatchResult(matched=False, fallback_message=self.FALLBACK_MESSAGE)

        best_faq: Optional[FAQEntry] = None
        best_score = 0.0

        for faq in active_faqs:
            if category and faq.category.upper() != category.upper():
                continue

            score = self._calculate_match_score(query_text, query_tokens, faq)
            if score > best_score:
                best_score = score
                best_faq = faq

        # Match threshold: at least 0.35 similarity or significant keyword overlap
        if best_faq and best_score >= 0.35:
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="FAQ_MATCHED",
                    entity_type="FAQEntry",
                    entity_id=str(best_faq.id),
                    new_value={"query": query_text, "score": round(best_score, 3)},
                )
            )
            return FAQMatchResult(
                matched=True,
                faq=FAQResponse.model_validate(best_faq),
                confidence=round(best_score, 3),
            )

        self._log_not_found(query_text, actor_id)
        return FAQMatchResult(matched=False, fallback_message=self.FALLBACK_MESSAGE)

    def _tokenize(self, text: str) -> set:
        normalized = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = {t for t in normalized.split() if len(t) > 2}
        # Filter common stopwords
        stopwords = {"the", "and", "for", "with", "that", "this", "what", "how", "can", "you", "tell", "about", "need", "have"}
        return tokens - stopwords

    def _calculate_match_score(self, raw_query: str, query_tokens: set, faq: FAQEntry) -> float:
        faq_q_tokens = self._tokenize(faq.question)
        keywords = {k.lower().strip() for k in (faq.keywords or []) if isinstance(k, str)}

        # Direct exact or substring containment bonus
        raw_q_lower = raw_query.lower()
        faq_q_lower = faq.question.lower()
        if faq_q_lower in raw_q_lower or raw_q_lower in faq_q_lower:
            return 1.0

        # Keyword matching
        matched_keywords = sum(1 for kw in keywords if kw in raw_q_lower or kw in query_tokens)
        keyword_score = (matched_keywords / max(len(keywords), 1)) if keywords else 0.0

        # Jaccard token overlap with question
        intersection = query_tokens.intersection(faq_q_tokens)
        union = query_tokens.union(faq_q_tokens)
        jaccard = (len(intersection) / len(union)) if union else 0.0

        # Weighted combination: 60% token overlap + 40% keyword match
        final_score = (jaccard * 0.6) + (keyword_score * 0.4)
        if matched_keywords > 0:
            final_score += 0.2  # Bonus for direct keyword hit

        return min(final_score, 1.0)

    def _log_not_found(self, query: str, actor_id: str) -> None:
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="FAQ_NOT_FOUND",
                entity_type="FAQEntry",
                entity_id="00000000-0000-0000-0000-000000000000",
                new_value={"query": query},
            )
        )
