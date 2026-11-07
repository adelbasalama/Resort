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
