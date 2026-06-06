from __future__ import annotations

import os
import re
from typing import Dict, Optional

import requests

from .utils import Logger


class LLM:
    """HTTP client for OpenRouter-compatible LLM APIs."""

    def __init__(
        self,
        url: str = "https://openrouter.ai/api/v1/chat/completions",
        model_name: str = "openai/gpt-oss-120b:free",
        timeout: float = 180.0,
        check: bool = True,
        api_key: Optional[str] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "text2sql")
        self._logger = Logger.get_logger("src.llm", filename="llm.log")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        if check:
            try:
                requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=self._headers(),
                    timeout=self.timeout,
                ).raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"Cannot reach LLM API: {exc}") from exc

    def call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        fallbacks = [m.strip() for m in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",") if m.strip()]
        models = [self.model_name] + [m for m in fallbacks if m != self.model_name]

        last_error: Optional[Exception] = None
        for model in models:
            try:
                resp = requests.post(
                    self.url,
                    headers=self._headers(),
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user",   "content": user_prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens":  max_tokens,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                choices = resp.json().get("choices", [])
                return choices[0].get("message", {}).get("content", "") if choices else ""
            except requests.RequestException as exc:
                last_error = exc
                body = getattr(getattr(exc, "response", None), "text", "") or ""
                self._logger.warning("Model %s failed: %s", model, body or str(exc))

        body = getattr(getattr(last_error, "response", None), "text", "") or ""
        raise RuntimeError(f"LLM API error: {body or str(last_error)}") from last_error

    def health(self) -> bool:
        try:
            return requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=self._headers(),
                timeout=self.timeout,
            ).status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def strip_fences(text: str) -> str:
        text = re.sub(r'^\s*```[\w]*\s*\n?', '', text.strip())
        text = re.sub(r'\n?\s*```\s*$',      '', text.strip())
        return text.strip()

    def _headers(self) -> Dict[str, str]:
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.site_url:
            h["HTTP-Referer"] = self.site_url
        if self.app_name:
            h["X-Title"] = self.app_name
        return h
