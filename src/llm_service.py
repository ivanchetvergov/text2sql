from typing import Any

import uvicorn
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

from llm import LLM


class Prompt(BaseModel):
    prompt: str


class LLMService:
    def __init__(self,
                 url: str = "http://localhost:11434/api/generate",
                 timeout: float = 100.0):
        self.client = LLM(url=url, timeout=timeout)

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


if __name__ == "__main__":
    LLMService().run()
