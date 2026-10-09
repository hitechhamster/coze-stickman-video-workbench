import httpx

from app.config import settings
from app.providers.base import LLMProvider

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterLLMProvider(LLMProvider):
    """OpenRouter 代理的文本模型，OpenAI 兼容格式。"""

    def __init__(self) -> None:
        self._api_key = settings.openrouter_api_key
        self._model = settings.openrouter_text_model

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter LLM 失败: {resp.status_code} {resp.text[:500]}")
            body = resp.json()

        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter LLM 无候选结果: {str(body)[:500]}")
        return choices[0]["message"]["content"]
