import logging
import os
import queue
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.audio import to_mp3
from app.db import DB
from app.engines import GenerateRequest, MusicEngine
from app.schemas import JobCreate

log = logging.getLogger("songgen.jobs")


def auto_title(r: JobCreate) -> str:
    """Suno-style fallback: first line of the chorus, else the idea, else the first style tag."""
    if r.title.strip():
        return r.title.strip()
    lines = [ln.strip() for ln in r.lyrics.splitlines()]
    for i, ln in enumerate(lines):
        if re.match(r"\[(final |main )?(chorus|hook|припев)", ln, re.I):
            first = next((x for x in lines[i + 1 :] if x and not x.startswith("[")), "")
            if first:
                return first.strip(" ,.!?…—-")[:80]
    if r.idea.strip():
        return r.idea.strip()[:80]
    return r.caption.split(",")[0].strip()[:80]


@dataclass
class Job:
    req: JobCreate
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"  # queued | running | done | error
    error: str | None = None


class JobRunner:
    """One worker thread owns the GPU: loads the engine once, then runs jobs one by one."""

    def __init__(self, engine: MusicEngine, db: DB, output_dir: Path) -> None:
        self.engine, self.db, self.output_dir = engine, db, output_dir
        self.q: queue.Queue[Job] = queue.Queue()
        # shortcut: finished jobs stay in memory until restart; fine for personal use.
        self.jobs: dict[str, Job] = {}
        self.ready = False
        self.load_error: str | None = None

    def start(self) -> None:
        threading.Thread(target=self._run, name="gpu-worker", daemon=True).start()

    def submit(self, req: JobCreate) -> Job:
        job = Job(req.model_copy(update={"title": auto_title(req)}))
        self.jobs[job.id] = job
        self.q.put(job)
        return job

    def position(self, job: Job) -> int:
        """0 = running or finished, n = n jobs ahead (including the running one)."""
        if job.status != "queued":
            return 0
        # list() snapshots the dict: the worker thread may add/update jobs concurrently.
        ahead = [j for j in list(self.jobs.values()) if j.status in ("queued", "running")]
        return ahead.index(job) if job in ahead else 0

    def _run(self) -> None:
        try:
            self.engine.load()
            self.ready = True
        except Exception as e:
            log.exception("Engine failed to load")
            self.load_error = str(e)
        while True:
            self._process(self.q.get())

    def _process(self, job: Job) -> None:
        if self.load_error:
            job.status, job.error = "error", f"Engine not loaded: {self.load_error}"
            return
        job.status = "running"
        r = job.req
        try:
            res = self.engine.generate(
                GenerateRequest(
                    caption=r.caption,
                    lyrics=r.lyrics,
                    duration=r.duration,
                    seed=r.seed,
                    instrumental=r.instrumental,
                    vocal_language=r.vocal_language,
                ),
                self.output_dir,
            )
            # Engines may reuse file names for identical params; give every track its own.
            wav = self.output_dir / f"{job.id}.wav"
            os.replace(res.wav_path, wav)
            mp3 = to_mp3(wav)
            self.db.insert(
                {
                    "id": job.id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "engine": self.engine.name,
                    "title": r.title,
                    "idea": r.idea,
                    "caption": r.caption,
                    "lyrics": r.lyrics,
                    "duration": r.duration,
                    "seed": res.seed,
                    "params": r.model_dump(),
                    "meta": res.meta,
                    "wav_path": str(wav),
                    "mp3_path": str(mp3),
                }
            )
            job.status = "done"
        except Exception as e:
            log.exception("Job %s failed", job.id)
            job.status, job.error = "error", str(e)
