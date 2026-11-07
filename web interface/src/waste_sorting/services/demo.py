"""Interface fixtures only. These are not image recognition or verified local rules."""
from ..models import GuidanceResult, RecognitionResult, Region

SAMPLES = {
    "can": {"name": "Drink can", "material": "Metal", "category": "Packaging", "bin": "Packaging collection",
            "steps": ["Empty the can completely.", "Check whether a deposit return applies first.",
                      "Confirm the accepted packaging with your local provider."]},
    "paper": {"name": "Paper bag", "material": "Paper", "category": "Paper", "bin": "Paper collection",
              "steps": ["Keep the paper clean and dry.", "Remove any non-paper handles or lining.",
                        "Confirm your local paper collection rules."]},
    "bottle": {"name": "Glass bottle", "material": "Glass", "category": "Glass", "bin": "Glass collection point",
               "steps": ["Check for a returnable deposit first.", "Empty the bottle.",
                         "Check your local colour-separated glass collection rules."]},
}


class DemoGuidanceClient:
    def regions(self):
        return [Region(id="dortmund", name="Dortmund", source_url="https://www.edg.de/"),
                Region(id="berlin", name="Berlin", source_url="https://www.bsr.de/"),
                Region(id="hamburg", name="Hamburg", source_url="https://www.stadtreinigung.hamburg/")]

    def guide(self, recognition, region_id):
        sample = SAMPLES[recognition.item_key]
        return GuidanceResult(submission_id=recognition.submission_id, region_id=region_id,
            status="missing_rule", category=sample["category"], bin_label=sample["bin"],
            preparation_steps=sample["steps"],
            explanation="This is an interface example. Actual disposal depends on deposit schemes, "
                        "item condition and your city's current rules. Connect subsystem C for verified local guidance.")


class DemoRecognitionClient:
    def __init__(self, sample_key=None):
        self.sample_key = sample_key

    def recognize(self, image, submission_id):
        if not self.sample_key:
            return RecognitionResult(submission_id=submission_id, status="uncertain", item_key="unknown",
                item_name="Your uploaded item", material="Unknown", condition="unknown", confidence=0)
        sample = SAMPLES[self.sample_key]
        return RecognitionResult(submission_id=submission_id, status="recognized", item_key=self.sample_key,
            item_name=sample["name"], material=sample["material"], condition="clean", confidence=.97, deposit="no")
