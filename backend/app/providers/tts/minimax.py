import httpx

from app.config import settings
from app.providers.base import AudioResult, TTSProvider

DEFAULT_MODEL = "speech-2.6-turbo"


class MiniMaxTTSProvider(TTSProvider):
    def __init__(self) -> None:
        self._host = settings.minimax_api_host.rstrip("/")
        self._api_key = settings.minimax_api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def synthesize(self, text: str, voice_id: str) -> AudioResult:
        payload = {
            "model": DEFAULT_MODEL,
            "text": text,
            "stream": False,
            "language_boost": "auto",
            "output_format": "hex",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self._host}/v1/t2a_v2", headers=self._headers(), json=payload)
            resp.raise_for_status()
            body = resp.json()

        base_resp = body.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(f"MiniMax T2A failed: {base_resp.get('status_msg')}")

        audio_hex = body["data"]["audio"]
        audio_bytes = bytes.fromhex(audio_hex)
        duration_ms = body.get("extra_info", {}).get("audio_length", 0)
        return AudioResult(audio_bytes=audio_bytes, duration_seconds=duration_ms / 1000.0, format="mp3")

    async def list_voices(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._host}/v1/get_voice",
                headers=self._headers(),
                json={"voice_type": "all"},
            )
            resp.raise_for_status()
            body = resp.json()

        base_resp = body.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(f"MiniMax get_voice failed: {base_resp.get('status_msg')}")

        voices = []
        for key in ("system_voice", "voice_cloning", "voice_generation"):
            for item in body.get(key, []) or []:
                voices.append(
                    {
                        "voice_id": item.get("voice_id"),
                        "voice_name": item.get("voice_name") or item.get("voice_id"),
                    }
                )
        return voices
