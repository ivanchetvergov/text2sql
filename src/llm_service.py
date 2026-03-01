from typing import Any, Optional
from pathlib import Path

import uvicorn
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

from .llm import LLM
from .rag import RAG
from .graph import KnowledgeGraph
from .embeddings import EmbeddingModel
from .utils import Logger


class Prompt(BaseModel):
    prompt: str


class LLMService:
    def __init__(self,
                 url: str = "http://localhost:11434/api/generate",
                 timeout: float = 180.0):

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

        self.client = LLM(url=url, timeout=timeout, rag=self.rag, kg=self.kg)

        self.router = APIRouter()
        self.app = FastAPI()

        self.router.post("/generate")(self._generate)
        self.router.get("/health")(self._health)

        self.app.include_router(self.router)


    def _generate(self, body: Prompt) -> dict[str, str]:
        text = self.client.generate(body.prompt)
        return {"text": text}

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
