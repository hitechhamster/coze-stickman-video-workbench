import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import Workbench from "./pages/Workbench";
import ProjectList from "./pages/ProjectList";
import StyleManager from "./pages/StyleManager";
import EffectPresetManager from "./pages/EffectPresetManager";
import MusicManager from "./pages/MusicManager";
import ProjectResult from "./pages/ProjectResult";
import CozeWorkbench from "./pages/CozeWorkbench";

function App() {
  const { pathname } = useLocation();
  if (pathname === "/") return <CozeWorkbench />;
  const isWorkbench = pathname === "/classic";

  if (isWorkbench) return <Workbench />;

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-mark">火</span>
            <h1>AI 动画工作台</h1>
          </div>
          <nav>
            <NavLink to="/">工作台</NavLink>
            <NavLink to="/projects">历史项目</NavLink>
            <NavLink to="/settings/styles">画风</NavLink>
            <NavLink to="/settings/effects">效果预设</NavLink>
            <NavLink to="/settings/music">音乐</NavLink>
          </nav>
        </div>
      </header>
      <div className="app">
        <main className="app-main">
          <Routes>
            <Route path="/projects" element={<ProjectList />} />
            <Route path="/projects/:id" element={<ProjectResult />} />
            <Route path="/settings/styles" element={<StyleManager />} />
            <Route path="/settings/effects" element={<EffectPresetManager />} />
            <Route path="/settings/music" element={<MusicManager />} />
          </Routes>
        </main>
      </div>
    </>
  );
}

export default App;
