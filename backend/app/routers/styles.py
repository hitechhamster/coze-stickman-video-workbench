from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Style
from app.providers.image import get_image_provider
from app.schemas import StyleCreate, StyleOut
from app.services import image_guard
from app.services.scene_prompt import build_character_prompt, load_reference_data_uri

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("", response_model=list[StyleOut])
def list_styles(db: Session = Depends(get_db)):
    return db.query(Style).order_by(Style.created_at).all()


@router.post("", response_model=StyleOut)
def create_style(payload: StyleCreate, db: Session = Depends(get_db)):
    style = Style(**payload.model_dump())
    db.add(style)
    db.commit()
    db.refresh(style)
    return style


@router.put("/{style_id}", response_model=StyleOut)
def update_style(style_id: str, payload: StyleCreate, db: Session = Depends(get_db)):
    style = db.get(Style, style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="画风不存在")
    if style.is_builtin:
        raise HTTPException(status_code=400, detail="内置画风不可修改，请新建自定义画风")
    for key, value in payload.model_dump().items():
        setattr(style, key, value)
    db.commit()
    db.refresh(style)
    return style


@router.post("/{style_id}/reference", response_model=StyleOut)
async def upload_style_reference(
    style_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """上传角色参考图。挂了参考图的画风，生成时会直接拿它锁定角色，跳过"生成角色定妆图"那一步。"""
    style = db.get(Style, style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="画风不存在")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的文件是空的")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="只支持 png / jpg / webp 图片")

    ref_dir = settings.storage_path / "style_refs"
    ref_dir.mkdir(parents=True, exist_ok=True)
    # 换图时把旧的清掉，避免同一画风留下不同后缀的两份文件
    for old in ref_dir.glob(f"{style.id}.*"):
        old.unlink(missing_ok=True)
    ref_path = ref_dir / f"{style.id}{suffix}"
    ref_path.write_bytes(content)

    style.reference_image_url = str(ref_path)
    db.commit()
    db.refresh(style)
    return style


@router.delete("/{style_id}/reference", response_model=StyleOut)
def delete_style_reference(style_id: str, db: Session = Depends(get_db)):
    style = db.get(Style, style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="画风不存在")

    if style.reference_image_url:
        Path(style.reference_image_url).unlink(missing_ok=True)
    style.reference_image_url = None
    db.commit()
    db.refresh(style)
    return style


@router.post("/{style_id}/preview", response_model=StyleOut)
async def generate_style_preview(style_id: str, db: Session = Depends(get_db)):
    style = db.get(Style, style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="画风不存在")

    prompt, negative_prompt = build_character_prompt(style)
    image_provider = get_image_provider(style.image_provider)
    # 有参考图就拿它做图生图，让预览图也长成参考图里那个角色
    reference_uri = load_reference_data_uri(style)
    try:
        result = await image_guard.generate_guarded(
            image_provider,
            prompt,
            negative_prompt=negative_prompt,
            reference_image_url=reference_uri,
            enforce_monochrome=style.enforce_monochrome,
            enforce_color=style.enforce_color,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"预览生成失败: {exc}") from exc

    preview_dir = settings.storage_path / "style_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"{style.id}.png"
    preview_path.write_bytes(result.image_bytes)

    style.thumbnail = str(preview_path)
    db.commit()
    db.refresh(style)
    return style


@router.delete("/{style_id}")
def delete_style(style_id: str, db: Session = Depends(get_db)):
    style = db.get(Style, style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="画风不存在")
    if style.is_builtin:
        raise HTTPException(status_code=400, detail="内置画风不可删除")
    db.delete(style)
    db.commit()
    return {"ok": True}
