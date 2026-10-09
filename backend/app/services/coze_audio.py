"""Per-sentence audio normalization; integer microseconds drive every track."""
import os
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg

from app.services.coze_profile import PAUSE, SPEED


def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(arguments):
    result = subprocess.run([ffmpeg(), "-hide_banner", "-y", *arguments],
                            capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0)
    if result.returncode:
        raise RuntimeError("音频处理失败：" + result.stderr.decode("utf-8", errors="replace")[-600:])


def duration_us(path: Path) -> int:
    with wave.open(str(path), "rb") as audio:
        return round(audio.getnframes() * 1_000_000 / audio.getframerate())


def normalize_audio(source: Path, destination: Path, *, speed=SPEED, trim=True):
    filters = [f"atempo={speed}"]
    if trim:
        # Keep interior pauses; only remove the leading/trailing silence.
        edge = f"silenceremove=start_periods=1:start_duration={PAUSE}:start_threshold=-40dB"
        filters.extend([edge, "areverse", edge, "areverse"])
    run_ffmpeg(["-i", str(source), "-af", ",".join(filters),
                "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(destination)])
    if duration_us(destination) <= 0:
        raise ValueError("配音返回空音频，请重试该段；未跳过任何文案")


def append_pause(path: Path, *, last=False):
    with wave.open(str(path), "rb") as audio:
        params = audio.getparams()
        data = audio.readframes(audio.getnframes())
    if not last:
        data += b"\x00" * round(PAUSE * params.framerate) * params.sampwidth * params.nchannels
        with wave.open(str(path), "wb") as audio:
            audio.setparams(params)
            audio.writeframes(data)


def prepare_music(source: Path, destination: Path):
    run_ffmpeg(["-i", str(source), "-ar", "24000", "-ac", "2", "-c:a", "pcm_s16le", str(destination)])
    if duration_us(destination) <= 0:
        raise ValueError("音乐或点击音效没有有效音频")
