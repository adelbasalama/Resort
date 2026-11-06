class DataFilter:
    """Stores the user's choice of region and time period."""

    PERIOD_TYPES = ["month", "year", "week"]

    def __init__(self, region=None, period_type="month", period_value=None):
        self.region = region or None
        self.period_value = period_value or None
        self.period_type = period_type if period_type in self.PERIOD_TYPES else "month"

    def matches(self, submission):
        if self.region and submission.region.lower() != self.region.lower():
            return False
        if self.period_value and submission.getPeriod(self.period_type) != self.period_value:
            return False
        return True