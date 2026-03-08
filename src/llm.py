from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import json
import requests
from .utils import Logger
from .promts import Prompts

_MAX_EXAMPLES = 3

class LLM:
    def __init__(self,
                 url: str = "http://localhost:11434/api/generate",
                 model_name: str = 'qwen2.5-coder:14b',
                 timeout: float = 180.0,
                 check: bool = True,
                 rag: Optional[Any] = None,
                 kg: Optional[Any] = None):
        self.url = url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.rag = rag
        self.kg = kg
        self._logger = Logger.get_logger("src.llm", filename="llm.log")
        if check:
            try:
                resp = requests.options(self.url, timeout=self.timeout)
                if resp.status_code not in (200, 204, 405):
                    resp.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"Error connecting to LLM API: {exc}") from exc

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = re.sub(r'^\s*```[\w]*\s*\n?', '', text.strip())
        text = re.sub(r'\n?\s*```\s*$', '', text.strip())
        return text.strip()

    def _call(self, prompt: str, temperature: float = 0.1, max_tokens: int = 600) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": 8192},
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError("LLM API error") from exc
        return data.get("response", "") or data.get("text", "")

    @staticmethod
    def _build_ctx(
        fk_hint: str,
        tables: Dict[str, str],
        examples: List[str],
        plan_block: str = "",
    ) -> str:
        parts: List[str] = []
        if plan_block:
            parts.append("## Подтверждённый план JOIN\n" + plan_block)
        elif fk_hint:
            parts.append("## Подсказка FK-пути\n" + fk_hint)
        if tables:
            parts.append("## Доступные таблицы\n" + "\n".join(f"- {v}" for v in tables.values() if v))
        if examples:
            parts.append("## Похожие примеры\n" + "\n\n".join(examples[:_MAX_EXAMPLES]))
        return "\n\n".join(parts)


    def _plan(self, schema_ctx: str, question: str) -> str:
        prompt = f"{Prompts.llm.plan_prompt}\n\n{schema_ctx}\n\n## Вопрос\n{question}"
        raw = self._strip_fences(self._call(prompt, temperature=0.0, max_tokens=400))
        self._logger.info("Stage 1 raw:\n%s", raw)
        try:
            plan = json.loads(raw)
            from_clause = plan.get("from_clause", "").strip()
            joins = [j.strip() for j in plan.get("joins", []) if j.strip()]
            if not from_clause:
                self._logger.warning("Stage 1: empty from_clause — skipping plan")
                return ""
            lines = [f"FROM {from_clause}"] + [f"  {j}" for j in joins]
            if plan.get("select_hint"):
                lines.append(f"SELECT цель: {plan['select_hint']}")
            if plan.get("where_hints"):
                lines.append("WHERE фильтры: " + "; ".join(plan["where_hints"]))
            block = "\n".join(lines)
            self._logger.info("Stage 1 plan:\n%s\n%s\n%s", "-" * 60, block, "-" * 60)
            return block
        except json.JSONDecodeError:
            self._logger.warning("Stage 1 JSON parse failed — skipping plan")
            return ""

    def _maybe_refine(self, sql: str, question: str, s2_ctx: str) -> str:
        """Stage 3: one judge pass — retry with error hint if SQL is rejected."""
        from .judje import Judge
        try:
            verdict = Judge(self).evaluate(question, sql)
        except Exception as exc:
            self._logger.warning("Judge call failed: %s", exc)
            return sql
        if verdict.get("valid"):
            return sql
        error = verdict.get("error", "unknown error")
        self._logger.info("Judge rejected SQL (%s) — retrying", error)
        correction_ctx = (
            s2_ctx
            + f"\n\n## Исправление\n{Prompts.llm.correction_prompt.format(error=error)}"
        )
        full = (Prompts.llm.sql_prompt + "\n\n" + correction_ctx
                + "\n\n## Вопрос\n" + question)
        refined = self._strip_fences(self._call(full))
        self._logger.info("Refined SQL:\n%s", refined)
        return refined


    def _retrieve_context(
        self, question: str
    ) -> Tuple[Dict[str, str], str, List[str]]:
        """RAG retrieval + graph FK expansion. Returns (tables, fk_hint, examples)."""
        tables, examples = self.rag.context_for(question) if self.rag else ({}, [])
        if self.kg:
            ddl             = self.rag.ddl_lookup() if self.rag else {}
            tables, fk_hint = self.kg.enrich(tables, ddl_lookup=ddl)
        else:
            fk_hint = ""
        return tables, fk_hint, examples

    def generate(
        self,
        prompt: Optional[str],
        temperature: float = 0.1,
        max_tokens: int = 600,
        **_kwargs,
    ) -> str:
        if not prompt:
            return ""
        self._logger.info("User prompt: %s", prompt)

        tables, fk_hint, examples = self._retrieve_context(prompt)

        schema_ctx = self._build_ctx(fk_hint, tables, examples)
        self._logger.info("Schema context:\n%s\n%s\n%s", "=" * 60, schema_ctx, "=" * 60)

        plan_block  = self._plan(schema_ctx, prompt) if schema_ctx else ""
        s2_ctx      = self._build_ctx(fk_hint, tables, examples, plan_block)
        full_prompt = Prompts.llm.sql_prompt + "\n\n" + s2_ctx + "\n\n## Вопрос\n" + prompt
        sql         = self._strip_fences(self._call(full_prompt, temperature, max_tokens))
        self._logger.info("Stage 2 SQL:\n%s", sql)

        # sql = self._maybe_refine(sql, prompt, s2_ctx)

        return sql

    def health(self) -> bool:
        try:
            resp = requests.options(self.url, timeout=self.timeout)
            return resp.status_code in (200, 204, 405)
        except requests.RequestException:
            return False
