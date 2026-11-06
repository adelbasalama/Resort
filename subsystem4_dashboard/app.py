from pathlib import Path

from flask import Flask, render_template, request

# Our own classes: chart creation, filter settings, and CSV loading + statistics
from dashboard.charts import ChartGenerator
from dashboard.data_filter import DataFilter
from dashboard.waste_data import WasteData

app = Flask(__name__)


@app.route("/")
def index():
    """Show the dashboard, filtered by the URL (?region=...&period_type=...&period=...)."""
    data = WasteData("submissions.csv")

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
    )



if __name__ == "__main__":
    app.run(debug=True)