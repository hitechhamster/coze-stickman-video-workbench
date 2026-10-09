"""生成后的画面质检：Gemini 没有 negative prompt 参数，"必须黑白"这类约束只能靠正向文本，
服从度不稳定——同一句提示词，有时出彩色有时不出。实测一批9张里有3张背景整片变蓝。

对策不是继续抠提示词措辞（做过 A/B，同一提示词单独跑3次全对，证明不是措辞问题，
就是模型随机性），而是生成后量一下，超标就重生成。
"""

import io
import logging

from PIL import Image

from app.providers.base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)

# 平均饱和度（HSV 的 S 通道，0-255）。
# 实测标定：干净的黑白线稿落在 1.9-5.9，背景整片染色的落在 47-115，
# 而背景只是淡淡一层灰蓝的边界样本是 14.3——取 12 能把两类干净分开。
MAX_AVG_SATURATION = 12.0

# 彩色画风的下限：允许颜色但不强制时，Gemini 会随机把几张退成灰/棕墨色。
# 实测同一批里满色的落在 40-76，退色的落在 0.8-10.5——取 15 能把"明显掉色"的挑出来，
# 又给"柔和水彩"这种低饱和但确实有色的画面留了余地。
MIN_AVG_SATURATION = 15.0

# 重试次数。实测单张漏色概率约 1/3，重试2次后仍全部漏色的概率不到 4%。
MAX_RETRIES = 2


def average_saturation(image_bytes: bytes) -> float:
    """图片的平均饱和度，纯黑白线稿接近 0。"""
    with Image.open(io.BytesIO(image_bytes)) as im:
        # 缩到 160px 够用了，全尺寸算没必要
        hsv = im.convert("RGB").resize((160, 160)).convert("HSV")
        saturations = [s for _, s, _ in hsv.getdata()]
    return sum(saturations) / len(saturations)


def offcolor_fraction(image_bytes: bytes) -> float:
    """非朱红的彩色像素占比(0-1)。

    平均饱和度对"局部彩色"是瞎的:一小堆全彩宝石摊在大片留白上,均值照样 ≤12。
    (2026-08-21 偏财 v3 第14帧就这么漏过去的。)所以再量一个占比:
    饱和度高、又不在朱红色相带里的像素超过 2%,就算违反黑白约束。"""
    with Image.open(io.BytesIO(image_bytes)) as im:
        hsv = im.convert("RGB").resize((160, 160)).convert("HSV")
        n = 0
        for h, s, _v in hsv.getdata():
            if s >= 70 and not (h >= _KEEP_HUE_LO or h <= _KEEP_HUE_HI):
                n += 1
    return n / (160 * 160)


MAX_OFFCOLOR_FRACTION = 0.02


def is_monochrome(image_bytes: bytes) -> bool:
    return (average_saturation(image_bytes) <= MAX_AVG_SATURATION
            and offcolor_fraction(image_bytes) <= MAX_OFFCOLOR_FRACTION)


# 选择性去色的保留色相。小黑画风只允许极小面积的红/橙点缀，
# 这个区间（HSV 色相 0-360 换算到 PIL 的 0-255）覆盖红到橙。
_KEEP_HUE_LO, _KEEP_HUE_HI = 244, 12          # 环绕 0 点，只留朱红（橙/铜/金一律压灰）
_KEEP_MIN_SAT = 90                            # 太淡的不算点缀，一并压掉


def selective_desaturate(image_bytes: bytes) -> bytes:
    """把画面压成黑白，但保留饱和的红/橙点缀。

    重试用尽仍漏色时的兜底。整张 convert("L") 会把小黑标志性的红圈也吃掉，
    所以按色相挑：红橙且够饱和的像素留原色，其余取灰度。
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        rgb = im.convert("RGB")
        hsv = rgb.convert("HSV")
        gray = rgb.convert("L").convert("RGB")

        h, s, _ = hsv.split()
        # 红橙色相：色相在环绕 0 的区间内，且饱和度够高
        hue_ok = h.point(lambda v: 255 if (v >= _KEEP_HUE_LO or v <= _KEEP_HUE_HI) else 0)
        sat_ok = s.point(lambda v: 255 if v >= _KEEP_MIN_SAT else 0)
        from PIL import ImageChops

        keep = ImageChops.multiply(hue_ok, sat_ok).convert("L")

        out = Image.composite(rgb, gray, keep)
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()


def _violates(image_bytes: bytes, enforce_monochrome: bool, enforce_color: bool) -> str | None:
    """返回违规原因（给日志用），合格返回 None。"""
    saturation = average_saturation(image_bytes)
    if enforce_monochrome:
        if saturation > MAX_AVG_SATURATION:
            return f"违反黑白约束 (平均饱和度 {saturation:.1f} > {MAX_AVG_SATURATION})"
        frac = offcolor_fraction(image_bytes)
        if frac > MAX_OFFCOLOR_FRACTION:
            return f"违反黑白约束 (非朱红彩色像素 {frac*100:.1f}% > {MAX_OFFCOLOR_FRACTION*100:.0f}%)"
    if enforce_color and saturation < MIN_AVG_SATURATION:
        return f"上色不足、接近灰阶 (平均饱和度 {saturation:.1f} < {MIN_AVG_SATURATION})"
    return None


async def generate_guarded(
    provider: ImageProvider,
    prompt: str,
    negative_prompt: str = "",
    reference_image_url: str | None = None,
    enforce_monochrome: bool = False,
    enforce_color: bool = False,
) -> ImageResult:
    """按画风的约束生成图片，不合格就重试。

    两条互斥的约束都靠同一个平均饱和度指标判定：
    - enforce_monochrome：必须黑白，饱和度超上限就重生成；
    - enforce_color：必须有色，饱和度低于下限（画面掉成灰阶）就重生成。
    重试用尽后返回最后一次的结果（宁可出一张不达标的，也不要整个生成任务失败）。
    """
    result = await provider.generate(
        prompt, negative_prompt=negative_prompt, reference_image_url=reference_image_url
    )
    if not (enforce_monochrome or enforce_color):
        return result

    for attempt in range(MAX_RETRIES):
        reason = _violates(result.image_bytes, enforce_monochrome, enforce_color)
        if reason is None:
            return result
        logger.warning("画面%s，重新生成 (%d/%d)", reason, attempt + 1, MAX_RETRIES)
        result = await provider.generate(
            prompt, negative_prompt=negative_prompt, reference_image_url=reference_image_url
        )

    # 重试用尽仍漏色：黑白画风直接后处理压掉，别把彩图混进片子。
    # 起因是「偏财」那期——题材本身把颜色勾出来（钱→金币→金色），
    # 模型对这个联想极强，14 张里漏了 5 张，重试根本兜不住。
    if enforce_monochrome and _violates(result.image_bytes, True, False):
        logger.warning("重试用尽仍漏色，改为后处理选择性去色")
        return ImageResult(image_bytes=selective_desaturate(result.image_bytes), format="png")

    return result
