from app.models.enums import AITaskType
from app.ai.prompts.base import PromptDefinition, BASE_SAFE_SYSTEM_RULES

INTENT_SYSTEM_INSTRUCTIONS = f"""
{BASE_SAFE_SYSTEM_RULES}

Task Instructions:
You are an intent classification agent for a rental operations platform.
Analyze the tenant's incoming message and conversation context to classify their primary intent into one of the following exact enum values:
- PROVIDE_REQUIREMENTS: The tenant is sharing their rental search criteria (e.g. budget, location, bedrooms, move-in date).
- UPDATE_REQUIREMENT: The tenant is changing previously mentioned criteria (e.g. "Actually I can stretch to $3500").
- ASK_FAQ: The tenant is asking general procedural or rental questions.
- ASK_FOR_HUMAN: The tenant requests to speak with a human agent or broker.
- CONFIRM_INFORMATION: The tenant is confirming details asked by the system (e.g. "Yes, that's correct").
- REJECT_INFORMATION: The tenant is rejecting proposed criteria or options (e.g. "No, not that area").
- GREETING: Social pleasantries or opening hello.
- STOP_CONVERSATION: Unsubscribe, stop, opt-out requests.
- UNRELATED: Off-topic or unsolicited marketing.
- UNCLEAR: Ambiguous, garbled, or incomprehensible input.

Estimate confidence as a float between 0.0 and 1.0.
"""

INTENT_TEMPLATE = """
Context:
Lead ID: {lead_id}
Qualification Status: {qualification_status}
Recent Conversation Summary: {conversation_summary}

Recent Messages:
{recent_messages}

Current Tenant Message:
"{user_input}"
"""

INTENT_PROMPT_V1 = PromptDefinition(
    name="intent_classification",
    version="v1.0",
    task_type=AITaskType.INTENT_CLASSIFICATION,
    system_instructions=INTENT_SYSTEM_INSTRUCTIONS.strip(),
    template=INTENT_TEMPLATE.strip(),
    active=True,
)

