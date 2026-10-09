const BASE_URL = "http://127.0.0.1:8010";

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : `请求失败: ${res.status}`);
  }
  return res.json();
}

export type ImageProviderName = "openrouter" | "gemini";
export type SceneMode = "drama" | "teaching";

export interface Style {
  id: string;
  name: string;
  prompt_suffix: string;
  negative_prompt: string;
  reference_image_url: string | null;
  thumbnail: string | null;
  image_provider: ImageProviderName;
  enforce_monochrome: boolean;
  enforce_color: boolean;
  scene_mode: SceneMode;
  is_builtin: boolean;
  created_at: string;
}

export interface StyleInput {
  name: string;
  prompt_suffix: string;
  negative_prompt: string;
  reference_image_url?: string | null;
  thumbnail?: string | null;
  image_provider: ImageProviderName;
  enforce_monochrome: boolean;
  enforce_color: boolean;
  scene_mode: SceneMode;
}

export interface Voice {
  voice_id: string;
  voice_name: string;
}

export interface EffectItem {
  name: string;
  intensity: number | null;
}

export interface EffectPresetInput {
  name: string;
  description?: string;
  caption_font: string;
  caption_size: number;
  caption_color: string;
  caption_border_color: string;
  caption_position: number;
  effects: EffectItem[];
  transition_name: string | null;
  zoom_end_scale: number;
}

export interface EffectPreset extends EffectPresetInput {
  id: string;
  is_builtin: boolean;
  created_at: string;
}

export interface CatalogEffect {
  name: string;
  label: string;
  has_intensity: boolean;
  default_intensity: number | null;
}

export interface CatalogTransition {
  name: string;
  label: string;
}

export interface Catalog {
  fonts: string[];
  effects: CatalogEffect[];
  transitions: CatalogTransition[];
}

export interface Music {
  id: string;
  name: string;
  file_path: string;
  duration: number | null;
  created_at: string;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  style_id: string;
  voice_id: string;
  music_id: string | null;
  effect_preset_id: string | null;
  is_builtin: boolean;
  created_at: string;
  style_name: string;
  music_name: string | null;
  style_thumbnail: string | null;
}

export interface TemplateInput {
  name: string;
  description?: string;
  style_id: string;
  voice_id: string;
  music_id?: string | null;
  effect_preset_id?: string | null;
}

export interface Segment {
  id: string;
  index: number;
  text: string;
  duration: number | null;
  image_path: string | null;
  status: string;
}

export interface Project {
  id: string;
  name: string;
  script: string;
  style_id: string;
  voice_id: string;
  music_id: string | null;
  effect_preset_id: string | null;
  template_id: string | null;
  mode: string;
  status: string;
  video_path: string | null;
  created_at: string;
}

export interface ProjectDetail extends Project {
  segments: Segment[];
}

export interface Job {
  id: string;
  project_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  progress: number;
  current_step: string;
  error_message: string | null;
}

export interface DraftInfo {
  draft_name: string;
  drafts_dir: string;
}

export const api = {
  listStyles: () => request<Style[]>("/styles"),
  createStyle: (input: StyleInput) =>
    request<Style>("/styles", { method: "POST", body: JSON.stringify(input) }),
  updateStyle: (id: string, input: StyleInput) =>
    request<Style>(`/styles/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteStyle: (id: string) => request<{ ok: boolean }>(`/styles/${id}`, { method: "DELETE" }),
  previewStyle: (id: string) => request<Style>(`/styles/${id}/preview`, { method: "POST" }),
  uploadStyleReference: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Style>(`/styles/${id}/reference`, { method: "POST", body: form });
  },
  deleteStyleReference: (id: string) =>
    request<Style>(`/styles/${id}/reference`, { method: "DELETE" }),
  /** 把后端存的绝对路径转成可访问的 /storage URL，供画风卡片和模板封面共用 */
  thumbnailUrl: (thumbnail: string | null) =>
    thumbnail ? `${BASE_URL}/storage/${thumbnail.split(/[\\/]storage[\\/]/).pop()}` : null,

  listVoices: (imageProvider?: string) =>
    request<Voice[]>(`/voices${imageProvider ? `?image_provider=${imageProvider}` : ""}`),

  listMusic: () => request<Music[]>("/music"),
  uploadMusic: (name: string, file: File) => {
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    return request<Music>("/music", { method: "POST", body: form });
  },
  deleteMusic: (id: string) => request<{ ok: boolean }>(`/music/${id}`, { method: "DELETE" }),
  musicUrl: (music: Music) => `${BASE_URL}/storage/${music.file_path.split(/[\\/]storage[\\/]/).pop()}`,

  listTemplates: () => request<Template[]>("/templates"),
  createTemplate: (input: TemplateInput) =>
    request<Template>("/templates", { method: "POST", body: JSON.stringify(input) }),
  deleteTemplate: (id: string) => request<{ ok: boolean }>(`/templates/${id}`, { method: "DELETE" }),

  listEffectPresets: () => request<EffectPreset[]>("/effect-presets"),
  createEffectPreset: (input: EffectPresetInput) =>
    request<EffectPreset>("/effect-presets", { method: "POST", body: JSON.stringify(input) }),
  updateEffectPreset: (id: string, input: EffectPresetInput) =>
    request<EffectPreset>(`/effect-presets/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteEffectPreset: (id: string) => request<{ ok: boolean }>(`/effect-presets/${id}`, { method: "DELETE" }),

  getCatalog: () => request<Catalog>("/catalog"),

  listProjects: () => request<Project[]>("/projects"),
  createProject: (input: {
    name: string;
    script: string;
    style_id: string;
    voice_id: string;
    music_id?: string | null;
    effect_preset_id?: string | null;
    template_id?: string | null;
  }) => request<Project>("/projects", { method: "POST", body: JSON.stringify(input) }),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  generateProject: (id: string) =>
    request<{ job_id: string }>(`/projects/${id}/generate`, { method: "POST" }),
  getDraft: (id: string) => request<DraftInfo>(`/projects/${id}/draft`),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),
};
