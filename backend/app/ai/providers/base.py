from abc import ABC, abstractmethod
from typing import Tuple, Type, TypeVar
from pydantic import BaseModel
from app.ai.schemas import AIRequest, AIUsage

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    """Abstract provider adapter interface for AI model dispatches."""

    @abstractmethod
    async def generate_structured(
        self, request: AIRequest, response_model: Type[T]
    ) -> Tuple[T, str, AIUsage]:
        """Execute request and return (parsed_pydantic_model, raw_response_text, usage_metadata)."""
        pass

    @abstractmethod
    async def generate_text(self, request: AIRequest) -> Tuple[str, AIUsage]:
        """Execute request and return (response_text, usage_metadata)."""
        pass
