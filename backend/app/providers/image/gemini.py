import base64
import re

import httpx

from app.config import settings
from app.providers.base import ImageProvider, ImageResult

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)


class GeminiImageProvider(ImageProvider):
    """Google Gemini (Nano Banana) 文生图适配器。

    相比 Seedream 贵一点，但能把提示词里用引号指定的英文短标签准确渲染进画面，
    "小黑怪诞手绘风"这类靠图内文字承载信息量的画风必须用它。

    两个坑（都是真实调用探出来的，不是文档抄的）：
    1. 没有 negative prompt 参数，负向词只能揉进正向提示词里
    2. 响应 parts 顺序不固定，模型有时会先回一句闲聊文字再给图，必须遍历找 inlineData
    """

    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_image_model

    def _headers(self) -> dict:
        return {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

    @staticmethod
    def _parse_data_uri(data_uri: str) -> tuple[str, str] | None:
        """把 pipeline 传来的 data:image/png;base64,xxx 拆成 (mime_type, base64_data)。"""
        match = _DATA_URI_RE.match(data_uri.strip())
        if not match:
            return None
        return match.group("mime"), match.group("data")

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image_url: str | None = None,
    ) -> ImageResult:
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid all of the following in the image: {negative_prompt}."

        parts: list[dict] = []
        if reference_image_url:
            parsed = self._parse_data_uri(reference_image_url)
            if parsed:
                mime_type, b64_data = parsed
                parts.append({"inlineData": {"mimeType": mime_type, "data": b64_data}})
        parts.append({"text": full_prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"imageConfig": {"aspectRatio": getattr(self, "aspect_ratio", "9:16")}},
        }

        url = f"{API_BASE}/{self._model}:generateContent"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini 生图失败: {resp.status_code} {resp.text[:500]}")
            body = resp.json()

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini 生图无候选结果: {str(body)[:500]}")

        for part in candidates[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                return ImageResult(image_bytes=base64.b64decode(inline["data"]), format="png")

        finish_reason = candidates[0].get("finishReason")
        raise RuntimeError(f"Gemini 返回结果里没有图片数据 (finishReason={finish_reason}): {str(body)[:500]}")
