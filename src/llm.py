from typing import Optional
import requests


class LLM:
    def __init__(self,
                 url: str = "http://localhost:11434/api/generate",
                 model_name: str = 'qwen2.5:14b',
                 timeout: float = 10.0,
                 check: bool = True):
        self.url = url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        if check:
            try:
                resp = requests.options(self.url, timeout=self.timeout)
                if resp.status_code not in (200, 204, 405):
                    resp.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"Error connecting to LLM API: {exc}") from exc

    def generate(
        self,
        prompt: Optional[str],
        temperature: float = 0.1,
        max_tokens: int = 600,
        top_p: float | None = None,
        top_k: int | None = None,
        stream: bool = False,
    ) -> str:
        if not prompt:
            return ""

        from promts import Prompts

        full_prompt = prompt
        if Prompts.llm.sql_prompt:
            full_prompt = Prompts.llm.sql_prompt + "\n\n" + prompt

        payload: dict[str, object] = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if top_p is not None:
            payload["options"]["top_p"] = top_p
        if top_k is not None:
            payload["options"]["top_k"] = top_k

        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError("Error generating response from LLM API") from exc

        return data.get("response", "") or data.get("text", "")

    def health(self) -> bool:
        try:
            resp = requests.options(self.url, timeout=self.timeout)
            return resp.status_code in (200, 204, 405)
        except requests.RequestException:
            return False
