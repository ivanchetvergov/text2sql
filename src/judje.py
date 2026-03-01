import json
from typing import Any

from .llm import LLM
from .promts import Prompts


class Judge:

    def __init__(self, llm: LLM):
        self.llm = llm

    def evaluate(self, user_request: str, sql: str) -> dict[str, Any]:
        prompt = Prompts.judge.prompt + "\n\n"
        prompt += f"User request: {user_request}\nGenerated SQL: {sql}\n"

        raw = self.llm._call(prompt)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"judge returned invalid JSON: {raw}") from exc

        for field in ("valid", "score", "error"):
            if field not in result:
                raise ValueError(f"missing field '{field}' in judge output")
        return result
