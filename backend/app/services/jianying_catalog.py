"""从 pyJianYingDraft 的枚举里挑一批贴合火柴人视频调性的字体/特效/转场，供前端选择器使用。

剪映本身有798个字体、1097个特效、453个转场，全丢给用户选没有意义，这里手工挑一批。
"""

import pyJianYingDraft as pyd

CURATED_FONTS = [
    "新青年体",
    "高字标志圆",
    "优设标题圆",
    "兰亭圆",
    "剪映圆隶",
    "圆体",
    "简中圆",
    "点字艺圆",
    "字语圆体",
]

# (特效名, 中文说明)
_CURATED_EFFECT_NAMES = [
    ("震动", "画面轻微震动，增加临场感"),
    ("荧幕噪点", "复古屏幕颗粒感"),
    ("暗角", "四角压暗，聚焦画面中心"),
    ("电影感", "电影感调色氛围"),
    ("老电影", "怀旧老电影质感"),
    ("胶片抖动", "胶片放映的轻微抖动感"),
    ("轻微抖动", "更细腻的轻微抖动"),
    ("闪白", "画面闪白强调"),
]

CURATED_TRANSITIONS = [
    ("漫画撕纸", "漫画风格撕纸翻页"),
    ("叠化", "经典淡入淡出"),
    ("闪黑", "黑场过渡，节奏感强"),
    ("模糊", "模糊过渡"),
    ("滑动", "画面滑动切换"),
    ("推近", "镜头推近过渡"),
    ("百叶窗", "百叶窗式切换"),
    ("快速缩放", "快速缩放过渡"),
    ("圆形遮罩", "圆形扩散过渡"),
]


def intensity_param_index(effect_name: str) -> int | None:
    """给 jianying_draft.py 用：这个特效的 params 列表里，第几个是强度参数（没有就返回None）。"""
    effect = getattr(pyd.VideoSceneEffectType, effect_name)
    param_names = [p.name for p in effect.value.params]
    return param_names.index("effects_adjust_intensity") if "effects_adjust_intensity" in param_names else None


def _effect_catalog() -> list[dict]:
    catalog = []
    for name, label in _CURATED_EFFECT_NAMES:
        effect = getattr(pyd.VideoSceneEffectType, name)
        param_names = [p.name for p in effect.value.params]
        intensity_index = (
            param_names.index("effects_adjust_intensity")
            if "effects_adjust_intensity" in param_names
            else None
        )
        catalog.append(
            {
                "name": name,
                "label": label,
                "has_intensity": intensity_index is not None,
                "default_intensity": 50 if intensity_index is not None else None,
            }
        )
    return catalog


def _transition_catalog() -> list[dict]:
    return [{"name": name, "label": label} for name, label in CURATED_TRANSITIONS]


def get_catalog() -> dict:
    return {
        "fonts": CURATED_FONTS,
        "effects": _effect_catalog(),
        "transitions": _transition_catalog(),
    }
