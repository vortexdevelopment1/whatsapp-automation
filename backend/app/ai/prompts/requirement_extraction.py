from app.models.enums import AITaskType
from app.ai.prompts.base import PromptDefinition, BASE_SAFE_SYSTEM_RULES

EXTRACTION_SYSTEM_INSTRUCTIONS = f"""
{BASE_SAFE_SYSTEM_RULES}

Task Instructions:
You are an extraction assistant for residential rental operations.
Extract tenant search criteria mentioned in the conversation and format them into structured JSON.
Recognize the following fields:
- preferred_locations: array of locations/districts/suburbs mentioned.
- budget_min: minimum monthly budget number (if given as range).
- budget_max: maximum monthly budget number.
- property_type: e.g. "Condo", "HDB", "Landed", "Apartment", "Studio".
- bedrooms: integer number of bedrooms requested.
- move_in_date: target move-in date in YYYY-MM-DD format if identifiable.
- lease_duration_months: lease duration in integer months.
- occupants: integer count of prospective occupants.
- furnishing: one of "FURNISHED", "PARTIALLY_FURNISHED", "UNFURNISHED", "FLEXIBLE", "UNKNOWN".
- special_requirements: dictionary of non-core preferences (e.g. pets, near MRT, parking, balcony).

For each extracted field:
- Assign confidence from 0.0 to 1.0.
- Set explicit = true if explicitly stated by tenant, or false if inferred.
- If ambiguous, set needs_confirmation = true.
"""

EXTRACTION_TEMPLATE = """
Lead ID: {lead_id}
Current Requirements on Record: {current_requirements}
Missing Required Fields: {missing_required_fields}

Recent Messages:
{recent_messages}

Tenant Input:
"{user_input}"
"""

REQUIREMENT_EXTRACTION_PROMPT_V1 = PromptDefinition(
    name="requirement_extraction",
    version="v1.0",
    task_type=AITaskType.REQUIREMENT_EXTRACTION,
    system_instructions=EXTRACTION_SYSTEM_INSTRUCTIONS.strip(),
    template=EXTRACTION_TEMPLATE.strip(),
    active=True,
)

