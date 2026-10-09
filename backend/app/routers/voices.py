from fastapi import APIRouter, HTTPException, Query

from app.providers.tts import get_tts_provider
from app.schemas import VoiceOut

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=list[VoiceOut])
async def list_voices(
    image_provider: str | None = Query(
        default=None,
        description="画风用的生图渠道；配音渠道跟着它走（gemini 用 Gemini 音色，其余用 MiniMax）",
    ),
):
    tts_provider = get_tts_provider(image_provider)
    try:
        voices = await tts_provider.list_voices()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"获取音色列表失败，请检查对应的 API Key 配置: {exc}") from exc
    return voices
