"""Read A's canonical outcomes without CSV exports or duplicate writes."""
import json
import logging
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from dashboard.errors import SubmissionStorageError
from dashboard.waste_data import WasteData
from dashboard.submission import Submission

logger = logging.getLogger(__name__)


@contextmanager
def read_only_database(path):
    # SQLite may need to create WAL sidecars even though records cannot be written.
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
            db.execute("PRAGMA query_only=ON")
            yield db
    except sqlite3.Error as error:
        raise SubmissionStorageError() from error


def load_submission_records(data_path, include_demo=False):
    """Read all statuses and attach the optional feedback without changing analytics."""
    path = Path(data_path).resolve()
    records, skipped = [], 0
    if not path.exists():
        return records, skipped, None
    try:
        with read_only_database(path) as db:
            rows = db.execute("""SELECT s.id, s.region_id, s.created_at, s.status, s.is_demo,
                s.outcome_json, f.helpful FROM submissions s
                LEFT JOIN feedback f ON f.submission_id = s.id
                WHERE (? OR s.is_demo=0) ORDER BY s.created_at DESC, s.id DESC""", (include_demo,)).fetchall()
        for identifier, region, timestamp, status, demo, outcome_json, helpful in rows:
            try:
                outcome = json.loads(outcome_json)
                recognition = outcome.get("recognition") or {}
                guidance = outcome.get("guidance") or {}
                submission = Submission(region, timestamp, guidance.get("category") or "unknown",
                                        recognition.get("item_name") or "Unidentified item")
                records.append({"id": identifier, "region": region, "timestamp": submission.timestamp,
                                "item_name": submission.item_name, "category": guidance.get("category"),
                                "status": status, "is_demo": bool(demo), "helpful": helpful})
            except (ValueError, TypeError, AttributeError):
                skipped += 1
        return records, skipped, None
    except SubmissionStorageError as error:
        logger.exception("Could not read submission history %s", path)
        return records, skipped, str(error)


class SubmissionStore(WasteData):
    def __init__(self, data_path, include_demo=False):
        self.include_demo = include_demo
        super().__init__(data_path)

    def load(self):
        self.submissions, self.skipped_rows, self.error = [], 0, None
        path = Path(self.data_path).resolve()
        if not path.exists():
            return  # A has not saved its first request yet.
        try:
            with read_only_database(path) as db:
                rows = db.execute("""SELECT region_id, created_at, outcome_json FROM submissions
                    WHERE status='completed' AND (? OR is_demo=0)""", (self.include_demo,)).fetchall()
            for region, timestamp, outcome_json in rows:
                try:
                    outcome = json.loads(outcome_json)
                    guidance, recognition = outcome["guidance"], outcome["recognition"]
                    # Missing rules are not disposal decisions and do not enter recycling rates.
                    if guidance["status"] not in {"matched", "special"}:
                        continue
                    self.submissions.append(Submission(region, timestamp, guidance["category"], recognition["item_name"]))
                except (ValueError, KeyError, TypeError, AttributeError):
                    self.skipped_rows += 1
        except SubmissionStorageError as error:
            logger.exception("Could not read submission database %s", path)
            self.error = str(error)
