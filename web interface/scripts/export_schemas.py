"""Export the authoritative shared models for teammates implementing B, C and D."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from waste_sorting.models import Feedback, GuidanceResult, RecognitionResult, Region, Submission

output = root / "docs" / "schemas"
output.mkdir(exist_ok=True)
for model in [Region, RecognitionResult, GuidanceResult, Submission, Feedback]:
    (output / f"{model.__name__}.json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
print(f"Exported 5 JSON schemas to {output}")
