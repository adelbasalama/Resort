import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard.data_filter import DataFilter
from dashboard.submission_store import SubmissionStore
from app import app


def insert_outcome(db):
    db.execute("INSERT INTO submissions VALUES (?,?,?,?,?)", (
        "dortmund", "2026-11-07T12:00:00+00:00", "completed", 0,
        json.dumps({"recognition": {"item_name": "Can"},
                    "guidance": {"status": "matched", "category": "recyclable"}})))
    db.commit()


def make_database(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE submissions (
        region_id TEXT, created_at TEXT, status TEXT, is_demo INTEGER, outcome_json TEXT)""")
    insert_outcome(db)
    db.close()


def test_closed_wal_database_and_new_live_commits_are_visible(tmp_path):
    path = tmp_path / "outcomes.sqlite3"
    make_database(path)
    assert not Path(str(path) + "-wal").exists()
    store = SubmissionStore(path)
    assert store.error is None
    assert store.get_statistics(DataFilter())["total"] == 1
    writer = sqlite3.connect(path)
    try:
        insert_outcome(writer)
        assert Path(str(path) + "-wal").exists()
        store.load()
        assert store.error is None
        assert store.get_statistics(DataFilter())["total"] == 2
    finally:
        writer.close()


def test_dashboard_connection_cannot_write_submission_records(tmp_path, monkeypatch):
    path = tmp_path / "outcomes.sqlite3"
    make_database(path)
    connect = sqlite3.connect
    def checked_connect(*args, **kwargs):
        db = connect(*args, **kwargs)
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                db.execute("DELETE FROM submissions")
        except BaseException:
            db.rollback()
            db.close()
            raise
        return db
    monkeypatch.setattr(sqlite3, "connect", checked_connect)
    store = SubmissionStore(path)
    assert store.error is None
    assert store.get_statistics(DataFilter())["total"] == 1


def test_storage_failure_is_reported_by_health_endpoint(tmp_path, monkeypatch):
    path = tmp_path / "invalid.sqlite3"
    path.write_bytes(b"not a database")
    monkeypatch.setenv("DATABASE_PATH", str(path))
    monkeypatch.delenv("DASHBOARD_CSV_PATH", raising=False)
    response = app.test_client().get("/health")
    assert response.status_code == 503
    assert response.get_json()["status"] == "error"


def test_not_yet_created_submission_database_is_healthy_empty_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "not-created.sqlite3"))
    monkeypatch.delenv("DASHBOARD_CSV_PATH", raising=False)
    client = app.test_client()
    assert client.get("/health").status_code == 200
    response = client.get("/api/stats")
    assert response.status_code == 200 and response.get_json()["total"] == 0
