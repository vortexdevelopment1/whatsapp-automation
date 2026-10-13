import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.enums import PropertyType, PropertyStatus
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate


class PropertyService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def get_property_or_404(self, property_id: uuid.UUID) -> Property:
        prop = (
            self.db.query(Property)
            .filter(Property.id == property_id)
            .first()
        )
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property with ID '{property_id}' not found.",
            )
        return prop

    def create_property(self, data: PropertyCreate, actor_id: str = "system") -> Property:
        canonical_name = data.canonical_name
        if not canonical_name:
            parts = []
            if data.building_name:
                parts.append(data.building_name)
            elif data.address_line_1:
                parts.append(data.address_line_1)
            if data.unit_number:
                parts.append(data.unit_number)
            canonical_name = " ".join(parts) if parts else "Unnamed Property"

        prop = Property(
            canonical_name=canonical_name,
            building_name=data.building_name,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            unit_number=data.unit_number,
            postal_code=data.postal_code,
            city=data.city,
            state_region=data.state_region,
            district=data.district,
            country=data.country or "Singapore",
            latitude=data.latitude,
            longitude=data.longitude,
            property_type=data.property_type,
            bedrooms=data.bedrooms,
            bathrooms=data.bathrooms,
            size_sqft=data.size_sqft,
            furnishing=data.furnishing,
            status=data.status,
        )
        self.db.add(prop)
        self.db.commit()
        self.db.refresh(prop)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_CREATED",
                entity_type="property",
                entity_id=str(prop.id),
                new_value={
                    "canonical_name": prop.canonical_name,
                    "building_name": prop.building_name,
                    "property_type": prop.property_type.value,
                    "status": prop.status.value,
                    "bedrooms": prop.bedrooms,
                },
            )
        )

        return prop

    def list_properties(
        self,
        property_type: Optional[PropertyType] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        bedrooms: Optional[int] = None,
        property_status: Optional[PropertyStatus] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Property]:
        query = self.db.query(Property)

        if property_type:
            query = query.filter(Property.property_type == property_type)
        if country:
            query = query.filter(Property.country.ilike(f"%{country}%"))
        if city:
            query = query.filter(Property.city.ilike(f"%{city}%"))
        if bedrooms is not None:
            query = query.filter(Property.bedrooms == bedrooms)
        if property_status:
            query = query.filter(Property.status == property_status)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Property.canonical_name.ilike(pattern),
                    Property.building_name.ilike(pattern),
                    Property.address_line_1.ilike(pattern),
                    Property.postal_code.ilike(pattern),
                    Property.district.ilike(pattern),
                    Property.city.ilike(pattern),
                )
            )

        return query.order_by(Property.created_at.desc()).offset(skip).limit(limit).all()

    def update_property(
        self, property_id: uuid.UUID, data: PropertyUpdate, actor_id: str = "system"
    ) -> Property:
        prop = self.get_property_or_404(property_id)
        old_val = {
            "canonical_name": prop.canonical_name,
            "property_type": prop.property_type.value,
            "status": prop.status.value,
            "bedrooms": prop.bedrooms,
        }

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(prop, key, value)

        self.db.commit()
        self.db.refresh(prop)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_UPDATED",
                entity_type="property",
                entity_id=str(prop.id),
                old_value=old_val,
                new_value={
                    "canonical_name": prop.canonical_name,
                    "property_type": prop.property_type.value,
                    "status": prop.status.value,
                    "bedrooms": prop.bedrooms,
                },
            )
        )

        return prop

    def archive_property(self, property_id: uuid.UUID, actor_id: str = "system") -> Property:
        prop = self.get_property_or_404(property_id)
        old_status = prop.status.value
        prop.status = PropertyStatus.ARCHIVED
        self.db.commit()
        self.db.refresh(prop)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_ARCHIVED",
                entity_type="property",
                entity_id=str(prop.id),
                old_value={"status": old_status},
                new_value={"status": prop.status.value},
            )
        )
        return prop

    def get_listings_count(self, property_id: uuid.UUID) -> int:
        return (
            self.db.query(func.count(PropertyListing.id))
            .filter(PropertyListing.property_id == property_id)
            .scalar()
            or 0
        )
