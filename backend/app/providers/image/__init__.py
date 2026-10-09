from app.providers.base import ImageProvider
from app.providers.image.gemini import GeminiImageProvider
from app.providers.image.openrouter import OpenRouterImageProvider

# 当前对外暴露的两个生图渠道。
# seedream.py / tongyi_wanxiang.py 仍留在仓库里当备用适配器，但不再作为选项。
DEFAULT_PROVIDER = "openrouter"

_FACTORIES = {
    "openrouter": OpenRouterImageProvider,
    "gemini": GeminiImageProvider,
}

# provider 实例是无状态的，进程内复用即可
_PROVIDERS: dict[str, ImageProvider] = {}


def get_image_provider(name: str | None) -> ImageProvider:
    """按画风上配置的 image_provider 取对应的文生图适配器，未知/为空时回落到默认渠道。"""
    key = name if name in _FACTORIES else DEFAULT_PROVIDER
    if key not in _PROVIDERS:
        _PROVIDERS[key] = _FACTORIES[key]()
    return _PROVIDERS[key]
