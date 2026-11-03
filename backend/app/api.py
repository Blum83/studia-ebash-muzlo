from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.db import DB
from app.engines import MusicEngine
from app.jobs import JobRunner
from app.schemas import JobCreate


def create_app(
    engine: MusicEngine,
    db: DB,
    output_dir: Path,
    allowed_hosts: list[str],
) -> FastAPI:
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = JobRunner(engine, db, output_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runner.start()  # model loads in the worker thread; jobs queue up meanwhile
        yield

    app = FastAPI(title="songgen", lifespan=lifespan)
    # No auth (loopback, single user); this blocks DNS-rebinding from random websites.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.state.runner = runner

    def track_out(t: dict[str, Any]) -> dict[str, Any]:
        t = {k: v for k, v in t.items() if k not in ("wav_path", "mp3_path")}
        return t | {"wav_url": f"/files/{t['id']}.wav", "mp3_url": f"/files/{t['id']}.mp3"}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return {
            "engine": engine.name,
            "engine_ready": runner.ready,
            "engine_error": runner.load_error,
            "lyrics_enabled": False,
        }

    @app.post("/api/jobs", status_code=202)
    def create_job(req: JobCreate) -> dict[str, str]:
        return {"id": runner.submit(req).id}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = runner.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        track = db.get(job.id) if job.status == "done" else None
        return {
            "id": job.id,
            "status": job.status,
            "error": job.error,
            "position": runner.position(job),
            "track": track_out(track) if track else None,
        }

    @app.get("/api/tracks")
    def list_tracks() -> list[dict[str, Any]]:
        return [track_out(t) for t in db.list()]

    @app.delete("/api/tracks/{track_id}", status_code=204)
    def delete_track(track_id: str) -> None:
        t = db.get(track_id)
        if not t:
            raise HTTPException(404, "Track not found")
        for p in (t["wav_path"], t["mp3_path"]):
            Path(p).unlink(missing_ok=True)
        db.delete(track_id)

    app.mount("/files", StaticFiles(directory=output_dir), name="files")
    return app
