"""MySQL repository. Configure MYSQL_* variables; see docker-compose.yml."""
import os
from app.domain.models import Region, RecyclingRule
from app.domain.errors import PersistenceError


def connect():
    try:
        import mysql.connector
        return mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "capstone"),
            password=os.environ.get("MYSQL_PASSWORD", "capstone_dev"),
            database=os.environ.get("MYSQL_DATABASE", "waste_assistant"),
        )
    except Exception as exc:
        raise PersistenceError("Database connection is unavailable") from exc


class MySQLRuleRepository:
    def list_rules(self, region_id=None):
        conn = connect()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""SELECT * FROM recycling_rules WHERE (%s IS NULL OR region_id=%s)
                ORDER BY region_id,item_key,condition_label,version DESC""", (region_id, region_id))
            return cursor.fetchall()
        finally:
            conn.close()

    def find_rule(self, region_id, item_key, condition="unknown"):
        try:
            conn = connect()
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""SELECT id, region_id, item_key, category, bin_label,
                    preparation, source_url, reviewed_on, version, condition_label, active
                    FROM recycling_rules WHERE region_id=%s AND item_key=%s AND active=1
                    AND condition_label IN (%s, 'any', 'unknown')
                    ORDER BY CASE WHEN condition_label=%s THEN 0 WHEN condition_label='any' THEN 1 ELSE 2 END,
                    version DESC LIMIT 1""", (region_id, item_key, condition, condition))
                row = cursor.fetchone()
                return _rule(row) if row else None
            finally: conn.close()
        except PersistenceError: raise
        except Exception as exc: raise PersistenceError("Could not read recycling rule") from exc

    def save_decision(self, region_id, item_key, condition, rule_id, rule_version,
                      recognition_id=None, recognition_confidence=None, image_ref=None):
        try:
            conn = connect()
            try:
                cursor = conn.cursor()
                cursor.execute("""INSERT INTO guidance_decisions
                    (region_id,item_key,condition_label,rule_id,rule_version,
                     recognition_id,recognition_confidence,image_ref)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (region_id, item_key, condition, rule_id, rule_version,
                     recognition_id, recognition_confidence, image_ref))
                conn.commit()
            finally: conn.close()
        except Exception as exc: raise PersistenceError("Could not record guidance decision") from exc

    def create_region(self, region):
        try:
            conn = connect()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO regions(id,name,source_url) VALUES (%s,%s,%s)",
                    (region.id, region.name, region.source_url),
                )
                conn.commit()
            finally: conn.close()
        except Exception as exc:
            raise PersistenceError("Could not create region") from exc

    def create_rule_revision(self, rule):
        try:
            conn = connect()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT COALESCE(MAX(version), 0) + 1
                    FROM recycling_rules
                    WHERE region_id=%s AND item_key=%s AND condition_label=%s""",
                    (rule.region_id, rule.item_key, rule.condition),
                )
                version = cursor.fetchone()[0]
                cursor.execute(
                    """UPDATE recycling_rules SET active=0
                    WHERE region_id=%s AND item_key=%s AND condition_label=%s
                    AND active=1""",
                    (rule.region_id, rule.item_key, rule.condition),
                )
                cursor.execute(
                    """INSERT INTO recycling_rules
                    (region_id,item_key,category,bin_label,preparation,source_url,
                     reviewed_on,version,condition_label,active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
                    (rule.region_id, rule.item_key, rule.category, rule.bin_label,
                     rule.preparation, rule.source_url, rule.reviewed_on, version,
                     rule.condition),
                )
                conn.commit()
                return cursor.lastrowid, version
            finally: conn.close()
        except Exception as exc:
            raise PersistenceError("Could not create rule revision") from exc

    def deactivate_rule(self, rule_id):
        try:
            conn = connect()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE recycling_rules SET active=0 WHERE id=%s", (rule_id,))
                conn.commit()
                return cursor.rowcount == 1
            finally: conn.close()
        except Exception as exc:
            raise PersistenceError("Could not deactivate rule") from exc

    def list_regions(self):
        try:
            conn = connect()
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, name, source_url FROM regions ORDER BY name")
                return [Region(**row) for row in cursor.fetchall()]
            finally: conn.close()
        except Exception as exc: raise PersistenceError("Could not read regions") from exc


def _rule(row):
    from datetime import date
    if isinstance(row["reviewed_on"], str): row["reviewed_on"] = date.fromisoformat(row["reviewed_on"])
    return RecyclingRule(id=row["id"], region_id=row["region_id"], item_key=row["item_key"],
        category=row["category"], bin_label=row["bin_label"], preparation=row["preparation"],
        source_url=row["source_url"], reviewed_on=row["reviewed_on"], version=row["version"],
        condition=row["condition_label"], active=bool(row["active"]))
