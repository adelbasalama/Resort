import os
from datetime import date

from flask import Flask, jsonify, request
from mysql.connector import Error

from app.db import MySQLRuleRepository


def create_app():
    app = Flask(__name__)
    repository = MySQLRuleRepository()

    @app.get("/v1/regions")
    def regions():
        return jsonify(regions=repository.list_regions())

    @app.get("/v1/rules")
    def rules():
        region_id = request.args.get("region_id", "").strip()
        if not region_id:
            return jsonify(error="region_id is required"), 400
        records = repository.list_active_rules(region_id)
        for record in records:
            reviewed_on = record["reviewed_on"]
            if isinstance(reviewed_on, date):
                record["reviewed_on"] = reviewed_on.isoformat()
        return jsonify(region_id=region_id, rules=records)

    @app.errorhandler(Error)
    def database_error(error):
        app.logger.error("MySQL query failed: %s", error)
        return jsonify(error="Rules database unavailable"), 503

    return app


if __name__ == "__main__":
    create_app().run(host=os.getenv("HOST", "127.0.0.1"), port=5000)
