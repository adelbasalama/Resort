# datetime is used to parse the timestamp text from the CSV into a real date/time
from datetime import datetime

WASTE_TYPES = ["recyclable", "compostable", "landfill", "special"]


class Submission:
    """One scanned waste item (= one row in the CSV)."""

    def __init__(self, region, timestamp, waste_type, item_name):
        self.region = region.strip() or "Unknown"
        self.timestamp = datetime.fromisoformat(timestamp.strip())
        waste_type = waste_type.strip().lower()
        self.waste_type = waste_type if waste_type in WASTE_TYPES else "unknown"
        self.item_name = item_name.strip() or "Unknown item"

    def getItemName(self):
        return self.item_name

    def getWasteType(self):
        return self.waste_type

    def getDate(self):
        return self.timestamp.strftime("%Y-%m-%d")

    def getPeriod(self, period_type):
        if period_type == "year":
            return self.timestamp.strftime("%Y")
        if period_type == "week":
            return self.timestamp.strftime("%G-W%V")
        return self.timestamp.strftime("%Y-%m")