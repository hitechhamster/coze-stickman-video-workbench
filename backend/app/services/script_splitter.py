import re

_SENTENCE_END = re.compile(r"(?<=[。！？.!?])\s*")


def split_script(script: str) -> list[str]:
    """按中文/英文句末标点切分脚本，过滤空白段落。"""
    lines = [line.strip() for line in script.splitlines()]
    segments: list[str] = []
    for line in lines:
        if not line:
            continue
        for piece in _SENTENCE_END.split(line):
            piece = piece.strip()
            if piece:
                segments.append(piece)
    return segments
