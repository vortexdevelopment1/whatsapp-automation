import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_agent import PropertyAgent
from app.models.property_import_batch import PropertyImportBatch
from app.models.property_import_row import PropertyImportRow
from app.models.property_duplicate_review import PropertyDuplicateReview
from app.models.enums import (
    PropertyImportType,
    PropertyImportBatchStatus,
    PropertyImportRowStatus,
    DuplicateReviewStatus,
    DuplicateConfidenceLevel,
    PropertyStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertySourceStatus,
    PropertyAgentStatus,
)
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.property_normalizer import PropertyNormalizer
from app.services.property_deduplication_service import PropertyDeduplicationService


class PropertyImportService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)
        self.dedup_service = PropertyDeduplicationService(db)

    def get_batch_or_404(self, batch_id: uuid.UUID) -> PropertyImportBatch:
        batch = (
            self.db.query(PropertyImportBatch)
            .options(joinedload(PropertyImportBatch.source))
            .filter(PropertyImportBatch.id == batch_id)
            .first()
        )
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import batch '{batch_id}' not found.",
            )
        return batch

    def parse_and_validate_csv(
        self, source_id: uuid.UUID, file_name: str, csv_text: str, actor_id: str = "system"
    ) -> PropertyImportBatch:
        source = (
            self.db.query(PropertySource)
            .filter(PropertySource.id == source_id)
            .first()
        )
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property source '{source_id}' not found.",
            )
        if source.status != PropertySourceStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property source '{source.name}' is inactive.",
            )

        if not csv_text or not csv_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded CSV file is empty.",
            )

        batch = PropertyImportBatch(
            source_id=source_id,
            file_name=file_name,
            import_type=PropertyImportType.CSV,
            status=PropertyImportBatchStatus.VALIDATING,
            created_by=actor_id,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            batch.status = PropertyImportBatchStatus.FAILED
            batch.error_summary = {"error": "CSV contains no headers."}
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV contains no valid headers.",
            )

        total_rows = 0
        valid_rows = 0
        invalid_rows = 0

        for row_idx, raw_row in enumerate(reader, start=1):
            total_rows += 1
            # Clean dictionary keys and values
            clean_raw = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
            row_errors: List[str] = []

            # 1. Price validation
            norm_price = None
            price_raw = clean_raw.get("asking_price") or clean_raw.get("price")
            if price_raw:
                try:
                    norm_price = PropertyNormalizer.normalize_price(price_raw)
                except ValueError as e:
                    row_errors.append(f"Invalid asking price: {str(e)}")

            # 2. Currency normalization
            currency_raw = clean_raw.get("currency")
            norm_curr, was_defaulted = PropertyNormalizer.normalize_currency(currency_raw, "SGD")

            # 3. Property Type
            type_raw = clean_raw.get("property_type")
            norm_type = PropertyNormalizer.normalize_property_type(type_raw)

            # 4. Furnishing
            furn_raw = clean_raw.get("furnishing")
            norm_furn = PropertyNormalizer.normalize_furnishing(furn_raw)

            # 5. Bedrooms & Bathrooms
            beds_raw = clean_raw.get("bedrooms")
            norm_beds = None
            if beds_raw:
                try:
                    norm_beds = PropertyNormalizer.normalize_bedrooms(beds_raw)
                except ValueError as e:
                    row_errors.append(f"Invalid bedrooms: {str(e)}")

            baths_raw = clean_raw.get("bathrooms")
            norm_baths = None
            if baths_raw:
                try:
                    norm_baths = PropertyNormalizer.normalize_bathrooms(baths_raw)
                except ValueError as e:
                    row_errors.append(f"Invalid bathrooms: {str(e)}")

            # 6. Lease Terms
            min_lease_raw = clean_raw.get("lease_min_months")
            max_lease_raw = clean_raw.get("lease_max_months")
            norm_min_lease, norm_max_lease = None, None
            if min_lease_raw or max_lease_raw:
                try:
                    norm_min_lease, norm_max_lease = PropertyNormalizer.normalize_lease_terms(
                        min_lease_raw, max_lease_raw
                    )
                except ValueError as e:
                    row_errors.append(f"Invalid lease terms: {str(e)}")

            # 7. Available From Date
            avail_from_raw = clean_raw.get("available_from")
            norm_avail_from = None
            if avail_from_raw:
                try:
                    norm_avail_from = PropertyNormalizer.normalize_date(avail_from_raw)
                except ValueError as e:
                    row_errors.append(f"Invalid available_from date: {str(e)}")

            # 8. Availability Status
            avail_stat_raw = clean_raw.get("availability_status")
            norm_avail_status = PropertyNormalizer.normalize_availability(avail_stat_raw)

            # 9. Address Normalization
            norm_addr = PropertyNormalizer.normalize_address(
                address_line_1=clean_raw.get("address_line_1"),
                address_line_2=clean_raw.get("address_line_2"),
                unit_number=clean_raw.get("unit_number"),
                building_name=clean_raw.get("building_name"),
                postal_code=clean_raw.get("postal_code"),
                city=clean_raw.get("city", "Singapore"),
                country=clean_raw.get("country", "Singapore"),
            )

            # 10. Agent Normalization
            norm_agent = PropertyNormalizer.normalize_agent(
                name=clean_raw.get("agent_name"),
                phone=clean_raw.get("agent_phone"),
                email=clean_raw.get("agent_email"),
                agency=clean_raw.get("agent_agency"),
                reg_no=clean_raw.get("agent_registration_number"),
            )

            is_valid = len(row_errors) == 0
            if is_valid:
                valid_rows += 1
                row_status = PropertyImportRowStatus.VALID
            else:
                invalid_rows += 1
                row_status = PropertyImportRowStatus.INVALID

            norm_payload = {
                "property_name": clean_raw.get("property_name") or clean_raw.get("building_name"),
                "building_name": clean_raw.get("building_name"),
                "address_line_1": clean_raw.get("address_line_1"),
                "address_line_2": clean_raw.get("address_line_2"),
                "unit_number": norm_addr["unit_normalized"],
                "postal_code": norm_addr["postal_code_normalized"],
                "city": clean_raw.get("city", "Singapore"),
                "state_region": clean_raw.get("state_region"),
                "district": clean_raw.get("district"),
                "country": clean_raw.get("country", "Singapore"),
                "address_normalized": norm_addr["address_normalized"],
                "property_fingerprint": norm_addr["property_fingerprint"],
                "property_type": norm_type.value,
                "bedrooms": norm_beds,
                "bathrooms": float(norm_baths) if norm_baths is not None else None,
                "size_sqft": float(clean_raw["size_sqft"]) if clean_raw.get("size_sqft") and clean_raw["size_sqft"].replace(".", "", 1).isdigit() else None,
                "furnishing": norm_furn.value,
                "source_listing_id": clean_raw.get("source_listing_id"),
                "source_url": clean_raw.get("source_url"),
                "asking_price": float(norm_price) if norm_price is not None else None,
                "currency": norm_curr,
                "currency_defaulted": was_defaulted,
                "availability_status": norm_avail_status.value,
                "available_from": norm_avail_from.isoformat() if norm_avail_from else None,
                "lease_min_months": norm_min_lease,
                "lease_max_months": norm_max_lease,
                "agent": norm_agent,
            }

            import_row = PropertyImportRow(
                batch_id=batch.id,
                row_number=row_idx,
                raw_payload=clean_raw,
                normalized_payload=norm_payload,
                status=row_status,
                error_codes=row_errors if row_errors else None,
            )
            self.db.add(import_row)

        batch.total_rows = total_rows
        batch.valid_rows = valid_rows
        batch.invalid_rows = invalid_rows
        batch.status = PropertyImportBatchStatus.UPLOADED
        self.db.commit()
        self.db.refresh(batch)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_IMPORT_UPLOADED",
                entity_type="property_import_batch",
                entity_id=str(batch.id),
                new_value={
                    "file_name": file_name,
                    "total_rows": total_rows,
                    "valid_rows": valid_rows,
                    "invalid_rows": invalid_rows,
                },
            )
        )

        return batch

    def preview_batch(self, batch_id: uuid.UUID) -> Dict[str, Any]:
        batch = self.get_batch_or_404(batch_id)
        rows = (
            self.db.query(PropertyImportRow)
            .filter(PropertyImportRow.batch_id == batch_id)
            .order_by(PropertyImportRow.row_number.asc())
            .all()
        )

        duplicate_listing_rows = 0
        matched_existing_property_rows = 0
        new_property_rows = 0
        manual_review_rows = 0

        row_previews = []

        for r in rows:
            if r.status == PropertyImportRowStatus.INVALID:
                row_previews.append({
                    "row_number": r.row_number,
                    "status": "INVALID",
                    "errors": r.error_codes,
                    "dedup_result": None,
                    "raw_payload": r.raw_payload,
                    "normalized_payload": r.normalized_payload,
                })
                continue

            norm = r.normalized_payload or {}
            source_listing_id = norm.get("source_listing_id")

            # 1. Source duplicate check
            existing_listing = self.dedup_service.check_source_duplicate_listing(
                batch.source_id, source_listing_id
            )
            if existing_listing:
                duplicate_listing_rows += 1
                dedup_res = {
                    "action": "UPDATE_EXISTING_LISTING",
                    "existing_listing_id": str(existing_listing.id),
                    "property_id": str(existing_listing.property_id),
                    "reasons": ["exact_source_and_listing_id"],
                }
                status_label = "DUPLICATE_LISTING"
            else:
                # 2. Canonical property candidate check
                candidate = self.dedup_service.find_canonical_property_candidate(
                    country=norm.get("country", "Singapore"),
                    postal_code=norm.get("postal_code"),
                    unit_number=norm.get("unit_number"),
                    address_normalized=norm.get("address_normalized"),
                    building_name=norm.get("building_name"),
                    property_fingerprint=norm.get("property_fingerprint"),
                    bedrooms=norm.get("bedrooms"),
                )

                if candidate["result"] == "MATCH_EXISTING_PROPERTY":
                    matched_existing_property_rows += 1
                    status_label = "MATCHED_EXISTING_PROPERTY"
                    dedup_res = {
                        "action": "ATTACH_TO_EXISTING_PROPERTY",
                        "property_id": str(candidate["property_id"]),
                        "confidence": candidate["confidence"],
                        "reasons": candidate["reasons"],
                    }
                elif candidate["result"] == "NEEDS_REVIEW":
                    manual_review_rows += 1
                    status_label = "NEEDS_REVIEW"
                    dedup_res = {
                        "action": "MANUAL_REVIEW_REQUIRED",
                        "candidate_property_id": str(candidate["property_id"]) if candidate.get("property_id") else None,
                        "confidence": candidate["confidence"],
                        "reasons": candidate["reasons"],
                    }
                else:
                    new_property_rows += 1
                    status_label = "NEW_PROPERTY_CREATED"
                    dedup_res = {
                        "action": "CREATE_NEW_PROPERTY",
                        "reasons": candidate["reasons"],
                    }

            r.deduplication_result = dedup_res
            row_previews.append({
                "row_number": r.row_number,
                "status": status_label,
                "errors": None,
                "dedup_result": dedup_res,
                "raw_payload": r.raw_payload,
                "normalized_payload": norm,
            })

        self.db.commit()

        return {
            "batch_id": str(batch.id),
            "status": batch.status.value,
            "counts": {
                "total_rows": batch.total_rows,
                "valid_rows": batch.valid_rows,
                "invalid_rows": batch.invalid_rows,
                "duplicate_listing_rows": duplicate_listing_rows,
                "matched_existing_property_rows": matched_existing_property_rows,
                "new_property_rows": new_property_rows,
                "manual_review_rows": manual_review_rows,
            },
            "rows": row_previews,
        }

    def commit_batch(self, batch_id: uuid.UUID, actor_id: str = "system") -> PropertyImportBatch:
        batch = self.get_batch_or_404(batch_id)
        if batch.status in (PropertyImportBatchStatus.COMPLETED, PropertyImportBatchStatus.COMPLETED_WITH_WARNINGS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch '{batch_id}' has already been committed.",
            )

        batch.status = PropertyImportBatchStatus.PROCESSING
        batch.started_at = datetime.now(timezone.utc)
        self.db.commit()

        # Audit start
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_IMPORT_STARTED",
                entity_type="property_import_batch",
                entity_id=str(batch.id),
                new_value={"status": batch.status.value},
            )
        )

        rows = (
            self.db.query(PropertyImportRow)
            .filter(PropertyImportRow.batch_id == batch_id)
            .order_by(PropertyImportRow.row_number.asc())
            .all()
        )

        duplicate_listing_count = 0
        matched_prop_count = 0
        new_prop_count = 0
        review_count = 0

        for r in rows:
            # Skip invalid or already completed rows
            if r.status in (
                PropertyImportRowStatus.INVALID,
                PropertyImportRowStatus.DUPLICATE_LISTING,
                PropertyImportRowStatus.MATCHED_EXISTING_PROPERTY,
                PropertyImportRowStatus.NEW_PROPERTY_CREATED,
            ):
                continue

            norm = r.normalized_payload or {}
            source_listing_id = norm.get("source_listing_id")

            # 1. Check if source listing already exists
            existing_listing = self.dedup_service.check_source_duplicate_listing(
                batch.source_id, source_listing_id
            )

            if existing_listing:
                # Update existing listing if price/availability changed
                old_price = existing_listing.asking_price
                new_price = Decimal(str(norm["asking_price"])) if norm.get("asking_price") is not None else None
                new_avail = ListingAvailabilityStatus(norm.get("availability_status", "UNKNOWN"))

                has_changes = False
                if new_price is not None and old_price != new_price:
                    existing_listing.asking_price = new_price
                    has_changes = True

                if existing_listing.availability_status != new_avail:
                    existing_listing.availability_status = new_avail
                    has_changes = True

                if norm.get("available_from"):
                    existing_listing.available_from = datetime.fromisoformat(norm["available_from"]).date()
                    has_changes = True

                if norm.get("lease_min_months"):
                    existing_listing.lease_min_months = norm["lease_min_months"]
                    has_changes = True

                existing_listing.last_verified_at = datetime.now(timezone.utc)
                if has_changes:
                    self.audit_repo.log(
                        AuditLogCreate(
                            actor_id=actor_id,
                            action="LISTING_UPDATED_FROM_IMPORT",
                            entity_type="property_listing",
                            entity_id=str(existing_listing.id),
                            old_value={"price": str(old_price) if old_price else None},
                            new_value={"price": str(new_price) if new_price else None, "availability": new_avail.value},
                        )
                    )

                r.listing_id = existing_listing.id
                r.property_id = existing_listing.property_id
                r.status = PropertyImportRowStatus.DUPLICATE_LISTING
                r.processed_at = datetime.now(timezone.utc)
                duplicate_listing_count += 1
                continue

            # 2. Check canonical property candidate
            candidate = self.dedup_service.find_canonical_property_candidate(
                country=norm.get("country", "Singapore"),
                postal_code=norm.get("postal_code"),
                unit_number=norm.get("unit_number"),
                address_normalized=norm.get("address_normalized"),
                building_name=norm.get("building_name"),
                property_fingerprint=norm.get("property_fingerprint"),
                bedrooms=norm.get("bedrooms"),
            )

            # Ensure or find listing agent if provided
            agent_id = self._resolve_or_create_agent(norm.get("agent"), batch.source_id, actor_id)

            if candidate["result"] == "MATCH_EXISTING_PROPERTY":
                matched_prop_id = candidate["property_id"]
                listing = self._create_listing_for_property(
                    property_id=matched_prop_id,
                    source_id=batch.source_id,
                    norm=norm,
                    agent_id=agent_id,
                    actor_id=actor_id,
                )
                r.property_id = matched_prop_id
                r.listing_id = listing.id
                r.status = PropertyImportRowStatus.MATCHED_EXISTING_PROPERTY
                r.processed_at = datetime.now(timezone.utc)
                matched_prop_count += 1

            elif candidate["result"] == "NEEDS_REVIEW":
                # Create PropertyDuplicateReview entry
                review = PropertyDuplicateReview(
                    batch_id=batch.id,
                    import_row_id=r.id,
                    candidate_property_id=candidate.get("property_id"),
                    incoming_normalized_data=norm,
                    match_reasons=candidate["reasons"],
                    confidence_level=DuplicateConfidenceLevel(candidate["confidence"]),
                    status=DuplicateReviewStatus.OPEN,
                )
                self.db.add(review)
                r.status = PropertyImportRowStatus.NEEDS_REVIEW
                r.processed_at = datetime.now(timezone.utc)
                review_count += 1

            else:
                # NEW_PROPERTY_CREATED
                new_prop = Property(
                    canonical_name=norm.get("property_name") or norm.get("building_name") or "New Imported Property",
                    building_name=norm.get("building_name"),
                    address_line_1=norm.get("address_line_1"),
                    address_line_2=norm.get("address_line_2"),
                    unit_number=norm.get("unit_number"),
                    postal_code=norm.get("postal_code"),
                    city=norm.get("city", "Singapore"),
                    state_region=norm.get("state_region"),
                    district=norm.get("district"),
                    country=norm.get("country", "Singapore"),
                    address_normalized=norm.get("address_normalized"),
                    property_fingerprint=norm.get("property_fingerprint"),
                    property_type=norm.get("property_type", "CONDO"),
                    bedrooms=norm.get("bedrooms"),
                    bathrooms=Decimal(str(norm["bathrooms"])) if norm.get("bathrooms") is not None else None,
                    size_sqft=Decimal(str(norm["size_sqft"])) if norm.get("size_sqft") is not None else None,
                    furnishing=norm.get("furnishing", "UNKNOWN"),
                    status=PropertyStatus.ACTIVE,
                )
                self.db.add(new_prop)
                self.db.commit()
                self.db.refresh(new_prop)

                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="PROPERTY_CREATED_FROM_IMPORT",
                        entity_type="property",
                        entity_id=str(new_prop.id),
                        new_value={"canonical_name": new_prop.canonical_name},
                    )
                )

                listing = self._create_listing_for_property(
                    property_id=new_prop.id,
                    source_id=batch.source_id,
                    norm=norm,
                    agent_id=agent_id,
                    actor_id=actor_id,
                )
                r.property_id = new_prop.id
                r.listing_id = listing.id
                r.status = PropertyImportRowStatus.NEW_PROPERTY_CREATED
                r.processed_at = datetime.now(timezone.utc)
                new_prop_count += 1

        batch.duplicate_listing_rows = duplicate_listing_count
        batch.matched_existing_property_rows = matched_prop_count
        batch.new_property_rows = new_prop_count
        batch.manual_review_rows = review_count
        batch.completed_at = datetime.now(timezone.utc)

        if batch.invalid_rows > 0 or review_count > 0:
            batch.status = PropertyImportBatchStatus.COMPLETED_WITH_WARNINGS
        else:
            batch.status = PropertyImportBatchStatus.COMPLETED

        self.db.commit()
        self.db.refresh(batch)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_IMPORT_COMPLETED",
                entity_type="property_import_batch",
                entity_id=str(batch.id),
                new_value={
                    "status": batch.status.value,
                    "matched_existing": matched_prop_count,
                    "new_properties": new_prop_count,
                    "duplicate_listings": duplicate_listing_count,
                    "manual_reviews": review_count,
                },
            )
        )

        return batch

    def retry_batch(self, batch_id: uuid.UUID, actor_id: str = "system") -> PropertyImportBatch:
        batch = self.get_batch_or_404(batch_id)
        # Find rows that are pending or failed
        pending_rows = (
            self.db.query(PropertyImportRow)
            .filter(
                PropertyImportRow.batch_id == batch_id,
                PropertyImportRow.status.in_([
                    PropertyImportRowStatus.PENDING,
                    PropertyImportRowStatus.FAILED,
                ]),
            )
            .all()
        )
        if not pending_rows:
            return batch

        for r in pending_rows:
            # Re-normalize and retry
            r.status = PropertyImportRowStatus.VALID
        self.db.commit()

        return self.commit_batch(batch_id, actor_id=actor_id)

    def _resolve_or_create_agent(
        self, agent_data: Optional[Dict[str, Any]], source_id: uuid.UUID, actor_id: str
    ) -> Optional[uuid.UUID]:
        if not agent_data or not agent_data.get("full_name"):
            return None

        phone_norm = agent_data.get("phone_normalized")
        agent = None
        if phone_norm:
            agent = (
                self.db.query(PropertyAgent)
                .filter(PropertyAgent.phone_normalized == phone_norm)
                .first()
            )

        if not agent and agent_data.get("registration_number"):
            agent = (
                self.db.query(PropertyAgent)
                .filter(PropertyAgent.registration_number == agent_data["registration_number"])
                .first()
            )

        if not agent:
            agent = PropertyAgent(
                full_name=agent_data.get("full_name"),
                agency_name=agent_data.get("agency_name"),
                registration_number=agent_data.get("registration_number"),
                phone=agent_data.get("phone"),
                phone_normalized=phone_norm,
                email=agent_data.get("email"),
                source_id=source_id,
                status=PropertyAgentStatus.ACTIVE,
            )
            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)

            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="PROPERTY_AGENT_CREATED_FROM_IMPORT",
                    entity_type="property_agent",
                    entity_id=str(agent.id),
                    new_value={"full_name": agent.full_name},
                )
            )

        return agent.id

    def _create_listing_for_property(
        self,
        property_id: uuid.UUID,
        source_id: uuid.UUID,
        norm: Dict[str, Any],
        agent_id: Optional[uuid.UUID],
        actor_id: str,
    ) -> PropertyListing:
        avail_date = None
        if norm.get("available_from"):
            try:
                avail_date = datetime.fromisoformat(norm["available_from"]).date()
            except ValueError:
                pass

        listing = PropertyListing(
            property_id=property_id,
            source_id=source_id,
            source_listing_id=norm.get("source_listing_id"),
            source_url=norm.get("source_url"),
            agent_id=agent_id,
            asking_price=Decimal(str(norm["asking_price"])) if norm.get("asking_price") is not None else None,
            currency=norm.get("currency", "SGD"),
            availability_status=ListingAvailabilityStatus(norm.get("availability_status", "UNKNOWN")),
            available_from=avail_date,
            lease_min_months=norm.get("lease_min_months"),
            lease_max_months=norm.get("lease_max_months"),
            listing_status=PropertyListingStatus.ACTIVE,
            last_verified_at=datetime.now(timezone.utc),
            listing_metadata={"imported_via_batch": True, "currency_defaulted": norm.get("currency_defaulted", False)},
        )
        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LISTING_CREATED_FROM_IMPORT",
                entity_type="property_listing",
                entity_id=str(listing.id),
                new_value={
                    "property_id": str(property_id),
                    "asking_price": str(listing.asking_price) if listing.asking_price else None,
                    "availability": listing.availability_status.value,
                },
            )
        )
        return listing

    # Deduplication review management
    def list_duplicate_reviews(
        self, status_filter: Optional[DuplicateReviewStatus] = None, skip: int = 0, limit: int = 50
    ) -> List[PropertyDuplicateReview]:
        query = (
            self.db.query(PropertyDuplicateReview)
            .options(
                joinedload(PropertyDuplicateReview.candidate_property),
                joinedload(PropertyDuplicateReview.import_row),
            )
        )
        if status_filter:
            query = query.filter(PropertyDuplicateReview.status == status_filter)
        return query.order_by(PropertyDuplicateReview.created_at.desc()).offset(skip).limit(limit).all()

    def get_duplicate_review_or_404(self, review_id: uuid.UUID) -> PropertyDuplicateReview:
        review = (
            self.db.query(PropertyDuplicateReview)
            .options(
                joinedload(PropertyDuplicateReview.candidate_property),
                joinedload(PropertyDuplicateReview.import_row),
            )
            .filter(PropertyDuplicateReview.id == review_id)
            .first()
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Duplicate review '{review_id}' not found.",
            )
        return review

    def resolve_review_attach(
        self, review_id: uuid.UUID, property_id: uuid.UUID, actor_id: str = "system"
    ) -> PropertyDuplicateReview:
        review = self.get_duplicate_review_or_404(review_id)
        prop = self.db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target property '{property_id}' not found.",
            )

        norm = review.incoming_normalized_data
        agent_id = self._resolve_or_create_agent(norm.get("agent"), review.batch.source_id if review.batch else None, actor_id)

        listing = self._create_listing_for_property(
            property_id=prop.id,
            source_id=review.batch.source_id,
            norm=norm,
            agent_id=agent_id,
            actor_id=actor_id,
        )

        review.status = DuplicateReviewStatus.ATTACHED_EXISTING
        review.resolved_by = actor_id
        review.resolved_at = datetime.now(timezone.utc)
        review.resolution_reason = f"Operator resolved uncertain duplicate by attaching listing to property '{prop.id}'."

        if review.import_row:
            review.import_row.property_id = prop.id
            review.import_row.listing_id = listing.id
            review.import_row.status = PropertyImportRowStatus.MATCHED_EXISTING_PROPERTY

        self.db.commit()
        self.db.refresh(review)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="DUPLICATE_REVIEW_RESOLVED_ATTACHED",
                entity_type="property_duplicate_review",
                entity_id=str(review.id),
                new_value={"property_id": str(prop.id), "listing_id": str(listing.id)},
            )
        )
        return review

    def resolve_review_create_new(
        self, review_id: uuid.UUID, actor_id: str = "system"
    ) -> PropertyDuplicateReview:
        review = self.get_duplicate_review_or_404(review_id)
        norm = review.incoming_normalized_data

        new_prop = Property(
            canonical_name=norm.get("property_name") or norm.get("building_name") or "New Reviewed Property",
            building_name=norm.get("building_name"),
            address_line_1=norm.get("address_line_1"),
            address_line_2=norm.get("address_line_2"),
            unit_number=norm.get("unit_number"),
            postal_code=norm.get("postal_code"),
            city=norm.get("city", "Singapore"),
            district=norm.get("district"),
            country=norm.get("country", "Singapore"),
            address_normalized=norm.get("address_normalized"),
            property_fingerprint=norm.get("property_fingerprint"),
            property_type=norm.get("property_type", "CONDO"),
            bedrooms=norm.get("bedrooms"),
            bathrooms=Decimal(str(norm["bathrooms"])) if norm.get("bathrooms") is not None else None,
            size_sqft=Decimal(str(norm["size_sqft"])) if norm.get("size_sqft") is not None else None,
            furnishing=norm.get("furnishing", "UNKNOWN"),
            status=PropertyStatus.ACTIVE,
        )
        self.db.add(new_prop)
        self.db.commit()
        self.db.refresh(new_prop)

        agent_id = self._resolve_or_create_agent(norm.get("agent"), review.batch.source_id if review.batch else None, actor_id)

        listing = self._create_listing_for_property(
            property_id=new_prop.id,
            source_id=review.batch.source_id,
            norm=norm,
            agent_id=agent_id,
            actor_id=actor_id,
        )

        review.status = DuplicateReviewStatus.CREATED_NEW
        review.resolved_by = actor_id
        review.resolved_at = datetime.now(timezone.utc)
        review.resolution_reason = "Operator decided candidate was a distinct physical property and created a new record."

        if review.import_row:
            review.import_row.property_id = new_prop.id
            review.import_row.listing_id = listing.id
            review.import_row.status = PropertyImportRowStatus.NEW_PROPERTY_CREATED

        self.db.commit()
        self.db.refresh(review)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="DUPLICATE_REVIEW_RESOLVED_CREATED_NEW",
                entity_type="property_duplicate_review",
                entity_id=str(review.id),
                new_value={"new_property_id": str(new_prop.id), "listing_id": str(listing.id)},
            )
        )
        return review

    def resolve_review_ignore(
        self, review_id: uuid.UUID, reason: str, actor_id: str = "system"
    ) -> PropertyDuplicateReview:
        review = self.get_duplicate_review_or_404(review_id)
        review.status = DuplicateReviewStatus.IGNORED
        review.resolved_by = actor_id
        review.resolved_at = datetime.now(timezone.utc)
        review.resolution_reason = reason

        self.db.commit()
        self.db.refresh(review)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="DUPLICATE_REVIEW_IGNORED",
                entity_type="property_duplicate_review",
                entity_id=str(review.id),
                new_value={"reason": reason},
            )
        )
        return review
