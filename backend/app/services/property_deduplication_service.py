import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_duplicate_review import PropertyDuplicateReview
from app.models.enums import DuplicateReviewStatus, DuplicateConfidenceLevel


class PropertyDeduplicationService:
    def __init__(self, db: Session):
        self.db = db

    def check_source_duplicate_listing(
        self, source_id: uuid.UUID, source_listing_id: Optional[str]
    ) -> Optional[PropertyListing]:
        """Finds if a listing under this specific source already exists."""
        if not source_listing_id:
            return None
        return (
            self.db.query(PropertyListing)
            .filter(
                PropertyListing.source_id == source_id,
                PropertyListing.source_listing_id == source_listing_id,
            )
            .first()
        )

    def find_canonical_property_candidate(
        self,
        country: str,
        postal_code: Optional[str],
        unit_number: Optional[str],
        address_normalized: Optional[str],
        building_name: Optional[str],
        property_fingerprint: Optional[str],
        bedrooms: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Deterministic deduplication engine evaluating physical property equivalence.
        Returns:
            result: "MATCH_EXISTING_PROPERTY" | "NEW_PROPERTY" | "NEEDS_REVIEW"
            property_id: Optional[UUID]
            confidence: "HIGH" | "MEDIUM" | "LOW"
            reasons: List[str]
        """
        # 1. Strong Deterministic Match by Fingerprint
        if property_fingerprint:
            match = (
                self.db.query(Property)
                .filter(Property.property_fingerprint == property_fingerprint)
                .first()
            )
            if match:
                return {
                    "result": "MATCH_EXISTING_PROPERTY",
                    "property_id": match.id,
                    "confidence": "HIGH",
                    "reasons": ["exact_property_fingerprint"],
                }

        # 2. Strong Match: Exact Postal Code + Exact Unit
        if postal_code and unit_number:
            match = (
                self.db.query(Property)
                .filter(
                    Property.postal_code == postal_code,
                    Property.unit_number.ilike(unit_number),
                )
                .first()
            )
            if match:
                return {
                    "result": "MATCH_EXISTING_PROPERTY",
                    "property_id": match.id,
                    "confidence": "HIGH",
                    "reasons": ["exact_postal_code", "exact_unit_number"],
                }

        # 3. Strong Match: Exact Normalized Address + Exact Unit
        if address_normalized and unit_number:
            match = (
                self.db.query(Property)
                .filter(
                    Property.address_normalized == address_normalized,
                    Property.unit_number.ilike(unit_number),
                )
                .first()
            )
            if match:
                return {
                    "result": "MATCH_EXISTING_PROPERTY",
                    "property_id": match.id,
                    "confidence": "HIGH",
                    "reasons": ["exact_normalized_address", "exact_unit_number"],
                }

        # 4. Strong Match: Coordinates within 20m + Exact Unit
        if latitude is not None and longitude is not None and unit_number:
            # Approx 0.00025 deg lat/long ~ 25 meters
            match = (
                self.db.query(Property)
                .filter(
                    Property.unit_number.ilike(unit_number),
                    Property.latitude.isnot(None),
                    Property.longitude.isnot(None),
                )
                .first()
            )
            if match and match.latitude is not None and match.longitude is not None:
                d_lat = abs(float(match.latitude) - float(latitude))
                d_lng = abs(float(match.longitude) - float(longitude))
                if d_lat < 0.0003 and d_lng < 0.0003:
                    return {
                        "result": "MATCH_EXISTING_PROPERTY",
                        "property_id": match.id,
                        "confidence": "HIGH",
                        "reasons": ["coordinates_proximity", "exact_unit_number"],
                    }

        # 5. Moderate / Uncertain Candidate Detection (NEEDS_REVIEW)
        # Case A: Same postal code, but unit number is missing on incoming or existing
        if postal_code:
            candidate = (
                self.db.query(Property)
                .filter(Property.postal_code == postal_code)
                .first()
            )
            if candidate:
                if not unit_number or not candidate.unit_number:
                    reasons = ["same_postal_code"]
                    if not unit_number:
                        reasons.append("incoming_unit_number_missing")
                    if not candidate.unit_number:
                        reasons.append("existing_unit_number_missing")
                    if bedrooms is not None and candidate.bedrooms == bedrooms:
                        reasons.append("same_bedrooms")

                    return {
                        "result": "NEEDS_REVIEW",
                        "property_id": candidate.id,
                        "confidence": "MEDIUM",
                        "reasons": reasons,
                    }

        # Case B: Same building name and same bedrooms, but unit number missing
        if building_name:
            norm_bldg = building_name.strip()
            candidate = (
                self.db.query(Property)
                .filter(Property.building_name.ilike(f"%{norm_bldg}%"))
                .first()
            )
            if candidate:
                if not unit_number or not candidate.unit_number:
                    reasons = ["same_building_name"]
                    if bedrooms is not None and candidate.bedrooms == bedrooms:
                        reasons.append("same_bedrooms")
                    if not unit_number:
                        reasons.append("incoming_unit_number_missing")

                    return {
                        "result": "NEEDS_REVIEW",
                        "property_id": candidate.id,
                        "confidence": "LOW",
                        "reasons": reasons,
                    }

        # Case C: Same normalized address without unit
        if address_normalized:
            candidate = (
                self.db.query(Property)
                .filter(Property.address_normalized == address_normalized)
                .first()
            )
            if candidate:
                reasons = ["same_normalized_address"]
                if not unit_number or not candidate.unit_number:
                    reasons.append("unit_number_missing")
                    return {
                        "result": "NEEDS_REVIEW",
                        "property_id": candidate.id,
                        "confidence": "MEDIUM",
                        "reasons": reasons,
                    }

        # 6. Distinct new physical property
        return {
            "result": "NEW_PROPERTY",
            "property_id": None,
            "confidence": "HIGH",
            "reasons": ["no_matching_address_or_postal_code"],
        }
