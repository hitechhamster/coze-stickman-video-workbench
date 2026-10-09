from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EffectPreset, Music, Style, Template
from app.schemas import TemplateCreate, TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


def _to_out(template: Template) -> TemplateOut:
    return TemplateOut(
        id=template.id,
        name=template.name,
        description=template.description,
        style_id=template.style_id,
        voice_id=template.voice_id,
        music_id=template.music_id,
        effect_preset_id=template.effect_preset_id,
        is_builtin=template.is_builtin,
        created_at=template.created_at,
        style_name=template.style.name,
        music_name=template.music.name if template.music else None,
        style_thumbnail=template.style.thumbnail,
    )


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(Template).order_by(Template.created_at).all()
    return [_to_out(t) for t in templates]


@router.post("", response_model=TemplateOut)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    if db.get(Style, payload.style_id) is None:
        raise HTTPException(status_code=400, detail="所选画风不存在")
    if payload.music_id and db.get(Music, payload.music_id) is None:
        raise HTTPException(status_code=400, detail="所选音乐不存在")
    if payload.effect_preset_id and db.get(EffectPreset, payload.effect_preset_id) is None:
        raise HTTPException(status_code=400, detail="所选效果预设不存在")

    template = Template(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return _to_out(template)


@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    if template.is_builtin:
        raise HTTPException(status_code=400, detail="内置模板不可删除")
    db.delete(template)
    db.commit()
    return {"ok": True}
