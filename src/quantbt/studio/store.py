"""Transactional runs and ordered events. One SQLite connection per operation."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL,
                    settings TEXT NOT NULL, result TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    time TEXT NOT NULL, agent TEXT NOT NULL, status TEXT NOT NULL,
                    detail TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE INDEX IF NOT EXISTS events_run ON events(run_id,seq);
            """)
            abandoned = [r[0] for r in db.execute("SELECT id FROM runs WHERE status='RUNNING'")]
        for run_id in abandoned:
            self.finish(run_id, error="Worker stopped before completion")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, settings: dict) -> str:
        run_id = uuid.uuid4().hex
        with self.connection() as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?, ?,NULL,NULL)",
                (run_id, timestamp(), "RUNNING", json.dumps(settings, allow_nan=False)),
            )
        return run_id

    def event(self, run_id: str, agent: str, status: str, detail: dict) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO events(run_id,time,agent,status,detail) VALUES (?,?,?,?,?)",
                (run_id, timestamp(), agent, status, json.dumps(detail, allow_nan=False)),
            )

    def finish(self, run_id: str, result: dict | None = None, error: str | None = None) -> None:
        with self.connection() as db:
            if error:
                active = db.execute(
                    "SELECT agent,status FROM events WHERE seq IN "
                    "(SELECT MAX(seq) FROM events WHERE run_id=? GROUP BY agent)",
                    (run_id,),
                ).fetchall()
                for row in active:
                    if row["status"] in {"RUNNING", "PROGRESS"}:
                        db.execute(
                            "INSERT INTO events(run_id,time,agent,status,detail) "
                            "VALUES (?,?,?,?,?)",
                            (
                                run_id,
                                timestamp(),
                                row["agent"],
                                "FAILED",
                                json.dumps({"message": error}),
                            ),
                        )
            db.execute(
                "UPDATE runs SET status=?, result=?, error=? WHERE id=?",
                (
                    "FAILED" if error else "COMPLETED",
                    json.dumps(result, allow_nan=False),
                    error,
                    run_id,
                ),
            )

    def runs(self, limit: int = 30) -> list[dict]:
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,status,error FROM runs ORDER BY created DESC LIMIT ?",
                    (limit,),
                )
            ]

    def get(self, run_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["settings"] = json.loads(result["settings"])
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 500",
                (run_id, after),
            ).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]
