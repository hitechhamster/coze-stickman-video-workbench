import asyncio
import base64
import io
import re
import wave

import httpx

from app.config import settings
from app.providers.base import AudioResult, SegmentedAudioResult, TTSProvider

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# 接口返回的是裸 PCM（audio/L16;codec=pcm;rate=24000），既没有文件头也不告诉你时长
_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2  # L16 = 16-bit
_DEFAULT_RATE = 24000

# 从接口报错信息里拿到的完整合法音色列表（传一个不存在的音色，它会把允许值全列出来）
VOICES = [
    "achernar", "achird", "algenib", "algieba", "alnilam", "aoede", "autonoe",
    "callirrhoe", "charon", "despina", "enceladus", "erinome", "fenrir", "gacrux",
    "iapetus", "kore", "laomedeia", "leda", "orus", "puck", "pulcherrima",
    "rasalgethi", "sadachbia", "sadaltager", "schedar", "sulafat", "umbriel",
    "vindemiatrix", "zephyr", "zubenelgenubi",
]
DEFAULT_VOICE = "charon"

# 整段脚本合成时，接口会高频返回 finishReason=OTHER 且不带音频——文本越长越容易触发，
# 长段落连试 8 次都失败并不罕见。但单句/短块几乎 100% 成功，所以策略是"化整为零"：
# 把脚本按句拆成小块逐块合成，再把 PCM 拼起来。块内仍保留少量重试兜底偶发波动。
_MAX_ATTEMPTS = 10
_RETRY_BACKOFF = 2.5

# 每块的字符预算：一句一块最稳（实测越短越不容易触发空音频），
# 短句才并块，避免调用次数爆炸
_MAX_CHUNK_CHARS = 100

# 块与块之间垫一小段静音，既让配音听起来有句读停顿，也给下游按静音切分留清晰的断点
_GAP_SECONDS = 0.28


def _parse_rate(mime_type: str) -> int:
    """从 'audio/L16;codec=pcm;rate=24000' 里抠出采样率。"""
    for chunk in mime_type.split(";"):
        chunk = chunk.strip()
        if chunk.startswith("rate="):
            try:
                return int(chunk[len("rate="):])
            except ValueError:
                break
    return _DEFAULT_RATE


def _split_chunks(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """按句末标点把脚本拆成小块，再把相邻短句贪心并到一起，尽量凑满 max_chars。

    单块越短，Gemini TTS 越不容易返回空音频；但也不必一句一次调用，
    所以在不超预算的前提下把连续短句合并，减少调用次数。
    """
    # 在句末标点后切开，保留标点
    sentences = [s for s in re.split(r"(?<=[。！？.!?;；])\s*", text.strip()) if s]
    if not sentences:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _silence_pcm(seconds: float, rate: int) -> bytes:
    return b"\x00" * int(seconds * rate) * _PCM_CHANNELS * _PCM_SAMPLE_WIDTH


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(_PCM_CHANNELS)
        w.setsampwidth(_PCM_SAMPLE_WIDTH)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class GeminiTTSProvider(TTSProvider):
    """Google Gemini 语音合成适配器。

    画风选了 gemini 生图时，配音也走 Gemini 自己闭环（OpenRouter 没有可用的 TTS）。

    两个坑（真实调用探出来的）：
    1. 返回裸 PCM，没有文件头，必须自己封成 WAV 才能给 ffmpeg / 剪映用
    2. 接口不返回时长，但 PCM 是定长编码，字节数 ÷ (采样率×位深×声道) 就是精确时长
       （跟 ffprobe 读出来的结果核对过，小数点后三位一致）
    """

    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_tts_model

    def _headers(self) -> dict:
        return {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

    async def _synthesize_chunk(
        self, client: httpx.AsyncClient, text: str, voice: str
    ) -> tuple[bytes, int]:
        """合成单个文本块，返回 (PCM, 采样率)。块内对偶发空音频做少量重试。"""
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
            },
        }
        url = f"{API_BASE}/{self._model}:generateContent"
        last_finish_reason = None
        for attempt in range(_MAX_ATTEMPTS):
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini TTS 失败: {resp.status_code} {resp.text[:500]}")

            candidates = resp.json().get("candidates") or []
            if candidates:
                for part in candidates[0].get("content", {}).get("parts", []):
                    inline = part.get("inlineData")
                    if not (inline and inline.get("data")):
                        continue
                    pcm = base64.b64decode(inline["data"])
                    return pcm, _parse_rate(inline.get("mimeType", ""))
                last_finish_reason = candidates[0].get("finishReason")

            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_RETRY_BACKOFF)

        raise RuntimeError(
            f"Gemini TTS 连续 {_MAX_ATTEMPTS} 次都没返回音频 (finishReason={last_finish_reason})"
        )

    async def synthesize(self, text: str, voice_id: str) -> AudioResult:
        voice = (voice_id or DEFAULT_VOICE).lower()
        if voice not in VOICES:
            voice = DEFAULT_VOICE

        chunks = _split_chunks(text)
        if not chunks:
            raise RuntimeError("Gemini TTS 收到空文本")

        pieces: list[bytes] = []
        rate = _DEFAULT_RATE
        async with httpx.AsyncClient(timeout=300) as client:
            for i, chunk in enumerate(chunks):
                pcm, rate = await self._synthesize_chunk(client, chunk, voice)
                if i > 0:
                    pieces.append(_silence_pcm(_GAP_SECONDS, rate))
                pieces.append(pcm)

        full_pcm = b"".join(pieces)
        duration = len(full_pcm) / (rate * _PCM_CHANNELS * _PCM_SAMPLE_WIDTH)
        return AudioResult(
            audio_bytes=_pcm_to_wav(full_pcm, rate), duration_seconds=duration, format="wav"
        )

    async def synthesize_segments(
        self, texts: list[str], voice_id: str
    ) -> SegmentedAudioResult:
        """逐个字幕段合成，返回整段音频 + 每段精确时长。

        每段单独合成（段内若过长再拆块），段与段之间垫一小段静音；每段的时长 = 它自己
        的语音 + 尾部那段静音。这样字幕/画面切点直接用这些时长排布，跟旁白严丝合缝，
        不再需要静音检测去猜边界。
        """
        voice = (voice_id or DEFAULT_VOICE).lower()
        if voice not in VOICES:
            voice = DEFAULT_VOICE

        gap = _silence_pcm(_GAP_SECONDS, _DEFAULT_RATE)
        pieces: list[bytes] = []
        durations: list[float] = []
        bytes_per_sec = _DEFAULT_RATE * _PCM_CHANNELS * _PCM_SAMPLE_WIDTH

        async with httpx.AsyncClient(timeout=300) as client:
            for i, text in enumerate(texts):
                chunks = _split_chunks(text) or [text]
                seg_pcm = b""
                for chunk in chunks:
                    pcm, _ = await self._synthesize_chunk(client, chunk, voice)
                    seg_pcm += pcm
                # 除最后一段外，尾部都带一段静音停顿，并计入本段时长
                if i < len(texts) - 1:
                    seg_pcm += gap
                pieces.append(seg_pcm)
                durations.append(len(seg_pcm) / bytes_per_sec)

        full_pcm = b"".join(pieces)
        return SegmentedAudioResult(
            audio_bytes=_pcm_to_wav(full_pcm, _DEFAULT_RATE), durations=durations, format="wav"
        )

    async def list_voices(self) -> list[dict]:
        return [{"voice_id": v, "voice_name": v.capitalize()} for v in VOICES]
