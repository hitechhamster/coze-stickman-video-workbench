from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    minimax_api_host: str = "https://api.minimaxi.com"
    minimax_api_key: str = ""
    minimax_text_model: str = "MiniMax-M2.5"

    ark_api_key: str = ""
    ark_image_model: str = "doubao-seedream-4-5-251128"
    ark_text_model: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volc_tts_api_key: str = ""
    volc_tts_resource_id: str = "seed-tts-2.0"
    volc_tts_speaker: str = ""
    coze_asset_dir: str = "workflow-assets"

    # Google Gemini (Nano Banana)：画风需要画面里出现准确英文文字时用它，Seedream 画不出可读文字
    # 注：不要随手换成 gemini-3.1-flash-image，实测它偏写实、英文反而会拼错
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_text_model: str = "gemini-2.5-flash"

    # OpenRouter：生图走它代理的 gemini-2.5-flash-image；它没有可用的TTS，所以配音回落到 MiniMax
    openrouter_api_key: str = ""
    openrouter_image_model: str = "google/gemini-2.5-flash-image"
    openrouter_text_model: str = "google/gemini-2.5-flash"

    # 备用：通义万相适配器仍保留在 providers/image/tongyi_wanxiang.py，如需切换回去要配这个
    dashscope_api_key: str = ""

    caption_font_path: str = "C:/Windows/Fonts/msyhbd.ttc"

    # 剪映草稿文件夹（剪映App "全局设置 -> 草稿位置" 里能查到自己的实际路径）
    jianying_drafts_dir: str = (
        str(Path.home() / "AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft")
    )
    canvas_width: int = 1080
    canvas_height: int = 1920

    storage_dir: str = "storage"

    @property
    def storage_path(self) -> Path:
        path = BACKEND_DIR / self.storage_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def workflow_assets_path(self) -> Path:
        return BACKEND_DIR / self.coze_asset_dir


settings = Settings()
