import httpx

from app.config import settings
from app.providers.base import LLMProvider

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLMProvider(LLMProvider):
    """Gemini 文本模型，用来把旁白转成结构化场景提示词。

    有了它，画风选 gemini 渠道时整条流水线（生图+配音+提示词）都只需要一个 GEMINI_API_KEY。
    """

    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_text_model

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            # Gemini 把 system prompt 单独放在 systemInstruction，不是塞进 contents
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }

        url = f"{API_BASE}/{self._model}:generateContent"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini LLM 失败: {resp.status_code} {resp.text[:500]}")
            body = resp.json()

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini LLM 无候选结果: {str(body)[:500]}")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            finish_reason = candidates[0].get("finishReason")
            raise RuntimeError(f"Gemini LLM 返回空文本 (finishReason={finish_reason})")
        return text
