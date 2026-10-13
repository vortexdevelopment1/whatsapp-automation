class AIError(Exception):
    """Base exception for all AI-related orchestration errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AIConfigurationError(AIError):
    """Raised when AI configuration is missing, incomplete, or invalid."""
    pass


class AIProviderError(AIError):
    """Raised when an external AI provider encounters an execution failure."""
    pass


class AITimeoutError(AIProviderError):
    """Raised when an AI provider call exceeds the configured timeout."""
    pass


class AIRateLimitError(AIProviderError):
    """Raised when an AI provider rate limit is encountered."""
    pass


class AIInvalidResponseError(AIError):
    """Raised when an AI provider returns malformed, unparseable, or non-JSON output."""
    pass


class AISchemaValidationError(AIError):
    """Raised when structured AI output fails Pydantic schema validation."""
    pass
