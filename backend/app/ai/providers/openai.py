import json
from typing import Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.ai.exceptions import (
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.ai.providers.base import AIProvider
from app.ai.schemas import AIRequest, AIUsage

T = TypeVar("T", bound=BaseModel)

# Approximate cost estimation per 1k tokens for standard OpenAI models (USD)
# Kept isolated and non-binding
ESTIMATED_PRICING_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
    "gpt-4o": {"input": 0.0025 / 1000, "output": 0.01 / 1000},
}


class OpenAIProvider(AIProvider):
    """
    OpenAI-compatible HTTP provider using native httpx.
    Supports structured JSON schema outputs, usage tracking, and safe error normalization.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        default_model: str = "gpt-4o-mini",
    ):
        if not api_key:
            raise AIConfigurationError("OpenAI API key is missing or not configured.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_model = default_model

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        for prefix, rates in ESTIMATED_PRICING_PER_1K.items():
            if model.startswith(prefix):
                return round((input_tokens * rates["input"]) + (output_tokens * rates["output"]), 6)
        return None

    def _parse_usage(self, data: dict, model: str) -> AIUsage:
        usage_data = data.get("usage", {})
        inp = usage_data.get("prompt_tokens", 0)
        out = usage_data.get("completion_tokens", 0)
        tot = usage_data.get("total_tokens", inp + out)
        cost = self._estimate_cost(model, inp, out)
        return AIUsage(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=tot,
            estimated_cost_usd=cost,
        )

    async def generate_structured(
        self, request: AIRequest, response_model: Type[T]
    ) -> Tuple[T, str, AIUsage]:
        model = request.model or self.default_model
        endpoint = f"{self.base_url}/chat/completions"

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(endpoint, headers=self._get_headers(), json=payload)
            except httpx.TimeoutException as exc:
                raise AITimeoutError(f"OpenAI request timed out after {self.timeout_seconds}s: {exc}") from exc
            except httpx.RequestError as exc:
                raise AIProviderError(f"Network error connecting to OpenAI: {exc}") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise AIConfigurationError("OpenAI authentication failed. Invalid or revoked API key.")
        elif resp.status_code == 429:
            raise AIRateLimitError("OpenAI rate limit or quota exceeded (HTTP 429).")
        elif resp.status_code >= 500:
            raise AIProviderError(f"OpenAI service returned server error HTTP {resp.status_code}.")
        elif resp.status_code != 200:
            raise AIProviderError(f"OpenAI returned unexpected HTTP status {resp.status_code}: {resp.text[:200]}")

        try:
            body = resp.json()
            raw_content = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AIInvalidResponseError(f"Failed to parse OpenAI JSON response body: {exc}") from exc

        try:
            parsed_json = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise AIInvalidResponseError(f"OpenAI content was not valid JSON: {exc}. Content: {raw_content[:200]}") from exc

        try:
            validated_obj = response_model.model_validate(parsed_json)
        except ValidationError as exc:
            raise AISchemaValidationError(
                f"OpenAI response failed schema validation for {response_model.__name__}: {exc}",
                raw_response=raw_content,
            ) from exc

        usage = self._parse_usage(body, model)
        return validated_obj, raw_content, usage

    async def generate_text(self, request: AIRequest) -> Tuple[str, AIUsage]:
        model = request.model or self.default_model
        endpoint = f"{self.base_url}/chat/completions"

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(endpoint, headers=self._get_headers(), json=payload)
            except httpx.TimeoutException as exc:
                raise AITimeoutError(f"OpenAI request timed out: {exc}") from exc
            except httpx.RequestError as exc:
                raise AIProviderError(f"Network error connecting to OpenAI: {exc}") from exc

        if resp.status_code in (401, 403):
            raise AIConfigurationError("OpenAI authentication failed.")
        elif resp.status_code == 429:
            raise AIRateLimitError("OpenAI rate limit exceeded.")
        elif resp.status_code >= 500:
            raise AIProviderError(f"OpenAI service error HTTP {resp.status_code}.")
        elif resp.status_code != 200:
            raise AIProviderError(f"OpenAI error HTTP {resp.status_code}.")

        try:
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AIInvalidResponseError(f"Failed to extract OpenAI text: {exc}") from exc

        usage = self._parse_usage(body, model)
        return text, usage
