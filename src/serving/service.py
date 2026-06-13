from contextlib import asynccontextmanager
from typing import Any, Optional
import json
import os
from pathlib import Path
import re

import asyncpg
import uvicorn
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

from ..retrieval import EmbeddingModel, KnowledgeGraph, RAG
from ..generation import LLM, Pipeline
from ..utils import Logger, load_env


def _pg_connect_kwargs() -> dict[str, str | int]:
    return {
        "user":     os.getenv("POSTGRES_USER",     "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "database": os.getenv("POSTGRES_DB",       "postgres"),
        "host":     os.getenv("DB_HOST",            "127.0.0.1"),
        "port":     int(os.getenv("DB_PORT",        "5432")),
    }


def _is_read_only(sql: str) -> bool:
    s = sql.strip().rstrip(";").lower()
    return s.startswith("select") or s.startswith("with")


def _apply_limit(sql: str, limit: int) -> str:
    base = sql.strip().rstrip(";")
    return base if re.search(r"\blimit\b", base, re.IGNORECASE) else f"{base}\nLIMIT {limit}"


class Prompt(BaseModel):
    prompt: str


class LLMService:
    def __init__(
        self,
        url: str = "https://openrouter.ai/api/v1/chat/completions",
        model_name: str = "qwen/qwen-2.5-coder-32b-instruct",
        timeout: float = 180.0,
    ) -> None:
        load_env()
        self._logger = Logger.get_logger("src.llm_service", filename="llm_service.log")

        rag = RAG(EmbeddingModel())
        try:
            rag.build_from_yaml()
        except Exception as exc:
            self._logger.exception("Failed to build RAG: %s", exc)

        kg: Optional[KnowledgeGraph] = None
        try:
            kg = KnowledgeGraph().load_from_yaml()
        except Exception as exc:
            self._logger.exception("Failed to load KnowledgeGraph: %s", exc)

        llm = LLM(
            url=os.getenv("OPENROUTER_URL", url),
            model_name=os.getenv("OPENROUTER_MODEL", model_name),
            timeout=timeout,
        )
        self.pipeline = Pipeline(llm=llm, rag=rag, kg=kg)
        self._pool: Optional[asyncpg.Pool] = None

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            self._pool = await asyncpg.create_pool(**_pg_connect_kwargs())
            yield
            if self._pool:
                await self._pool.close()

        self.router = APIRouter()
        self.app    = FastAPI(lifespan=lifespan)
        self.router.post("/generate")(self._generate)
        self.router.get("/health")(self._health)
        self.app.include_router(self.router)

    async def _generate(self, body: Prompt) -> dict[str, str]:
        try:
            sql = self.pipeline.generate(body.prompt)
        except Exception as exc:
            msg = str(exc)
            if "503" in msg.lower() or "no healthy upstream" in msg.lower():
                self._logger.warning("LLM provider unavailable: %s", msg)
                return {"text": "SQL:\n\n<not generated>\n\nRESULT:\n\nLLM provider unavailable. Retry in 10-30s."}
            self._logger.exception("LLM generation failed: %s", exc)
            return {"text": f"SQL:\n\n<not generated>\n\nRESULT:\n\nError: {msg}"}

        self._logger.info("Generated SQL:\n%s", sql)

        if not sql.strip():
            return {"text": "SQL:\n\n<empty>\n\nRESULT:\n\nNo SQL generated."}
        if not _is_read_only(sql):
            return {"text": f"SQL:\n\n{sql}\n\nRESULT:\n\nOnly SELECT/CTE queries are allowed."}

        limited = _apply_limit(sql, int(os.getenv("LLM_RESULT_LIMIT", "20")))
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(limited)
            data     = [dict(r) for r in rows]
            rendered = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            return {"text": f"SQL:\n\n{limited}\n\nRESULT (up to {os.getenv('LLM_RESULT_LIMIT', '20')} rows):\n\n{rendered}"}
        except Exception as exc:
            self._logger.exception("SQL execution failed: %s", exc)
            return {"text": f"SQL:\n\n{limited}\n\nRESULT:\n\nExecution error: {exc}"}

    def _health(self) -> dict[str, str]:
        return {"status": "ok" if self.pipeline.llm.health() else "error"}

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs: Any) -> None:
        uvicorn.run(self.app, host=host, port=port, **kwargs)


def make_app():
    return LLMService().app


if __name__ == "__main__":
    LLMService().run()
