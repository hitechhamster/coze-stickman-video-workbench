import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Music
from app.schemas import MusicOut
from app.services.audio_align import probe_duration

router = APIRouter(prefix="/music", tags=["music"])


@router.get("", response_model=list[MusicOut])
def list_music(db: Session = Depends(get_db)):
    return db.query(Music).order_by(Music.created_at.desc()).all()


@router.post("", response_model=MusicOut)
async def upload_music(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    music_dir = settings.storage_path / "music"
    music_dir.mkdir(parents=True, exist_ok=True)

    suffix = "." + file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else ".mp3"
    file_path = music_dir / f"{uuid.uuid4().hex}{suffix}"
    file_path.write_bytes(await file.read())

    duration = probe_duration(file_path)

    music = Music(name=name, file_path=str(file_path), duration=duration)
    db.add(music)
    db.commit()
    db.refresh(music)
    return music


@router.delete("/{music_id}")
def delete_music(music_id: str, db: Session = Depends(get_db)):
    music = db.get(Music, music_id)
    if music is None:
        raise HTTPException(status_code=404, detail="音乐不存在")

    Path(music.file_path).unlink(missing_ok=True)
    db.delete(music)
    db.commit()
    return {"ok": True}
