import sys
from pathlib import Path

import pytest

# Make the "dashboard" package importable when running pytest from any folder
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.data_filter import DataFilter
from dashboard.submission import Submission
from dashboard.waste_data import WasteData


# Helper: write a temporary CSV file with the standard header and the given rows
def make_csv(tmp_path, lines):
    path = tmp_path / "test.csv"
    path.write_text("region,timestamp,waste_type,item_name\n" + "\n".join(lines), encoding="utf-8")
    return path


# ---------- WasteData ----------

# The original bug: one item must not show 25% of every type
def test_single_item_gives_100_percent(tmp_path):
    path = make_csv(tmp_path, ["Berlin,2026-10-01 10:00:00,recyclable,Bottle"])
    stats = WasteData(path).get_statistics(DataFilter())
    assert stats["total"] == 1
    assert stats["counts"] == {"recyclable": 1}
    assert stats["recycling_rate"] == "100.0%"


# A waste type that is not in WASTE_TYPES must show up as "unknown", not disappear
def test_unknown_type_is_visible(tmp_path):
    path = make_csv(tmp_path, ["Berlin,2026-10-01 10:00:00,plastic,Bottle"])
    assert WasteData(path).get_statistics(DataFilter())["counts"] == {"unknown": 1}


# Region filter ignores upper/lower case, period filter matches the exact period label
def test_region_and_period_filter(tmp_path):
    path = make_csv(tmp_path, [
        "Berlin,2026-10-01 10:00:00,landfill,Bag",
        "Hamburg,2026-10-02 10:00:00,landfill,Bag",
        "Berlin,2025-01-02 10:00:00,special,Battery",
    ])
    data = WasteData(path)
    assert data.get_statistics(DataFilter(region="berlin"))["total"] == 2
    assert data.get_statistics(DataFilter(region="Berlin", period_type="year", period_value="2026"))["total"] == 1
    assert data.get_periods("year", region="Hamburg") == ["2026"]


# A missing file must not crash, it sets an error message and gives empty statistics
def test_missing_file_does_not_crash(tmp_path):
    data = WasteData(tmp_path / "missing.csv")
    assert data.error is not None
    assert data.get_statistics(DataFilter())["total"] == 0


# Spaces and upper case in the CSV must not turn a known type into "unknown"
def test_waste_type_is_normalized(tmp_path):
    path = make_csv(tmp_path, ["Berlin,2026-10-01 10:00:00, Recyclable ,Bottle"])
    assert WasteData(path).get_statistics(DataFilter())["counts"] == {"recyclable": 1}


# One invalid timestamp must not crash the load: the row is skipped and counted
def test_bad_rows_are_skipped(tmp_path):
    path = make_csv(tmp_path, ["Berlin,not-a-date,landfill,Bag", "Berlin,2026-10-01 10:00:00,landfill,Bag"])
    data = WasteData(path)
    assert data.skipped_rows == 1
    assert len(data.submissions) == 1

# Region and item name are cleaned, empty values get a readable placeholder
def test_submission_cleans_region_and_item():
    s = Submission("  Berlin ", "2026-10-31 08:15:00", "landfill", "  ")
    assert s.region == "Berlin"
    assert s.item_name == "Unknown item"

# ---------- Submission ----------

# The getter methods return the values of the row
def test_submission_getters():
    s = Submission("Berlin", "2026-10-31 08:15:00", "landfill", "Bag")
    assert s.getItemName() == "Bag"
    assert s.getWasteType() == "landfill"
    assert s.getDate() == "2026-10-31"


# The three period types give the expected labels
def test_submission_periods():
    s = Submission("Berlin", "2026-10-31 08:15:00", "landfill", "Bag")
    assert s.getPeriod("year") == "2026"
    assert s.getPeriod("month") == "2026-10"
    assert s.getPeriod("week") == "2026-W44"


# Around New Year the week label must use the ISO year (2024-12-30 belongs to week 1 of 2025)
def test_week_uses_iso_year():
    s = Submission("Berlin", "2024-12-30 12:00:00", "landfill", "Bag")
    assert s.getPeriod("week") == "2025-W01"


# ---------- DataFilter ----------

# An unknown period type falls back to "month"
def test_filter_invalid_period_type_falls_back():
    assert DataFilter(period_type="decade").period_type == "month"


# Empty strings from the HTML form mean "no filter", so every submission matches
def test_filter_empty_strings_mean_no_filter():
    s = Submission("Berlin", "2026-10-31 08:15:00", "landfill", "Bag")
    data_filter = DataFilter(region="", period_value="")
    assert data_filter.region is None
    assert data_filter.period_value is None
    assert data_filter.matches(s)