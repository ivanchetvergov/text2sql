from typing import Any, Optional
import json
import os
from pathlib import Path
import re

import asyncpg
import uvicorn
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

from .llm import LLM
from .rag import RAG
from .graph import KnowledgeGraph
from .embeddings import EmbeddingModel
from .utils import Logger


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _pg_connect_kwargs() -> dict[str, str | int]:
    return {
        "user": os.getenv("POSTGRES_USER", "competition_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "competition_pass"),
        "database": os.getenv("POSTGRES_DB", "competition_db"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5436")),
    }


def _is_read_only_sql(sql: str) -> bool:
    s = sql.strip().rstrip(";").lower()
    return s.startswith("select") or s.startswith("with")


def _apply_limit(sql: str, row_limit: int) -> str:
    base = sql.strip().rstrip(";")
    if re.search(r"\blimit\b", base, flags=re.IGNORECASE):
        return base
    return f"{base}\nLIMIT {row_limit}"


class Prompt(BaseModel):
    prompt: str


class LLMService:
    def __init__(self,
                 url: str = "https://openrouter.ai/api/v1/chat/completions",
                 model_name: str = "qwen/qwen-2.5-coder-32b-instruct",
                 timeout: float = 180.0):

        _load_env_file()

        self._logger = Logger.get_logger("src.llm_service", filename="llm_service.log")

        self.rag = RAG(EmbeddingModel())
        try:
            self.rag.build_from_yaml()
        except Exception as exc:
            self._logger.exception("Failed to build RAG from rag.yaml: %s", exc)

        self.kg: Optional[KnowledgeGraph] = None
        try:
            self.kg = KnowledgeGraph().load_from_yaml()
        except Exception as exc:
            self._logger.exception("Failed to load KnowledgeGraph: %s", exc)

        resolved_url = os.getenv("OPENROUTER_URL", url)
        resolved_model = os.getenv("OPENROUTER_MODEL", model_name)
        self.client = LLM(
            url=resolved_url,
            model_name=resolved_model,
            timeout=timeout,
            rag=self.rag,
            kg=self.kg,
        )

        self.router = APIRouter()
        self.app = FastAPI()

        self.router.post("/generate")(self._generate)
        self.router.get("/health")(self._health)

        self.app.include_router(self.router)


    async def _generate(self, body: Prompt) -> dict[str, str]:
        sql = self.client.generate(body.prompt)
        row_limit = int(os.getenv("LLM_RESULT_LIMIT", "20"))

        self._logger.info("Generated SQL:\n%s", sql)

        if not sql.strip():
            return {"text": "SQL:\n\n<empty>\n\nRESULT:\n\nNo SQL generated."}

        if not _is_read_only_sql(sql):
            return {
                "text": (
                    f"SQL:\n\n{sql}\n\n"
                    "RESULT:\n\nOnly read-only SELECT/CTE queries are allowed."
                )
            }

        limited_sql = _apply_limit(sql, row_limit)
        conn = None
        try:
            conn = await asyncpg.connect(**_pg_connect_kwargs())
            rows = await conn.fetch(limited_sql)
            data = [dict(r) for r in rows]
            rendered = json.dumps(data, ensure_ascii=False, indent=2)
            return {
                "text": (
                    f"SQL:\n\n{limited_sql}\n\n"
                    f"RESULT (up to {row_limit} rows):\n\n{rendered}"
                )
            }
        except Exception as exc:
            self._logger.exception("SQL execution failed: %s", exc)
            return {
                "text": (
                    f"SQL:\n\n{limited_sql}\n\n"
                    f"RESULT:\n\nExecution error: {exc}"
                )
            }
        finally:
            if conn is not None:
                await conn.close()

    def _health(self) -> dict[str, str]:
        ok = self.client.health()
        return {"status": "ok" if ok else "error"}

    def run(self,
            host: str = "0.0.0.0",
            port: int = 8000,
            **uvicorn_kwargs: Any) -> None:

        uvicorn.run(self.app, host=host, port=port, **uvicorn_kwargs)

def make_app():
    svc = LLMService()
    return svc.app


if __name__ == "__main__":
    LLMService().run()
