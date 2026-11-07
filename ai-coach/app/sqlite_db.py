"""Local SQLite rules repository."""
import sqlite3
import json
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from app.domain.models import Region, RecyclingRule
from app.domain.errors import PersistenceError


class SQLiteRuleRepository:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS regions (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, source_url TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS recycling_rules (
                    id INTEGER PRIMARY KEY, region_id TEXT NOT NULL REFERENCES regions(id),
                    item_key TEXT NOT NULL, category TEXT NOT NULL, bin_label TEXT NOT NULL,
                    preparation TEXT NOT NULL, source_url TEXT NOT NULL, reviewed_on TEXT NOT NULL,
                    version INTEGER NOT NULL, condition_label TEXT NOT NULL, active INTEGER NOT NULL,
                    UNIQUE(region_id, item_key, condition_label, version));
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_rule ON recycling_rules
                    (region_id, item_key, condition_label) WHERE active=1;
                CREATE TABLE IF NOT EXISTS guidance_decisions (
                    id INTEGER PRIMARY KEY, region_id TEXT NOT NULL REFERENCES regions(id),
                    item_key TEXT NOT NULL, condition_label TEXT NOT NULL,
                    rule_id INTEGER NOT NULL REFERENCES recycling_rules(id), rule_version INTEGER NOT NULL,
                    recognition_id TEXT, recognition_confidence REAL, image_ref TEXT,
                    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS seed_datasets (
                    dataset_id TEXT PRIMARY KEY, installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)
            # Seed only once: never reactivate an administrator's disabled demo rules.
            if not db.execute("SELECT 1 FROM regions WHERE id='demo-dortmund'").fetchone():
                db.execute("INSERT INTO regions VALUES (?, ?, ?)",
                           ("demo-dortmund", "Dortmund (demo rules)", "https://www.dortmund.de/"))
                fixtures = [
                    ("beverage_can", "recyclable", "Packaging collection", "Empty the can. Check deposit return first."),
                    ("plastic_bottle", "recyclable", "Packaging collection", "Check deposit return and local accepted plastics."),
                    ("plastic_container", "recyclable", "Packaging collection", "Empty the container. Check local accepted plastics."),
                    ("banana_peel", "compostable", "Organic waste collection", "Remove stickers before disposal."),
                    ("battery", "special", "Battery collection point", "Never put batteries in household bins. Ask an authorized collection point."),
                    ("paper_bag", "recyclable", "Paper collection", "Keep paper clean and dry. Remove non-paper lining."),
                    ("glass_bottle", "recyclable", "Glass collection point", "Check deposit return first. Check local colour separation."),
                ]
                for item, category, label, preparation in fixtures:
                    db.execute("""INSERT INTO recycling_rules
                        (region_id,item_key,category,bin_label,preparation,source_url,reviewed_on,
                         version,condition_label,active) VALUES (?,?,?,?,?,?,?,1,'any',1)""",
                        ("demo-dortmund", item, category, label, preparation,
                         "https://www.dortmund.de/", "2026-11-06"))
        self.install_regional_seed()

    def install_regional_seed(self):
        """Add a versioned dataset to fresh AND existing volumes without overwriting edits."""
        seed = json.loads((Path(__file__).resolve().parents[1] / "seeds/regional_rules.json").read_text(encoding="utf-8"))
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM seed_datasets WHERE dataset_id=?", (seed["dataset_id"],)).fetchone():
                return
            for region in seed["regions"]:
                db.execute("INSERT OR IGNORE INTO regions VALUES (?,?,?)",
                           (region["id"], region["name"], region["source_url"]))
            for rule in seed["rules"]:
                if db.execute("SELECT 1 FROM recycling_rules WHERE region_id=? AND item_key=? AND condition_label=?",
                              (rule["region_id"], rule["item_key"], rule["condition"])).fetchone():
                    continue
                db.execute("""INSERT INTO recycling_rules
                    (region_id,item_key,category,bin_label,preparation,source_url,reviewed_on,version,condition_label,active)
                    VALUES (?,?,?,?,?,?,?,?,?,1)""", (rule["region_id"], rule["item_key"], rule["category"],
                    rule["bin_label"], rule["preparation"], rule["source_url"], rule["reviewed_on"],
                    rule["version"], rule["condition"]))
            db.execute("INSERT INTO seed_datasets(dataset_id) VALUES (?)", (seed["dataset_id"],))

    def list_rules(self, region_id=None):
        with self.connection() as db:
            return [dict(row) for row in db.execute("""SELECT * FROM recycling_rules
                WHERE (? IS NULL OR region_id=?) ORDER BY region_id,item_key,condition_label,version DESC""",
                (region_id, region_id))]

    @contextmanager
    def connection(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        except sqlite3.Error as exc:
            raise PersistenceError("Rules database operation failed") from exc
        finally:
            if db is not None:
                db.close()

    def list_regions(self):
        with self.connection() as db:
            return [Region(**dict(row)) for row in db.execute("SELECT * FROM regions ORDER BY name")]

    def find_rule(self, region_id, item_key, condition="unknown"):
        with self.connection() as db:
            row = db.execute("""SELECT * FROM recycling_rules
                WHERE region_id=? AND item_key=? AND active=1
                AND condition_label IN (?, 'any', 'unknown')
                ORDER BY CASE WHEN condition_label=? THEN 0 WHEN condition_label='any' THEN 1 ELSE 2 END,
                version DESC LIMIT 1""", (region_id, item_key, condition, condition)).fetchone()
            return _rule(dict(row)) if row else None

    def save_decision(self, region_id, item_key, condition, rule_id, rule_version,
                      recognition_id=None, recognition_confidence=None, image_ref=None):
        with self.connection() as db:
            db.execute("""INSERT INTO guidance_decisions
                (region_id,item_key,condition_label,rule_id,rule_version,recognition_id,recognition_confidence,image_ref)
                VALUES (?,?,?,?,?,?,?,?)""",
                (region_id, item_key, condition, rule_id, rule_version,
                 recognition_id, recognition_confidence, image_ref))

    def create_region(self, region):
        with self.connection() as db:
            db.execute("INSERT INTO regions VALUES (?,?,?)", (region.id, region.name, region.source_url))

    def create_rule_revision(self, rule):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            key = (rule.region_id, rule.item_key, rule.condition)
            version = db.execute("""SELECT COALESCE(MAX(version),0)+1 FROM recycling_rules
                WHERE region_id=? AND item_key=? AND condition_label=?""", key).fetchone()[0]
            db.execute("""UPDATE recycling_rules SET active=0
                WHERE region_id=? AND item_key=? AND condition_label=? AND active=1""", key)
            cursor = db.execute("""INSERT INTO recycling_rules
                (region_id,item_key,category,bin_label,preparation,source_url,reviewed_on,version,condition_label,active)
                VALUES (?,?,?,?,?,?,?,?,?,1)""", (rule.region_id, rule.item_key, rule.category,
                rule.bin_label, rule.preparation, rule.source_url, rule.reviewed_on.isoformat(), version, rule.condition))
            return cursor.lastrowid, version

    def deactivate_rule(self, rule_id):
        with self.connection() as db:
            return db.execute("UPDATE recycling_rules SET active=0 WHERE id=?", (rule_id,)).rowcount == 1


def _rule(row):
    if isinstance(row["reviewed_on"], str): row["reviewed_on"] = date.fromisoformat(row["reviewed_on"])
    return RecyclingRule(id=row["id"], region_id=row["region_id"], item_key=row["item_key"],
        category=row["category"], bin_label=row["bin_label"], preparation=row["preparation"],
        source_url=row["source_url"], reviewed_on=row["reviewed_on"], version=row["version"],
        condition=row["condition_label"], active=bool(row["active"]))
