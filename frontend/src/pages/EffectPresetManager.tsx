import { useEffect, useState } from "react";
import { api, type Catalog, type EffectItem, type EffectPreset, type EffectPresetInput } from "../api/client";

const EMPTY_FORM: EffectPresetInput = {
  name: "",
  description: "",
  caption_font: "高字标志圆",
  caption_size: 11,
  caption_color: "#ffffff",
  caption_border_color: "#000000",
  caption_position: -0.83,
  effects: [],
  transition_name: null,
  zoom_end_scale: 1.06,
};

function CaptionPreview({ form }: { form: EffectPresetInput }) {
  const topPercent = ((1 - form.caption_position) / 2) * 100;
  const border = form.caption_border_color;
  return (
    <div className="caption-preview">
      <div
        className="caption-preview-text"
        style={{
          top: `${topPercent}%`,
          color: form.caption_color,
          fontSize: `${8 + form.caption_size}px`,
          textShadow: [-1, 1].flatMap((x) => [-1, 1].map((y) => `${x}px ${y}px 0 ${border}`)).join(", "),
        }}
      >
        这是一句示例字幕
      </div>
    </div>
  );
}

export default function EffectPresetManager() {
  const [presets, setPresets] = useState<EffectPreset[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [form, setForm] = useState<EffectPresetInput>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.listEffectPresets().then(setPresets).catch((e) => setError(e.message));

  useEffect(() => {
    load();
    api.getCatalog().then(setCatalog).catch((e) => setError(e.message));
  }, []);

  const toggleEffect = (name: string, defaultIntensity: number | null) => {
    setForm((f) => {
      const exists = f.effects.find((e) => e.name === name);
      if (exists) {
        return { ...f, effects: f.effects.filter((e) => e.name !== name) };
      }
      const item: EffectItem = { name, intensity: defaultIntensity };
      return { ...f, effects: [...f.effects, item] };
    });
  };

  const setEffectIntensity = (name: string, intensity: number) => {
    setForm((f) => ({
      ...f,
      effects: f.effects.map((e) => (e.name === name ? { ...e, intensity } : e)),
    }));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("效果预设名称不能为空");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.createEffectPreset(form);
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("确定删除这个自定义效果预设吗？")) return;
    try {
      await api.deleteEffectPreset(id);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="style-manager">
      <section>
        <h2>效果预设</h2>
        <p className="hint">特效、转场、字幕样式打包成一套预设，创建项目时和画风分开选，可以自由组合。</p>
        <div className="style-grid">
          {presets.map((p) => (
            <div key={p.id} className="style-card">
              <h4>
                {p.name} {p.is_builtin && <span className="tag">内置</span>}
              </h4>
              <p>{p.description}</p>
              <div className="preset-tags">
                <span className="chip">🔤 {p.caption_font}</span>
                {p.effects.map((e) => (
                  <span className="chip" key={e.name}>
                    ✨ {e.name}
                    {e.intensity !== null ? ` ${e.intensity}` : ""}
                  </span>
                ))}
                {p.transition_name && <span className="chip">🔀 {p.transition_name}</span>}
              </div>
              {!p.is_builtin && (
                <button className="btn-link danger" onClick={() => remove(p.id)}>
                  删除
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>制作效果预设</h2>
        {!catalog ? (
          <p className="hint">加载可选项中…</p>
        ) : (
          <div className="effect-editor">
            <form className="form" onSubmit={submit}>
              <label>
                预设名称
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="例如：影院感"
                />
              </label>
              <label>
                描述（可选）
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="例如：暗角+老电影+叠化转场"
                />
              </label>

              <label>
                字幕字体
                <select
                  value={form.caption_font}
                  onChange={(e) => setForm({ ...form, caption_font: e.target.value })}
                >
                  {catalog.fonts.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                字号：{form.caption_size}
                <input
                  type="range"
                  min={6}
                  max={18}
                  step={0.5}
                  value={form.caption_size}
                  onChange={(e) => setForm({ ...form, caption_size: Number(e.target.value) })}
                />
              </label>

              <label>
                字幕位置：{form.caption_position <= -0.5 ? "贴底" : form.caption_position >= 0.5 ? "贴顶" : "居中"}
                <input
                  type="range"
                  min={-1}
                  max={1}
                  step={0.01}
                  value={form.caption_position}
                  onChange={(e) => setForm({ ...form, caption_position: Number(e.target.value) })}
                />
              </label>

              <div className="color-row">
                <label>
                  文字颜色
                  <input
                    type="color"
                    value={form.caption_color}
                    onChange={(e) => setForm({ ...form, caption_color: e.target.value })}
                  />
                </label>
                <label>
                  描边颜色
                  <input
                    type="color"
                    value={form.caption_border_color}
                    onChange={(e) => setForm({ ...form, caption_border_color: e.target.value })}
                  />
                </label>
              </div>

              <label>
                特效（可多选）
                <div className="effect-chip-grid">
                  {catalog.effects.map((e) => {
                    const selected = form.effects.find((x) => x.name === e.name);
                    return (
                      <div key={e.name} className={`effect-chip ${selected ? "active" : ""}`}>
                        <button
                          type="button"
                          className="effect-chip-toggle"
                          onClick={() => toggleEffect(e.name, e.default_intensity)}
                          title={e.label}
                        >
                          {e.name}
                        </button>
                        {selected && e.has_intensity && (
                          <input
                            type="range"
                            min={0}
                            max={100}
                            value={selected.intensity ?? 50}
                            onChange={(ev) => setEffectIntensity(e.name, Number(ev.target.value))}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </label>

              <label>
                转场
                <select
                  value={form.transition_name ?? ""}
                  onChange={(e) => setForm({ ...form, transition_name: e.target.value || null })}
                >
                  <option value="">无转场</option>
                  {catalog.transitions.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name} · {t.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                推镜幅度：{form.zoom_end_scale.toFixed(2)}x
                <input
                  type="range"
                  min={1.0}
                  max={1.3}
                  step={0.01}
                  value={form.zoom_end_scale}
                  onChange={(e) => setForm({ ...form, zoom_end_scale: Number(e.target.value) })}
                />
              </label>

              {error && <p className="error">{error}</p>}
              <button className="btn" type="submit" disabled={saving}>
                {saving ? "保存中…" : "保存效果预设"}
              </button>
            </form>

            <div className="effect-preview-col">
              <p className="hint">字幕样式预览（示意，非剪映真实渲染）</p>
              <CaptionPreview form={form} />
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
