"""Concrete LLM providers: OpenAI and Gemini. Both use native JSON modes
for ``complete_json``; both normalize SDK errors into ``LLMError``."""
from __future__ import annotations

import json

from ..config import settings
from .base import LLMError, LLMProvider, parse_json_loosely


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI(api_key=api_key)

    def complete_text(self, system: str, user: str, *, temperature: float = 0.2,
                      max_tokens: int = 2000) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=temperature,
                max_completion_tokens=max_tokens)
            return resp.choices[0].message.content or ""
        except Exception as e:                                # noqa: BLE001
            raise LLMError(f"OpenAI call failed: {e}") from e

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0,
                      max_tokens: int = 3000) -> dict | list:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system",
                           "content": system + "\nRespond with valid JSON only."},
                          {"role": "user", "content": user}],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"})
            return parse_json_loosely(resp.choices[0].message.content or "")
        except LLMError:
            raise
        except Exception as e:                                # noqa: BLE001
            raise LLMError(f"OpenAI call failed: {e}") from e


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        from google import genai
        self.model = model
        self._client = genai.Client(api_key=api_key)

    def _generate(self, system: str, user: str, temperature: float,
                  max_tokens: int, json_mode: bool) -> str:
        from google.genai import types
        try:
            cfg = types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json" if json_mode else None)
            resp = self._client.models.generate_content(
                model=self.model, contents=user, config=cfg)
            return resp.text or ""
        except Exception as e:                                # noqa: BLE001
            raise LLMError(f"Gemini call failed: {e}") from e

    def complete_text(self, system: str, user: str, *, temperature: float = 0.2,
                      max_tokens: int = 2000) -> str:
        return self._generate(system, user, temperature, max_tokens, json_mode=False)

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0,
                      max_tokens: int = 3000) -> dict | list:
        return parse_json_loosely(
            self._generate(system, user, temperature, max_tokens, json_mode=True))


class MockProvider(LLMProvider):
    """Deterministic provider for tests: pops canned responses."""
    name = "mock"
    model = "scripted"

    def __init__(self, responses: list[str | dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete_text(self, system: str, user: str, **kw) -> str:
        self.calls.append({"system": system, "user": user})
        if not self._responses:
            raise LLMError("MockProvider ran out of scripted responses")
        r = self._responses.pop(0)
        return r if isinstance(r, str) else json.dumps(r)


def build_provider() -> LLMProvider | None:
    """Resolve the configured provider. Returns None when nothing is
    configured — callers must degrade honestly, not guess."""
    choice = settings.llm_provider.lower()
    if choice == "openai" or (choice == "auto" and settings.openai_api_key):
        if not settings.openai_api_key:
            return None
        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    if choice == "gemini" or (choice == "auto" and settings.gemini_api_key):
        if not settings.gemini_api_key:
            return None
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return None
