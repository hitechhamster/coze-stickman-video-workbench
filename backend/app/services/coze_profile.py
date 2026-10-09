"""Source-derived settings: never substitute the second project's defaults."""
import hashlib
import json
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "workflows/coze_original.json"
WORKFLOW = json.loads(SOURCE.read_text(encoding="utf-8"))


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get("nodes", []))


NODES = {node["id"]: node for node in flatten(WORKFLOW["nodes"])}


def inputs(node_id):
    return {p["name"]: p.get("input", {}).get("value")
            for p in NODES[node_id]["parameters"].get("node_inputs", [])}


def llm_params(node_id):
    return {p["name"]: p.get("input", {}).get("value")
            for p in NODES[node_id]["parameters"]["llmParam"]}


IMAGE_PROMPT = NODES["155753"]["parameters"]["prompt"]
CAPTIONS = inputs("1290600")
WIDTH = inputs("105280")["width"]
HEIGHT = inputs("105280")["height"]
SPEED = inputs("122028")["speed_ratio"]
PAUSE = inputs("136490")["silence_duration"]
BGM_URL = inputs("1041638")["String1"]
CLICK_URL = inputs("154178")["String1"]
CLICK_END = json.loads(inputs("1909183")["all_timeline"])[0]["end"]
VOICE_ID = NODES["100001"]["parameters"]["node_outputs"]["yinse"]["default_value"]
SOURCE_SHA256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def profile():
    return {
        "name": WORKFLOW["description"], "source_name": WORKFLOW["name"],
        "source_sha256": SOURCE_SHA256,
        "node_count": len(NODES), "canvas": {"width": WIDTH, "height": HEIGHT},
        "voice_id": VOICE_ID, "speed": SPEED, "pause_seconds": PAUSE,
        "caption": {k: v for k, v in CAPTIONS.items() if not isinstance(v, dict)},
        "effects": ["震动", "荧幕噪点"],
        "bgm_volume": inputs("145750")["volume"],
        "click_volume": inputs("1466353")["volume"],
        "click_duration_us": CLICK_END,
        "transition": None, "zoom": None,
        "shot_rule": {"opening": 4, "minimum": 3, "maximum": 5},
        "image_model_internal_id": NODES["155753"]["parameters"]["modelSetting"]["model"],
        "notes": [
            "原文件的“正文视频”输出仍是图片，未调用视频模型。",
            "原文件没有指定转场或推拉关键帧，默认直接切镜。",
            "两套创建草稿链路重复处理同一批素材，导出返回第二套；本地只组装最终一套。",
            "文案切分、剪去呼吸/静音及提示词优化插件未包含源码，使用本地替代实现。",
            "Coze 内部模型编号及音色 ID 无法直接用于厂商 API，需配置模型与对应音色。",
            "字幕 Y=-800 按千分坐标换算为 -0.8；原插件坐标定义未导出，需在剪映校准。",
        ],
    }


def split_text(text: str) -> list[str]:
    """Local replacement for the opaque text_splitter plugin, punctuation cleaned."""
    text = re.sub(r"[\u200b\ufeff]", "", text)
    return [part.strip(" \t\r\n“”\"‘’") for part in re.split(r"[，,。！？!?；;\n]+", text)
            if part.strip(" \t\r\n“”\"‘’")]


def sentence_timeline(texts, durations_us):
    if len(texts) != len(durations_us):
        raise ValueError("配音条数与文案不一致，禁止跳过失败段落")
    cursor = 0
    result = []
    for text, duration in zip(texts, durations_us):
        if not isinstance(duration, int) or duration <= 0:
            raise ValueError("配音时长为空或无效")
        result.append({"content": text, "start": cursor, "end": cursor + duration})
        cursor += duration
    return result


def group_shots(timeline):
    """Implement the exact N=4/MIN=3/MAX=5 algorithm in node 117064."""
    groups = [[row] for row in timeline[:4]]
    remaining = timeline[4:]
    while remaining:
        count = len(remaining)
        if count <= 5:
            size = count
        elif count < 8:
            size = (count + 1) // 2  # 6 -> 3+3; 7 -> 4+3
        else:
            size = 5
        groups.append(remaining[:size])
        remaining = remaining[size:]
    return [{"shot_id": f"shot_{i + 1:02d}",
             "merged_content": "。".join(row["content"] for row in group),
             "start": group[0]["start"], "end": group[-1]["end"]}
            for i, group in enumerate(groups)]


def decode_json(text):
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    value = json.loads(cleaned)
    return value
