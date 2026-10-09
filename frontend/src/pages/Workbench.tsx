import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Catalog, type Music, type Style as StyleItem, type Voice } from "../api/client";
import xiaoheiImg from "../assets/xiaohei.png";

/** 内置主角：角色 + 配套画风打包。选中即锁定角色，底层复用 seed 进来的同名画风。 */
const PRESET_CHARACTERS = [
  {
    key: "xiaohei",
    name: "小黑",
    styleName: "小黑怪诞手绘风",
    img: xiaoheiImg,
    blurb: "全身漆黑的小怪物，圆白点眼，怪诞黑白手绘风",
  },
];

const STYLE_CHIPS = ["粉笔风", "马克笔涂鸦", "简笔画", "水墨", "报纸漫画", "蜡笔"];
const COLOR_SWATCHES = ["#ffffff", "#f5f0d0", "#ff6b6b", "#a0d8ef", "#b8e986"];
const BORDER_SWATCHES = ["#000000", "#333333", "#1a1a2e"];

export default function Workbench() {
  const navigate = useNavigate();
  const [panel, setPanel] = useState("char");

  /* ── Character ── */
  const [charName, setCharName] = useState("");
  const [charDesc, setCharDesc] = useState("");
  const [charFile, setCharFile] = useState<File | null>(null);
  const [charPreview, setCharPreview] = useState("");
  /** 当前选中的内置主角 key（小黑等），选中时角色和画风一起锁定 */
  const [presetChar, setPresetChar] = useState<string | null>(null);
  const charRef = useRef<HTMLInputElement>(null);

  /* ── Style ── */
  const [styles, setStyles] = useState<StyleItem[]>([]);
  /** 选中的已有画风。没改过就直接复用它，改过则以它为底新建一个。 */
  const [baseStyleId, setBaseStyleId] = useState<string | null>(null);
  const [styleDirty, setStyleDirty] = useState(false);
  const [colorMode, setColorMode] = useState<"free" | "bw" | "color">("free");
  const [sceneMode, setSceneMode] = useState<"drama" | "teaching">("drama");
  const [styleChip, setStyleChip] = useState("");
  const [stylePrompt, setStylePrompt] = useState("");
  const [negPrompt, setNegPrompt] = useState("");
  const [provider, setProvider] = useState<"gemini" | "openrouter">("gemini");

  /* ── Voice ── */
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");

  /* ── Effects ── */
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [captionFont, setCaptionFont] = useState("高字标志圆");
  const [captionSize, setCaptionSize] = useState(11);
  const [captionColor, setCaptionColor] = useState("#ffffff");
  const [captionBorder, setCaptionBorder] = useState("#000000");
  const [captionPos, setCaptionPos] = useState(80);
  const [activeEffects, setActiveEffects] = useState<Set<string>>(new Set());
  const [transName, setTransName] = useState<string | null>(null);
  const [zoomPct, setZoomPct] = useState(6);

  /* ── Music ── */
  const [musicList, setMusicList] = useState<Music[]>([]);
  const [musicId, setMusicId] = useState("");

  /* ── Script ── */
  const [scriptMode, setScriptMode] = useState<"auto" | "manual">("manual");
  const [rawScript, setRawScript] = useState("");

  /* ── Project ── */
  const [projectName, setProjectName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ── Fetch once ── */
  useEffect(() => {
    api.listMusic().then(setMusicList).catch(() => {});
    api.getCatalog().then(setCatalog).catch(() => {});
    api.listStyles().then(setStyles).catch(() => {});
  }, []);

  useEffect(() => {
    api
      .listVoices(provider)
      .then((list) => {
        setVoices(list);
        if (list.length > 0) setVoiceId((v) => (list.find((x) => x.voice_id === v) ? v : list[0].voice_id));
      })
      .catch(() => setVoices([]));
  }, [provider]);

  /* ── Handlers ── */
  const onCharFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setPresetChar(null); // 上传自己的角色 = 放弃内置主角
    setCharFile(f);
    const r = new FileReader();
    r.onload = () => {
      setCharPreview(r.result as string);
      if (!charName) setCharName(f.name.replace(/\.[^.]+$/, ""));
    };
    r.readAsDataURL(f);
  };

  const clearChar = () => {
    if (presetChar) {
      // 移除内置主角时把它带进来的画风也一并解绑
      setBaseStyleId(null);
      setStyleDirty(false);
    }
    setPresetChar(null);
    setCharFile(null);
    setCharPreview("");
    setCharName("");
    if (charRef.current) charRef.current.value = "";
  };

  const toggleEffect = (name: string) =>
    setActiveEffects((prev) => {
      const s = new Set(prev);
      s.has(name) ? s.delete(name) : s.add(name);
      return s;
    });

  /** 任何画风字段被改动 → 提交时就不能再直接复用选中的已有画风 */
  const markDirty = () => setStyleDirty(true);

  const pickStyleChip = (c: string) => {
    setStyleChip(c === styleChip ? "" : c);
    setStylePrompt(c === styleChip ? "" : c);
    markDirty();
  };

  /** 把一个已有画风的参数灌进表单并选中它 */
  const applyStyle = (s: StyleItem) => {
    setBaseStyleId(s.id);
    setStylePrompt(s.prompt_suffix);
    setNegPrompt(s.negative_prompt);
    setProvider(s.image_provider);
    setColorMode(s.enforce_monochrome ? "bw" : s.enforce_color ? "color" : "free");
    setSceneMode(s.scene_mode);
    setStyleChip("");
    setStyleDirty(false);
  };

  /** 选中一个已有画风，再点一次取消选中 */
  const pickExistingStyle = (s: StyleItem) => {
    if (baseStyleId === s.id) {
      setBaseStyleId(null);
      setStyleDirty(false);
      return;
    }
    setPresetChar(null);
    applyStyle(s);
  };

  /** 选中内置主角（小黑）：角色 + 配套画风一起锁定；再点一次取消 */
  const pickPresetChar = (p: (typeof PRESET_CHARACTERS)[number]) => {
    if (presetChar === p.key) {
      clearChar();
      return;
    }
    const style = styles.find((s) => s.name === p.styleName);
    if (!style) return;
    setPresetChar(p.key);
    setCharName(p.name);
    setCharPreview(p.img);
    setCharFile(null);
    if (charRef.current) charRef.current.value = "";
    applyStyle(style);
  };

  const reusingStyle = !!baseStyleId && !styleDirty && !charFile;
  /** 内置主角的配套画风不再出现在「画风」列表里，避免把角色当画风选 */
  const pickableStyles = styles.filter((s) => !PRESET_CHARACTERS.some((p) => p.styleName === s.name));
  const availablePresets = PRESET_CHARACTERS.filter((p) => styles.some((s) => s.name === p.styleName));
  const baseStyleName = styles.find((s) => s.id === baseStyleId)?.name;

  /* ── Script stats ── */
  const scriptChars = rawScript.replace(/\s/g, "").length;
  const scriptSentences = (rawScript.match(/[。！？.!?；]/g) || []).length || (rawScript.trim() ? 1 : 0);

  /* ── Submit ── */
  const submit = async () => {
    if (!rawScript.trim()) {
      setError("请先输入脚本内容");
      return;
    }
    if (!voiceId) {
      setError("请选择配音");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // 选了已有画风且一个字没改 → 直接复用，不往库里堆重复画风
      let styleId = baseStyleId;
      if (!reusingStyle) {
        const style = await api.createStyle({
          name: charName || projectName || `风格_${Date.now()}`,
          prompt_suffix: [charDesc, stylePrompt].filter(Boolean).join("\n"),
          negative_prompt: negPrompt,
          image_provider: provider,
          enforce_monochrome: colorMode === "bw",
          enforce_color: colorMode === "color",
          scene_mode: sceneMode,
        });
        if (charFile) await api.uploadStyleReference(style.id, charFile);
        styleId = style.id;
      }

      const preset = await api.createEffectPreset({
        name: `预设_${Date.now()}`,
        caption_font: captionFont,
        caption_size: captionSize,
        caption_color: captionColor,
        caption_border_color: captionBorder,
        caption_position: 1 - captionPos / 50,
        effects: [...activeEffects].map((n) => ({
          name: n,
          intensity: catalog?.effects.find((e) => e.name === n)?.default_intensity ?? null,
        })),
        transition_name: transName,
        zoom_end_scale: 1 + zoomPct / 100,
      });

      const project = await api.createProject({
        name: projectName || charName || `项目_${Date.now()}`,
        script: rawScript,
        style_id: styleId!,
        voice_id: voiceId,
        music_id: musicId || null,
        effect_preset_id: preset.id,
      });

      const { job_id } = await api.generateProject(project.id);
      navigate(`/projects/${project.id}?job=${job_id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  };

  /* ── Nav ── */
  const NAV = [
    { key: "char", label: "主角", num: "1", ok: !!charPreview || !!charDesc.trim() },
    { key: "style", label: "画风", num: "2", ok: !!stylePrompt.trim() || !!baseStyleId },
    { key: "voice", label: "配音", num: "3", ok: !!voiceId },
    { key: "fx", label: "字幕与特效", num: "4", ok: true },
    { key: "music", label: "背景音乐", num: "5", ok: !!musicId },
    { key: "script", label: "脚本", num: "6", ok: !!rawScript.trim() },
  ];

  /* ── Preview effect CSS ── */
  const fxClass = [
    colorMode === "bw" && "mode-bw",
    activeEffects.has("老电影") && "old",
    activeEffects.has("震动") && "shake",
  ]
    .filter(Boolean)
    .join(" ");

  const subStyle: React.CSSProperties = {
    top: `${captionPos}%`,
    transform: "translateX(-50%) translateY(-50%)",
    left: "50%",
    fontSize: `${Math.round(captionSize * 1.8)}px`,
    color: captionColor,
    WebkitTextStroke: captionBorder === "transparent" ? "0" : `1px ${captionBorder}`,
    textShadow: captionBorder === "transparent" ? "none" : `0 2px 0 ${captionBorder}, 0 0 8px rgba(0,0,0,.5)`,
  };

  /* ── Subtitle drag ── */
  const frameRef = useRef<HTMLDivElement>(null);
  const onSubDown = (e: React.PointerEvent) => {
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const rect = frameRef.current?.getBoundingClientRect();
    if (!rect) return;
    const move = (ev: PointerEvent) => {
      const p = Math.min(95, Math.max(5, Math.round(((ev.clientY - rect.top) / rect.height) * 100)));
      setCaptionPos(p);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  };

  return (
    <div className="wb">
      {/* ═══ Top bar ═══ */}
      <header className="wb-top">
        <div className="wb-brand">
          <span className="wb-mark" />
          <span className="wb-brand-name">AI 动画工作台</span>
          <span className="wb-proj">
            /{" "}
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="未命名短片" />
          </span>
        </div>
        {error && <span className="wb-err">{error}</span>}
        <span className="wb-cost">
          约 {scriptSentences} 帧 · {Math.round(scriptSentences * 4)}s
        </span>
        <button className="wb-gen" onClick={submit} disabled={submitting}>
          {submitting ? "生成中…" : "▶ 生成短片"}
        </button>
      </header>

      <div className="wb-body">
        {/* ═══ Left nav ═══ */}
        <nav className="wb-nav">
          {NAV.map((n) => (
            <button key={n.key} className={panel === n.key ? "on" : ""} onClick={() => setPanel(n.key)}>
              <b>{n.num}</b>
              {n.label}
              <span className={`wb-dot ${n.ok ? "ok" : ""}`} />
            </button>
          ))}
          <div className="wb-nav-tip">绿点 = 已配置。脚本是唯一必填项。</div>
        </nav>

        {/* ═══ Center panel ═══ */}
        <main className="wb-panel">
          {/* ── 1. 主角 ── */}
          {panel === "char" && (
            <section>
              <h2>主角</h2>
              <p className="wb-sub">选一个内置主角，或上传一张角色参考图，每一帧都会锚定这个角色。</p>

              {availablePresets.length > 0 && (
                <>
                  <h3 style={{ marginTop: 0 }}>
                    内置主角 <small>点选即用，角色和配套画风一起锁定</small>
                  </h3>
                  <div className="wb-row" style={{ marginBottom: 16 }}>
                    {availablePresets.map((p) => (
                      <button
                        key={p.key}
                        className={`wb-card wb-preset-char ${presetChar === p.key ? "on" : ""}`}
                        onClick={() => pickPresetChar(p)}
                      >
                        <img src={p.img} alt={p.name} />
                        <span>
                          <span className="wb-t">{p.name}</span>
                          <span className="wb-d">{p.blurb}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              )}

              {charPreview ? (
                <div className="wb-hero">
                  <div className="wb-hero-art">
                    <img src={charPreview} alt="" />
                  </div>
                  <div>
                    <input
                      className="wb-hero-name"
                      value={charName}
                      onChange={(e) => setCharName(e.target.value)}
                      placeholder="角色名称"
                    />
                    <p className="wb-d">
                      {presetChar
                        ? "内置主角，配套画风已自动应用到「画风」面板。"
                        : "上传的参考图将作为每一帧的角色锚点。"}
                    </p>
                    <div className="wb-row" style={{ marginTop: 10 }}>
                      <button className="wb-chip" onClick={clearChar}>
                        × 移除
                      </button>
                      <span className="wb-cost">{presetChar ? "内置主角" : charFile?.name}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <label className="wb-upload" htmlFor="charFile">
                  ⇪ <b>上传一张角色参考图</b>
                  <span>PNG / JPG，正面半身最稳定</span>
                </label>
              )}
              <input ref={charRef} type="file" id="charFile" accept="image/*" style={{ display: "none" }} onChange={onCharFile} />

              <h3>
                外貌描述 <small>prompt_suffix，随每一帧一起发送</small>
              </h3>
              <textarea
                rows={3}
                value={charDesc}
                onChange={(e) => {
                  setCharDesc(e.target.value);
                  markDirty();
                }}
                placeholder="描述主角的外形特征，例如：一只全身漆黑的小怪物，圆脑袋、巨大白眼…"
              />
            </section>
          )}

          {/* ── 2. 画风 ── */}
          {panel === "style" && (
            <section>
              <h2>画风</h2>
              <p className="wb-sub">色彩与场景模式决定整体气质，文字描述负责细节。</p>

              {pickableStyles.length > 0 && (
                <>
                  <h3>
                    已有画风 <small>选一个直接用，参数会自动填好</small>
                  </h3>
                  <div className="wb-row" style={{ marginBottom: 8 }}>
                    {pickableStyles.map((s) => (
                      <button
                        key={s.id}
                        className={`wb-chip ${baseStyleId === s.id ? "on" : ""}`}
                        onClick={() => pickExistingStyle(s)}
                      >
                        {s.name}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {baseStyleId && (
                <p className="wb-d" style={{ marginBottom: 4 }}>
                  {reusingStyle
                    ? `将直接复用「${baseStyleName}」，不会新建。`
                    : `已改动，提交时会以「${baseStyleName}」为底新建一个画风。`}
                </p>
              )}

              <h3>色彩</h3>
              <div className="wb-seg">
                {(["free", "color", "bw"] as const).map((v) => (
                  <button
                    key={v}
                    className={colorMode === v ? "on" : ""}
                    onClick={() => {
                      setColorMode(v);
                      markDirty();
                    }}
                  >
                    {{ free: "自由", color: "强制彩色", bw: "强制黑白" }[v]}
                  </button>
                ))}
              </div>

              <h3>场景模式</h3>
              <div className="wb-grid g2">
                <button
                  className={`wb-card ${sceneMode === "drama" ? "on" : ""}`}
                  onClick={() => {
                    setSceneMode("drama");
                    markDirty();
                  }}
                >
                  <div className="wb-thumb" style={{ background: "linear-gradient(135deg,#4a2c2c,#2b3234)" }}>
                    😤💥
                  </div>
                  <div className="wb-t">
                    Drama <span>戏剧</span>
                  </div>
                  <div className="wb-d">冲突、夸张表情、快速切换镜头</div>
                </button>
                <button
                  className={`wb-card ${sceneMode === "teaching" ? "on" : ""}`}
                  onClick={() => {
                    setSceneMode("teaching");
                    markDirty();
                  }}
                >
                  <div className="wb-thumb" style={{ background: "linear-gradient(135deg,#2c3a4a,#2b3234)" }}>
                    📊🎓
                  </div>
                  <div className="wb-t">
                    Teaching <span>讲解</span>
                  </div>
                  <div className="wb-d">沉稳叙述、图解轮换、节奏均匀</div>
                </button>
              </div>

              <h3>画风描述</h3>
              <div className="wb-row" style={{ marginBottom: 8 }}>
                {STYLE_CHIPS.map((c) => (
                  <button key={c} className={`wb-chip ${styleChip === c ? "on" : ""}`} onClick={() => pickStyleChip(c)}>
                    {c}
                  </button>
                ))}
              </div>
              <textarea
                rows={2}
                value={stylePrompt}
                onChange={(e) => {
                  setStylePrompt(e.target.value);
                  markDirty();
                }}
                placeholder="画风描述，例如：粉笔风，深色黑板底，线条粗糙带颗粒"
              />

              <h3>
                负面提示 <small>不想出现的元素</small>
              </h3>
              <input
                type="text"
                value={negPrompt}
                onChange={(e) => {
                  setNegPrompt(e.target.value);
                  markDirty();
                }}
                placeholder="文字、水印、多余的手指、写实照片质感…"
              />

              <h3>出图引擎</h3>
              <div className="wb-seg">
                {(["gemini", "openrouter"] as const).map((v) => (
                  <button
                    key={v}
                    className={provider === v ? "on" : ""}
                    onClick={() => {
                      setProvider(v);
                      markDirty();
                    }}
                  >
                    {{ gemini: "Gemini", openrouter: "OpenRouter" }[v]}
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* ── 3. 配音 ── */}
          {panel === "voice" && (
            <section>
              <h2>配音</h2>
              <p className="wb-sub">选择一个音色。引擎跟着画风走。</p>
              <div className="wb-row" style={{ marginBottom: 14 }}>
                <span className="wb-cost">{provider === "gemini" ? "Gemini TTS" : "MiniMax TTS"}</span>
              </div>
              {voices.length === 0 ? (
                <p className="wb-d">加载音色中…</p>
              ) : (
                <div className="wb-grid g2 wb-voice-grid">
                  {voices.map((v) => (
                    <button
                      key={v.voice_id}
                      className={`wb-voice ${voiceId === v.voice_id ? "on" : ""}`}
                      onClick={() => setVoiceId(v.voice_id)}
                    >
                      <span className="wb-voice-play">▶</span>
                      <span className="wb-voice-n">{v.voice_name}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ── 4. 字幕与特效 ── */}
          {panel === "fx" && (
            <section>
              <h2>字幕与特效</h2>
              <p className="wb-sub">右侧预览实时反映改动，字幕可拖拽调整位置。</p>

              <h3>字幕</h3>
              <div className="wb-grid g2">
                <div>
                  <label className="wb-f">字体</label>
                  <select value={captionFont} onChange={(e) => setCaptionFont(e.target.value)}>
                    {(catalog?.fonts ?? ["高字标志圆"]).map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="wb-f">字号</label>
                  <div className="wb-slider">
                    <input
                      type="range"
                      min={5}
                      max={20}
                      value={captionSize}
                      onChange={(e) => setCaptionSize(+e.target.value)}
                    />
                    <output>{captionSize}</output>
                  </div>
                </div>
              </div>

              <div className="wb-grid g2" style={{ marginTop: 12 }}>
                <div>
                  <label className="wb-f">文字颜色</label>
                  <div className="wb-swatches">
                    {COLOR_SWATCHES.map((c) => (
                      <button
                        key={c}
                        className={captionColor === c ? "on" : ""}
                        style={{ background: c }}
                        onClick={() => setCaptionColor(c)}
                      />
                    ))}
                    <input type="color" value={captionColor} onChange={(e) => setCaptionColor(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="wb-f">描边颜色</label>
                  <div className="wb-swatches">
                    {BORDER_SWATCHES.map((c) => (
                      <button
                        key={c}
                        className={captionBorder === c ? "on" : ""}
                        style={{ background: c }}
                        onClick={() => setCaptionBorder(c)}
                      />
                    ))}
                    <button
                      className={captionBorder === "transparent" ? "on" : ""}
                      style={{ background: "transparent", border: "1px dashed var(--line-2)" }}
                      onClick={() => setCaptionBorder("transparent")}
                    />
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 12 }}>
                <label className="wb-f">垂直位置</label>
                <div className="wb-slider">
                  <input type="range" min={5} max={95} value={captionPos} onChange={(e) => setCaptionPos(+e.target.value)} />
                  <output>{captionPos}%</output>
                </div>
              </div>

              <h3>
                画面特效 <small>可叠加</small>
              </h3>
              <div className="wb-grid g3">
                {(catalog?.effects ?? []).map((fx) => (
                  <button
                    key={fx.name}
                    className={`wb-toggle ${activeEffects.has(fx.name) ? "on" : ""}`}
                    onClick={() => toggleEffect(fx.name)}
                  >
                    {fx.label || fx.name}
                    <span className="wb-sw" />
                  </button>
                ))}
              </div>

              <h3>转场</h3>
              <div className="wb-row">
                <button className={`wb-chip ${transName === null ? "on" : ""}`} onClick={() => setTransName(null)}>
                  无
                </button>
                {(catalog?.transitions ?? []).map((t) => (
                  <button
                    key={t.name}
                    className={`wb-chip ${transName === t.name ? "on" : ""}`}
                    onClick={() => setTransName(t.name)}
                  >
                    {t.label || t.name}
                  </button>
                ))}
              </div>

              <h3>
                推镜 <small>Ken Burns</small>
              </h3>
              <div className="wb-slider">
                <input type="range" min={0} max={25} value={zoomPct} onChange={(e) => setZoomPct(+e.target.value)} />
                <output>{zoomPct}%</output>
              </div>
            </section>
          )}

          {/* ── 5. 背景音乐 ── */}
          {panel === "music" && (
            <section>
              <h2>背景音乐</h2>
              <p className="wb-sub">选一首或上传 mp3，会自动循环铺满短片并在末尾淡出。可留空。</p>

              <div className="wb-grid" style={{ gap: 8 }}>
                <button className={`wb-card ${musicId === "" ? "on" : ""}`} onClick={() => setMusicId("")}>
                  <div className="wb-t">无背景音乐</div>
                </button>
                {musicList.map((m) => (
                  <button
                    key={m.id}
                    className={`wb-card ${musicId === m.id ? "on" : ""}`}
                    onClick={() => setMusicId(m.id)}
                  >
                    <div className="wb-t">{m.name}</div>
                    <div className="wb-d">{m.duration ? `${Math.round(m.duration)}s` : ""}</div>
                  </button>
                ))}
              </div>
              {musicList.length === 0 && (
                <p className="wb-d" style={{ marginTop: 12 }}>
                  还没有上传背景音乐。去{" "}
                  <a href="/settings/music" style={{ color: "var(--accent)" }}>
                    音乐管理
                  </a>{" "}
                  上传后就能在这里选。
                </p>
              )}
            </section>
          )}

          {/* ── 6. 脚本 ── */}
          {panel === "script" && (
            <section>
              <h2>脚本</h2>
              <p className="wb-sub">输入或粘贴口播文案，按句号/问号/感叹号自动分段，每段生成一帧。</p>

              <div className="wb-seg" style={{ marginBottom: 16 }}>
                <button className={scriptMode === "auto" ? "on" : ""} onClick={() => setScriptMode("auto")}>
                  给个选题
                </button>
                <button className={scriptMode === "manual" ? "on" : ""} onClick={() => setScriptMode("manual")}>
                  我有脚本
                </button>
              </div>

              {scriptMode === "auto" && (
                <div>
                  <textarea
                    rows={3}
                    value={rawScript}
                    onChange={(e) => setRawScript(e.target.value)}
                    placeholder={"输入一个选题，例如：为什么程序员总说“在我电脑上是好的”"}
                  />
                  <p className="wb-d" style={{ marginTop: 8 }}>
                    输入选题后，在这里直接粘贴模型生成的稿子，系统会按句号分段。
                  </p>
                </div>
              )}

              {scriptMode === "manual" && (
                <div>
                  <textarea
                    rows={8}
                    value={rawScript}
                    onChange={(e) => setRawScript(e.target.value)}
                    placeholder="把整段文案粘进来。会按句号/问号/感叹号自动分段，每段对应一帧。"
                  />
                  <div className="wb-row" style={{ marginTop: 8 }}>
                    <span className="wb-cost">
                      {scriptChars} 字 · 预计 {scriptSentences} 句
                    </span>
                  </div>
                </div>
              )}
            </section>
          )}
        </main>

        {/* ═══ Right preview ═══ */}
        <aside className="wb-pv">
          <div className="wb-pv-hd">
            <strong>预览</strong>
            <span>9:16 · {scriptSentences} 帧</span>
          </div>
          <div className="wb-stage">
            <div className={`wb-frame ${fxClass}`} ref={frameRef} style={{ "--kb": 1 + zoomPct / 100 } as React.CSSProperties}>
              <div className="wb-art">
                <div className="wb-board" />
                {charPreview ? (
                  <img src={charPreview} alt="" className="wb-char-img" />
                ) : (
                  <div className="wb-char-placeholder">⇪</div>
                )}
              </div>
              {activeEffects.has("荧幕噪点") && <div className="wb-fx wb-fx-grain" />}
              {activeEffects.has("暗角") && <div className="wb-fx wb-fx-vig" />}
              {activeEffects.has("电影感") && <div className="wb-fx wb-fx-bars" />}
              <div className="wb-sub-text" style={subStyle} onPointerDown={onSubDown}>
                {rawScript.split(/[。！？.!?；]/).filter(Boolean)[0]?.slice(0, 30) || "在这里输入脚本…"}
              </div>
              <div className="wb-prog">
                <i style={{ width: "38%" }} />
              </div>
            </div>
          </div>
          <div className="wb-pv-info">
            <span>
              {charName || "未选主角"} · {voiceId || "未选配音"}
            </span>
            <span>00:00 / {Math.round(scriptSentences * 4)}s</span>
          </div>
        </aside>
      </div>
    </div>
  );
}
