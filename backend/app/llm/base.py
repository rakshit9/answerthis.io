"""Pluggable LLM provider interface.

The rest of the app never imports an SDK directly — it asks the registry
for a provider and calls ``complete_json`` / ``complete_text``. Adding a
new provider = one subclass + one registry entry.

When no provider is configured the registry returns ``None`` and callers
degrade honestly (e.g. claim checks report "cannot verify — no LLM
configured" instead of faking a verdict with keyword overlap).
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod


class LLMError(Exception):
    """A provider call failed (network, auth, quota…). Surfaced to the UI."""


class LLMUnavailable(LLMError):
    """No provider is configured at all."""


class LLMProvider(ABC):
    name: str = "abstract"
    model: str = ""

    @abstractmethod
    def complete_text(self, system: str, user: str, *, temperature: float = 0.2,
                      max_tokens: int = 2000) -> str: ...

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0,
                      max_tokens: int = 3000) -> dict | list:
        """Ask for strict JSON and parse it. Providers may override with a
        native JSON mode; this base implementation post-processes text."""
        raw = self.complete_text(
            system + "\nRespond with ONLY valid JSON. No prose, no markdown fences.",
            user, temperature=temperature, max_tokens=max_tokens)
        return parse_json_loosely(raw)

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


def parse_json_loosely(raw: str) -> dict | list:
    """Parse JSON out of an LLM response, tolerating fences and prefixes."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # find the outermost object or array
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"Model did not return parseable JSON: {raw[:200]!r}")
