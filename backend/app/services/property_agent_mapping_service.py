import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.enums import PropertyAgentStatus, AgentMappingStatus
from app.schemas.property_agent_outreach import PropertyAgentMappingResult
from app.services.phone_service import normalize_phone_number, PhoneNormalizationError


class PropertyAgentMappingService:
    """
    Resolves the listing/property agent associated with a PropertyMatch,
    validates agent status and contactability, and returns a structured mapping result.
    """

    def __init__(self, db: Session):
        self.db = db

    def resolve_agent_for_match(self, match: PropertyMatch) -> PropertyAgentMappingResult:
        if not match.listing_id and not match.listing:
            return PropertyAgentMappingResult(
                match_id=match.id,
                mapping_status=AgentMappingStatus.MISSING_AGENT,
                error_message="Match has no associated property listing",
            )

        listing = match.listing
        if not listing:
            listing = self.db.query(PropertyListing).filter(PropertyListing.id == match.listing_id).first()

        if not listing:
            return PropertyAgentMappingResult(
                match_id=match.id,
                mapping_status=AgentMappingStatus.MISSING_AGENT,
                error_message="Associated property listing not found in database",
            )

        if not listing.agent_id and not listing.agent:
            return PropertyAgentMappingResult(
                match_id=match.id,
                listing_id=listing.id,
                mapping_status=AgentMappingStatus.MISSING_AGENT,
                error_message="Listing has no associated property agent",
            )

        agent = listing.agent
        if not agent:
            agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == listing.agent_id).first()

        if not agent:
            return PropertyAgentMappingResult(
                match_id=match.id,
                listing_id=listing.id,
                mapping_status=AgentMappingStatus.MISSING_AGENT,
                error_message="Listing agent record not found in database",
            )

        # Check agent status
        if agent.status != PropertyAgentStatus.ACTIVE:
            return PropertyAgentMappingResult(
                match_id=match.id,
                listing_id=listing.id,
                property_agent_id=agent.id,
                agent_name=agent.full_name,
                agency_name=agent.agency_name,
                phone_raw=agent.phone,
                mapping_status=AgentMappingStatus.AGENT_INACTIVE,
                error_message=f"Property agent '{agent.full_name or agent.id}' is inactive or archived",
            )

        # Validate & normalize phone
        phone_to_check = agent.phone_normalized or agent.phone
        if not phone_to_check or not phone_to_check.strip():
            return PropertyAgentMappingResult(
                match_id=match.id,
                listing_id=listing.id,
                property_agent_id=agent.id,
                agent_name=agent.full_name,
                agency_name=agent.agency_name,
                phone_raw=agent.phone,
                mapping_status=AgentMappingStatus.INVALID_CONTACT,
                error_message="Agent has no phone number",
            )

        try:
            phone_norm = normalize_phone_number(phone_to_check, default_region="SG")
        except PhoneNormalizationError as err:
            return PropertyAgentMappingResult(
                match_id=match.id,
                listing_id=listing.id,
                property_agent_id=agent.id,
                agent_name=agent.full_name,
                agency_name=agent.agency_name,
                phone_raw=agent.phone,
                mapping_status=AgentMappingStatus.INVALID_CONTACT,
                error_message=f"Agent phone '{phone_to_check}' is invalid: {str(err)}",
            )

        return PropertyAgentMappingResult(
            match_id=match.id,
            listing_id=listing.id,
            property_agent_id=agent.id,
            agent_name=agent.full_name,
            agency_name=agent.agency_name,
            phone_raw=agent.phone,
            phone_normalized=phone_norm,
            mapping_status=AgentMappingStatus.READY,
        )
