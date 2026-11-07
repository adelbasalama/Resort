# datetime is used to parse the timestamp text from the CSV into a real date/time
from datetime import datetime, timezone

WASTE_TYPES = ["recyclable", "compostable", "landfill", "special"]


class Submission:
    """One scanned waste item from a submission database or CSV."""

    def __init__(self, region, timestamp, waste_type, item_name):
        self.region = region
        self.timestamp = timestamp
        self.waste_type = waste_type
        self.item_name = item_name

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = value.strip() or "Unknown"

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        timestamp = datetime.fromisoformat(value.strip()) if isinstance(value, str) else value
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be ISO text or a datetime")
        # Compare legacy naive CSV times and UTC/offset-aware stored times safely.
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        self._timestamp = timestamp.astimezone(timezone.utc)

    @property
    def waste_type(self):
        return self._waste_type

    @waste_type.setter
    def waste_type(self, value):
        waste_type = value.strip().lower()
        self._waste_type = waste_type if waste_type in WASTE_TYPES else "unknown"

    @property
    def item_name(self):
        return self._item_name

    @item_name.setter
    def item_name(self, value):
        self._item_name = value.strip() or "Unknown item"

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
