import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Project } from "../api/client";

const STATUS_LABEL: Record<string, string> = {
  draft: "未生成",
  generating: "生成中",
  succeeded: "已完成",
  failed: "失败",
};

export default function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>加载中…</p>;
  if (error) return <p className="error">加载失败：{error}</p>;

  if (projects.length === 0) {
    return (
      <div className="empty-state">
        <p>还没有项目</p>
        <Link className="btn" to="/new">
          + 新建项目
        </Link>
      </div>
    );
  }

  return (
    <div className="project-grid">
      {projects.map((p) => (
        <Link key={p.id} to={`/projects/${p.id}`} className="project-card">
          <h3>{p.name}</h3>
          <p className="script-preview">{p.script.slice(0, 60)}</p>
          <span className={`status-badge status-${p.status}`}>
            {STATUS_LABEL[p.status] ?? p.status}
          </span>
        </Link>
      ))}
    </div>
  );
}
