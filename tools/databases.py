"""Consistent SQLite snapshots for local and Docker databases."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"rules": {"regions", "recycling_rules", "guidance_decisions"},
            "submissions": {"submissions", "feedback"}}


def inspect(path, kind):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA trusted_schema=OFF")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed.")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Database contains invalid foreign keys.")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        allowed = REQUIRED[kind] | ({"seed_datasets"} if kind == "rules" else set())
        if not REQUIRED[kind] <= tables or not tables <= allowed:
            raise ValueError(f"This is not a supported {kind} database.")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
            raise ValueError("Unexpected database triggers or views.")
        return {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in sorted(tables)}


def snapshot(source, output, kind, replace=False):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if source == output:
        raise ValueError("Source and destination must be different files.")
    inspect(source, kind)
    if output.exists() and not replace:
        raise ValueError(f"Output already exists: {output}. Choose a new filename.")
    output.parent.mkdir(parents=True, exist_ok=True)
    # The backup API includes committed WAL data; copying only the .sqlite3 file does not.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(output, timeout=30)) as dst:
            src.backup(dst)
    return inspect(output, kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "import", "inspect"])
    parser.add_argument("kind", choices=sorted(REQUIRED))
    parser.add_argument("file", type=Path, help="Snapshot file to write, restore or inspect")
    args = parser.parse_args()
    target = Path(os.getenv("RULES_DATABASE_PATH" if args.kind == "rules" else "DATABASE_PATH",
                            str(ROOT / "data" / ("rules.sqlite3" if args.kind == "rules" else "waste_sorting.sqlite3"))))
    try:
        if args.action == "inspect":
            counts = inspect(args.file, args.kind)
        elif args.action == "export":
            counts = snapshot(target, args.file, args.kind)
        else:
            inspect(args.file, args.kind)  # Reject invalid input before touching the destination.
            if target.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup = args.file.resolve().parent / f"before-import-{args.kind}-{stamp}.sqlite3"
                snapshot(target, backup, args.kind)
                print(f"Previous database backed up to {backup}")
            counts = snapshot(args.file, target, args.kind, replace=True)
        print(f"{args.action} {args.kind}: {counts}")
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Database operation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
