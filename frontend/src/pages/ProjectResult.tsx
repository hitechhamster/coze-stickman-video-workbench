import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, type DraftInfo, type Job, type ProjectDetail } from "../api/client";
import { useNavigate } from "react-router-dom";

export default function ProjectResult() {
  const navigate = useNavigate();
  const [retrying, setRetrying] = useState(false);
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const jobId = searchParams.get("job");

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [draft, setDraft] = useState<DraftInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const loadProject = () => {
    if (!id) return;
    api
      .getProject(id)
      .then((p) => {
        setProject(p);
        if (p.video_path && p.status === "succeeded") {
          api.getDraft(id).then(setDraft).catch((e) => setError(e.message));
        }
      })
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    loadProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const j = await api.getJob(jobId);
        setJob(j);
        if (j.status === "succeeded" || j.status === "failed") {
          loadProject();
          return;
        }
        timerRef.current = window.setTimeout(poll, 2000);
      } catch (e) {
        setError((e as Error).message);
      }
    };
    poll();

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  if (error) return <p className="error">{error}</p>;
  if (!project) return <p>加载中…</p>;

  const isGenerating = job ? job.status === "running" || job.status === "pending" : project.status === "generating";

  return (
    <div className="project-result">
      <h2>{project.name}</h2>

      {isGenerating && job && (
        <div className="progress-box">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
          <p>{job.current_step || "准备中…"}</p>
        </div>
      )}

      {job?.status === "failed" && (
        <div className="error-box">
          <p>生成失败：</p>
          <pre>{job.error_message}</pre>
          {project.mode === "coze_original" && <button disabled={retrying} onClick={async () => {
            setRetrying(true);
            try {
              const { job_id } = await api.generateProject(project.id);
              setJob(null);
              navigate(`/projects/${project.id}?job=${job_id}`);
            } catch (e) { setError((e as Error).message); }
            finally { setRetrying(false); }
          }}>{retrying ? "正在重试…" : "重试生成（复用成功素材）"}</button>}
        </div>
      )}

      {draft && (
        <div className="video-box">
          <p>
            剪映草稿已生成：<strong>{draft.draft_name}</strong>
          </p>
          <p className="draft-hint">
            请打开剪映App，在草稿箱中找到这个草稿即可预览/编辑/导出。
            <br />
            草稿文件夹位置：<code>{draft.drafts_dir}</code>
          </p>
        </div>
      )}

      <section className="segments">
        <h3>分镜段落（{project.segments.length}）</h3>
        {project.mode === "coze_original" && <p>以下为逐句配音与字幕；画面按前四句独立、后续三到五句合镜排列。</p>}
        <ol>
          {project.segments.map((s) => (
            <li key={s.id} className={`segment status-${s.status}`}>
              <span className="segment-text">{s.text}</span>
              <span className="segment-meta">
                {s.duration ? `${s.duration.toFixed(1)}s` : ""} {s.status}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
