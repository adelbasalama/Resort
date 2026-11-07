import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-coach"))
sys.path.insert(0, str(ROOT / "tools"))
from app.sqlite_db import SQLiteRuleRepository
from databases import inspect, snapshot


def test_seven_regions_cover_categories_and_preserve_admin_edits(tmp_path):
    repo = SQLiteRuleRepository(tmp_path / "rules.sqlite3")
    names = {region.id for region in repo.list_regions()}
    assert names == {"dortmund", "bochum", "hagen", "witten", "unna", "luenen", "castrop-rauxel", "demo-dortmund"}
    for region in names - {"demo-dortmund"}:
        rows = repo.list_rules(region)
        assert len(rows) == 19
        assert {r["category"] for r in rows} == {"recyclable", "compostable", "landfill", "special"}
        assert all(r["source_url"].startswith("https://") and r["reviewed_on"] == "2026-11-07" for r in rows)
    assert "Wertstoffhof" in repo.find_rule("hagen", "banana_peel").bin_label
    assert "Biotonne" in repo.find_rule("dortmund", "banana_peel").bin_label
    target = repo.find_rule("dortmund", "paper_bag", "clean")
    repo.deactivate_rule(target.id)
    restored = SQLiteRuleRepository(repo.path)
    assert restored.find_rule("dortmund", "paper_bag", "clean") is None
    assert len(restored.list_rules("dortmund")) == 19


def test_existing_demo_database_is_upgraded_without_losing_decisions(tmp_path):
    path = tmp_path / "old.sqlite3"
    repo = SQLiteRuleRepository(path)
    with repo.connection() as db:
        db.execute("DELETE FROM recycling_rules WHERE region_id NOT LIKE 'demo-%'")
        db.execute("DELETE FROM regions WHERE id NOT LIKE 'demo-%'")
        db.execute("DELETE FROM seed_datasets")
        rule = repo.find_rule("demo-dortmund", "battery")
        db.execute("INSERT INTO guidance_decisions(region_id,item_key,condition_label,rule_id,rule_version) VALUES (?,?,?,?,?)",
                   ("demo-dortmund", "battery", "unknown", rule.id, rule.version))
    upgraded = SQLiteRuleRepository(path)
    assert len(upgraded.list_regions()) == 8
    with upgraded.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM guidance_decisions").fetchone()[0] == 1


def test_snapshot_roundtrip_includes_wal_and_rejects_wrong_kind(tmp_path):
    repo = SQLiteRuleRepository(tmp_path / "source.sqlite3")
    with sqlite3.connect(repo.path) as writer:
        writer.execute("INSERT INTO regions VALUES ('snapshot-test','Snapshot test','https://example.org')")
        writer.commit()
        output = tmp_path / "backup.sqlite3"
        counts = snapshot(repo.path, output, "rules")
        assert counts["regions"] == 9
    assert inspect(output, "rules")["recycling_rules"] == 140
    restored = tmp_path / "restored.sqlite3"
    snapshot(output, restored, "rules")
    assert inspect(restored, "rules") == counts
    with pytest.raises(ValueError):
        inspect(output, "submissions")
    with pytest.raises(ValueError):
        snapshot(output, restored, "rules")


def test_restore_cli_creates_previous_database_backup(tmp_path, monkeypatch):
    import databases
    target, incoming = tmp_path / "active.sqlite3", tmp_path / "incoming.sqlite3"
    SQLiteRuleRepository(target)
    repo = SQLiteRuleRepository(incoming)
    from app.domain.models import Region
    repo.create_region(Region("imported", "Imported", "https://example.org"))
    monkeypatch.setenv("RULES_DATABASE_PATH", str(target))
    monkeypatch.setattr(sys, "argv", ["databases.py", "import", "rules", str(incoming)])
    assert databases.main() == 0
    assert inspect(target, "rules")["regions"] == 9
    backups = list(tmp_path.glob("before-import-*.sqlite3"))
    assert len(backups) == 1 and inspect(backups[0], "rules")["regions"] == 8


@pytest.mark.parametrize("failure", ["provider", "different_bin", "overlong"])
def test_openai_education_failure_preserves_database_decision(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from openai import OpenAIError
    from app import coach
    from app.domain.services import RegionalGuidanceService
    repo = SQLiteRuleRepository(tmp_path / "rules.sqlite3")
    rule = repo.find_rule("dortmund", "diaper")
    client = MagicMock()
    client.__enter__.return_value = client
    if failure == "provider":
        client.responses.parse.side_effect = OpenAIError("provider unavailable")
    else:
        text = "Use some other bin." if failure == "different_bin" else rule.bin_label + " word" * 101
        client.responses.parse.return_value = SimpleNamespace(status="completed",
            output_parsed=coach.EducationText(explanation=text))
    monkeypatch.setattr(coach, "OpenAI", lambda **kwargs: client)
    result = RegionalGuidanceService(repo, coach.OpenAICoach("test-only")).decide_and_explain("dortmund", "diaper")
    assert result["explanation"].is_fallback
    assert result["rule"].category == "landfill" and result["rule"].bin_label == rule.bin_label
