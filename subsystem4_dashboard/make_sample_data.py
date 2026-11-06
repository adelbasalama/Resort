"""Creates a sample submissions.csv. Run once: python make_sample_data.py"""
import csv
import random
from datetime import datetime, timedelta

random.seed(1)
ITEMS = {
    "recyclable": ["Plastic bottle", "Glass jar", "Cardboard box", "Tin can"],
    "compostable": ["Banana peel", "Coffee grounds", "Apple core"],
    "landfill": ["Chip bag", "Diaper", "Broken mug"],
    "special": ["Battery", "Light bulb", "Paint can"],
}
REGIONS = ["Berlin", "Hamburg", "Munich"]

start = datetime(2026, 9, 1)
with open("submissions.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["region", "timestamp", "waste_type", "item_name"])
    for _ in range(300):
        waste_type = random.choice(list(ITEMS))
        when = start + timedelta(days=random.randint(0, 60), hours=random.randint(7, 20),
                                 minutes=random.randint(0, 59))
        writer.writerow([random.choice(REGIONS), when.isoformat(sep=" "),
                         waste_type, random.choice(ITEMS[waste_type])])
