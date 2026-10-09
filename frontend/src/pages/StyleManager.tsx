import { useEffect, useState } from "react";
import { api, type Style, type StyleInput } from "../api/client";

const EMPTY_FORM: StyleInput = {
  name: "",
  prompt_suffix: "",
  negative_prompt: "",
  image_provider: "openrouter",
  enforce_monochrome: false,
  enforce_color: false,
  scene_mode: "drama",
};

const PROVIDER_LABEL: Record<string, string> = {
  openrouter: "OpenRouter",
  gemini: "Gemini",
};

export default function StyleManager() {
  const [styles, setStyles] = useState<Style[]>([]);
  const [form, setForm] = useState<StyleInput>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [uploadingId, setUploadingId] = useState<string | null>(null);

  const load = () => api.listStyles().then(setStyles).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const generatePreview = async (id: string) => {
    setPreviewingId(id);
    setError(null);
    try {
      await api.previewStyle(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewingId(null);
    }
  };

  const uploadReference = async (id: string, file: File) => {
    setUploadingId(id);
    setError(null);
    try {
      await api.uploadStyleReference(id, file);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploadingId(null);
    }
  };

  const removeReference = async (id: string) => {
    if (!confirm("确定移除这个画风的角色参考图吗？之后生成会改回每次自动生成角色定妆图。")) return;
    try {
      await api.deleteStyleReference(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.prompt_suffix.trim()) {
      setError("画风名称和风格提示词不能为空");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.createStyle(form);
      setForm(EMPTY_FORM);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("确定删除这个自定义画风吗？")) return;
    try {
      await api.deleteStyle(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="style-manager">
      <section>
        <h2>画风预设</h2>
        <div className="style-grid">
          {styles.map((s) => {
            const thumbnailUrl = api.thumbnailUrl(s.thumbnail);
            const referenceUrl = api.thumbnailUrl(s.reference_image_url);
            return (
              <div key={s.id} className="style-card">
                {thumbnailUrl && (
                  <img className="style-thumb" src={thumbnailUrl} alt={`${s.name} 预览`} />
                )}
                <h4>
                  {s.name} {s.is_builtin && <span className="tag">内置</span>}{" "}
                  <span className="tag">{PROVIDER_LABEL[s.image_provider] ?? s.image_provider}</span>
                  {referenceUrl && <span className="tag">已锁定角色</span>}
                  {s.enforce_monochrome && <span className="tag">强制黑白</span>}
                  {s.enforce_color && <span className="tag">强制上色</span>}
                  <span className="tag">{s.scene_mode === "teaching" ? "教学向" : "戏剧向"}</span>
                </h4>
                <p>{s.prompt_suffix}</p>

                <div className="style-ref">
                  {referenceUrl ? (
                    <>
                      <img className="style-ref-thumb" src={referenceUrl} alt="角色参考图" />
                      <div className="style-ref-info">
                        <span className="hint">每张分镜都以这张图为准，不再自动生成定妆图</span>
                        <button type="button" className="btn-link danger" onClick={() => removeReference(s.id)}>
                          移除参考图
                        </button>
                      </div>
                    </>
                  ) : (
                    <label className="btn-link style-ref-upload">
                      {uploadingId === s.id ? "上传中…" : "上传角色参考图"}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        disabled={uploadingId === s.id}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) uploadReference(s.id, file);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  )}
                </div>

                <div className="style-card-actions">
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => generatePreview(s.id)}
                    disabled={previewingId === s.id}
                  >
                    {previewingId === s.id ? "生成中…" : thumbnailUrl ? "重新生成预览" : "一键生成预览"}
                  </button>
                  {!s.is_builtin && (
                    <button type="button" className="btn-link danger" onClick={() => remove(s.id)}>
                      删除
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h2>制作画风</h2>
        <form className="form" onSubmit={submit}>
          <label>
            画风名称
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如：赛博朋克火柴人"
            />
          </label>
          <label>
            生图渠道
            <select
              value={form.image_provider}
              onChange={(e) =>
                setForm({ ...form, image_provider: e.target.value as StyleInput["image_provider"] })
              }
            >
              <option value="openrouter">OpenRouter（配音需另配 MiniMax）</option>
              <option value="gemini">Gemini 官方（一个 key 全包）</option>
            </select>
            <p className="hint">
              两个渠道都用 Nano Banana（gemini-2.5-flash-image）出图，画面里可以出现拼写正确的英文短标签。
              {form.image_provider === "gemini"
                ? " 生图、配音、场景提示词全走 Gemini，只需要 GEMINI_API_KEY。"
                : " OpenRouter 上没有可用的 TTS，所以配音会回落到 MiniMax，需要额外配 MINIMAX_API_KEY。"}
            </p>
          </label>
          <label>
            叙事模式
            <select
              value={form.scene_mode}
              onChange={(e) =>
                setForm({ ...form, scene_mode: e.target.value as StyleInput["scene_mode"] })
              }
            >
              <option value="drama">戏剧向（主体在冲突/挣扎的最高点，适合故事、爽文）</option>
              <option value="teaching">教学向（主体从容讲解、画面传递信息，适合科普、命理）</option>
            </select>
            <p className="hint">
              决定每张分镜的叙事取向。戏剧向张力强但主体常常"很惨"；教学向让主体像老师一样演示概念，画面重信息、不卖惨。
            </p>
          </label>
          <label>
            风格提示词（会拼接到每段分镜画面提示词后面）
            <textarea
              rows={3}
              value={form.prompt_suffix}
              onChange={(e) => setForm({ ...form, prompt_suffix: e.target.value })}
              placeholder="例如：霓虹色彩，赛博朋克风格，火柴人剪影，故障艺术效果，竖版构图"
            />
          </label>
          <label>
            反向提示词（不希望出现的元素，可选）
            <input
              value={form.negative_prompt}
              onChange={(e) => setForm({ ...form, negative_prompt: e.target.value })}
              placeholder="例如：写实,照片,文字,水印,模糊"
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.enforce_monochrome}
              onChange={(e) =>
                setForm({
                  ...form,
                  enforce_monochrome: e.target.checked,
                  // 黑白与上色互斥，勾一个就把另一个取消
                  enforce_color: e.target.checked ? false : form.enforce_color,
                })
              }
            />
            强制纯黑白
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.enforce_color}
              onChange={(e) =>
                setForm({
                  ...form,
                  enforce_color: e.target.checked,
                  enforce_monochrome: e.target.checked ? false : form.enforce_monochrome,
                })
              }
            />
            强制上色
          </label>
          <p className="hint">
            生图模型对颜色约束的服从度都不稳定。勾「强制纯黑白」时，出彩色就自动重生成；勾「强制上色」时，画面掉成灰阶就自动重生成。两者互斥，实测九张里各有三四张会跑偏，靠生成后检测彩度兜底。
          </p>

          <p className="hint">
            想让某个固定角色出演每一张分镜？先保存画风，再到上面的卡片里「上传角色参考图」。
          </p>
          {error && <p className="error">{error}</p>}
          <button className="btn" type="submit" disabled={saving}>
            {saving ? "保存中…" : "保存画风"}
          </button>
        </form>
      </section>
    </div>
  );
}
