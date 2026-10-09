from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EffectPreset
from app.schemas import EffectPresetCreate, EffectPresetOut

router = APIRouter(prefix="/effect-presets", tags=["effect-presets"])


def _payload_dict(payload: EffectPresetCreate) -> dict:
    data = payload.model_dump()
    data["effects"] = [item.model_dump() for item in payload.effects]
    return data


@router.get("", response_model=list[EffectPresetOut])
def list_effect_presets(db: Session = Depends(get_db)):
    return db.query(EffectPreset).order_by(EffectPreset.created_at).all()


@router.post("", response_model=EffectPresetOut)
def create_effect_preset(payload: EffectPresetCreate, db: Session = Depends(get_db)):
    preset = EffectPreset(**_payload_dict(payload))
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.put("/{preset_id}", response_model=EffectPresetOut)
def update_effect_preset(preset_id: str, payload: EffectPresetCreate, db: Session = Depends(get_db)):
    preset = db.get(EffectPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="效果预设不存在")
    if preset.is_builtin:
        raise HTTPException(status_code=400, detail="内置效果预设不可修改，请新建自定义预设")
    for key, value in _payload_dict(payload).items():
        setattr(preset, key, value)
    db.commit()
    db.refresh(preset)
    return preset


@router.delete("/{preset_id}")
def delete_effect_preset(preset_id: str, db: Session = Depends(get_db)):
    preset = db.get(EffectPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="效果预设不存在")
    if preset.is_builtin:
        raise HTTPException(status_code=400, detail="内置效果预设不可删除")
    db.delete(preset)
    db.commit()
    return {"ok": True}
