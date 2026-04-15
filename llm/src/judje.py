from __future__ import annotations

import json
from typing import Any, Dict

from .llm import LLM
from .promts import Prompts
from .utils import Logger

_REQUIRED_FIELDS = ("valid", "score", "error")


class Judge:
    """LLM-based SQL quality evaluator."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self._logger = Logger.get_logger("src.judge", filename="judge.log")

    # ─── public API ───────────────────────────────────────────────────────────

    def evaluate(self, user_request: str, sql: str) -> Dict[str, Any]:
        """Return a verdict dict with keys: valid, score, error, comments."""
        prompt = self._build_prompt(user_request, sql)
        raw    = self.llm._strip_fences(self.llm._call(prompt))
        self._logger.info("Judge raw response:\n%s", raw)
        result = self._parse(raw)
        self._logger.info(
            "Verdict: valid=%s score=%.2f error=%s",
            result["valid"], result["score"], result.get("error", ""),
        )
        return result

    # ─── private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(user_request: str, sql: str) -> str:
        return (
            Prompts.judge.prompt
            + f"\n\nUser request: {user_request}\nGenerated SQL: {sql}\n"
        )

    @staticmethod
    def _parse(raw: str) -> Dict[str, Any]:
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"judge returned invalid JSON: {raw}") from exc
        for field in _REQUIRED_FIELDS:
            if field not in result:
                raise ValueError(f"missing field '{field}' in judge output")
        return result
