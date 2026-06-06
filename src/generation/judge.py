from __future__ import annotations

import json
from typing import Any, Dict

from .llm import LLM
from .prompts import Prompts
from ..utils import Logger

_REQUIRED_FIELDS = ("valid", "score", "error")


class Judge:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self._logger = Logger.get_logger("src.judge", filename="judge.log")

    def evaluate(self, user_request: str, sql: str) -> Dict[str, Any]:
        raw = LLM.strip_fences(
            self.llm.call(
                system_prompt=Prompts.judge.prompt,
                user_prompt=f"User request: {user_request}\nGenerated SQL: {sql}\n",
                max_tokens=200,
            )
        )
        self._logger.info("Judge raw response:\n%s", raw)
        result = self._parse(raw)
        self._logger.info(
            "Verdict: valid=%s score=%.2f error=%s",
            result["valid"], result["score"], result.get("error", ""),
        )
        return result

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
