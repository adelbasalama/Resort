class DataFilter:
    """Stores the user's choice of region and time period."""

    PERIOD_TYPES = ["month", "year", "week"]

    def __init__(self, region=None, period_type="month", period_value=None):
        self.region = region
        self.period_value = period_value
        self.period_type = period_type

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = value or None

    @property
    def period_value(self):
        return self._period_value

    @period_value.setter
    def period_value(self, value):
        self._period_value = value or None

    @property
    def period_type(self):
        return self._period_type

    @period_type.setter
    def period_type(self, value):
        self._period_type = value if value in self.PERIOD_TYPES else "month"

    def matches(self, submission):
        if self.region and submission.region.lower() != self.region.lower():
            return False
        if self.period_value and submission.getPeriod(self.period_type) != self.period_value:
            return False
        return True
