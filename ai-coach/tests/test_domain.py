"""15 focused unit tests for the capstone domain, streaming and errors."""
import unittest
from datetime import date
from unittest.mock import patch
from app.domain.models import Region, RecyclingRule, CoachExplanation
from app.domain.services import CoachProviderError, RegionalGuidanceService, RuleNotFoundError
from app.coach import OpenAICoach, EducationText
from app.domain.errors import InvalidGuidanceRequest, GuidanceUnavailable, PersistenceError
from app.streaming.pipeline import StreamProcessor, FilterProcessor, MapProcessor, Pipeline, EventStream


def rule(**overrides):
    values = dict(id=1, region_id="demo", item_key="can", category="recyclable",
        bin_label="Yellow bin", preparation="Empty it", source_url="https://example.org/rules",
        reviewed_on=date(2026, 11, 6), condition="any", version=1)
    values.update(overrides)
    return RecyclingRule(**values)

class Repo:
    def __init__(self, found=None):
        self.found = found
        self.saved = []
    def find_rule(self, region_id, item_key, condition="unknown"):
        if self.found and self.found.region_id == region_id and self.found.matches(item_key, condition): return self.found
        return None
    def save_decision(self, *decision):
        self.saved.append(decision)

class DomainTests(unittest.TestCase):
    def test_region_initializes_state(self):
        region = Region("demo", "Demo", "https://example.org")
        self.assertEqual(region.get_name(), "Demo")
    def test_region_rejects_empty_name(self):
        with self.assertRaises(ValueError): Region("demo", " ", "https://example.org")
    def test_region_rejects_non_http_source(self):
        with self.assertRaises(ValueError): Region("demo", "Demo", "file:///rules")
    def test_rule_rejects_unknown_category(self):
        with self.assertRaises(ValueError): rule(category="reusables")
    def test_rule_rejects_nonpositive_version(self):
        with self.assertRaises(ValueError): rule(version=0)
    def test_rule_matches_any_condition(self):
        self.assertTrue(rule().matches("can", "soiled"))
    def test_rule_rejects_different_item(self):
        self.assertFalse(rule().matches("battery"))
    def test_rule_can_be_disabled(self):
        self.assertFalse(rule(active=False).matches("can"))
    def test_explanation_enforces_100_words(self):
        with self.assertRaises(ValueError): CoachExplanation(1, "word " * 101)
    def test_service_returns_reviewed_rule(self):
        service = RegionalGuidanceService(Repo(rule()))
        self.assertEqual(service.get_guidance("demo", "can").bin_label, "Yellow bin")
    def test_service_missing_rule_is_explicit(self):
        with self.assertRaises(RuleNotFoundError): RegionalGuidanceService(Repo()).get_guidance("demo", "glass")
    def test_service_uses_fallback_without_ai(self):
        result = RegionalGuidanceService(Repo(rule())).explain(rule())
        self.assertTrue(result.is_fallback)
    def test_service_ignores_overlong_ai_text(self):
        service = RegionalGuidanceService(Repo(), educator=lambda _: "coach " * 101)
        self.assertTrue(service.explain(rule()).is_fallback)
    def test_service_ignores_blank_ai_text(self):
        service = RegionalGuidanceService(Repo(), educator=lambda _: "  ")
        self.assertTrue(service.explain(rule()).is_fallback)
    def test_service_falls_back_when_coach_provider_is_unavailable(self):
        def unavailable(_):
            raise CoachProviderError("provider unavailable")

        service = RegionalGuidanceService(Repo(), educator=unavailable)

        self.assertTrue(service.explain(rule()).is_fallback)

    @patch("app.coach.OpenAI")
    def test_openai_coach_uses_reviewed_rule_and_configured_model(self, factory):
        from types import SimpleNamespace
        client = factory.return_value.__enter__.return_value
        client.responses.parse.return_value = SimpleNamespace(
            status="completed", output_parsed=EducationText(explanation="Use the Yellow bin. Empty it."))
        text = OpenAICoach("test-key", model="gpt-4.1-mini")(rule())
        self.assertIn("Yellow bin", text)
        options = client.responses.parse.call_args.kwargs
        self.assertEqual(options["model"], "gpt-4.1-mini")
        self.assertFalse(options["store"])
        self.assertIn("Yellow bin", options["input"])
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)

    def test_service_records_the_selected_rule_version(self):
        repository = Repo(rule(version=3))
        service = RegionalGuidanceService(repository)
        result = service.decide_and_explain("demo", "can", "clean")

        service.record_decision("demo", "can", "clean", result["rule"])

        self.assertEqual(repository.saved, [("demo", "can", "clean", 1, 3)])
    def test_abstract_processor_cannot_be_instantiated(self):
        with self.assertRaises(TypeError): StreamProcessor()
    def test_pipeline_filters_maps_and_iterates(self):
        pipeline = FilterProcessor(lambda x: x["confidence"] >= .6) | MapProcessor(lambda x: x["item"].upper())
        self.assertEqual(list(EventStream([{"confidence": .9, "item": "can"}, {"confidence": .2, "item": "cup"}], pipeline)), ["CAN"])

if __name__ == "__main__": unittest.main()
