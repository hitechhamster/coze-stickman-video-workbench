import httpx

from app.config import settings
from app.providers.base import LLMProvider


class MiniMaxLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._host = settings.minimax_api_host.rstrip("/")
        self._api_key = settings.minimax_api_key
        self._model = settings.minimax_text_model

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._host}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()

        base_resp = body.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(f"MiniMax chat completions failed: {base_resp.get('status_msg')}")

        return body["choices"][0]["message"]["content"]
