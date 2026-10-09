"""Assemble the final exported chain locally instead of calling Jianying plugins."""
import json
import shutil
import uuid
from pathlib import Path

import pyJianYingDraft as pyd

from app.services.coze_audio import duration_us
from app.services.coze_profile import CAPTIONS, CLICK_END, HEIGHT, WIDTH, inputs, profile


def tile_audio(script, path, track, start, end, volume):
    source_duration = duration_us(path)
    if source_duration <= 0:
        raise ValueError("音频素材时长为零")
    material = pyd.AudioMaterial(str(path))
    # MediaInfo can round WAV durations to milliseconds. Use the actual sample count.
    material.duration = source_duration
    cursor = start
    while cursor < end:
        length = min(source_duration, end - cursor)
        script.add_segment(pyd.AudioSegment(material, pyd.trange(cursor, length),
                           source_timerange=pyd.trange(0, length), volume=volume), track)
        cursor += length


def build_coze_draft(name, shots, captions, audio_paths, bgm_path, click_path, drafts_dir, manifest):
    if not captions or len(captions) != len(audio_paths):
        raise ValueError("字幕与配音条数不一致")
    if not shots or shots[0]["start"] != 0 or shots[-1]["end"] != captions[-1]["end"]:
        raise ValueError("分镜没有覆盖完整配音时间线")
    previous_end = 0
    for shot in shots:
        if shot["start"] != previous_end or shot["end"] <= shot["start"]:
            raise ValueError("分镜存在空缺或重叠")
        previous_end = shot["end"]
        if not Path(shot["image_path"]).is_file():
            raise ValueError("分镜配图缺失")

    Path(drafts_dir).mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in name if c not in '<>:"/\\|?*').strip(" .")[:70] or "彩色火柴人"
    draft_name = f"{safe_name}_{uuid.uuid4().hex[:8]}"
    folder = pyd.DraftFolder(str(drafts_dir))
    script = folder.create_draft(draft_name, WIDTH, HEIGHT, fps=30)
    draft_dir = Path(drafts_dir) / draft_name
    assets = draft_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    def local(source, filename):
        destination = assets / filename
        shutil.copy2(source, destination)
        return destination.resolve()

    images = script.append_track(pyd.TrackSpec(pyd.TrackType.video, name="火柴人分镜"))
    text_track = script.append_track(pyd.TrackSpec(pyd.TrackType.text, name="逐句字幕"))
    voice = script.append_track(pyd.TrackSpec(pyd.TrackType.audio, name="正文配音"))
    music = script.append_track(pyd.TrackSpec(pyd.TrackType.audio, name="背景音乐"))
    click = script.append_track(pyd.TrackSpec(pyd.TrackType.audio, name="开头点击音效"))
    total_us = captions[-1]["end"]

    # Original graph specifies no transitions/zoom. Do not inherit upstream's zoom default.
    for i, shot in enumerate(shots):
        image = local(shot["image_path"], f"shot_{i + 1:03d}.png")
        script.add_segment(pyd.VideoSegment(str(image),
            pyd.trange(shot["start"], shot["end"] - shot["start"])), images)

    for i, (row, audio) in enumerate(zip(captions, audio_paths)):
        audio = local(audio, f"voice_{i + 1:03d}.wav")
        length = row["end"] - row["start"]
        if abs(duration_us(audio) - length) > 50:
            raise ValueError(f"第 {i + 1} 段配音与字幕时间线不一致")
        timerange = pyd.trange(row["start"], length)
        material = pyd.AudioMaterial(str(audio))
        material.duration = duration_us(audio)
        segment = pyd.AudioSegment(material, timerange)
        segment.add_effect(pyd.AudioSceneEffectType.人声增强3)
        script.add_segment(segment, voice)
        # Exported plugin omits its coordinate unit. Explicit calibrated mapping is recorded.
        script.add_segment(pyd.TextSegment(row["content"], timerange,
            font=getattr(pyd.FontType, CAPTIONS["font"]),
            style=pyd.TextStyle(size=float(CAPTIONS["font_size"]), color=(1, 1, 1),
                                align=1, auto_wrapping=True, max_line_width=0.85),
            border=pyd.TextBorder(color=(0, 0, 0)),
            clip_settings=pyd.ClipSettings(scale_x=float(CAPTIONS["scale_x"]),
                scale_y=float(CAPTIONS["scale_y"]), transform_y=float(CAPTIONS["transform_y"]) / 1000)), text_track)

    bgm = local(bgm_path, "bgm.wav")
    click_audio = local(click_path, "click.wav")
    tile_audio(script, bgm, music, 0, total_us, inputs("145750")["volume"])
    tile_audio(script, click_audio, click, 0, min(CLICK_END, total_us), inputs("1466353")["volume"])
    for name in ("震动", "荧幕噪点"):
        track = script.append_track(pyd.TrackSpec(pyd.TrackType.effect, name=name))
        script.add_effect(getattr(pyd.VideoSceneEffectType, name), pyd.trange(0, total_us), track_name=track.name)
    script.save()
    report = {**manifest, "draft_name": draft_name, "profile": profile(),
              "duration_us": total_us, "sentences": captions,
              "shots": [{k: v for k, v in shot.items() if k != "image_path"} for shot in shots]}
    (draft_dir / "workflow_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft_name
