from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import os
import re
import requests
from .utils import Logger
from .prompts import Prompts

_MAX_EXAMPLES = 3


def _trim_tables(tables: Dict[str, str], limit: int) -> Dict[str, str]:
    if limit <= 0:
        return {}
    if len(tables) <= limit:
        return tables
    return dict(list(tables.items())[:limit])

class LLM:
    def __init__(self,
                 url: str = "https://openrouter.ai/api/v1/chat/completions",
                 model_name: str = "openai/gpt-oss-120b:free",
                 timeout: float = 180.0,
                 check: bool = True,
                 api_key: Optional[str] = None,
                 rag: Optional[Any] = None,
                 kg: Optional[Any] = None):
        self.url = url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "text2sql-db-cli")
        self.rag = rag
        self.kg = kg
        self._logger = Logger.get_logger("src.llm", filename="llm.log")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        if check:
            try:
                resp = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code != 200:
                    resp.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"Error connecting to LLM API: {exc}") from exc

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = re.sub(r'^\s*```[\w]*\s*\n?', '', text.strip())
        text = re.sub(r'\n?\s*```\s*$', '', text.strip())
        return text.strip()

    def _call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        fallback_raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
        fallbacks = [m.strip() for m in fallback_raw.split(",") if m.strip()]
        models = [self.model_name] + [m for m in fallbacks if m != self.model_name]

        last_error: Optional[Exception] = None
        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                resp = requests.post(
                    self.url,
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return ""
                message = choices[0].get("message", {})
                return message.get("content", "") or ""
            except requests.RequestException as exc:
                last_error = exc
                body = ""
                try:
                    body = exc.response.text if exc.response is not None else ""
                except Exception:
                    body = ""
                self._logger.warning("Model %s failed: %s", model, body or str(exc))

        if last_error is None:
            raise RuntimeError("LLM API error: no models configured")

        body = ""
        try:
            body = last_error.response.text if getattr(last_error, "response", None) is not None else ""
        except Exception:
            body = ""
        raise RuntimeError(f"LLM API error: {body or str(last_error)}") from last_error

    @staticmethod
    def _build_ctx(
        fk_hint: str,
        tables: Dict[str, str],
        examples: List[str],
    ) -> str:
        parts: List[str] = []
        if fk_hint:
            parts.append("## FK Path Hint\n" + fk_hint)
        if tables:
            parts.append("## Available Tables\n" + "\n".join(f"- {v}" for v in tables.values() if v))
        if examples:
            parts.append("## Similar Examples\n" + "\n\n".join(examples[:_MAX_EXAMPLES]))
        return "\n\n".join(parts)

    def _maybe_refine(self, sql: str, question: str, s2_ctx: str) -> str:
        """Stage 3: one judge pass — retry with error hint if SQL is rejected."""
        from .judge import Judge
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
            + f"\n\n## Correction\n{Prompts.llm.correction_prompt.format(error=error)}"
        )
        full = (Prompts.llm.sql_prompt + "\n\n" + correction_ctx
                + "\n\n## Question\n" + question)
        refined = self._strip_fences(
            self._call(
                system_prompt=Prompts.llm_service.prompt,
                user_prompt=full,
                temperature=0.0,
                max_tokens=600,
            )
        )
        self._logger.info("Refined SQL:\n%s", refined)
        return refined


    def _retrieve_context(
        self, question: str
    ) -> Tuple[Dict[str, str], str, List[str]]:
        """RAG retrieval + graph FK expansion. Returns (tables, fk_hint, examples)."""
        tables, examples = self.rag.context_for(question) if self.rag else ({}, [])
        rag_table_limit = int(os.getenv("RAG_TABLE_LIMIT", "6"))
        tables = _trim_tables(tables, rag_table_limit)
        if self.kg:
            ddl             = self.rag.ddl_lookup() if self.rag else {}
            tables, fk_hint = self.kg.enrich(tables, ddl_lookup=ddl)
            final_table_limit = int(os.getenv("RAG_FINAL_TABLE_LIMIT", str(rag_table_limit)))
            tables = _trim_tables(tables, final_table_limit)
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

        full_prompt = Prompts.llm.sql_prompt + "\n\n" + schema_ctx + "\n\n## Question\n" + prompt
        sql = self._strip_fences(
            self._call(
                system_prompt=Prompts.llm_service.prompt,
                user_prompt=full_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        self._logger.info("Generated SQL:\n%s", sql)

        sql = self._maybe_refine(sql, prompt, schema_ctx)

        return sql

    def health(self) -> bool:
        try:
            resp = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
