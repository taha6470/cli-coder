from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMClient:
    base_url: str
    api_key: str
    model: str
    timeout_s: int = 120

    def chat_completions(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        if resp.status_code >= 400:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:1000]}")
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from LLM: {e}") from e

