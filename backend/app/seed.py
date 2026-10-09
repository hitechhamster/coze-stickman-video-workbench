from app.db import SessionLocal
from app.models import Style

# 仓库只自带这一个示例画风，装完就能直接出片，也当作自建画风的参照。
# 其余画风由用户在工作台里自己建。
#
# 参考 github.com/helloianneo/ian-xiaohei-illustrations 的「小黑」IP 画风改写，
# 原版是 16:9 纯白正文配图，这里改成竖版构图适配竖屏视频。
# 用 gemini（Nano Banana）出图，因为这个画风依赖画面里出现拼写正确的英文短标签，
# 换成画不出可读文字的模型只会得到乱码字形。
BUILTIN_STYLES: list[dict] = [
    {
        "name": "小黑怪诞手绘风",
        "image_provider": "gemini",
        # 这个画风必须黑白（只留极小面积的红/橙/蓝点缀），生图模型对此服从度不稳，
        # 靠生成后检测平均饱和度、超标重生成来兜底
        "enforce_monochrome": True,
        "prompt_suffix": "A small solid black creature character with two round white dot eyes, thin black legs and occasionally thin arms, blank calm serious expression, irregular hand-drawn silhouette, body shaped like a blob, bean, cylinder, box, or shadow. Solid flat black fill with a clean black hand-drawn outline, slightly wobbly sketchy line quality, not mechanical, not vector-clean, no internal shading or texture blotches. The entire image is strictly black, white, and gray only — the background, environment, and all objects stay black-and-white line art on a plain white background, with zero colored backgrounds, zero colored lighting, zero colored scenery. The only color allowed is small red, orange, or blue accent marks: simple arrows, dashes, circles, or underlines. Generous negative space, character occupying only 40-60% of the vertical frame. Loose hand-drawn marker-sketch aesthetic, weird but grounded visual metaphor. This black creature character is always the one and only main character and must physically appear performing the action in every single image, acting out an abstract or literal idea from the scene through an odd invented prop or pose — never replace it with a realistic human, baby, animal, or any photographic subject, no matter how emotional or literal the scene description is. The illustration fills the entire canvas edge to edge with no border, no frame, no picture frame, no browser window chrome, no screen or monitor bezel, no photo of paper on a table or desk, no vignette, no drop shadow around the edges — it is a flat full-bleed digital illustration directly on the white background, not a photograph or scan of a physical object.",
        "negative_prompt": "cute mascot, children's cartoon, sparkly eyes, complex clothing, commercial illustration, PPT infographic, gradient, texture, glossy, garbled text, illegible scribbles, watermark, realistic human, real person, human baby, real skin, photorealistic face, photograph, portrait, live-action, real body parts, human hands, human eyes, colored background, colored scenery, colored lighting, colorful environment, blue background, warm lighting, sepia, golden light, black border, picture frame, photo frame, framed photo, border around image, vignette edges, browser window, browser chrome, address bar, window UI, screen bezel, monitor frame, paper on table, desk surface, photo of paper, polaroid, picture-in-picture, canvas edge shadow",
    },
]


def seed_builtin_styles() -> None:
    db = SessionLocal()
    try:
        existing = {s.name for s in db.query(Style).filter(Style.is_builtin.is_(True)).all()}
        for style in BUILTIN_STYLES:
            if style["name"] in existing:
                continue
            db.add(Style(**style, is_builtin=True))
        db.commit()
    finally:
        db.close()


BUILTIN_EFFECT_PRESETS: list[dict] = []
BUILTIN_TEMPLATES: list[dict] = []


def seed_builtin_effect_presets() -> None:
    pass


def seed_builtin_templates() -> None:
    pass
