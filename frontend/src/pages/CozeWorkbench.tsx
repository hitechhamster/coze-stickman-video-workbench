import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, request, type Music, type Project, type Voice } from "../api/client";
import "./coze.css";

type Engine = "ark" | "gemini" | "openrouter";
type Speech = "volcengine" | "gemini" | "minimax";
interface Environment {
  keys: Record<string, boolean>;
  ark_text_model: string;
  ark_image_model: string;
  volc_tts_speaker: string;
  volc_tts_resource_id: string;
  jianying_drafts_dir: string;
  assets: { bgm: boolean; click: boolean };
}
interface Profile {
  name: string;
  node_count: number;
  environment: Environment;
}
interface Shot { shot_id: string; merged_content: string; start: number; end: number }
interface Plan { estimated: boolean; shots: Shot[]; captions: { content: string }[] }

const engines: [Engine, string][] = [["ark", "豆包 / 火山方舟"], ["gemini", "Gemini"], ["openrouter", "OpenRouter"]];
const stages = ["口播文案", "逐段配音", "合并分镜", "火柴人配图", "字幕与音效", "剪映草稿"];

export default function CozeWorkbench() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [scriptMode, setScriptMode] = useState<"manual" | "auto">("manual");
  const [subject, setSubject] = useState("");
  const [script, setScript] = useState("");
  const [llm, setLlm] = useState<Engine>("ark");
  const [image, setImage] = useState<Engine>("ark");
  const [tts, setTts] = useState<Speech>("volcengine");
  const [voice, setVoice] = useState("");
  const [voices, setVoices] = useState<Voice[]>([]);
  const [music, setMusic] = useState("");
  const [musicList, setMusicList] = useState<Music[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [config, setConfig] = useState<Record<string, string>>({});

  useEffect(() => {
    request<Profile>("/workflow/profile").then(p => {
      setProfile(p);
      setVoice(p.environment.volc_tts_speaker);
      setConfig({ ark_text_model: p.environment.ark_text_model, ark_image_model: p.environment.ark_image_model,
        volc_tts_speaker: p.environment.volc_tts_speaker, volc_tts_resource_id: p.environment.volc_tts_resource_id,
        jianying_drafts_dir: p.environment.jianying_drafts_dir });
    }).catch(e => setError(`无法连接工作台：${e.message}`));
    api.listMusic().then(setMusicList).catch(() => {});
  }, []);

  useEffect(() => {
    setVoices([]);
    if (tts === "volcengine") return;
    api.listVoices(tts === "gemini" ? "gemini" : "openrouter").then(setVoices)
      .catch(e => setError(e.message));
  }, [tts]);

  const options = { name: name || "彩色火柴人", script, subject, script_mode: scriptMode,
    llm_provider: llm, image_provider: image, tts_provider: tts, voice_id: voice, music_id: music || null };

  async function previewPlan() {
    setError(""); setBusy(true);
    try {
      setPlan(await request<Plan>("/workflow/plan", { method: "POST", body: JSON.stringify({ script }) }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function generate() {
    setError(""); setNotice("");
    if (scriptMode === "manual" ? !script.trim() : !subject.trim()) {
      setError(scriptMode === "manual" ? "请先填写口播文案" : "请先填写选题"); return;
    }
    setBusy(true);
    try {
      const check = await request<{ missing: string[] }>("/workflow/check", { method: "POST", body: JSON.stringify(options) });
      if (check.missing.length) {
        setConfigOpen(true); throw new Error(`还需配置：${check.missing.join("、")}`);
      }
      const project = await request<Project>("/workflow/projects", { method: "POST", body: JSON.stringify(options) });
      const { job_id } = await api.generateProject(project.id);
      navigate(`/projects/${project.id}?job=${job_id}`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function saveConfig() {
    setError(""); setBusy(true);
    try {
      const environment = await request<Environment>("/workflow/settings", { method: "POST", body: JSON.stringify(config) });
      setProfile(p => p ? { ...p, environment } : p);
      setConfig(c => Object.fromEntries(Object.entries(c).filter(([key]) => !key.endsWith("api_key"))));
      if (environment.volc_tts_speaker && tts === "volcengine") setVoice(environment.volc_tts_speaker);
      setNotice("配置已保存在本机，可以开始生成。");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function uploadMusic(file?: File) {
    if (!file) return;
    setBusy(true); setError("");
    try {
      const item = await api.uploadMusic(file.name, file);
      setMusicList(items => [item, ...items]); setMusic(item.id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const fields = [
    ["ark_api_key", "火山方舟 API Key", true], ["ark_text_model", "豆包文本模型 / 接入点 ID", false],
    ["ark_image_model", "豆包生图模型 / 接入点 ID", false],
    ["volc_tts_api_key", "豆包语音 API Key", true], ["volc_tts_speaker", "火山引擎音色 ID", false],
    ["volc_tts_resource_id", "语音模型资源 ID", false],
    ["gemini_api_key", "Gemini API Key（选用时填写）", true],
    ["openrouter_api_key", "OpenRouter API Key（选用时填写）", true],
    ["minimax_api_key", "MiniMax API Key（选用时填写）", true],
    ["jianying_drafts_dir", "剪映草稿位置", false],
  ] as const;

  return <div className="coze-workbench">
    <header className="cw-header">
      <Link to="/" className="cw-brand"><span className="cw-logo">✳</span><span>火柴人视频工作台<small>Coze 原流程 · 本地剪映草稿</small></span></Link>
      <nav><Link to="/projects">历史项目</Link><button onClick={() => setConfigOpen(v => !v)}>服务配置</button></nav>
    </header>
    <main className="cw-main">
      <div className="cw-heading"><div><span className="cw-eyebrow">彩色水彩 · 16:9 横屏</span><h1>把想说的话，变成一支短片。</h1>
        <p>沿用原工作流的分镜节奏、画风、字幕与音效，在剪映中完成最后的编辑。</p></div>
        <div className="cw-output-tag">输出到剪映<strong>可编辑草稿</strong></div></div>
      <div className="cw-stages">{stages.map((s, i) => <span key={s}><b>{i + 1}</b>{s}</span>)}</div>
      {error && <div className="cw-message cw-error" role="alert">{error}</div>}
      {notice && <div className="cw-message" role="status">{notice}</div>}
      {configOpen && <section className="cw-card cw-config">
        <div className="cw-card-title"><h2>连接生成服务</h2><button onClick={() => setConfigOpen(false)}>收起</button></div>
        <p>填写你选择的服务。密钥只保存在本机；已配置的密钥留空即可保留。</p>
        <div className="cw-fields">{fields.map(([key, label, secret]) => <label key={key}>{label}
          <input type={secret ? "password" : "text"} autoComplete="off" value={config[key] || ""}
            placeholder={secret && profile?.environment.keys[key] ? "已配置，留空保留" : "请输入"}
            onChange={e => setConfig(c => ({ ...c, [key]: e.target.value }))} /></label>)}</div>
        <p className="cw-help">草稿位置可在剪映「全局设置 → 草稿位置」中查看。原 Coze 的数字音色 ID 需要对应的厂商音色，不能直接填写。</p>
        <button className="cw-primary" disabled={busy} onClick={saveConfig}>保存本机配置</button>
      </section>}
      <div className="cw-columns">
        <section className="cw-card cw-create">
          <div className="cw-card-title"><h2>01 / 内容</h2><span>从一句想法开始</span></div>
          <label>短片名称<input value={name} onChange={e => setName(e.target.value)} placeholder="例如：斯多葛主义" /></label>
          <div className="cw-tabs"><button className={scriptMode === "manual" ? "selected" : ""} onClick={() => setScriptMode("manual")}>我有文案</button>
            <button className={scriptMode === "auto" ? "selected" : ""} onClick={() => { setScriptMode("auto"); setPlan(null); }}>AI 写文案</button></div>
          {scriptMode === "manual" ? <>
            <label>口播文案<textarea rows={10} value={script} onChange={e => { setScript(e.target.value); setPlan(null); }}
              placeholder="粘贴你的口播文案。生成时逐段配音，前四段快速切镜，后续按三到五段合并分镜。" /></label>
            <div className="cw-script-footer"><span>{script.trim().length} 字</span><button disabled={busy || !script.trim()} onClick={previewPlan}>预览分镜分组</button></div>
          </> : <><label>选题<textarea rows={5} value={subject} onChange={e => setSubject(e.target.value)} placeholder="例如：为什么你总是用愤怒保护自己？" /></label>
            <p className="cw-help">沿用原流程的 400–600 字口播提示词：情感共鸣 → 概念重塑 → 场景深化 → 升华结尾。</p></>}
          {plan && <div className="cw-plan"><h3>{plan.captions.length} 段文案 / {plan.shots.length} 个分镜</h3>
            <p>仅预览分组。实际时间线以生成的配音时长为准。</p>
            <ol>{plan.shots.map(s => <li key={s.shot_id}><b>{s.shot_id.replace("shot_", "")}</b><span>{s.merged_content}</span></li>)}</ol></div>}
        </section>
        <section className="cw-card cw-recipe">
          <div className="cw-card-title"><h2>02 / 原片配方</h2><span>保持原流程参数</span></div>
          <div className="cw-illustration" aria-label="火柴人画风示意，非生成结果">
            <svg viewBox="0 0 480 270" role="img"><title>火柴人画风示意</title>
              <rect width="480" height="270" fill="#edece0"/><ellipse cx="130" cy="180" rx="110" ry="95" fill="#d4e3da"/><ellipse cx="385" cy="60" rx="125" ry="100" fill="#dbe7ee"/>
              <g fill="none" stroke="#383e35" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="245" cy="72" rx="28" ry="31" fill="#fffef3"/>
                <path d="M245 105 L244 161 M244 125 L209 143 L184 122 M244 126 L276 145 L299 122 M244 161 L218 213 M244 161 L273 213"/>
                <path d="M233 75 L237 75 M251 75 L255 75 M240 87 Q245 90 250 87" strokeWidth="3"/>
              </g><g fill="none" stroke="#9ea69b" strokeWidth="3" strokeLinecap="round"><circle cx="357" cy="116" r="17" fill="#eeeee4"/><path d="M357 133 L357 177 M357 145 L332 157 M357 145 L380 157 M357 177 L342 212 M357 177 L373 212"/></g>
            </svg><span>画风示意 · 成片由你选择的模型生成</span>
          </div>
          <dl className="cw-specs"><div><dt>画面</dt><dd>1920 × 1080 · 彩色水彩火柴人</dd></div>
            <div><dt>切镜</dt><dd>前 4 段独立，后续 3–5 段合镜</dd></div>
            <div><dt>字幕</dt><dd>高字标志圆 · 白字黑边 · 底部</dd></div>
            <div><dt>配音</dt><dd>1.1 倍速 · 人声增强 3</dd></div>
            <div><dt>音乐</dt><dd>原背景音乐循环 · 音量 0.3</dd></div>
            <div><dt>音效</dt><dd>开头点击 · 约 0.392 秒 · 音量 3</dd></div>
            <div><dt>特效</dt><dd>全程震动 + 荧幕噪点</dd></div>
            <div><dt>转场</dt><dd>原流程未指定 · 直接切镜</dd></div></dl>
          <div className="cw-footnote">原画风提示词完整保留。字幕位置及生成画面需在剪映中确认。</div>
        </section>
        <section className="cw-card cw-services">
          <div className="cw-card-title"><h2>03 / 生成与输出</h2></div>
          <label>文案和提示词<select value={llm} onChange={e => setLlm(e.target.value as Engine)}>{engines.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>配图服务<select value={image} onChange={e => setImage(e.target.value as Engine)}>{engines.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>配音服务<select value={tts} onChange={e => { setTts(e.target.value as Speech); setVoice(""); }}>
            <option value="volcengine">豆包语音 / 火山引擎</option><option value="gemini">Gemini</option><option value="minimax">MiniMax</option></select></label>
          <label>音色{voices.length > 0 ? <select value={voice} onChange={e => setVoice(e.target.value)}><option value="">请选择音色</option>{voices.map(v => <option key={v.voice_id} value={v.voice_id}>{v.voice_name}</option>)}</select>
            : <input value={voice} onChange={e => setVoice(e.target.value)} placeholder="填写此配音服务的音色 ID" />}</label>
          <label>背景音乐<select value={music} onChange={e => setMusic(e.target.value)}><option value="">原工作流背景音乐</option>{musicList.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
          <label className="cw-upload">＋ 上传替换音乐<input type="file" accept="audio/*" disabled={busy} onChange={e => uploadMusic(e.target.files?.[0])} /></label>
          <p className="cw-help">更换生成服务会影响画面与音色表现。保持同一模型和音色，更容易接近原片。</p>
          <div className="cw-status"><span className={profile?.environment.assets.bgm && profile?.environment.assets.click ? "cw-dot ready" : "cw-dot"} />
            {profile ? (profile.environment.assets.bgm && profile.environment.assets.click ? "原音乐与音效已就绪" : "原音乐或音效尚未就绪") : "正在连接本地工作台…"}</div>
          <button className="cw-primary cw-generate" onClick={generate} disabled={busy || !profile}>{busy ? "处理中…" : "生成剪映草稿 →"}</button>
          <p className="cw-help cw-centered">生成使用外部 AI 服务，按对应账户计费。<br />完成后在剪映里编辑、导出。</p>
        </section>
      </div>
      <footer className="cw-footer"><span>保留原流程，素材生成与草稿组装在本地工作台完成。</span><Link to="/classic">打开原版自由工作台</Link></footer>
    </main>
  </div>;
}
