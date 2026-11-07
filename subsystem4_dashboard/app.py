from pathlib import Path
import os

from flask import Flask, render_template, request, jsonify, Response
from plotly.offline import get_plotlyjs

# Our own classes: chart creation, filter settings, and CSV loading + statistics
from dashboard.charts import ChartGenerator
from dashboard.data_filter import DataFilter
from dashboard.waste_data import WasteData
from dashboard.submission_store import SubmissionStore

app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent / "templates"))


@app.get("/health")
def health():
    if load_data().error:
        return jsonify({"status": "error", "message": "Submission storage is unavailable."}), 503
    return jsonify({"status": "ok"})


def load_data():
    include_demo = request.args.get("include_demo") == "1"
    csv_path = os.getenv("DASHBOARD_CSV_PATH")
    if csv_path:
        return WasteData(csv_path)
    path = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parents[1] / "data/waste_sorting.sqlite3"))
    return SubmissionStore(path, include_demo=include_demo)


@app.get("/api/stats")
def statistics():
    data = load_data()
    if data.error:
        return jsonify({"error": data.error}), 503
    return jsonify(data.get_statistics(DataFilter(
        region=request.args.get("region"), period_type=request.args.get("period_type", "month"),
        period_value=request.args.get("period"))))


@app.get("/static/plotly.js")
def plotly_script():
    response = Response(get_plotlyjs(), mimetype="application/javascript")
    response.cache_control.max_age = 86400
    return response


@app.route("/")
def index():
    """Show the dashboard, filtered by the URL (?region=...&period_type=...&period=...)."""
    data = load_data()

    data_filter = DataFilter(
        region=request.args.get("region"),
        period_type=request.args.get("period_type", "month"),
        period_value=request.args.get("period"),
    )

    regions = data.get_regions()
    periods = data.get_periods(data_filter.period_type, data_filter.region)
    stats = data.get_statistics(data_filter)

    charts = ChartGenerator()

    return render_template(
        "index.html",
        regions=regions,                        
        region=data_filter.region,              
        period_types=DataFilter.PERIOD_TYPES,   
        period_type=data_filter.period_type,    
        periods=periods,                        
        period=data_filter.period_value,        
        stats=stats,                            
        pie_chart=charts.composition_pie(stats["counts"]),      
        top_chart=charts.top_items_bar(stats["top_items"]),    
        line_chart=charts.daily_line(stats["daily"]),           
        skipped_rows=data.skipped_rows,        
        error=data.error,                     
        include_demo=request.args.get("include_demo") == "1",
    )



if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5003")), debug=False)
