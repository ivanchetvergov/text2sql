from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from .llm import LLM
from .prompts import Prompts
from .utils import Logger

_MAX_EXAMPLES = 3


def _trim(tables: Dict[str, str], limit: int) -> Dict[str, str]:
    if limit <= 0:
        return {}
    return dict(list(tables.items())[:limit]) if len(tables) > limit else tables


def _build_ctx(fk_hint: str, tables: Dict[str, str], examples: List[str]) -> str:
    parts: List[str] = []
    if fk_hint:
        parts.append("## FK Path Hint\n" + fk_hint)
    if tables:
        parts.append("## Available Tables\n" + "\n".join(f"- {v}" for v in tables.values() if v))
    if examples:
        parts.append("## Similar Examples\n" + "\n\n".join(examples[:_MAX_EXAMPLES]))
    return "\n\n".join(parts)


class Pipeline:
    """Orchestrates RAG retrieval, KG enrichment, SQL generation, and judge refinement."""

    def __init__(
        self,
        llm: LLM,
        rag: Optional[Any] = None,
        kg: Optional[Any] = None,
    ) -> None:
        self.llm = llm
        self.rag = rag
        self.kg  = kg
        self._logger = Logger.get_logger("src.pipeline", filename="llm.log")

    def generate(self, question: str) -> str:
        if not question:
            return ""
        self._logger.info("Question: %s", question)
        tables, fk_hint, examples = self._retrieve(question)
        ctx = _build_ctx(fk_hint, tables, examples)
        self._logger.info("Context:\n%s\n%s\n%s", "=" * 60, ctx, "=" * 60)
        sql = LLM.strip_fences(
            self.llm.call(
                system_prompt=Prompts.llm_service.prompt,
                user_prompt=f"{Prompts.llm.sql_prompt}\n\n{ctx}\n\n## Question\n{question}",
            )
        )
        self._logger.info("Generated SQL:\n%s", sql)
        return self._refine(sql, question, ctx)

    def _retrieve(self, question: str) -> Tuple[Dict[str, str], str, List[str]]:
        tables, examples = self.rag.context_for(question) if self.rag else ({}, [])
        limit = int(os.getenv("RAG_TABLE_LIMIT", "6"))
        tables = _trim(tables, limit)
        if self.kg:
            ddl = self.rag.ddl_lookup() if self.rag else {}
            tables, fk_hint = self.kg.enrich(tables, ddl_lookup=ddl)
            tables = _trim(tables, int(os.getenv("RAG_FINAL_TABLE_LIMIT", str(limit))))
        else:
            fk_hint = ""
        return tables, fk_hint, examples

    def _refine(self, sql: str, question: str, ctx: str) -> str:
        from .judge import Judge
        try:
            verdict = Judge(self.llm).evaluate(question, sql)
        except Exception as exc:
            self._logger.warning("Judge failed, keeping original SQL: %s", exc)
            return sql
        if verdict.get("valid"):
            return sql
        error = verdict.get("error", "unknown error")
        self._logger.info("Judge rejected SQL (%s) — retrying", error)
        correction = ctx + f"\n\n## Correction\n{Prompts.llm.correction_prompt.format(error=error)}"
        refined = LLM.strip_fences(
            self.llm.call(
                system_prompt=Prompts.llm_service.prompt,
                user_prompt=f"{Prompts.llm.sql_prompt}\n\n{correction}\n\n## Question\n{question}",
                temperature=0.0,
            )
        )
        self._logger.info("Refined SQL:\n%s", refined)
        return refined
