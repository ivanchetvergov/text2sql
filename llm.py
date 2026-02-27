from typing import Optional
import requests

class LLM:
    def __init__(self,
                 url: str = "http://localhost:11434/api/generate",
                 timeout: int = 10):
        self.url = url
        self.timeout = timeout
        try:
            resp = requests.get(self.url, timeout=self.timeout)
            resp.raise_for_status()

        except requests.RequestException as e:
            raise RuntimeError(f"Error connecting to LLM API: {e}")


    def generate(self, prompt: Optional[str]) -> str:
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        payload = {"prompt": prompt}
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()

        except requests.RequestException as e:
            raise RuntimeError(f"Error generating response from LLM API: {e}")

        data = response.json()
        return data.get("response", "")
