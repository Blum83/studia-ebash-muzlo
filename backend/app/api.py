from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.db import DB
from app.engines import MusicEngine
from app.jobs import Job, JobRunner, auto_title
from app.lyrics import LyricsError, Song
from app.schemas import JobCreate, LyricsRequest

Songwriter = Callable[..., Song]


def create_app(
    engine: MusicEngine,
    db: DB,
    output_dir: Path,
    allowed_hosts: list[str],
    songwriter: Songwriter | None = None,
    frontend_dir: Path | None = None,
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
        return t | {
            "title": t["title"] or auto_title(JobCreate.model_validate(t["params"])),  # old rows
            "wav_url": f"/files/{t['id']}.wav",
            "mp3_url": f"/files/{t['id']}.mp3",
        }

    def job_out(job: Job) -> dict[str, Any]:
        track = db.get(job.id) if job.status == "done" else None
        return {
            "id": job.id,
            "status": job.status,
            "error": job.error,
            "position": runner.position(job),
            "params": job.req.model_dump(),
            "track": track_out(track) if track else None,
        }

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return {
            "engine": engine.name,
            "engine_ready": runner.ready,
            "engine_error": runner.load_error,
            "lyrics_enabled": songwriter is not None,
        }

    @app.post("/api/jobs", status_code=202)
    def create_job(req: JobCreate) -> dict[str, str]:
        return {"id": runner.submit(req).id}

    @app.get("/api/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        """Unfinished and failed jobs (finished ones are in /api/tracks)."""
        return [job_out(j) for j in list(runner.jobs.values()) if j.status != "done"]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = runner.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job_out(job)

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def dismiss_job(job_id: str) -> None:
        job = runner.jobs.get(job_id)
        if not job or job.status != "error":
            raise HTTPException(409, "Only failed jobs can be dismissed")
        runner.jobs.pop(job_id, None)

    @app.post("/api/lyrics")
    def lyrics(req: LyricsRequest) -> Song:
        if songwriter is None:
            raise HTTPException(503, "Lyrics writer is not configured")
        try:
            return songwriter(**req.model_dump())
        except LyricsError as e:
            raise HTTPException(502, str(e)) from e

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
    if frontend_dir and frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
