"""Local calls to model vendors, with original Coze prompts and parameters."""
import base64
import io
import json
import uuid
import wave

import httpx

from app.config import settings
from app.providers.base import AudioResult, ImageResult
from app.providers.image.gemini import GeminiImageProvider
from app.providers.image.openrouter import OpenRouterImageProvider
from app.providers.tts.gemini import GeminiTTSProvider, VOICES
from app.providers.tts.minimax import MiniMaxTTSProvider
from app.services.coze_profile import IMAGE_PROMPT, llm_params


async def complete(node_id, variables, provider):
    params = llm_params(node_id)
    user = params["prompt"]
    for key, value in variables.items():
        user = user.replace("{{" + key + "}}", str(value))
    # Coze adds output-schema constraints outside its exported system prompt.
    schema = ('Return ONLY a JSON object with the string field "wenan".' if node_id == "180546"
              else 'Return ONLY a JSON object with string fields "img_prompt" and "video_prompt".')
    return await chat(provider, params["systemPrompt"] + "\n\n" + schema, user,
                      float(params["temperature"]), int(params["maxTokens"]))


async def chat(provider, system, user, temperature=0.3, max_tokens=12288):
    async with httpx.AsyncClient(timeout=180) as client:
        if provider == "gemini":
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_text_model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"parts": [{"text": user}]}],
                      "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}})
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates") or []
            if not candidates:
                raise RuntimeError("文本模型没有返回结果")
            result = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))
        else:
            if provider == "ark":
                url, key, model = settings.ark_base_url.rstrip("/") + "/chat/completions", settings.ark_api_key, settings.ark_text_model
            elif provider == "openrouter":
                url, key, model = "https://openrouter.ai/api/v1/chat/completions", settings.openrouter_api_key, settings.openrouter_text_model
            else:
                raise ValueError("未知文本服务")
            response = await client.post(url, headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user}], "temperature": temperature, "max_tokens": max_tokens})
            response.raise_for_status()
            choices = response.json().get("choices") or []
            result = choices[0]["message"].get("content") if choices else None
        if not result or not result.strip():
            raise RuntimeError("文本模型返回空文本")
        return result.strip()


async def generate_image(prompt, provider):
    full = IMAGE_PROMPT["prompt"].replace("{{img_prompt}}", prompt)
    negative = IMAGE_PROMPT["negative_prompt"]
    if provider == "ark":
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(settings.ark_base_url.rstrip("/") + "/images/generations",
                headers={"Authorization": f"Bearer {settings.ark_api_key}"},
                json={"model": settings.ark_image_model, "prompt": full + "\n避免：" + negative,
                      "size": "1920x1080", "watermark": False, "response_format": "url"})
            response.raise_for_status()
            items = response.json().get("data") or []
            if not items:
                raise ValueError("生图结果为空")
            if items[0].get("b64_json"):
                raw = base64.b64decode(items[0]["b64_json"])
            elif items[0].get("url"):
                response = await client.get(items[0]["url"])
                response.raise_for_status()
                raw = response.content
            else:
                raise ValueError("生图结果缺少图片链接")
        return ImageResult(raw)
    factory = {"gemini": GeminiImageProvider, "openrouter": OpenRouterImageProvider}
    image = factory[provider]()
    image.aspect_ratio = "16:9"
    return await image.generate(full, negative_prompt=negative)


def parse_tts_lines(lines):
    chunks = []
    for line in lines:
        if not line.strip():
            continue
        body = json.loads(line)
        code = body.get("code")
        # 20000000 appears in the legacy API; 0 is the current documented success code.
        if code not in (0, 20000000):
            raise ValueError(f"豆包配音失败：{code} {body.get('message', '')}")
        if body.get("data"):
            chunks.append(base64.b64decode(body["data"], validate=True))
    pcm = b"".join(chunks)
    if not pcm or len(pcm) % 2:
        raise ValueError("豆包配音返回空或不完整音频")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(pcm)
    return AudioResult(buffer.getvalue(), len(pcm) / 48000, "wav")


async def synthesize(text, voice_id, provider):
    if provider == "volcengine":
        if not voice_id or voice_id.isdigit():
            raise ValueError("请填写火山引擎音色 ID；Coze 的数字音色 ID 不能直接调用厂商接口")
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post("https://openspeech.bytedance.com/api/v3/tts/unidirectional",
                headers={"X-Api-Key": settings.volc_tts_api_key,
                         "X-Api-Resource-Id": settings.volc_tts_resource_id,
                         "X-Api-Request-Id": str(uuid.uuid4())},
                json={"req_params": {"text": text, "speaker": voice_id,
                       "audio_params": {"format": "pcm", "sample_rate": 24000, "speech_rate": 0}}})
            response.raise_for_status()
            return parse_tts_lines(response.text.splitlines())
    if provider == "gemini":
        if voice_id.lower() not in VOICES:
            raise ValueError("请选择有效 Gemini 音色")
        return await GeminiTTSProvider().synthesize(text, voice_id)
    if provider == "minimax":
        return await MiniMaxTTSProvider().synthesize(text, voice_id)
    raise ValueError("未知配音服务")
