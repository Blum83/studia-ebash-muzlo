import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import DB
from app.engines import GenerateRequest, GenerateResult, MusicEngine, get_engine


class FakeEngine(MusicEngine):
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def generate(self, req: GenerateRequest, out_dir: Path) -> GenerateResult:
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        # Same name for identical params, like ACE-Step: the runner must still keep both.
        path = out_dir / "same-key.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 8000)
        return GenerateResult(wav_path=path, seed=123 if req.seed < 0 else req.seed)


def make_client(tmp_path: Path, engine: MusicEngine) -> TestClient:
    return TestClient(create_app(engine, DB(":memory:"), tmp_path, ["testserver"]))


def wait_job(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


BODY = {"caption": "synthwave", "lyrics": "[Verse]\nla la", "duration": 30, "seed": 7}


def test_generate_list_delete(tmp_path: Path) -> None:
    with make_client(tmp_path, FakeEngine()) as c:
        ids = [c.post("/api/jobs", json=BODY).json()["id"] for _ in range(2)]
        jobs = [wait_job(c, i) for i in ids]
        assert [j["status"] for j in jobs] == ["done", "done"]
        assert jobs[0]["track"]["seed"] == 7
        assert jobs[0]["track"]["params"]["lyrics"] == "[Verse]\nla la"
        assert c.get("/api/config").json()["engine_ready"] is True

        tracks = c.get("/api/tracks").json()
        assert {t["id"] for t in tracks} == set(ids)
        assert c.get(tracks[0]["mp3_url"]).status_code == 200

        assert c.delete(f"/api/tracks/{ids[0]}").status_code == 204
        assert not (tmp_path / f"{ids[0]}.wav").exists()
        assert (tmp_path / f"{ids[1]}.wav").exists()
        assert [t["id"] for t in c.get("/api/tracks").json()] == [ids[1]]
        assert c.delete(f"/api/tracks/{ids[0]}").status_code == 404


def test_engine_error_is_reported(tmp_path: Path) -> None:
    with make_client(tmp_path, FakeEngine(fail=True)) as c:
        job = wait_job(c, c.post("/api/jobs", json=BODY).json()["id"])
        assert job["status"] == "error"
        assert "out of memory" in job["error"]
        assert c.get("/api/tracks").json() == []


@pytest.mark.parametrize("patch", [{"duration": 5}, {"duration": 601}, {"caption": ""}])
def test_validation(tmp_path: Path, patch: dict) -> None:
    with make_client(tmp_path, FakeEngine()) as c:
        assert c.post("/api/jobs", json=BODY | patch).status_code == 422


def test_unknown_job_404(tmp_path: Path) -> None:
    with make_client(tmp_path, FakeEngine()) as c:
        assert c.get("/api/jobs/nope").status_code == 404


def test_foreign_host_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path, FakeEngine()) as c:
        r = c.get("/api/tracks", headers={"Host": "evil.example"})
        assert r.status_code == 400


def test_unknown_engine() -> None:
    with pytest.raises(ValueError):
        get_engine(Settings(engine="nope"))


@pytest.mark.parametrize(
    ("caption", "bpm"),
    [("pop rock, 150 bpm", 150), ("rap, 95BPM, raspy", 95), ("ambient", None), ("1000 bpm", None)],
)
def test_caption_bpm(caption: str, bpm: int | None) -> None:
    from app.engines.acestep import caption_bpm  # no torch import at module level

    assert caption_bpm(caption) == bpm
