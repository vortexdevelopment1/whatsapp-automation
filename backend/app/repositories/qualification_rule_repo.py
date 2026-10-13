import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.qualification_rule import QualificationRule


DEFAULT_REQUIRED_FIELDS = [
    "preferred_locations",
    "budget_max",
    "property_type",
    "move_in_date",
    "lease_duration_months",
    "occupants",
]

DEFAULT_OPTIONAL_FIELDS = [
    "bedrooms",
    "furnishing",
    "special_requirements",
]

DEFAULT_QUESTION_ORDER = [
    "preferred_locations",
    "budget_max",
    "property_type",
    "move_in_date",
    "lease_duration_months",
    "occupants",
    "bedrooms",
    "furnishing",
    "special_requirements",
]


class QualificationRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, rule_id: uuid.UUID) -> Optional[QualificationRule]:
        return self.db.query(QualificationRule).filter(QualificationRule.id == rule_id).first()

    def get_active_rule(self, route: Optional[str] = None) -> QualificationRule:
        query = self.db.query(QualificationRule).filter(QualificationRule.active == True)
        if route:
            route_rule = query.filter(QualificationRule.route == route).first()
            if route_rule:
                return route_rule
        # Fallback to default rule
        default_rule = query.filter(QualificationRule.route == None).first()
        if not default_rule:
            default_rule = query.first()

        # If no rule exists in DB, create standard default rule
        if not default_rule:
            default_rule = QualificationRule(
                name="Standard Residential Qualification Rule",
                route=None,
                required_fields=DEFAULT_REQUIRED_FIELDS,
                optional_fields=DEFAULT_OPTIONAL_FIELDS,
                question_order=DEFAULT_QUESTION_ORDER,
                active=True,
                version="v1",
            )
            self.db.add(default_rule)
            self.db.commit()
            self.db.refresh(default_rule)

        return default_rule

    def list_rules(self) -> List[QualificationRule]:
        return self.db.query(QualificationRule).order_by(QualificationRule.created_at.desc()).all()

    def create(self, data: dict) -> QualificationRule:
        rule = QualificationRule(**data)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
