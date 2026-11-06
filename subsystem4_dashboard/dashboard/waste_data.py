# csv: reads the CSV file row by row into dictionaries
import csv
from collections import Counter

from dashboard.submission import Submission


class WasteData:
    """Loads the CSV and calculates the statistics for the dashboard."""

    def __init__(self, data_path):
        self.data_path = data_path
        self.submissions = []
        self.error = None
        self.skipped_rows = 0
        self.load()

    def load(self):
        self.submissions = []
        self.skipped_rows = 0
        self.error = None

        try:
            with open(self.data_path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    try:
                        self.submissions.append(
                            Submission(
                                region=row.get("region") or "",
                                timestamp=row.get("timestamp") or "",
                                waste_type=row.get("waste_type") or "",
                                item_name=row.get("item_name") or "",
                            )
                        )
                    except ValueError: 
                        self.skipped_rows += 1
                        self.error = f"Skiped Rows: {self.skipped_rows}"
        except FileNotFoundError:
            self.error = f"File not found: {self.data_path}"

    def get_regions(self):
        return sorted({s.region for s in self.submissions})

    def get_periods(self, period_type, region=None):
        periods = set()
        for s in self.submissions:
            if region is None or s.region.lower() == region.lower():
                periods.add(s.getPeriod(period_type))
        return sorted(periods, reverse=True)

    def get_filtered_submissions(self, data_filter):
        return [s for s in self.submissions if data_filter.matches(s)]

    def get_statistics(self, data_filter):
        filtered = self.get_filtered_submissions(data_filter)
        total = len(filtered)

        counts = Counter(s.getWasteType() for s in filtered)
        item_counts = Counter(s.getItemName() for s in filtered)
        daily_counts = Counter(s.getDate() for s in filtered)

        recycling_rate = counts["recyclable"] / total * 100 if total > 0 else 0

        latest = sorted(filtered, key=lambda s: s.timestamp, reverse=True)[:50]

        return {
            "total": total,
            "recycling_rate": f"{recycling_rate:.1f}%",
            "counts": dict(counts),
            "top_items": item_counts.most_common(10),
            "daily": sorted(daily_counts.items()),
            "rows": [
                {
                    "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "item_name": s.item_name,
                    "waste_type": s.waste_type,
                }
                for s in latest
            ],
        }