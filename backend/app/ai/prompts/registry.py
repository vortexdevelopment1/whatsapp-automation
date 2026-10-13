from typing import Dict, Tuple, Optional
from app.models.enums import AITaskType
from app.ai.prompts.base import PromptDefinition
from app.ai.prompts.intent import INTENT_PROMPT_V1
from app.ai.prompts.requirement_extraction import REQUIREMENT_EXTRACTION_PROMPT_V1
from app.ai.prompts.qualification_question import QUALIFICATION_QUESTION_PROMPT_V1
from app.ai.prompts.qualification_summary import QUALIFICATION_SUMMARY_PROMPT_V1
from app.ai.prompts.agent_response_extraction import AGENT_RESPONSE_EXTRACTION_PROMPT_V1
from app.ai.exceptions import AIConfigurationError


class PromptRegistry:
    """Centralized prompt version catalog."""

    def __init__(self):
        self._prompts: Dict[Tuple[str, str], PromptDefinition] = {}
        self.register(INTENT_PROMPT_V1)
        self.register(REQUIREMENT_EXTRACTION_PROMPT_V1)
        self.register(QUALIFICATION_QUESTION_PROMPT_V1)
        self.register(QUALIFICATION_SUMMARY_PROMPT_V1)
        self.register(AGENT_RESPONSE_EXTRACTION_PROMPT_V1)

    def register(self, prompt: PromptDefinition) -> None:
        self._prompts[(prompt.name, prompt.version)] = prompt

    def get(self, name: str, version: Optional[str] = None) -> PromptDefinition:
        if version:
            prompt = self._prompts.get((name, version))
            if prompt:
                return prompt
            raise AIConfigurationError(f"Prompt '{name}' with version '{version}' not found.")

        # Find active or latest version
        matches = [p for (n, v), p in self._prompts.items() if n == name and p.active]
        if matches:
            return matches[0]

        raise AIConfigurationError(f"No active prompt found for name '{name}'.")

    def get_by_task(self, task_type: AITaskType, version: Optional[str] = None) -> PromptDefinition:
        candidates = [p for p in self._prompts.values() if p.task_type == task_type]
        if version:
            matches = [p for p in candidates if p.version == version]
            if matches:
                return matches[0]
            raise AIConfigurationError(f"No prompt for task '{task_type}' and version '{version}' found.")

        active_matches = [p for p in candidates if p.active]
        if active_matches:
            return active_matches[0]

        raise AIConfigurationError(f"No active prompt found for task '{task_type}'.")


prompt_registry = PromptRegistry()


def get_active_prompt(name: str, version: Optional[str] = None) -> PromptDefinition:
    return prompt_registry.get(name=name, version=version)

