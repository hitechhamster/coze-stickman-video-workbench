import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_suffix: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    reference_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    # 生图渠道：openrouter（代理的 gemini-2.5-flash-image，配音回落MiniMax）
    # / gemini（官方直连，配音也走Gemini自己闭环）
    image_provider: Mapped[str] = mapped_column(String, default="openrouter")
    # 纯黑白画风勾上它：生成后检测彩度，出彩色就自动重生成
    # （生图模型对"必须黑白"的服从度不稳定，只靠提示词压不住）
    enforce_monochrome: Mapped[bool] = mapped_column(Boolean, default=False)
    # 彩色画风勾上它：饱和度太低（画面掉成灰阶）就自动重生成，跟上面的黑白约束互为反面
    enforce_color: Mapped[bool] = mapped_column(Boolean, default=False)
    # 场景叙事模式：drama=戏剧张力（主体在冲突/挣扎的最高点），teaching=教学讲解
    # （主体从容演示、画面传递信息）。命理/科普这类知识内容适合 teaching。
    scene_mode: Mapped[str] = mapped_column(String, default="drama")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EffectPreset(Base):
    """字幕样式 + 特效 + 转场 + 推镜幅度的一整套预设，跟画风(Style)彼此独立、自由组合。"""

    __tablename__ = "effect_presets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    caption_font: Mapped[str] = mapped_column(String, default="高字标志圆")
    caption_size: Mapped[float] = mapped_column(Float, default=11.0)
    caption_color: Mapped[str] = mapped_column(String, default="#ffffff")
    caption_border_color: Mapped[str] = mapped_column(String, default="#000000")
    # transform_y：剪映坐标，单位是半个画布高，-1贴底 0居中 1贴顶
    caption_position: Mapped[float] = mapped_column(Float, default=-0.83)

    # [{"name": "震动", "intensity": 15}, ...]；intensity为None表示该特效不支持强度调节
    effects: Mapped[list] = mapped_column(JSON, default=list)
    transition_name: Mapped[str | None] = mapped_column(String, nullable=True)
    zoom_end_scale: Mapped[float] = mapped_column(Float, default=1.06)


class Music(Base):
    __tablename__ = "music"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    style_id: Mapped[str] = mapped_column(String, ForeignKey("styles.id"), nullable=False)
    voice_id: Mapped[str] = mapped_column(String, nullable=False)
    music_id: Mapped[str | None] = mapped_column(String, ForeignKey("music.id"), nullable=True)
    effect_preset_id: Mapped[str | None] = mapped_column(String, ForeignKey("effect_presets.id"), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    style: Mapped["Style"] = relationship()
    music: Mapped["Music | None"] = relationship()
    effect_preset: Mapped["EffectPreset | None"] = relationship()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    style_id: Mapped[str] = mapped_column(String, ForeignKey("styles.id"), nullable=False)
    voice_id: Mapped[str] = mapped_column(String, nullable=False)
    music_id: Mapped[str | None] = mapped_column(String, ForeignKey("music.id"), nullable=True)
    effect_preset_id: Mapped[str | None] = mapped_column(String, ForeignKey("effect_presets.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String, ForeignKey("templates.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String, default="ppt_image")
    workflow_options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    # 生成完成后落盘的剪映草稿名（草稿实体在 JIANYING_DRAFTS_DIR 下的同名子文件夹里）
    video_path: Mapped[str | None] = mapped_column(String, nullable=True)
    character_ref_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    style: Mapped["Style"] = relationship()
    music: Mapped["Music | None"] = relationship()
    effect_preset: Mapped["EffectPreset | None"] = relationship()
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="project", order_by="Segment.index", cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/running/succeeded/failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[str] = mapped_column(String, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 整段配音里这句话的起止时间（秒），配音是整段一次性合成的，不再有每句独立的音频文件
    start_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    video_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")

    project: Mapped["Project"] = relationship(back_populates="segments")
