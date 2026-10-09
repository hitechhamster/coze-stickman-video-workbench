import uuid
from pathlib import Path
from types import SimpleNamespace

import pyJianYingDraft as pyd
from pyJianYingDraft import (
    ClipSettings,
    DraftFolder,
    KeyframeProperty,
    TextBorder,
    TextStyle,
    TrackType,
    TransitionType,
    VideoSceneEffectType,
    trange,
)

from app.config import settings
from app.models import EffectPreset, Project, Segment
from app.services import audio_align
from app.services.jianying_catalog import intensity_param_index

BGM_VOLUME = 0.15
BGM_FADE_OUT = 1.5

# effect_preset 为空时的兜底默认值，跟内置"经典"预设保持一致
DEFAULT_PRESET = SimpleNamespace(
    caption_font="新青年体",
    caption_size=8.0,
    caption_color="#ffffff",
    caption_border_color="#000000",
    caption_position=-0.83,
    effects=[{"name": "荧幕噪点", "intensity": None}],
    transition_name=None,
    zoom_end_scale=1.06,
)


def _to_us(seconds: float) -> int:
    return round(seconds * 1_000_000)


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b)


def _tile_bgm(script: pyd.ScriptFile, track_name: str, music_path: Path, total_duration: float) -> None:
    """把背景音乐按自身时长循环铺满整段时间线，最后一段做淡出（对齐原ffmpeg mix_background_music的做法）。"""
    music_duration = audio_align.probe_duration(music_path)
    if music_duration <= 0:
        return

    # 全程用整数微秒推进，避免每块各自取整后累积出重叠
    total_us = _to_us(total_duration)
    music_us = _to_us(music_duration)

    tiles: list[tuple[int, int]] = []
    cursor = 0
    while cursor < total_us:
        tile_len = min(music_us, total_us - cursor)
        tiles.append((cursor, tile_len))
        cursor += tile_len

    for i, (start, length) in enumerate(tiles):
        seg = pyd.AudioSegment(
            str(music_path),
            trange(start, length),
            source_timerange=trange(0, length),
            volume=BGM_VOLUME,
        )
        if i == len(tiles) - 1:
            seg.add_fade(0, min(_to_us(BGM_FADE_OUT), length))
        script.add_segment(seg, track_name)


def _add_effect_tracks(script: pyd.ScriptFile, effects: list[dict], full_range: pyd.Timerange) -> None:
    for i, item in enumerate(effects):
        name = item["name"] if isinstance(item, dict) else item.name
        intensity = item.get("intensity") if isinstance(item, dict) else item.intensity
        effect_type = getattr(VideoSceneEffectType, name)

        params = None
        if intensity is not None:
            idx = intensity_param_index(name)
            if idx is not None:
                params = [None] * (idx + 1)
                params[idx] = float(intensity)

        track = script.append_track(pyd.TrackSpec(TrackType.effect, name=f"fx_{i}_{name}"))
        script.add_effect(effect_type, full_range, track_name=track.name, params=params)


def build_draft(
    project: Project,
    segments: list[Segment],
    voice_audio_path: Path,
    total_duration: float,
    effect_preset: EffectPreset | None = None,
) -> str:
    """把整段配音 + 每句分镜图 + 字幕 + BGM + 全局特效 + 转场装配成一个剪映草稿，返回草稿名。"""
    preset = effect_preset or DEFAULT_PRESET

    draft_name = f"{project.name}_{uuid.uuid4().hex[:8]}"
    folder = DraftFolder(settings.jianying_drafts_dir)
    script = folder.create_draft(draft_name, settings.canvas_width, settings.canvas_height, fps=30)

    video_track = script.append_track(pyd.TrackSpec(TrackType.video, name="body"))
    text_track = script.append_track(pyd.TrackSpec(TrackType.text, name="captions"))
    voice_track = script.append_track(pyd.TrackSpec(TrackType.audio, name="voice"))

    full_range = trange("0s", f"{total_duration:.3f}s")

    voice_seg = pyd.AudioSegment(str(voice_audio_path), full_range)
    script.add_segment(voice_seg, voice_track)

    caption_font = getattr(pyd.FontType, preset.caption_font)
    # size控制字号，max_line_width是自动换行的可用宽度占比（相对画布宽度）——
    # 字幕大小只应该靠size调，不要再叠加clip_settings的scale，
    # 否则换行是按size算的，缩放却是在换行之后整体拉伸，行宽会超出安全区导致溢出屏幕
    caption_style = TextStyle(
        size=preset.caption_size,
        color=_hex_to_rgb(preset.caption_color),
        align=1,
        auto_wrapping=True,
        max_line_width=0.85,
    )
    caption_border = TextBorder(color=_hex_to_rgb(preset.caption_border_color))
    caption_clip_settings = ClipSettings(transform_y=preset.caption_position)
    transition_type = getattr(TransitionType, preset.transition_name) if preset.transition_name else None

    usable_segments = [
        seg for seg in segments if seg.image_path and seg.start_offset is not None and seg.duration
    ]
    # 先把所有起点定死在整数微秒上，每段时长再由"下一段起点减本段起点"反推。
    # 如果让 start 和 duration 各自四舍五入，前一段的 end 可能比后一段的 start 大 1 微秒，
    # 剪映轨道会判定为片段重叠直接报错。
    starts_us = [_to_us(seg.start_offset) for seg in usable_segments]
    if usable_segments:
        last = usable_segments[-1]
        ends_us = starts_us[1:] + [_to_us(last.start_offset + last.duration)]

    for i, seg in enumerate(usable_segments):
        duration_us = ends_us[i] - starts_us[i]
        seg_range = trange(starts_us[i], duration_us)

        video_seg = pyd.VideoSegment(seg.image_path, seg_range)
        video_seg.add_keyframe(KeyframeProperty.uniform_scale, 0, 1.0)
        video_seg.add_keyframe(KeyframeProperty.uniform_scale, duration_us, preset.zoom_end_scale)
        if transition_type is not None and i < len(usable_segments) - 1:
            # 转场要加在前一个片段上，这是pyJianYingDraft的约定
            video_seg.add_transition(transition_type)
        script.add_segment(video_seg, video_track)

        text_seg = pyd.TextSegment(
            seg.text,
            seg_range,
            font=caption_font,
            style=caption_style,
            border=caption_border,
            clip_settings=caption_clip_settings,
        )
        script.add_segment(text_seg, text_track)

    _add_effect_tracks(script, preset.effects, full_range)

    if project.music and project.music.file_path:
        bgm_track = script.append_track(pyd.TrackSpec(TrackType.audio, name="bgm"))
        _tile_bgm(script, bgm_track.name, Path(project.music.file_path), total_duration)

    script.save()
    return draft_name
