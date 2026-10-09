import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.coze_profile import NODES, SOURCE_SHA256, inputs

IMPLEMENTATIONS = {
    "180546": ("original_prompt", "coze_providers.complete", "原文案提示词、温度0.3和12288令牌；模型通过配置绑定。"),
    "138522": ("local_branch", "coze_pipeline.run_coze_generation", "手动文案与AI选题分支。"),
    "139542": ("local_merge", "coze_pipeline.run_coze_generation", "两条文案分支合并为正文。"),
    "139031": ("opaque_plugin_replacement", "coze_profile.split_text", "按标点清洗分段；插件源码未导出。"),
    "1773492": ("opaque_plugin_replacement", "coze_profile.split_text", "与自定义文案使用同一清洗分段实现。"),
    "136490": ("opaque_plugin_replacement", "coze_audio.normalize_audio / append_pause", "首尾静音裁剪、0.15秒段间停顿、采样数实测微秒时长。去呼吸不保证与封闭插件相同。"),
    "159936": ("local_validation", "coze_pipeline.voice_worker", "检查每段音频，不将null传入下游；错误定位到段号。"),
    "168591": ("local_batch", "coze_pipeline._bounded", "生图并发3；批量上限100；输入为合镜后的分镜。"),
    "155753": ("original_prompt", "coze_providers.generate_image", "保留角色附加词和负向词；1920x1080；Coze内部模型编号10需配置厂商模型。"),
    "152234": ("opaque_plugin_replacement", "coze_pipeline.image_worker", "失败时由文本模型优化提示词；原优化插件源码未导出。"),
    "192618": ("local_branch", "coze_pipeline.image_worker", "生图失败分支触发优化并重试。"),
    "129292": ("local_merge", "coze_pipeline.image_worker", "选取成功配图；两条原来源都是image类型。"),
    "1175150": ("original_prompt", "coze_providers.generate_image", "优化后使用同一生图配置重试。"),
    "121063": ("local_merge", "coze_profile.sentence_timeline", "完整保留正文顺序，将文案与实测音频逐条配对。"),
    "168059": ("original_prompt", "coze_providers.complete", "保留完整水彩火柴人提示词、温度0.8和12288令牌；并发10。"),
    "186545": ("redundant_draft_chain", "coze_draft.build_coze_draft", "原最终输出不引用第一套草稿；本地避免重复写两套。"),
    "1041638": ("original_asset", "backend/workflow-assets/bgm-original.mp3", "原音频已缓存，不依赖签名链接持续有效。"),
    "154178": ("original_asset", "backend/workflow-assets/click-original.mp3", "原点击音效已缓存。"),
    "137655": ("local_timeline", "coze_draft.tile_audio", "按素材时长循环铺满正文总时间线。"),
    "1909183": ("original_timeline", "coze_draft.tile_audio", "点击音效区间0至391833微秒，未扩展到所有切镜。"),
    "117064": ("original_algorithm", "coze_profile.group_shots", "按原系统提示词中N4/MIN3/MAX5算法本地合镜；不让模型改时间码。"),
    "122028": ("provider_binding", "coze_providers.synthesize / coze_audio.normalize_audio", "逐段配音、并发10、1.1倍速；Coze数字音色ID不能直接传厂商。"),
    "105280": ("local_draft", "coze_draft.build_coze_draft", "最终返回的第二套草稿链路；1920x1080。"),
    "100001": ("local_inputs", "workflow.create_workflow_project", "选题、可选文案、音色输入。"),
    "900001": ("local_output", "projects.get_project_draft", "返回本地草稿名称与草稿位置。"),
}

for node_id in ("145750", "171836", "199111"):
    IMPLEMENTATIONS[node_id] = ("original_audio", "coze_draft.tile_audio", "最终一套草稿的背景音乐轨道，音量0.3。")
for node_id in ("1466353", "1201245", "1741338"):
    IMPLEMENTATIONS[node_id] = ("original_audio", "coze_draft.tile_audio", "最终一套草稿的开头点击音效轨道，音量3。")
for node_id in ("125474", "1919687", "1616431"):
    IMPLEMENTATIONS[node_id] = ("original_image_timeline", "coze_draft.build_coze_draft", "按sceneTimeline放置配图；未加入原流程未指定的推拉。")
for node_id in ("138196", "1853227", "1290600"):
    IMPLEMENTATIONS[node_id] = ("original_caption_parameters", "coze_draft.build_coze_draft", "逐句字幕参数保留；Y=-800按千分坐标暂映射-0.8，需校准。")
for node_id in ("199084", "106243", "148803", "112125"):
    IMPLEMENTATIONS[node_id] = ("source_type_correction", "coze_draft.build_coze_draft", "原video_url_list实际为图片；使用图片素材轨道覆盖sceneTimeline，未伪造5秒视频。原video_prompt保存在清单。")
for node_id in ("183054", "1381849", "1488114"):
    IMPLEMENTATIONS[node_id] = ("original_audio_effect", "coze_draft.build_coze_draft", "正文逐段音频、人声增强3；名称开场人声实际引用全正文。")
for node_id in ("150490", "164226", "149033"):
    IMPLEMENTATIONS[node_id] = ("original_effect", "coze_draft.build_coze_draft", "全时间线震动特效，原文件未指定强度。")
for node_id in ("1278366", "1180131", "1099852"):
    IMPLEMENTATIONS[node_id] = ("original_effect", "coze_draft.build_coze_draft", "全时间线荧幕噪点，原文件未指定强度。")

assert set(IMPLEMENTATIONS) == set(NODES), f"Unmapped nodes: {set(NODES) - set(IMPLEMENTATIONS)}"
report = {"source_sha256": SOURCE_SHA256, "node_count": len(NODES), "nodes": []}
for node_id, node in NODES.items():
    status, implementation, note = IMPLEMENTATIONS[node_id]
    report["nodes"].append({"id": node_id, "title": node["title"], "type": node["type"],
                            "status": status, "implementation": implementation, "note": note,
                            "source_inputs": inputs(node_id)})
(ROOT / "工作流节点对照.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Mapped {len(NODES)} source nodes")
