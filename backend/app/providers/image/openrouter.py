import base64
import re

import httpx

from app.config import settings
from app.providers.base import ImageProvider, ImageResult

API_URL = "https://openrouter.ai/api/v1/chat/completions"

_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)


class OpenRouterImageProvider(ImageProvider):
    """OpenRouter 代理的文生图适配器（默认走 google/gemini-2.5-flash-image）。

    跟直连 Gemini 的差别：
    - 接口是 OpenAI 风格的 chat/completions，不是 Gemini 原生的 generateContent
    - 图片藏在 choices[0].message.images[].image_url.url 里，是个 data URI
    - 同样没有 negative prompt 参数，负向词揉进正向提示词
    - 竖屏必须用顶层的 image_config.aspect_ratio。实测下面几种写法都会被静默忽略、
      默默返回 1024x1024 方图（不报错，所以很容易踩坑）：
        generationConfig.imageConfig.aspectRatio（Gemini 原生写法）
        size: "768x1344"（OpenAI images 写法）
        在提示词里写 "vertical 9:16"
    """

    def __init__(self) -> None:
        self._api_key = settings.openrouter_api_key
        self._model = settings.openrouter_image_model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _decode_data_uri(data_uri: str) -> bytes | None:
        match = _DATA_URI_RE.match(data_uri.strip())
        if not match:
            return None
        return base64.b64decode(match.group("data"))

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image_url: str | None = None,
    ) -> ImageResult:
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid all of the following in the image: {negative_prompt}."

        content: list[dict] = [{"type": "text", "text": full_prompt}]
        if reference_image_url:
            content.append({"type": "image_url", "image_url": {"url": reference_image_url}})

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": getattr(self, "aspect_ratio", "9:16")},
        }

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(API_URL, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter 生图失败: {resp.status_code} {resp.text[:500]}")
            body = resp.json()

        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter 生图无候选结果: {str(body)[:500]}")

        message = choices[0].get("message") or {}
        for image in message.get("images") or []:
            url = (image.get("image_url") or {}).get("url", "")
            raw = self._decode_data_uri(url)
            if raw:
                return ImageResult(image_bytes=raw, format="png")

        raise RuntimeError(f"OpenRouter 返回结果里没有图片数据: {str(body)[:500]}")
