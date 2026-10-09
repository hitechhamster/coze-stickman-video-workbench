from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db import init_db
from app.routers import catalog, effect_presets, jobs, music, projects, styles, templates, voices, workflow
from app.seed import seed_builtin_effect_presets, seed_builtin_styles, seed_builtin_templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_builtin_styles()
    seed_builtin_effect_presets()
    seed_builtin_templates()
    from app.db import SessionLocal
    from app.models import Job, Project
    with SessionLocal() as db:
        for job in db.query(Job).filter(Job.status.in_(["pending", "running"])).all():
            job.status = "failed"
            job.error_message = "上次服务退出时任务中断；已缓存素材，可重试生成"
            project = db.get(Project, job.project_id)
            if project:
                project.status = "failed"
        db.commit()
    yield


app = FastAPI(title="AI火柴人", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(styles.router)
app.include_router(effect_presets.router)
app.include_router(catalog.router)
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(voices.router)
app.include_router(music.router)
app.include_router(templates.router)
app.include_router(workflow.router)

app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")


@app.get("/health")
def health():
    return {"ok": True}


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and scope["method"] in ("GET", "HEAD"):
                return await super().get_response("index.html", scope)
            raise


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/ui", SPAFiles(directory=frontend_dist, html=True), name="workbench")


@app.get("/")
def open_workbench():
    return RedirectResponse("/ui/")
