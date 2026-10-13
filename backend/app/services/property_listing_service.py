import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_agent import PropertyAgent
from app.models.enums import (
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertySourceStatus,
    PropertyAgentStatus,
    PropertyStatus,
)
from app.schemas.property_listing import (
    PropertyListingCreate,
    PropertyListingUpdate,
    PropertyListingResponse,
)
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate


class PropertyListingService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def get_listing_or_404(self, listing_id: uuid.UUID) -> PropertyListing:
        listing = (
            self.db.query(PropertyListing)
            .options(
                joinedload(PropertyListing.property),
                joinedload(PropertyListing.source),
                joinedload(PropertyListing.agent),
            )
            .filter(PropertyListing.id == listing_id)
            .first()
        )
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property listing with ID '{listing_id}' not found.",
            )
        return listing

    def create_listing(
        self, property_id: uuid.UUID, data: PropertyListingCreate, actor_id: str = "system"
    ) -> PropertyListing:
        # 1. Verify Property
        prop = self.db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property with ID '{property_id}' not found.",
            )
        if prop.status == PropertyStatus.ARCHIVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add a listing to an archived property.",
            )

        # 2. Verify Source
        source = (
            self.db.query(PropertySource)
            .filter(PropertySource.id == data.source_id)
            .first()
        )
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property source with ID '{data.source_id}' not found.",
            )
        if source.status != PropertySourceStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property source '{source.name}' is inactive.",
            )

        # 3. Verify Agent if supplied
        if data.agent_id:
            agent = (
                self.db.query(PropertyAgent)
                .filter(PropertyAgent.id == data.agent_id)
                .first()
            )
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Property agent with ID '{data.agent_id}' not found.",
                )
            if agent.status == PropertyAgentStatus.ARCHIVED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign an archived property agent.",
                )

        # 4. Check uniqueness of source_id + source_listing_id
        if data.source_listing_id:
            duplicate = (
                self.db.query(PropertyListing)
                .filter(
                    PropertyListing.source_id == data.source_id,
                    PropertyListing.source_listing_id == data.source_listing_id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Listing with source_listing_id '{data.source_listing_id}' already exists for this source.",
                )

        # 5. Persist listing with provenance
        listing = PropertyListing(
            property_id=property_id,
            source_id=data.source_id,
            source_listing_id=data.source_listing_id,
            source_url=data.source_url,
            listing_reference=data.listing_reference,
            agent_id=data.agent_id,
            asking_price=data.asking_price,
            currency=data.currency or "SGD",
            availability_status=data.availability_status or ListingAvailabilityStatus.UNKNOWN,
            available_from=data.available_from,
            lease_min_months=data.lease_min_months,
            lease_max_months=data.lease_max_months,
            listing_status=data.listing_status or PropertyListingStatus.ACTIVE,
            source_last_updated_at=data.source_last_updated_at,
            last_verified_at=data.last_verified_at,
            listing_metadata=data.metadata,
        )
        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LISTING_CREATED",
                entity_type="property_listing",
                entity_id=str(listing.id),
                new_value={
                    "property_id": str(property_id),
                    "source_id": str(data.source_id),
                    "agent_id": str(data.agent_id) if data.agent_id else None,
                    "asking_price": str(listing.asking_price) if listing.asking_price else None,
                    "currency": listing.currency,
                    "availability_status": listing.availability_status.value,
                    "listing_status": listing.listing_status.value,
                },
            )
        )

        return self.get_listing_or_404(listing.id)

    def list_listings_for_property(
        self,
        property_id: uuid.UUID,
        listing_status: Optional[PropertyListingStatus] = None,
        availability_status: Optional[ListingAvailabilityStatus] = None,
    ) -> List[PropertyListing]:
        query = (
            self.db.query(PropertyListing)
            .options(
                joinedload(PropertyListing.source),
                joinedload(PropertyListing.agent),
            )
            .filter(PropertyListing.property_id == property_id)
        )
        if listing_status:
            query = query.filter(PropertyListing.listing_status == listing_status)
        if availability_status:
            query = query.filter(PropertyListing.availability_status == availability_status)

        return query.order_by(PropertyListing.created_at.desc()).all()

    def list_listings(
        self,
        property_id: Optional[uuid.UUID] = None,
        source_id: Optional[uuid.UUID] = None,
        agent_id: Optional[uuid.UUID] = None,
        listing_status: Optional[PropertyListingStatus] = None,
        availability_status: Optional[ListingAvailabilityStatus] = None,
        currency: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[PropertyListing]:
        query = (
            self.db.query(PropertyListing)
            .options(
                joinedload(PropertyListing.source),
                joinedload(PropertyListing.agent),
            )
        )
        if property_id:
            query = query.filter(PropertyListing.property_id == property_id)
        if source_id:
            query = query.filter(PropertyListing.source_id == source_id)
        if agent_id:
            query = query.filter(PropertyListing.agent_id == agent_id)
        if listing_status:
            query = query.filter(PropertyListing.listing_status == listing_status)
        if availability_status:
            query = query.filter(PropertyListing.availability_status == availability_status)
        if currency:
            query = query.filter(PropertyListing.currency == currency.upper())

        return query.order_by(PropertyListing.created_at.desc()).offset(skip).limit(limit).all()

    def update_listing(
        self, listing_id: uuid.UUID, data: PropertyListingUpdate, actor_id: str = "system"
    ) -> PropertyListing:
        listing = self.get_listing_or_404(listing_id)
        old_val = {
            "asking_price": str(listing.asking_price) if listing.asking_price else None,
            "currency": listing.currency,
            "availability_status": listing.availability_status.value,
            "listing_status": listing.listing_status.value,
            "agent_id": str(listing.agent_id) if listing.agent_id else None,
        }

        update_dict = data.model_dump(exclude_unset=True)

        if "source_id" in update_dict and update_dict["source_id"]:
            source = (
                self.db.query(PropertySource)
                .filter(PropertySource.id == update_dict["source_id"])
                .first()
            )
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Property source with ID '{update_dict['source_id']}' not found.",
                )

        if "agent_id" in update_dict and update_dict["agent_id"]:
            agent = (
                self.db.query(PropertyAgent)
                .filter(PropertyAgent.id == update_dict["agent_id"])
                .first()
            )
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Property agent with ID '{update_dict['agent_id']}' not found.",
                )

        if "metadata" in update_dict:
            update_dict["listing_metadata"] = update_dict.pop("metadata")

        for key, value in update_dict.items():
            setattr(listing, key, value)

        self.db.commit()
        self.db.refresh(listing)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LISTING_UPDATED",
                entity_type="property_listing",
                entity_id=str(listing.id),
                old_value=old_val,
                new_value={
                    "asking_price": str(listing.asking_price) if listing.asking_price else None,
                    "currency": listing.currency,
                    "availability_status": listing.availability_status.value,
                    "listing_status": listing.listing_status.value,
                    "agent_id": str(listing.agent_id) if listing.agent_id else None,
                },
            )
        )

        return self.get_listing_or_404(listing.id)

    def archive_listing(self, listing_id: uuid.UUID, actor_id: str = "system") -> PropertyListing:
        listing = self.get_listing_or_404(listing_id)
        old_status = listing.listing_status.value
        listing.listing_status = PropertyListingStatus.ARCHIVED
        self.db.commit()
        self.db.refresh(listing)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LISTING_ARCHIVED",
                entity_type="property_listing",
                entity_id=str(listing.id),
                old_value={"listing_status": old_status},
                new_value={"listing_status": listing.listing_status.value},
            )
        )
        return self.get_listing_or_404(listing.id)

    def update_availability(
        self,
        listing_id: uuid.UUID,
        availability_status: ListingAvailabilityStatus,
        available_from: Optional[date] = None,
        last_verified_at: Optional[datetime] = None,
        actor_id: str = "system",
    ) -> PropertyListing:
        listing = self.get_listing_or_404(listing_id)
        old_status = listing.availability_status.value
        listing.availability_status = availability_status
        if available_from is not None:
            listing.available_from = available_from
        listing.last_verified_at = last_verified_at or datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(listing)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AVAILABILITY_STATUS_UPDATED",
                entity_type="property_listing",
                entity_id=str(listing.id),
                old_value={"availability_status": old_status},
                new_value={
                    "availability_status": listing.availability_status.value,
                    "last_verified_at": listing.last_verified_at.isoformat() if listing.last_verified_at else None,
                },
            )
        )
        return self.get_listing_or_404(listing.id)

    @staticmethod
    def format_listing_response(listing: PropertyListing) -> PropertyListingResponse:
        return PropertyListingResponse(
            id=listing.id,
            property_id=listing.property_id,
            source_id=listing.source_id,
            source_listing_id=listing.source_listing_id,
            source_url=listing.source_url,
            listing_reference=listing.listing_reference,
            agent_id=listing.agent_id,
            asking_price=listing.asking_price,
            currency=listing.currency,
            availability_status=listing.availability_status,
            available_from=listing.available_from,
            lease_min_months=listing.lease_min_months,
            lease_max_months=listing.lease_max_months,
            listing_status=listing.listing_status,
            source_last_updated_at=listing.source_last_updated_at,
            last_verified_at=listing.last_verified_at,
            metadata=listing.listing_metadata,
            source_name=listing.source.name if listing.source else None,
            agent_name=listing.agent.full_name if listing.agent else None,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )
