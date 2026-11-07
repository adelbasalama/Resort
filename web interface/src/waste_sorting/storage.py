"""Shared metadata storage. Image bytes and filenames are never persisted."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Feedback, Submission


class Repository:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    region_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_demo INTEGER NOT NULL,
                    outcome_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_region_date ON submissions(region_id, created_at);
                CREATE TABLE IF NOT EXISTS feedback (
                    submission_id TEXT PRIMARY KEY REFERENCES submissions(id),
                    helpful INTEGER NOT NULL CHECK(helpful IN (0, 1)),
                    created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def save(self, submission: Submission):
        with self.connection() as db:
            db.execute("""INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                updated_at=excluded.updated_at, is_demo=excluded.is_demo,
                outcome_json=excluded.outcome_json""",
                (submission.id, submission.region_id, submission.status,
                 submission.created_at.isoformat(), submission.updated_at.isoformat(),
                 int(submission.is_demo), submission.model_dump_json()))

    def get(self, submission_id: str):
        with self.connection() as db:
            row = db.execute("SELECT outcome_json FROM submissions WHERE id=?", (submission_id,)).fetchone()
        return Submission.model_validate_json(row[0]) if row else None

    def claim(self, submission: Submission) -> bool:
        """Claim an ID atomically without holding a lock during network calls."""
        with self.connection() as db:
            cursor = db.execute("INSERT OR IGNORE INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (submission.id, submission.region_id, submission.status,
                 submission.created_at.isoformat(), submission.updated_at.isoformat(),
                 int(submission.is_demo), submission.model_dump_json()))
            return cursor.rowcount == 1

    def save_feedback(self, feedback: Feedback):
        with self.connection() as db:
            row = db.execute("SELECT status FROM submissions WHERE id=?", (feedback.submission_id,)).fetchone()
            if not row or row[0] != "completed":
                raise ValueError("Feedback requires a completed submission.")
            db.execute("""INSERT INTO feedback VALUES (?, ?, ?)
                ON CONFLICT(submission_id) DO UPDATE SET helpful=excluded.helpful,
                created_at=excluded.created_at""",
                (feedback.submission_id, int(feedback.helpful), feedback.created_at.isoformat()))
