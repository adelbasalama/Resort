from pathlib import Path
import json
import os
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Flask, render_template, request, jsonify, Response
from plotly.offline import get_plotlyjs

# Our own classes: chart creation, filter settings, and CSV loading + statistics
from dashboard.charts import ChartGenerator
from dashboard.data_filter import DataFilter
from dashboard.waste_data import WasteData
from dashboard.submission_store import SubmissionStore, load_submission_records

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
PAGE_SIZE = 25
CATEGORIES = {"recyclable": "Recyclable", "compostable": "Compostable", "landfill": "Residual waste",
              "special": "Special handling", "unknown": "Unknown"}


def database_path():
    return os.getenv("DATABASE_PATH", str(ROOT.parent / "data/waste_sorting.sqlite3"))


@app.template_filter("region_name")
def region_name(value):
    if value == "luenen":
        return "Lünen"
    if value.startswith("demo-"):
        return f"{value[5:].replace('-', ' ').title()} (demo)"
    return value.title()


@app.context_processor
def navigation_context():
    return {"demo_filter": {"include_demo": 1} if request.args.get("include_demo") == "1" else {},
            "category_labels": CATEGORIES}


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
    return SubmissionStore(database_path(), include_demo=include_demo)


@app.get("/submissions")
def submissions():
    include_demo = request.args.get("include_demo") == "1"
    records, skipped, error = load_submission_records(database_path(), include_demo)
    regions = sorted({row["region"] for row in records}, key=region_name)
    region = request.args.get("region", "")
    query = request.args.get("q", "").strip()[:100]
    matches = [row for row in records if (not region or row["region"] == region)
               and (not query or query.casefold() in row["item_name"].casefold())]
    pages = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(pages, max(1, request.args.get("page", 1, type=int)))
    start = (page - 1) * PAGE_SIZE
    return render_template("submissions.html", records=matches[start:start + PAGE_SIZE],
                           regions=regions, region=region, query=query, total=len(matches),
                           page=page, pages=pages, include_demo=include_demo,
                           skipped_rows=skipped, error=error), 503 if error else 200


@app.get("/region-rules")
def region_rules():
    base_url = os.getenv("GUIDANCE_API_URL", "http://127.0.0.1:5002").rstrip("/")
    selected_id = request.args.get("region", "")[:100]
    try:
        with urlopen(f"{base_url}/v1/rules?{urlencode({'region_id': selected_id})}", timeout=4) as response:
            catalog = json.load(response)
        regions, selected, rules = catalog["regions"], catalog["selected"], catalog["rules"]
        if not isinstance(regions, list) or not isinstance(rules, list) or (selected is not None and not isinstance(selected, dict)):
            raise ValueError("Invalid regional catalogue")
    except (URLError, OSError, ValueError, KeyError, TypeError):
        app.logger.exception("Could not load the regional rules catalogue")
        return render_template("region_rules.html", regions=[], selected=None, rules=[],
                               error="Region rules are unavailable. Try refreshing once the guidance service is running."), 503
    return render_template("region_rules.html", regions=regions, selected=selected, rules=rules)


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
