from app.providers.base import LLMProvider
from app.providers.llm.gemini_llm import GeminiLLMProvider
from app.providers.llm.openrouter_llm import OpenRouterLLMProvider

_PROVIDERS: dict[str, LLMProvider] = {}


def get_llm_provider(image_provider: str | None) -> LLMProvider:
    """生成结构化场景提示词用的文本模型，跟着画风的生图渠道走。

    这样每个渠道都尽量自我闭环：
    - gemini     -> Gemini 生图 + Gemini 配音 + Gemini 提示词，只需要一个 GEMINI_API_KEY
    - openrouter -> OpenRouter 生图 + OpenRouter 提示词（配音仍需 MiniMax，
                    因为 OpenRouter 上没有可用的 TTS）

    MiniMax 的 LLM 适配器仍保留在 llm/minimax_llm.py 当备用。
    """
    key = "gemini" if image_provider == "gemini" else "openrouter"
    if key not in _PROVIDERS:
        _PROVIDERS[key] = GeminiLLMProvider() if key == "gemini" else OpenRouterLLMProvider()
    return _PROVIDERS[key]
