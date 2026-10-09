from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AudioResult:
    audio_bytes: bytes
    duration_seconds: float
    format: str = "mp3"


@dataclass
class SegmentedAudioResult:
    """逐段合成的配音：整段音频 + 每个字幕段的精确时长。

    有了每段精确时长，字幕/画面切换就能跟旁白严丝合缝，不用再靠静音检测反推边界。
    durations 的长度和顺序跟传入的 texts 一一对应，累加即为总时长。
    """

    audio_bytes: bytes
    durations: list[float]
    format: str = "wav"


@dataclass
class ImageResult:
    image_bytes: bytes
    format: str = "png"


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice_id: str) -> AudioResult: ...

    async def synthesize_segments(
        self, texts: list[str], voice_id: str
    ) -> "SegmentedAudioResult | None":
        """逐段合成，返回每段精确时长；不支持的provider返回None，调用方回落到整段合成+静音切分。"""
        return None

    @abstractmethod
    async def list_voices(self) -> list[dict]: ...


class LLMProvider(ABC):
    """把旁白转成结构化场景提示词用的文本模型。"""

    @abstractmethod
    async def chat(self, system_prompt: str, user_prompt: str) -> str: ...


class ImageProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_image_url: str | None = None,
    ) -> ImageResult: ...


class VideoProvider(ABC):
    """Mode B（AI短片拼接）预留扩展点，本次 MVP 不实现。"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        reference_image_url: str | None = None,
    ) -> bytes: ...
