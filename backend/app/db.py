import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    engine TEXT NOT NULL,
    idea TEXT NOT NULL,
    caption TEXT NOT NULL,
    lyrics TEXT NOT NULL,
    duration REAL NOT NULL,
    seed INTEGER NOT NULL,
    params TEXT NOT NULL,
    meta TEXT NOT NULL,
    wav_path TEXT NOT NULL,
    mp3_path TEXT NOT NULL
)
"""
JSON_COLS = ("params", "meta")


class DB:
    def __init__(self, path: Path | str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # One connection shared by the API and the worker thread, serialized by a lock.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.conn.execute(SCHEMA)

    def insert(self, row: dict[str, Any]) -> None:
        row = {
            k: json.dumps(v, ensure_ascii=False) if k in JSON_COLS else v for k, v in row.items()
        }
        cols = ", ".join(row)
        with self.lock, self.conn:
            self.conn.execute(
                f"INSERT INTO tracks ({cols}) VALUES ({', '.join(':' + k for k in row)})", row
            )

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM tracks ORDER BY created_at DESC").fetchall()
        return [_decode(r) for r in rows]

    def get(self, track_id: str) -> dict[str, Any] | None:
        with self.lock:
            r = self.conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return _decode(r) if r else None

    def delete(self, track_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))


def _decode(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for k in JSON_COLS:
        d[k] = json.loads(d[k])
    return d
