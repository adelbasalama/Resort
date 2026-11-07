"""Read regional waste data from MySQL."""

import os

import mysql.connector


class MySQLRuleRepository:
    def list_regions(self):
        return self._select("SELECT id, name, source_url FROM regions ORDER BY name, id")

    def list_active_rules(self, region_id):
        return self._select(
            """SELECT item_key, category, bin_label, preparation, source_url,
                      reviewed_on, version, condition_label
               FROM recycling_rules WHERE region_id = %s AND active = 1
               ORDER BY item_key, condition_label""",
            (region_id,),
        )

    def _select(self, query, params=()):
        with mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "capstone"),
            password=os.getenv("MYSQL_PASSWORD", "capstone_dev"),
            database=os.getenv("MYSQL_DATABASE", "waste_assistant"),
            connection_timeout=5,
        ) as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
