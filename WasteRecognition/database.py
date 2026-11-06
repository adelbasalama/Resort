"""HomeTask3 database access layer for shared RecognitionAttempt objects."""

import os
from pathlib import Path
import mysql.connector


def format_result(row):
    if row is not None:
        row.pop("id", None)  # MySQL's integer ID stays internal.
        row["condition"] = row.pop("item_condition")
        row["special"] = bool(row["special"])
        row["created_at"] = row["created_at"].isoformat() + "Z"
    return row


class RecognitionRepository:
    def __init__(self):
        self.config = {
            "host": os.environ.get("DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("DB_PORT", "3306")),
            "user": os.environ.get("DB_USER", "root"),
            "password": os.environ.get("DB_PASSWORD", ""),
            "database": "waste_recognition",
            "connection_timeout": 5,
            "time_zone": "+00:00",
        }

    def connect(self):
        return mysql.connector.connect(**self.config)

    def save(self, attempt):
        # to_dict() validates the same object used by HomeTask1 and HomeTask2.
        data = attempt.to_dict()
        values = (
            data["attempt_id"], data["submission_id"], data["model_id"],
            data["item_key"], data["material"], data["confidence"],
            data["status"], data["condition"], data["special"], data["routing_code"],
        )
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO recognition_attempts
                    (attempt_id, submission_id, model_id, item_key, material,
                     confidence, status, item_condition, special, routing_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, values)
                connection.commit()
        return data["attempt_id"]

    def get_all(self):
        with self.connect() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM recognition_attempts ORDER BY id DESC")
                return [format_result(row) for row in cursor.fetchall()]

    def get_by_id(self, attempt_id):
        with self.connect() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM recognition_attempts WHERE attempt_id = %s",
                    (attempt_id,),
                )
                return format_result(cursor.fetchone())


def upgrade_previous_schema(cursor):
    """Add the two new columns if the earlier HomeTask3 table already exists."""
    cursor.execute("SHOW COLUMNS FROM recognition_attempts")
    columns = {row[0] for row in cursor.fetchall()}
    if "attempt_id" not in columns:
        cursor.execute("ALTER TABLE recognition_attempts ADD COLUMN attempt_id VARCHAR(100) NULL")
    # Also completes this step if an earlier initialization was interrupted.
    cursor.execute("UPDATE recognition_attempts SET attempt_id = CONCAT('legacy_', id) WHERE attempt_id IS NULL")
    cursor.execute("ALTER TABLE recognition_attempts MODIFY COLUMN attempt_id VARCHAR(100) NOT NULL")
    cursor.execute("SHOW INDEX FROM recognition_attempts")
    has_unique_id = any(row[1] == 0 and row[4] == "attempt_id" for row in cursor.fetchall())
    if not has_unique_id:
        cursor.execute("ALTER TABLE recognition_attempts ADD UNIQUE KEY unique_attempt_id (attempt_id)")
    if "routing_code" not in columns:
        cursor.execute("ALTER TABLE recognition_attempts ADD COLUMN routing_code VARCHAR(20) NOT NULL DEFAULT 'REVIEW'")


def initialize_database():
    config = RecognitionRepository().config.copy()
    config.pop("database")
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8-sig")
    with mysql.connector.connect(**config) as connection:
        with connection.cursor() as cursor:
            for statement in schema.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            upgrade_previous_schema(cursor)
            connection.commit()
    print("Database ready: waste_recognition")


if __name__ == "__main__":
    initialize_database()
