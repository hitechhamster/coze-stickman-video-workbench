import base64

import httpx

from app.config import settings
from app.providers.base import ImageProvider, ImageResult

API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


class SeedreamImageProvider(ImageProvider):
    """火山引擎方舟(Ark) 豆包·Seedream 文生图适配器。

    与通义万相不同，这个接口是同步返回结果的，不需要轮询任务状态。
    model 传的是模型名（如 doubao-seedream-4-5-251128），如果账号是走
    "推理接入点"模式，把 ARK_IMAGE_MODEL 换成控制台里创建的 ep-xxxx 接入点ID即可。
    """

    def __init__(self) -> None:
        self._api_key = settings.ark_api_key
        self._model = settings.ark_image_model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image_url: str | None = None,
    ) -> ImageResult:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "size": "1440x2560",
            "response_format": "url",
            "watermark": False,
        }
        if reference_image_url:
            payload["image"] = reference_image_url

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(API_URL, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Seedream 生图失败: {resp.status_code} {resp.text[:500]}")
            body = resp.json()

            items = body.get("data") or []
            if not items:
                raise RuntimeError(f"Seedream 生图任务成功但无结果: {body}")

            item = items[0]
            if item.get("b64_json"):
                image_bytes = base64.b64decode(item["b64_json"])
            elif item.get("url"):
                image_resp = await client.get(item["url"], timeout=60)
                image_resp.raise_for_status()
                image_bytes = image_resp.content
            else:
                raise RuntimeError(f"Seedream 返回结果里没有图片数据: {item}")

        return ImageResult(image_bytes=image_bytes, format="png")
