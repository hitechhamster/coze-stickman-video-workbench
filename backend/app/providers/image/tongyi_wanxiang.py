import asyncio

import httpx

from app.config import settings
from app.providers.base import ImageProvider, ImageResult

API_HOST = "https://dashscope.aliyuncs.com"
CREATE_URL = f"{API_HOST}/api/v1/services/aigc/text2image/image-synthesis"
TASK_URL = f"{API_HOST}/api/v1/tasks/{{task_id}}"
DEFAULT_MODEL = "wanx2.1-t2i-turbo"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 120


class TongyiWanxiangImageProvider(ImageProvider):
    """通义万相(DashScope) 文生图适配器。

    标准 text2image 接口不支持传参考图做风格迁移，reference_image_url
    暂不使用，仅通过 prompt/negative_prompt 控制画风。
    """

    def __init__(self) -> None:
        self._api_key = settings.dashscope_api_key

    def _headers(self, async_mode: bool = False) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        return headers

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image_url: str | None = None,
    ) -> ImageResult:
        payload = {
            "model": DEFAULT_MODEL,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
            },
            "parameters": {
                "size": "720*1280",
                "n": 1,
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(CREATE_URL, headers=self._headers(async_mode=True), json=payload)
            resp.raise_for_status()
            body = resp.json()

            task_id = body.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"通义万相创建任务失败: {body}")

            image_url = await self._poll_task(client, task_id)
            image_resp = await client.get(image_url, timeout=60)
            image_resp.raise_for_status()

        return ImageResult(image_bytes=image_resp.content, format="png")

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str) -> str:
        elapsed = 0
        while elapsed < POLL_TIMEOUT_SECONDS:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS

            resp = await client.get(TASK_URL.format(task_id=task_id), headers=self._headers())
            resp.raise_for_status()
            output = resp.json().get("output", {})
            status = output.get("task_status")

            if status == "SUCCEEDED":
                results = output.get("results") or []
                if not results or not results[0].get("url"):
                    raise RuntimeError(f"通义万相任务成功但无结果: {output}")
                return results[0]["url"]
            if status in ("FAILED", "UNKNOWN"):
                raise RuntimeError(f"通义万相生图任务失败: {output}")
            # PENDING / RUNNING -> 继续轮询

        raise TimeoutError(f"通义万相生图任务超时: task_id={task_id}")
