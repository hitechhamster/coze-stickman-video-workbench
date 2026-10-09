import asyncio
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageOps

from app.config import settings
from app.db import SessionLocal
from app.models import Job, Project, Segment
from app.services import coze_audio, coze_providers
from app.services.coze_draft import build_coze_draft
from app.services.coze_profile import (IMAGE_PROMPT, SOURCE_SHA256, decode_json, group_shots,
                                      llm_params, sentence_timeline, split_text)


def digest(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def readiness(options, voice_id=""):
    missing = []
    for role in ("llm_provider", "image_provider"):
        provider = options.get(role, "ark")
        key = {"ark": settings.ark_api_key, "gemini": settings.gemini_api_key,
               "openrouter": settings.openrouter_api_key}.get(provider)
        if not key:
            missing.append(f"{provider} API Key")
    if options.get("llm_provider", "ark") == "ark" and not settings.ark_text_model:
        missing.append("豆包文本模型接入点 ID")
    tts = options.get("tts_provider", "volcengine")
    if not {"volcengine": settings.volc_tts_api_key, "gemini": settings.gemini_api_key,
            "minimax": settings.minimax_api_key}.get(tts):
        missing.append(f"{tts} 配音 API Key")
    if not voice_id or (tts == "volcengine" and voice_id.isdigit()):
        missing.append("可用于厂商 API 的音色 ID")
    if not options.get("music_id") and not (settings.workflow_assets_path / "bgm-original.mp3").exists():
        missing.append("原背景音乐素材")
    if not (settings.workflow_assets_path / "click-original.mp3").exists():
        missing.append("原点击音效素材")
    return list(dict.fromkeys(missing))


def _save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


async def _bounded(items, worker, limit):
    semaphore = asyncio.Semaphore(limit)

    async def run(index, item):
        async with semaphore:
            return await worker(index, item)

    # Wait for all in-flight work before failure so completed assets are cached for retry.
    results = await asyncio.gather(*(run(i, item) for i, item in enumerate(items)), return_exceptions=True)
    errors = [str(value) for value in results if isinstance(value, Exception)]
    if errors:
        raise RuntimeError("；".join(errors[:3]) + "。成功素材已缓存，可重试失败任务。")
    return results


def run_coze_generation(job_id):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        project = db.get(Project, job.project_id)
        if project is None:
            raise ValueError("项目不存在")
        options = project.workflow_options or {}
        missing = readiness({**options, "music_id": project.music_id}, project.voice_id)
        if missing:
            raise ValueError("请先配置：" + "、".join(missing))
        project_dir = settings.storage_path / "projects" / project.id
        cache = project_dir / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        job.status = "running"

        def step(text, progress):
            job.current_step = text
            job.progress = progress
            db.commit()

        llm_provider = options.get("llm_provider", "ark")
        image_provider = options.get("image_provider", "ark")
        tts_provider = options.get("tts_provider", "volcengine")
        if options.get("script_mode") == "auto":
            step("按原工作流生成口播文案", 0.02)
            key = digest(options.get("subject"), llm_provider, settings.ark_text_model,
                         settings.gemini_text_model, settings.openrouter_text_model, SOURCE_SHA256)
            script_file = cache / f"script_{key}.txt"
            if script_file.exists():
                script = script_file.read_text(encoding="utf-8")
            else:
                result = decode_json(asyncio.run(coze_providers.complete("180546",
                    {"subject": options.get("subject", "")}, llm_provider)))
                if not isinstance(result, dict) or not isinstance(result.get("wenan"), str) or not result["wenan"].strip():
                    raise ValueError("文案模型必须返回包含 wenan 字段的 JSON 对象")
                script = result["wenan"]
                script_file.write_text(script, encoding="utf-8")
            project.script = script
            db.commit()
        else:
            script = project.script
        texts = split_text(script)
        if not texts:
            raise ValueError("文案为空")
        if len(texts) > 100:
            raise ValueError("文案超过原工作流的 100 段上限，请缩短文案")
        db.query(Segment).filter(Segment.project_id == project.id).delete()
        segments = [Segment(project_id=project.id, index=i, text=text) for i, text in enumerate(texts)]
        db.add_all(segments)
        db.commit()

        step(f"逐段合成配音（共 {len(texts)} 段，检查空音频）", 0.08)

        async def voice_worker(index, text):
            key = digest(index, text, project.voice_id, tts_provider, SOURCE_SHA256,
                         settings.gemini_tts_model, settings.volc_tts_resource_id, index == len(texts) - 1)
            final = cache / f"voice_{key}.wav"
            try:
                if final.exists() and coze_audio.duration_us(final) > 0:
                    return final
                result = await coze_providers.synthesize(text, project.voice_id, tts_provider)
                if not result.audio_bytes:
                    raise ValueError("data 为空，没有生成音频")
                source = cache / f"voice_raw_{key}.{result.format}"
                source.write_bytes(result.audio_bytes)
                temporary = cache / f"voice_work_{key}.wav"
                await asyncio.to_thread(coze_audio.normalize_audio, source, temporary)
                await asyncio.to_thread(coze_audio.append_pause, temporary, last=index == len(texts) - 1)
                temporary.replace(final)
                return final
            except Exception as exc:
                raise RuntimeError(f"第 {index + 1} 段配音失败（{text[:25]}）：{exc}") from exc

        audio_paths = asyncio.run(_bounded(texts, voice_worker, 10))
        captions = sentence_timeline(texts, [coze_audio.duration_us(p) for p in audio_paths])
        shots = group_shots(captions)
        if len(shots) > 100:
            raise ValueError("分镜数量超出原工作流上限")
        for segment, row in zip(segments, captions):
            segment.start_offset = row["start"] / 1_000_000
            segment.duration = (row["end"] - row["start"]) / 1_000_000
        db.commit()
        _save_json(project_dir / "timeline.json", {"captions": captions, "shots": shots})
        step(f"按原规则合镜：{len(texts)} 段文案 → {len(shots)} 个分镜", 0.32)

        async def prompt_worker(index, shot):
            key = digest(index, shot["merged_content"], llm_provider, settings.ark_text_model,
                         settings.gemini_text_model, settings.openrouter_text_model, SOURCE_SHA256)
            file = cache / f"prompt_{key}.json"
            try:
                if file.exists():
                    prompt = json.loads(file.read_text(encoding="utf-8"))
                else:
                    prompt = decode_json(await coze_providers.complete("168059",
                        {"content": shot["merged_content"]}, llm_provider))
                    if isinstance(prompt, list) and len(prompt) == 1:
                        prompt = prompt[0]
                    if not isinstance(prompt, dict) or any(not isinstance(prompt.get(k), str) or not prompt[k].strip()
                                                          for k in ("img_prompt", "video_prompt")):
                        raise ValueError("缺少 img_prompt 或 video_prompt")
                    _save_json(file, prompt)
                return prompt
            except Exception as exc:
                raise RuntimeError(f"分镜 {index + 1} 提示词生成失败：{exc}") from exc

        prompts = asyncio.run(_bounded(shots, prompt_worker, 10))
        step(f"生成彩色水彩火柴人配图（{len(shots)} 个分镜）", 0.45)

        async def image_worker(index, prompt):
            key = digest(index, prompt["img_prompt"], image_provider, settings.ark_image_model,
                         settings.gemini_image_model, settings.openrouter_image_model, SOURCE_SHA256)
            file = cache / f"image_{key}.png"
            if file.exists():
                try:
                    with Image.open(file) as image:
                        image.verify()
                    return str(file)
                except Exception:
                    pass
            try:
                try:
                    result = await coze_providers.generate_image(prompt["img_prompt"], image_provider)
                except Exception:
                    # Exact exported branch: image failure -> prompt optimization -> image retry.
                    improved = await coze_providers.chat(llm_provider,
                        "Optimize this image prompt for generation. Preserve every character, art style, palette and scene. Return only the improved prompt.",
                        prompt["img_prompt"])
                    result = await coze_providers.generate_image(improved, image_provider)
                with Image.open(io.BytesIO(result.image_bytes)) as image:
                    # Models may return nearby resolutions. Fit the original horizontal canvas.
                    image = ImageOps.fit(image.convert("RGB"), (1920, 1080), method=Image.Resampling.LANCZOS)
                    temporary = file.with_suffix(".tmp")
                    image.save(temporary, format="PNG")
                    temporary.replace(file)
                return str(file)
            except Exception as exc:
                raise RuntimeError(f"分镜 {index + 1} 配图失败：{exc}") from exc

        image_paths = asyncio.run(_bounded(prompts, image_worker, 3))
        for shot, prompt, path in zip(shots, prompts, image_paths):
            shot.update(prompt)
            shot["image_path"] = path
        for segment, row in zip(segments, captions):
            shot = next(s for s in shots if s["start"] <= row["start"] < s["end"])
            segment.image_path = shot["image_path"]
            segment.video_prompt = shot["video_prompt"]
            segment.status = "done"
        db.commit()
        step("准备原背景音乐和开头点击音效", 0.88)
        bgm_source = Path(project.music.file_path) if project.music else settings.workflow_assets_path / "bgm-original.mp3"
        click_source = settings.workflow_assets_path / "click-original.mp3"
        music_paths = []
        for source in (bgm_source, click_source):
            key = digest(hashlib.sha256(source.read_bytes()).hexdigest())
            target = cache / f"music_{key}.wav"
            if not target.exists():
                coze_audio.prepare_music(source, target)
            music_paths.append(target)
        manifest = {"source_sha256": SOURCE_SHA256, "options": options,
                    "voice_id": project.voice_id, "prompt_engine": llm_provider,
                    "image_engine": image_provider, "audio_engine": tts_provider,
                    "model_bindings": {"ark_text": settings.ark_text_model, "ark_image": settings.ark_image_model,
                                       "gemini_text": settings.gemini_text_model, "gemini_image": settings.gemini_image_model},
                    "rendering": "static_images_hard_cuts", "draft_chain": "105280 -> 1488114"}
        step("按原参数组装剪映草稿", 0.95)
        draft_name = build_coze_draft(project.name, shots, captions, audio_paths,
            music_paths[0], music_paths[1], settings.jianying_drafts_dir, manifest)
        _save_json(project_dir / "workflow_manifest.json", {**manifest, "draft_name": draft_name,
                                                             "captions": captions, "shots": shots})
        project.video_path = draft_name
        project.status = "succeeded"
        job.status = "succeeded"
        step("剪映草稿已完成", 1.0)
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.current_step = "生成中断，成功素材已缓存"
            project = db.get(Project, job.project_id)
            if project:
                project.status = "failed"
            db.commit()
    finally:
        db.close()
