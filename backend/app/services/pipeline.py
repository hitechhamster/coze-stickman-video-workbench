import asyncio
import json
import traceback
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.models import Job, Project, Segment
from app.providers.image import get_image_provider
from app.providers.tts import get_tts_provider
from app.services import audio_align, image_guard, jianying_draft, scene_prompt
from app.services.script_splitter import split_script


def _project_dir(project_id: str) -> Path:
    path = settings.storage_path / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_segment_image(
    image_provider, style, img_prompt, segment_text, negative_prompt, ref_uri, last_bytes
):
    """单段生图，带多级降级，保证一段失败不拖垮整条视频。

    顺序：戏剧化提示词(带参考图) → 中性提示词(带参考图) → 中性提示词(去参考图) →
    复用上一张。中性提示词刻意平淡，绕开 Gemini 偶发的 PROHIBITED_CONTENT 安全拦截。
    """
    neutral = (
        f"A single clean cartoon illustration for this scene: {segment_text}. {style.prompt_suffix}"
    )
    attempts = [
        (img_prompt, ref_uri),
        (neutral, ref_uri),
        (neutral, None),
    ]
    for idx, (prompt, ref) in enumerate(attempts):
        try:
            result = asyncio.run(
                image_guard.generate_guarded(
                    image_provider,
                    prompt,
                    negative_prompt=negative_prompt,
                    reference_image_url=ref,
                    enforce_monochrome=style.enforce_monochrome,
                    enforce_color=style.enforce_color,
                )
            )
            if idx > 0:
                print(f"[image DEBUG] 段生图降级到方案 {idx + 1} 成功")
            return result.image_bytes
        except Exception as exc:  # noqa: BLE001
            print(f"[image DEBUG] 生图方案 {idx + 1} 失败: {str(exc)[:160]}")
    if last_bytes is not None:
        print("[image DEBUG] 所有方案失败，复用上一段画面")
        return last_bytes
    raise RuntimeError("首段生图连续失败且无可复用画面")


def run_generation(job_id: str) -> None:
    """同步函数，供 FastAPI BackgroundTasks 在线程池中执行。"""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        project = db.get(Project, job.project_id)
        if project is None:
            job.status = "failed"
            job.error_message = "项目不存在"
            db.commit()
            return

        job.status = "running"
        job.current_step = "拆分脚本"
        db.commit()

        texts = split_script(project.script)
        if not texts:
            raise ValueError("脚本为空，无法生成")

        # 重新生成时清掉上一轮遗留的分镜段落，避免新旧数据混在一起
        db.query(Segment).filter(Segment.project_id == project.id).delete()
        db.commit()

        project_dir = _project_dir(project.id)
        # 每句可选的「画面提示」:storage/projects/<id>/scene_hints.json,{"分镜序号": "提示"}。
        # 旁白负责说什么,提示负责画什么——教学句(工资/上班这类具体概念)靠场景引擎
        # 自由发挥常常飘成抽象隐喻,给了提示就按提示画。字幕和配音仍用干净的旁白文本。
        scene_hints: dict = {}
        hints_file = project_dir / "scene_hints.json"
        if hints_file.exists():
            try:
                scene_hints = json.loads(hints_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                print("[scene_hints] 解析失败,忽略")
        segments = [
            Segment(project_id=project.id, index=i, text=text) for i, text in enumerate(texts)
        ]
        db.add_all(segments)
        db.commit()

        style = project.style
        # 文字/水印这些要不要禁止完全交给每个画风自己的negative_prompt决定，
        # 不在这里写死——像"小黑怪诞手绘风"就是故意允许极短标签文字的
        negative_prompt = style.negative_prompt or ""
        image_provider = get_image_provider(style.image_provider)
        tts_provider = get_tts_provider(style.image_provider)

        # 配音合成。优先走"逐段合成"——每个字幕段单独合成、直接拿到精确时长，
        # 字幕/画面切点就能跟旁白严丝合缝；provider不支持时回落到"整段合成+静音检测切分"。
        job.current_step = "配音合成中"
        db.commit()
        segmented = asyncio.run(tts_provider.synthesize_segments(texts, project.voice_id))
        if segmented is not None:
            voice_path = project_dir / f"full_voice.{segmented.format}"
            voice_path.write_bytes(segmented.audio_bytes)
            cursor = 0.0
            for segment, dur in zip(segments, segmented.durations):
                segment.start_offset = cursor
                segment.duration = dur
                cursor += dur
            total_duration = cursor
            db.commit()
        else:
            audio_result = asyncio.run(tts_provider.synthesize(project.script, project.voice_id))
            # 扩展名跟着实际格式走：MiniMax 出 mp3，Gemini 出 wav，
            # 写错扩展名会让剪映拿到一个"名不副实"的音频文件
            voice_path = project_dir / f"full_voice.{audio_result.format}"
            voice_path.write_bytes(audio_result.audio_bytes)
            total_duration = audio_result.duration_seconds or audio_align.probe_duration(voice_path)

            # 用静音检测把整段配音切回每句的时间线（检测点不够时会自动降级为按字数比例切）
            job.current_step = "按停顿切分句子时间线"
            db.commit()
            boundaries = audio_align.split_by_silence(voice_path, texts)
            for segment, (start, end) in zip(segments, boundaries):
                segment.start_offset = start
                segment.duration = end - start
            db.commit()

        # 后面每句配图都拿一张"角色参考图"做图生图，锁定跨分镜的角色一致性。
        # 画风上传了固定参考图就直接用它（角色永远锁死、还省一次生图调用）；
        # 没有的话才现生成一张角色定妆图。
        character_ref_data_uri = scene_prompt.load_reference_data_uri(style)
        if character_ref_data_uri:
            job.current_step = "使用画风的角色参考图"
            project.character_ref_path = style.reference_image_url
            db.commit()
        else:
            job.current_step = "生成角色定妆图"
            db.commit()
            character_prompt, _ = scene_prompt.build_character_prompt(style)
            character_result = asyncio.run(
                image_guard.generate_guarded(
                    image_provider,
                    character_prompt,
                    negative_prompt=negative_prompt,
                    enforce_monochrome=style.enforce_monochrome,
                    enforce_color=style.enforce_color,
                )
            )
            character_ref_path = project_dir / "character_ref.png"
            character_ref_path.write_bytes(character_result.image_bytes)
            project.character_ref_path = str(character_ref_path)
            db.commit()
            character_ref_data_uri = scene_prompt.to_data_uri(character_result.image_bytes)

        total_steps = len(segments) + 1  # +1 for final draft assembly
        last_image_bytes = None
        for i, segment in enumerate(segments):
            job.current_step = f"第 {i + 1}/{len(segments)} 段：生成结构化场景提示词"
            db.commit()

            try:
                hint = scene_hints.get(str(i), "")
                scene_text = (
                    segment.text + "\n[画面指定:" + hint + "。就画这个场景,不要另行发挥别的隐喻]"
                    if hint else segment.text
                )
                img_prompt, video_prompt_text = asyncio.run(
                    scene_prompt.build_scene_prompt(scene_text, style, index=i)
                )
                segment.video_prompt = video_prompt_text
            except Exception:  # noqa: BLE001
                # 结构化提示词生成失败时优雅降级，不影响整体生成
                print(f"[scene_prompt DEBUG] failed:\n{traceback.format_exc()}")
                img_prompt = (
                    f"{style.prompt_suffix}\n"
                    f"为下面这句旁白配一张对应场景的插画，画面中禁止出现任何文字、字幕、汉字或水印：{segment.text}"
                )
            db.commit()

            job.current_step = f"第 {i + 1}/{len(segments)} 段：画面生成中"
            db.commit()

            image_bytes = _generate_segment_image(
                image_provider,
                style,
                img_prompt,
                segment.text,
                negative_prompt,
                character_ref_data_uri,
                last_image_bytes,
            )
            last_image_bytes = image_bytes
            image_path = project_dir / f"segment_{i}.png"
            image_path.write_bytes(image_bytes)
            segment.image_path = str(image_path)
            segment.status = "done"
            db.commit()

            job.progress = (i + 1) / total_steps
            db.commit()

        job.current_step = "装配剪映草稿"
        db.commit()
        draft_name = jianying_draft.build_draft(
            project, segments, voice_path, total_duration, effect_preset=project.effect_preset
        )

        project.video_path = draft_name
        project.status = "succeeded"
        job.progress = 1.0
        job.status = "succeeded"
        job.current_step = "完成"
        db.commit()

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = f"{exc}\n{traceback.format_exc()[-1500:]}"
            db.commit()
        project = db.get(Project, job.project_id) if job else None
        if project is not None:
            project.status = "failed"
            db.commit()
    finally:
        db.close()
