from app.providers.base import TTSProvider
from app.providers.tts.gemini import GeminiTTSProvider
from app.providers.tts.minimax import MiniMaxTTSProvider

_PROVIDERS: dict[str, TTSProvider] = {}


def get_tts_provider(image_provider: str | None) -> TTSProvider:
    """配音渠道跟着画风的生图渠道走。

    选 gemini 生图时配音也用 Gemini，自己闭环；
    选 openrouter 时配音回落到 MiniMax——OpenRouter 上没有可用的 TTS
    （只有音乐生成和对话式语音，都不适合"整段旁白合成一条连续人声"这个用法）。
    """
    key = "gemini" if image_provider == "gemini" else "minimax"
    if key not in _PROVIDERS:
        _PROVIDERS[key] = GeminiTTSProvider() if key == "gemini" else MiniMaxTTSProvider()
    return _PROVIDERS[key]
