import { useEffect, useRef, useState } from "react";
import { api, type Music } from "../api/client";

export default function MusicManager() {
  const [musicList, setMusicList] = useState<Music[]>([]);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = () => api.listMusic().then(setMusicList).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !file) {
      setError("请填写名称并选择一个音频文件");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.uploadMusic(name, file);
      setName("");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("确定删除这段背景音乐吗？")) return;
    try {
      await api.deleteMusic(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="style-manager">
      <section>
        <h2>音乐库</h2>
        <p className="hint">
          背景音乐需要你自己上传（比如你自己获取的曲目），这里不会预置任何版权音乐。
        </p>
        <div className="music-list">
          {musicList.length === 0 && <p className="hint">还没有上传任何背景音乐</p>}
          {musicList.map((m) => (
            <div key={m.id} className="music-row">
              <div className="music-info">
                <span className="music-name">{m.name}</span>
                <span className="music-duration">
                  {m.duration ? `${m.duration.toFixed(1)}s` : ""}
                </span>
              </div>
              <audio controls src={api.musicUrl(m)} />
              <button className="btn-link danger" onClick={() => remove(m.id)}>
                删除
              </button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>上传背景音乐</h2>
        <form className="form" onSubmit={submit}>
          <label>
            名称
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：维瓦尔第《夏》第三乐章"
            />
          </label>
          <label>
            音频文件（mp3/wav）
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn" type="submit" disabled={saving}>
            {saving ? "上传中…" : "上传"}
          </button>
        </form>
      </section>
    </div>
  );
}
