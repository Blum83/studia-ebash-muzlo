from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.db import DB
from app.jobs import auto_title
from app.lyrics import LyricsError, Song
from app.lyrics.claude import parse_song
from app.schemas import JobCreate
from tests.test_api import BODY, FakeEngine, wait_job


def client(tmp_path: Path, songwriter=None) -> TestClient:
    return TestClient(
        create_app(FakeEngine(), DB(":memory:"), tmp_path, ["testserver"], songwriter=songwriter)
    )


def test_lyrics_endpoint(tmp_path: Path) -> None:
    calls = []

    def fake(**kw):
        calls.append(kw)
        return Song(title="Т", caption="rap", lyrics="[Verse]\nа")

    with client(tmp_path, fake) as c:
        assert c.get("/api/config").json()["lyrics_enabled"] is True
        r = c.post("/api/lyrics", json={"idea": "про биллинг", "language": "ru"})
        assert r.json() == {"title": "Т", "caption": "rap", "lyrics": "[Verse]\nа"}
        assert calls[0]["language"] == "ru"


def test_lyrics_disabled_and_errors(tmp_path: Path) -> None:
    with client(tmp_path) as c:
        assert c.get("/api/config").json()["lyrics_enabled"] is False
        assert c.post("/api/lyrics", json={"idea": "x"}).status_code == 503

    def broken(**_):
        raise LyricsError("not logged in")

    with client(tmp_path, broken) as c:
        r = c.post("/api/lyrics", json={"idea": "x"})
        assert r.status_code == 502 and "not logged in" in r.json()["detail"]


def test_parse_song_tolerates_fences() -> None:
    s = parse_song('```json\n{"title": "a", "caption": "b", "lyrics": "[Verse]\\nc"}\n```')
    assert s.title == "a"
    with pytest.raises(LyricsError):
        parse_song("sorry, no")


@pytest.mark.parametrize(
    ("patch", "title"),
    [
        ({"title": " Мой трек "}, "Мой трек"),
        (
            {"lyrics": "[Verse]\nраз\n\n[Chorus - shouted]\nБиллинг впереди планеты всей!"},
            "Биллинг впереди планеты всей",
        ),
        ({"lyrics": "[Verse]\nраз", "idea": "ночная электричка"}, "ночная электричка"),
        ({"lyrics": "", "caption": "synthwave, dreamy"}, "synthwave"),
    ],
)
def test_auto_title(patch: dict, title: str) -> None:
    assert auto_title(JobCreate(**({"caption": "x"} | patch))) == title


def test_job_gets_auto_title(tmp_path: Path) -> None:
    with client(tmp_path) as c:
        body = BODY | {"lyrics": "[Chorus]\nХей, хей"}
        job = wait_job(c, c.post("/api/jobs", json=body).json()["id"])
        assert job["track"]["title"] == "Хей, хей"
