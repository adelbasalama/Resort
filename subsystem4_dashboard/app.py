import os
from pathlib import Path

from flask import Flask, jsonify, request

from dashboard.data_filter import DataFilter
from dashboard.submission_store import SubmissionStore
from dashboard.waste_data import WasteData


ROOT = Path(__file__).resolve().parent
app = Flask(__name__)


def load_data():
    csv_path = os.getenv("DASHBOARD_CSV_PATH")
    if csv_path:
        return WasteData(csv_path)
    path = os.getenv("DATABASE_PATH", str(ROOT.parent / "data/waste_sorting.sqlite3"))
    return SubmissionStore(path, include_demo=request.args.get("include_demo") == "1")


@app.get("/health")
def health():
    if load_data().error:
        return jsonify({"status": "error", "message": "Submission storage is unavailable."}), 503
    return jsonify({"status": "ok"})


@app.get("/api/stats")
def statistics():
    data = load_data()
    if data.error:
        return jsonify({"error": data.error}), 503
    return jsonify(data.get_statistics(DataFilter(
        region=request.args.get("region"),
        period_type=request.args.get("period_type", "month"),
        period_value=request.args.get("period"),
    )))


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5003")))
