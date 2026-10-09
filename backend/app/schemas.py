from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StyleCreate(BaseModel):
    name: str
    prompt_suffix: str = ""
    negative_prompt: str = ""
    reference_image_url: str | None = None
    thumbnail: str | None = None
    image_provider: Literal["openrouter", "gemini"] = "openrouter"
    enforce_monochrome: bool = False
    enforce_color: bool = False
    scene_mode: Literal["drama", "teaching"] = "drama"


class StyleOut(StyleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_builtin: bool
    created_at: datetime


class EffectItem(BaseModel):
    name: str
    intensity: int | None = None


class EffectPresetCreate(BaseModel):
    name: str
    description: str = ""
    caption_font: str = "高字标志圆"
    caption_size: float = 11.0
    caption_color: str = "#ffffff"
    caption_border_color: str = "#000000"
    caption_position: float = -0.83
    effects: list[EffectItem] = []
    transition_name: str | None = None
    zoom_end_scale: float = 1.06


class EffectPresetOut(EffectPresetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_builtin: bool
    created_at: datetime


class MusicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    file_path: str
    duration: float | None
    created_at: datetime


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    style_id: str
    voice_id: str
    music_id: str | None = None
    effect_preset_id: str | None = None


class TemplateOut(TemplateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_builtin: bool
    created_at: datetime
    style_name: str
    music_name: str | None = None
    # 复用画风的"一键生成预览"图当模板卡片封面
    style_thumbnail: str | None = None


class ProjectCreate(BaseModel):
    name: str
    script: str
    style_id: str
    voice_id: str
    music_id: str | None = None
    effect_preset_id: str | None = None
    template_id: str | None = None
    mode: str = "ppt_image"


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    index: int
    text: str
    duration: float | None
    image_path: str | None
    status: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    script: str
    style_id: str
    voice_id: str
    music_id: str | None
    effect_preset_id: str | None
    template_id: str | None
    mode: str
    status: str
    video_path: str | None
    created_at: datetime


class ProjectDetailOut(ProjectOut):
    segments: list[SegmentOut] = []


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    progress: float
    current_step: str
    error_message: str | None


class GenerateResponse(BaseModel):
    job_id: str


class DraftInfoOut(BaseModel):
    draft_name: str
    drafts_dir: str


class VoiceOut(BaseModel):
    voice_id: str
    voice_name: str
