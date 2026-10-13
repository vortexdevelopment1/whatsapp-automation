import enum
from app.models.enums import AITaskType, AICallStatus


class TenantIntent(str, enum.Enum):
    PROVIDE_REQUIREMENTS = "PROVIDE_REQUIREMENTS"
    UPDATE_REQUIREMENT = "UPDATE_REQUIREMENT"
    ASK_FAQ = "ASK_FAQ"
    ASK_FOR_HUMAN = "ASK_FOR_HUMAN"
    CONFIRM_INFORMATION = "CONFIRM_INFORMATION"
    REJECT_INFORMATION = "REJECT_INFORMATION"
    GREETING = "GREETING"
    STOP_CONVERSATION = "STOP_CONVERSATION"
    UNRELATED = "UNRELATED"
    UNCLEAR = "UNCLEAR"


class ConfidenceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MessageRole(str, enum.Enum):
    TENANT = "TENANT"
    AGENT = "AGENT"
    OPERATOR = "OPERATOR"
    AI = "AI"
