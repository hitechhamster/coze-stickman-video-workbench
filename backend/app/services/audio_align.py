import re
import subprocess
import shutil
from pathlib import Path

SILENCE_NOISE_DB = "-30dB"
SILENCE_MIN_DURATION = 0.3  # 秒，短于这个时长的停顿不算句间静音
_EDGE_GUARD = 0.15  # 秒，太靠近首尾的静音点不当作句间边界（多半是开头/结尾的留白）


def probe_duration(path: Path) -> float:
    if shutil.which("ffprobe") is None:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(str(path))
        for track in info.tracks:
            if track.track_type == "General" and track.duration:
                return float(track.duration) / 1000
        raise ValueError("无法读取音频时长")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout or ""
    try:
        return float(output.strip())
    except ValueError:
        raise RuntimeError(f"无法读取音频时长: {path}, ffprobe输出: {output!r}")


def _detect_silences(audio_path: Path) -> list[tuple[float, float]]:
    """用 ffmpeg silencedetect 滤镜找出音频里的静音区间，返回 [(start, end), ...]。

    ffmpeg 把 silencedetect 的日志写到 stderr，但在 FastAPI 的线程池里用
    capture_output=True 同时接两个管道时，stderr 偶发会拿到 None（Windows下的一个
    subprocess/线程池交互怪癖）。这里改成把 stderr 合并进 stdout，只接一个管道，规避掉。
    """
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(audio_path),
            "-af", f"silencedetect=noise={SILENCE_NOISE_DB}:d={SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout or ""
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", output)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", output)]
    # 如果整段音频以静音收尾，silence_start 会比 silence_end 多一个，zip会自动丢掉这个不完整的尾巴
    return list(zip(starts, ends))


def _pick_boundaries(candidates: list[float], k: int, total_duration: float) -> list[float]:
    """从静音中点候选里挑k个，尽量贴近total_duration的k等分理想点。"""
    ideal = [total_duration * (i + 1) / (k + 1) for i in range(k)]
    chosen: list[float] = []
    remaining = list(candidates)
    for target in ideal:
        if not remaining:
            break
        nearest = min(remaining, key=lambda b: abs(b - target))
        chosen.append(nearest)
        remaining.remove(nearest)
    return sorted(chosen)


def _split_proportional(sentence_texts: list[str], total_duration: float) -> list[tuple[float, float]]:
    """静音点不够用时的保底方案：按每句字符数占比切分整段时长。"""
    total_chars = sum(len(t) for t in sentence_texts) or 1
    edges = [0.0]
    acc = 0
    for text in sentence_texts:
        acc += len(text)
        edges.append(total_duration * acc / total_chars)
    edges[-1] = total_duration
    return list(zip(edges[:-1], edges[1:]))


def split_by_silence(audio_path: Path, sentence_texts: list[str]) -> list[tuple[float, float]]:
    """把整段配音按句子切成 [(start, end), ...]（单位秒），优先用静音检测，检测点不够时降级按字数比例切。"""
    if not sentence_texts:
        return []

    total_duration = probe_duration(audio_path)
    n = len(sentence_texts)
    if n == 1:
        return [(0.0, total_duration)]

    silences = _detect_silences(audio_path)
    midpoints = sorted((s + e) / 2 for s, e in silences if e > s)
    candidates = [m for m in midpoints if _EDGE_GUARD < m < total_duration - _EDGE_GUARD]

    if len(candidates) >= n - 1:
        chosen = _pick_boundaries(candidates, n - 1, total_duration)
        edges = [0.0, *chosen, total_duration]
        return list(zip(edges[:-1], edges[1:]))

    return _split_proportional(sentence_texts, total_duration)
