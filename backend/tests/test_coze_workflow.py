import asyncio
import base64
import io
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import Base
from app.models import Job, Project, Style
from app.providers.base import AudioResult, ImageResult
from app.services import coze_pipeline
from app.services.coze_profile import group_shots, profile, sentence_timeline, split_text
from app.services.coze_providers import parse_tts_lines


def fixture_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        frames = [struct.pack("<h", round(math.sin(i * 2 * math.pi * 440 / 24000) * 3000)) for i in range(16800)]
        audio.writeframes(b"".join(frames))
    return buffer.getvalue()


class ProfileTests(unittest.TestCase):
    def test_exported_constants(self):
        source = profile()
        self.assertEqual(source["canvas"], {"width": 1920, "height": 1080})
        self.assertEqual(source["effects"], ["震动", "荧幕噪点"])
        self.assertEqual(source["caption"]["scale_x"], 1.5)
        self.assertEqual(source["click_duration_us"], 391833)
        self.assertIsNone(source["transition"])

    def test_all_supported_lengths_preserve_order_and_timestamps(self):
        for count in range(1, 101):
            texts = [f"第{i}句" for i in range(count)]
            timeline = sentence_timeline(texts, [1234567 + i for i in range(count)])
            shots = group_shots(timeline)
            self.assertEqual([s["merged_content"] for s in shots[:min(4, count)]], texts[:4])
            self.assertEqual("。".join(s["merged_content"] for s in shots), "。".join(texts))
            self.assertEqual(shots[0]["start"], 0)
            self.assertEqual(shots[-1]["end"], timeline[-1]["end"])
            for a, b in zip(shots, shots[1:]):
                self.assertEqual(a["end"], b["start"])
            for shot in shots[4:]:
                self.assertLessEqual(len(shot["merged_content"].split("。")), 5)
                if count - 4 >= 3:
                    self.assertGreaterEqual(len(shot["merged_content"].split("。")), 3)

    def test_six_and_seven_tail_balance(self):
        for tail, expected in ((6, [3, 3]), (7, [4, 3])):
            shots = group_shots(sentence_timeline([str(i) for i in range(4 + tail)], [1000000] * (4 + tail)))
            self.assertEqual([len(s["merged_content"].split("。")) for s in shots[4:]], expected)

    def test_missing_audio_is_never_dropped(self):
        with self.assertRaises(ValueError):
            sentence_timeline(["第一句", "第二句"], [1000000])
        with self.assertRaises(ValueError):
            sentence_timeline(["第一句"], [0])
        self.assertEqual(split_text('“你好”，你好。\n下一句！'), ["你好", "你好", "下一句"])

    def test_streamed_tts_and_null_failure(self):
        pcm = struct.pack("<h", 120) * 24000
        result = parse_tts_lines([json.dumps({"code": 0, "data": base64.b64encode(pcm).decode()})])
        self.assertEqual(result.duration_seconds, 1)
        with self.assertRaisesRegex(ValueError, "空"):
            parse_tts_lines(['{"code":0,"data":null}'])
        with self.assertRaisesRegex(ValueError, "失败"):
            parse_tts_lines(['{"code":45000001,"message":"bad voice"}'])


class PipelineTests(unittest.TestCase):
    def test_eighth_voice_failure_retry_and_real_draft_assembly(self):
        root = Path(__file__).resolve().parents[2]
        output = root / "outputs"
        output.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            directory = Path(temporary)
            engine = create_engine(f"sqlite:///{directory / 'test.db'}", poolclass=NullPool)
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine)
            with factory() as db:
                style = Style(id="fixture", name="fixture", image_provider="gemini")
                db.add(style)
                project = Project(id="fixture-project", name="工作流测试素材", script="。".join(f"旁白{i}" for i in range(11)),
                                  style_id="fixture", voice_id="fixture", mode="coze_original",
                                  workflow_options={"script_mode": "manual", "llm_provider": "ark", "image_provider": "ark", "tts_provider": "volcengine"})
                db.add(project)
                db.add(Job(id="first-job", project_id=project.id))
                db.commit()
            counters = {"tts": 0, "image": 0, "prompt": 0}
            failed_once = False

            async def tts(text, voice, provider):
                nonlocal failed_once
                counters["tts"] += 1
                if text == "旁白7" and not failed_once:
                    failed_once = True
                    return AudioResult(b"", 0, "wav")
                return AudioResult(fixture_wav(), .7, "wav")

            async def prompt(*args):
                counters["prompt"] += 1
                return '{"img_prompt":"fixture test image","video_prompt":"fixture retained prompt"}'

            async def image(*args):
                counters["image"] += 1
                buffer = io.BytesIO()
                Image.new("RGB", (1920, 1080), "#dbe5d5").save(buffer, "PNG")
                return ImageResult(buffer.getvalue())

            # Each shot's image needs distinct cache keys in the test.
            async def distinct_prompt(node, variables, provider):
                value = json.loads(await prompt())
                value["img_prompt"] += variables["content"]
                return json.dumps(value)

            with patch.object(coze_pipeline, "SessionLocal", factory), patch.object(coze_pipeline, "readiness", return_value=[]), \
                 patch.object(settings, "storage_dir", str(directory / "storage")), \
                 patch.object(settings, "jianying_drafts_dir", str(directory / "drafts")), \
                 patch.object(coze_pipeline.coze_providers, "synthesize", tts), \
                 patch.object(coze_pipeline.coze_providers, "complete", distinct_prompt), \
                 patch.object(coze_pipeline.coze_providers, "generate_image", image):
                coze_pipeline.run_coze_generation("first-job")
                with factory() as db:
                    self.assertEqual(db.get(Job, "first-job").status, "failed")
                    self.assertIn("第 8 段", db.get(Job, "first-job").error_message)
                    self.assertIsNone(db.get(Project, "fixture-project").video_path)
                    db.add(Job(id="retry-job", project_id="fixture-project"))
                    db.commit()
                coze_pipeline.run_coze_generation("retry-job")
                with factory() as db:
                    job = db.get(Job, "retry-job")
                    self.assertEqual(job.status, "succeeded", job.error_message)
                    project = db.get(Project, "fixture-project")
                    self.assertEqual(len(project.segments), 11)
                    draft_dir = directory / "drafts" / project.video_path
                    draft = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
                    manifest = json.loads((draft_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(counters, {"tts": 12, "image": 6, "prompt": 6})
            self.assertEqual((draft["canvas_config"]["width"], draft["canvas_config"]["height"]), (1920, 1080))
            tracks = {track["name"]: track for track in draft["tracks"]}
            self.assertEqual(len(tracks["火柴人分镜"]["segments"]), 6)
            self.assertEqual(len(tracks["正文配音"]["segments"]), 11)
            self.assertEqual(len(tracks["逐句字幕"]["segments"]), 11)
            self.assertEqual(tracks["背景音乐"]["segments"][0]["volume"], .3)
            self.assertEqual(tracks["开头点击音效"]["segments"][0]["volume"], 3)
            self.assertEqual(sum(s["target_timerange"]["duration"] for s in tracks["开头点击音效"]["segments"]), 391833)
            for track_name in ("震动", "荧幕噪点"):
                self.assertEqual(tracks[track_name]["segments"][0]["target_timerange"]["duration"], manifest["duration_us"])
            # Keep the evidence in a durable folder, clearly labelled as synthetic fixture media.
            import shutil
            durable = output / "verification-draft"
            if durable.exists():
                # Copy over files only; do not recursively remove user directories.
                shutil.copytree(draft_dir, durable, dirs_exist_ok=True)
            else:
                shutil.copytree(draft_dir, durable)
            manifest["test_fixture"] = True
            (durable / "workflow_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            # Rebind absolute asset paths after copying the verification draft.
            text = (durable / "draft_content.json").read_text(encoding="utf-8")
            text = text.replace(str(draft_dir.resolve()).replace("\\", "\\\\"), str(durable.resolve()).replace("\\", "\\\\"))
            (durable / "draft_content.json").write_text(text, encoding="utf-8")
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
