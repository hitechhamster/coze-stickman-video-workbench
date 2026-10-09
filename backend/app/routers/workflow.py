from pathlib import Path
from typing import Literal

from dotenv import set_key
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, settings
from app.db import get_db
from app.models import EffectPreset, Music, Project, Style
from app.schemas import ProjectOut
from app.services.coze_pipeline import readiness
from app.services.coze_profile import IMAGE_PROMPT, group_shots, profile, sentence_timeline, split_text

router = APIRouter(prefix="/workflow", tags=["Coze local workflow"])


class WorkflowProjectInput(BaseModel):
    name: str = Field(default="彩色火柴人", max_length=100)
    script: str = Field(default="", max_length=20000)
    subject: str = Field(default="", max_length=1000)
    script_mode: Literal["manual", "auto"] = "manual"
    llm_provider: Literal["ark", "gemini", "openrouter"] = "ark"
    image_provider: Literal["ark", "gemini", "openrouter"] = "ark"
    tts_provider: Literal["volcengine", "gemini", "minimax"] = "volcengine"
    voice_id: str = ""
    music_id: str | None = None


class PlanInput(BaseModel):
    script: str = Field(max_length=20000)


class SettingsInput(BaseModel):
    ark_api_key: str | None = None
    ark_text_model: str | None = None
    ark_image_model: str | None = None
    volc_tts_api_key: str | None = None
    volc_tts_speaker: str | None = None
    volc_tts_resource_id: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    minimax_api_key: str | None = None
    jianying_drafts_dir: str | None = None


def environment_status():
    return {
        "keys": {name: bool(getattr(settings, name)) for name in
                 ("ark_api_key", "volc_tts_api_key", "gemini_api_key", "openrouter_api_key", "minimax_api_key")},
        "ark_text_model": settings.ark_text_model,
        "ark_image_model": settings.ark_image_model,
        "volc_tts_speaker": settings.volc_tts_speaker,
        "volc_tts_resource_id": settings.volc_tts_resource_id,
        "jianying_drafts_dir": settings.jianying_drafts_dir,
        "assets": {"bgm": (settings.workflow_assets_path / "bgm-original.mp3").is_file(),
                   "click": (settings.workflow_assets_path / "click-original.mp3").is_file()},
    }


@router.get("/profile")
def get_profile():
    return {**profile(), "environment": environment_status()}


@router.post("/settings")
def save_settings(payload: SettingsInput, db: Session = Depends(get_db)):
    # Do not change credentials/model bindings underneath active jobs.
    from app.models import Job
    if db.query(Job).filter(Job.status.in_(["running", "pending"])).first():
        raise HTTPException(409, "任务正在生成，请完成后再修改服务配置")
    values = payload.model_dump(exclude_none=True)
    values = {name: value.strip() for name, value in values.items() if value.strip()}
    if "jianying_drafts_dir" in values:
        path = Path(values["jianying_drafts_dir"])
        if not path.is_absolute():
            raise HTTPException(400, "草稿位置必须是完整的本地文件夹路径")
    env_file = BACKEND_DIR / ".env"
    env_file.touch(exist_ok=True)
    for name, value in values.items():
        set_key(str(env_file), name.upper(), value)
        setattr(settings, name, value)
    return environment_status()


@router.post("/plan")
def plan(payload: PlanInput):
    texts = split_text(payload.script)
    if not texts:
        raise HTTPException(400, "请先输入文案")
    if len(texts) > 100:
        raise HTTPException(400, "超过原工作流的 100 段上限")
    # Planning estimates are clearly distinct from measured generation timestamps.
    captions = sentence_timeline(texts, [max(800000, len(t) * 180000) for t in texts])
    return {"estimated": True, "captions": captions, "shots": group_shots(captions)}


@router.post("/projects", response_model=ProjectOut)
def create_workflow_project(payload: WorkflowProjectInput, db: Session = Depends(get_db)):
    if payload.script_mode == "auto" and not payload.subject.strip():
        raise HTTPException(400, "请输入选题")
    if payload.script_mode == "manual" and not payload.script.strip():
        raise HTTPException(400, "请输入自己的文案")
    if payload.music_id and not db.get(Music, payload.music_id):
        raise HTTPException(400, "所选背景音乐不存在")
    if payload.script_mode == "manual" and len(split_text(payload.script)) > 100:
        raise HTTPException(400, "超过原工作流的 100 段上限")
    style = db.query(Style).filter(Style.id == "coze-stickman-original").first()
    if not style:
        style = Style(id="coze-stickman-original", name="Coze 原彩色火柴人",
                      prompt_suffix=IMAGE_PROMPT["prompt"], negative_prompt=IMAGE_PROMPT["negative_prompt"],
                      image_provider="gemini", enforce_color=True, scene_mode="teaching", is_builtin=True)
        db.add(style)
        db.flush()
    preset = db.get(EffectPreset, "coze-original-effects")
    if not preset:
        preset = EffectPreset(id="coze-original-effects", name="Coze 原字幕与特效", is_builtin=True,
                              caption_font="高字标志圆", caption_size=5, caption_position=-0.8,
                              effects=[{"name": "震动", "intensity": None}, {"name": "荧幕噪点", "intensity": None}],
                              transition_name=None, zoom_end_scale=1.0)
        db.add(preset)
        db.flush()
    options = payload.model_dump(exclude={"name", "script", "voice_id", "music_id"})
    project = Project(name=payload.name.strip() or "彩色火柴人", script=payload.script,
                      style_id=style.id, effect_preset_id=preset.id, voice_id=payload.voice_id.strip(),
                      music_id=payload.music_id, mode="coze_original", workflow_options=options)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/check")
def check(payload: WorkflowProjectInput):
    return {"missing": readiness(payload.model_dump(), payload.voice_id)}
