"""FastAPI 应用工厂。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from work_report.config import ROOT_DIR
from work_report.db.session import init_db


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="Work Report Admin", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from work_report.api.routes_config import router as config_router
    from work_report.api.routes_projects import router as projects_router
    from work_report.api.routes_runs import router as runs_router
    from work_report.api.routes_system import router as system_router

    app.include_router(system_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")

    dist_dir = ROOT_DIR / "web_dist"
    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        assets = dist_dir / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index_page() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str) -> FileResponse:
            # 避免吞掉未匹配的 /api（交由 404）
            if full_path.startswith("api/") or full_path == "api":
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not Found")
            candidate = dist_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist_dir / "index.html")
    else:

        @app.get("/")
        def index_placeholder() -> dict:
            return {
                "message": "Work Report API 已启动。前端未构建：请在 web/ 执行 npm install && npm run build",
                "docs": "/docs",
            }

    return app
