import base64
import mimetypes
import re
from pathlib import Path

from app.models import Style
from app.providers.llm import get_llm_provider

SYSTEM_PROMPT_DRAMA = """你是一名"情感可视化脚本工程师"，负责把单句场景旁白压缩成两段可以直接喂给生图模型(img_prompt)和轻动画模型(video_prompt)的提示词。

## 输出格式（严格按下面两行输出，不要用JSON、不要用代码块、不要输出任何多余的解释文字）
IMG_PROMPT: 场景主体+表情姿态+配角描述+环境元素+色彩构图+风格锚点（写成一段连贯文字）
VIDEO_PROMPT: 5秒场景：主体<动作>，配角<互动>，镜头<轻微运动>，转场描述（写成一段连贯文字）

## 首要目标：戏剧张力

每一张图都必须是一个**有张力的瞬间**，不是一张平静的说明图。想象你在给一部无声短片画分镜：观众不听旁白，光看这一格画面，就应该感受到情绪和冲突。

判断标准：如果这张图可以配任意一句旁白都不违和，说明它太空泛了，重写。

具体做法（每张图至少做到其中3条）：
- 抓**动作的最高点**，不要画"站着思考"，要画"整个人被压弯的那一刻""伸手却抓空的那一刻"
- 给主体一个**夸张的、能一眼读懂的表情和肢体语言**：瞪大眼、龇牙、瘫倒、踮脚、抱头、双臂张开
- 把抽象概念**实体化成具体物件**并让主体和它发生物理互动：概念不是飘在旁边的图标，是压在他背上的巨石、缠住他脚踝的藤蔓、他正在奋力推开的墙
- 用**尺寸对比**制造压迫感或渺小感：巨大的东西 vs 小小的他
- 用**倾斜、失衡、动势线**打破呆板：身体前倾、物体正在坠落、尘土飞扬、汗滴甩出
- 需要的话可以给**特写或极端视角**：只画他的手和那个物件、从上往下俯视他

## img_prompt 撰写规则（固定顺序）

1. 戏剧性场景与动作（约35%篇幅）：主体正在做什么、这一刻发生了什么冲突或转折。用有画面感的动词。
2. 表情与肢体（约15%）：表情要外放（震惊/绝望/狂喜/警觉/精疲力竭/如释重负），肢体要有张力（前倾/后仰/蜷缩/张开/失去平衡）
3. 配角或对抗物（约15%，没有就写"No supporting characters"，若整体用中文撰写则写"无配角"）：

配角/对抗物视觉体系：
- 互动对象/群体：2-4个简化人形剪影，与主体形成呼应或对峙
- 拟人化的抽象力量：把概念画成有形的对手——一堵墙、一只巨手、一道裂缝、缠绕的根须、压顶的乌云
- 思绪/念头：主体头顶的气泡或漂浮物，可以是正在破碎、正在膨胀、正在坠落的状态
- 陪伴/支持者：轮廓化的人形，位置和姿态要表明关系（托举/拉扯/背对）

数量控制：保持画面焦点唯一，配角服务于主体的动作，不要喧宾夺主。

4. 环境与道具（约20%）：环境要**参与叙事**，不是背景板。地面可以龟裂、可以塌陷；可以有风、有落叶、有飞溅的水花、有散落一地的物件。道具要能被主体抓握、推动、背负、躲避。

5. 构图（约15%）：**画面要填满，不要让主体缩成中间一小团**。主体连同他正在互动的物件应当撑满整个竖幅画面，从上边缘延伸到下边缘；环境元素（岩壁、根系、裂纹、飞尘）要一直铺到画面四个边角。主体本身占画面 50-70%。用对角线、低角度、俯视这类有情绪的机位，而不是永远正面平视居中。明确写出类似 "fills the entire vertical frame edge to edge"、"low angle looking up"、"towering over him from the top of the frame" 这样的构图指令。

6. 风格锚点（约15%，完全固定，不要改写）：
__STYLE_ANCHOR__

注：构图指令由程序自动追加在最后，你不用写。但你描述环境和道具时要**为它做好准备**——让岩壁、根系、裂纹、飞尘这些元素本来就是朝画面四边延伸的，而不是孤零零围着主体一小圈。

## video_prompt 撰写规则

"5秒场景：主体<一个具体的、有始有终的动作>，配角<互动动作>，镜头<轻微推进1-2%/轻微平移2%/静止不动/轻微拉远1.5%>，转场描述（如：平滑过渡/明快过渡）"

注意：video_prompt 里的镜头运动仍然保持克制（我们只用静态图做轻微推镜），戏剧张力体现在**画面内容**上，不是镜头运动上。

请严格按 "IMG_PROMPT: ..." 和 "VIDEO_PROMPT: ..." 两行输出。img_prompt 和 video_prompt 的场景描述部分：默认使用英文撰写；只有当输入的旁白原文本身是中文时，才改用中文撰写。风格锚点部分保持原文不译。

__TEXT_POLICY__

重要：上面几条规则(1-6)里出现的中文词汇（如"构图"、"环境与道具"、"表情与肢体"等）只是给你解释规则用的，不是要你原样抄进输出里。如果你决定用英文撰写这一句img_prompt，那么从头到尾都必须是英文，包括环境、道具、构图这几部分也要翻译成英文描述（例如"cracked earth splitting beneath his feet, dust flying"、"composition: low angle, subject leaning hard against the frame"），不能保留任何中文字词或中文标点。写完后自查一遍，确认没有遗漏的汉字。"""

SYSTEM_PROMPT_TEACHING = """你是一名"知识可视化脚本工程师"，负责把单句教学旁白压缩成两段可以直接喂给生图模型(img_prompt)和轻动画模型(video_prompt)的提示词。这是一个知识科普系列，主体是一位从容的讲解者。

## 输出格式（严格按下面两行输出，不要用JSON、不要用代码块、不要输出任何多余的解释文字）
IMG_PROMPT: 讲解场景+主体姿态表情+图解元素+环境道具+构图+风格锚点（写成一段连贯文字）
VIDEO_PROMPT: 5秒场景：主体<动作>，图解<变化>，镜头<轻微运动>，转场描述（写成一段连贯文字）

## 首要目标：把这一句"讲清楚"

每一张图都是一幅**讲得清楚的示意图**，像教科书插画、或老师在黑板前的一次演示。观众光看这一格画面，就应该学到这句旁白讲的那个知识点。

判断标准：如果这张图没有传达出这句话**特有的信息**（换句话说，配别的旁白也毫无违和），说明它太空泛了，重写。

具体做法（每张图至少做到其中3条）：
- 主体是**从容的讲解者**：他在指、在展示、在演示、在举起某个道具、在对比两样东西。表情从容、专注、了然——**但绝不痛苦、绝望、被压垮**。这是知识分享，不是苦难现场。
- **画面必须填满，严禁大片空白**：多用相关的图元把画面铺开——多个元素符号、连接的箭头、铺到底部的地面/桌面、周围相关的小物、背景的淡淡示意。哪怕是黑白线稿，也要有信息密度，绝不能是"一个小人飘在大片白底里"。
- 把这句话的核心概念画成**清楚的视觉图解**：符号、关系箭头、并排对比、前后对照、剖面示意图。
- **每一段的镜头类型都要换着来**（见下方「镜头类型」），别每张都是"先生站中间指一下"。用户会给你一个"本段建议镜头"，优先照它来，除非这句内容明显更适合别的。

## 镜头类型（每段挑一种，尽量和相邻段不同；主体大小/位置随之变化）
- **全景讲解**：先生在一个铺满画面、能说明这句的环境或大图解中讲解，人物中等大小，环境延伸到四边
- **道具特写**：只画先生的手和道具/图解，道具密集撑满画面（人物半入镜或只见手），几乎没有留白
- **大图解为主**：先生站在画面一侧，一个大的图解/符号/剖面占据画面主体，箭头和标注铺开
- **桌面俯视**：从上往下看一张桌面/地面，摆开一排代表概念的物件，先生的手从边缘指点或摆放
- **左右对比**：画面左右分成两半对照（强 vs 弱、之前 vs 之后、缺 vs 补），先生居中作分隔或在一侧点评

## img_prompt 撰写规则（固定顺序）

1. 讲解场景与动作（约35%篇幅）：主体正在**演示/指向/呈现/对比/展示**什么，这一格在教哪个知识点。用有画面感的讲解动词（presenting, pointing at, holding up, comparing, gesturing toward, demonstrating）。
2. 表情与姿态（约15%）：从容、专注、了然、讲到重点时的强调；肢体是**讲解性**的（伸手指示、双手展开呈现、举起道具），不是挣扎痛苦。
3. 图解元素（约15%，没有就写"No supporting characters"或"无配角"）：

图解/配角视觉体系：
- 信息图元：把概念画成清楚的示意——五行/元素符号、关系箭头、并排对比的两个物件、简单的图表、剖面图
- 具体化的概念物件：一棵树、一堆土、一座小房子剖面，摆在主体面前供他讲解
- 仅当需要表现人际或关系时，才用2-4个简化人形剪影

数量控制：画面焦点唯一，图解服务于"讲清这一句"，不要堆砌。

4. 环境与道具（约20%）：环境为**教学服务**——一块可画图的黑板或地面、摆放着代表概念的物件、一间可供讲解的房子剖面。道具清楚可辨、和讲解内容直接相关，不要无关的戏剧性破坏（龟裂、塌陷、飞尘这些留给别的系列）。

5. 构图（约15%）：**画面必须填满、严禁大片空白**——图解、符号、箭头、物件、地面/桌面一起铺到竖幅的四个边缘。机位以"看得清"为先（不用夸张俯仰），但主体的**大小和位置要随本段镜头类型变化**：特写时只见手和道具、道具占满画面；全景时人物中等、环境撑满；大图解时人物偏一侧、图解占主体。**不要每张都把先生摆在正中间**。

6. 风格锚点（约15%，完全固定，不要改写）：
__STYLE_ANCHOR__

注：构图指令由程序自动追加在最后，你不用写。但你描述图解和道具时要**为它做好准备**——让图解元素本来就是朝画面铺开、和主体一起填满画面的。

## video_prompt 撰写规则

"5秒场景：主体<一个具体的讲解动作>，图解<轻微出现/依次点亮/箭头流动>，镜头<轻微推进1-2%/轻微平移2%/静止不动>，转场描述（如：平滑过渡/明快过渡）"

注意：镜头运动保持克制，信息的清晰体现在**画面内容**上。

请严格按 "IMG_PROMPT: ..." 和 "VIDEO_PROMPT: ..." 两行输出。img_prompt 和 video_prompt 的场景描述部分：默认使用英文撰写；只有当输入的旁白原文本身是中文时，才改用中文撰写。风格锚点部分保持原文不译。

__TEXT_POLICY__

重要：上面几条规则里出现的中文词汇只是给你解释规则用的，不是要你原样抄进输出里。如果你决定用英文撰写img_prompt，那么从头到尾都必须是英文，包括图解、道具、构图这几部分也要翻译成英文描述，不能保留任何中文字词或中文标点。写完后自查一遍，确认没有遗漏的汉字。"""


# 不同文生图模型对"画面内文字"的能力差异很大，提示词策略要分开走
TEXT_POLICY_NO_TEXT = """## 画面内文字规则（重要）

场景描述里绝对不能包含任何具体的文字、标语、屏幕上的字句或数字内容——只描述"有一块屏幕/一份文件/一个牌子"这类物件轮廓，不描述上面写了什么。当前使用的生图模型画不出可读的文字，硬要求写字只会得到一堆乱码字形。"""

TEXT_POLICY_ALLOW_TEXT = """## 画面内文字规则（重要，这是知识科普视频，要靠画面上的文字帮观众学到东西）

当前使用的生图模型能准确渲染**简短**的英文，但整段长句会画糊、拼错。所以在"短、干净、拼写正确"的前提下，**尽量给这一句配一处清晰的教学文字**，让观众光看画面也能学到这句的知识点。

**每张图放一处文字板**（一块屏幕 / 卡片 / 标牌 / 底部字幕条），内容可以是：
- 一个关键术语（全大写），例如 `"SPREAD"`；
- 或"术语 + 极简释义"，控制在大约 6 个单词以内，例如 `"SPREAD = BUY/SELL GAP"`、`"LEVERAGE: SMALL DEPOSIT, BIG TRADE"`。

写法：用双引号明确写出要渲染的确切文字，全大写，指明它出现在画面里的哪块屏幕/卡片/标牌上。
例如：`a glowing screen behind him displays the text "PIP = SMALLEST PRICE MOVE" in bold capital letters`。

护栏（超出就会糊成乱码，务必遵守）：
- **整张图只放这一处文字板**，不要到处贴标签；
- 文字总长控制在**一个术语 + 一句极简释义（≤6 词）**以内，不要写整段句子、不要多行长文；
- 只用英文和数字，**不要中文**；
- 想不出合适的短语时就只放术语，或干脆不放文字、改用箭头/圈注符号。宁可少，也不要糊。"""


def _strip_think(content: str) -> str:
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def _extract_prompts(content: str) -> tuple[str, str]:
    img_match = re.search(r"IMG_PROMPT:\s*(.+?)(?:\n\s*VIDEO_PROMPT:|$)", content, re.DOTALL)
    video_match = re.search(r"VIDEO_PROMPT:\s*(.+)", content, re.DOTALL)
    if not img_match:
        raise ValueError(f"未找到 IMG_PROMPT: {content[:200]}")
    img_prompt = img_match.group(1).strip()
    video_prompt = video_match.group(1).strip() if video_match else ""
    return img_prompt, video_prompt


def to_data_uri(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def load_reference_data_uri(style: Style) -> str | None:
    """画风上挂的角色参考图，读成 data URI 喂给生图模型；没挂或文件丢了就返回 None。"""
    if not style.reference_image_url:
        return None
    path = Path(style.reference_image_url)
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return to_data_uri(path.read_bytes(), mime)


def build_character_prompt(style: Style) -> tuple[str, str]:
    """返回 (prompt, negative_prompt)，用于生成角色定妆图/画风预览图（不涉及具体场景，只描述角色本体）。

    文字/水印这些要不要禁止完全交给画风自己的negative_prompt决定，不在这里写死。
    """
    # 这张图会作为参考图传给后续每一段分镜，所以必须是干净的角色本体，
    # 不能出现任何标注文字/箭头/说明——否则那些元素会被后续每张图继承下来
    prompt = (
        f"{style.prompt_suffix}\n\n"
        "Show only the character alone, standing upright facing forward in a neutral pose, "
        "on a plain empty background. This is a clean character portrait, not an annotated "
        "reference sheet: no labels, no callout text, no annotation arrows, no captions, "
        "no measurement lines, no words anywhere in the image."
    )
    negative_prompt = style.negative_prompt or ""
    return prompt, negative_prompt


def _text_policy(style: Style) -> str:
    """能准确渲染文字的模型才允许在画面里要求出现文字。"""
    return TEXT_POLICY_ALLOW_TEXT if style.image_provider == "gemini" else TEXT_POLICY_NO_TEXT


# 让 LLM 自己写这句不可靠——它一旦把篇幅花在动作描写上就会把构图段落整个省掉，
# 而且风格锚点拼在末尾还会把它挤走。固定内容直接在代码里追加，省一次不确定性。
_COMPOSITION_SUFFIX_DRAMA = (
    " Composition: the scene is full-bleed and fills the entire vertical frame edge to edge — "
    "the environment, props, and dramatic elements extend past all four edges of the canvas. "
    "The subject and the thing he is struggling with dominate the frame; never leave him as a "
    "small isolated figure floating in the middle of empty space."
)
_COMPOSITION_SUFFIX_TEACHING = (
    " Composition: fill the entire vertical frame edge to edge with informative line-art content — "
    "the diagram, symbols, arrows, objects, and a ground or table surface spread out and reach all "
    "four edges, leaving no large blank white areas. Vary the teacher's scale and placement to match "
    "the shot (sometimes only his hands and the props in tight close-up filling the frame, sometimes "
    "a mid-size figure off to one side of a large diagram) — do not default to a small centered figure "
    "floating in empty white space. He is a calm presenter, never in distress or crushed."
)


# teaching模式下按分镜序号机械轮换镜头类型，保证相邻段不重样（光靠LLM会每张都画成"站着指"）
_TEACHING_SHOT_CYCLE = [
    "全景讲解（先生中等大小在铺满画面的环境/图解中讲解，环境延伸到四边）",
    "道具特写（只画先生的手和道具/图解，道具密集撑满画面，几乎没有留白）",
    "大图解为主（先生偏画面一侧，一个大图解/剖面占据主体，箭头标注铺开）",
    "左右对比（画面左右分两半对照，先生居中作分隔或在一侧点评）",
    "桌面俯视（从上往下看桌面/地面摆开一排概念物件，先生的手从边缘指点）",
]


def _system_prompt(style: Style) -> tuple[str, str]:
    """按画风的叙事模式选 (系统提示词模板, 构图后缀)。"""
    if style.scene_mode == "teaching":
        return SYSTEM_PROMPT_TEACHING, _COMPOSITION_SUFFIX_TEACHING
    return SYSTEM_PROMPT_DRAMA, _COMPOSITION_SUFFIX_DRAMA


async def build_scene_prompt(segment_text: str, style: Style, index: int = 0) -> tuple[str, str]:
    """返回 (img_prompt, video_prompt)。LLM调用失败或解析失败时抛出异常，调用方负责降级。

    index 是分镜序号：teaching模式据此轮换建议镜头类型，让整条视频的画面穿插多样。
    """
    template, composition_suffix = _system_prompt(style)
    system_prompt = template.replace(
        "__STYLE_ANCHOR__", style.prompt_suffix or "无特殊风格锚点"
    ).replace("__TEXT_POLICY__", _text_policy(style))
    user_prompt = f"content: {segment_text}"
    if style.scene_mode == "teaching":
        shot = _TEACHING_SHOT_CYCLE[index % len(_TEACHING_SHOT_CYCLE)]
        user_prompt = f"本段建议镜头：{shot}\n{user_prompt}"

    llm_provider = get_llm_provider(style.image_provider)
    raw = await llm_provider.chat(system_prompt, user_prompt)
    cleaned = _strip_think(raw)
    img_prompt, video_prompt = _extract_prompts(cleaned)
    return img_prompt + composition_suffix, video_prompt
