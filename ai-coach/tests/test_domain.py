"""15 focused unit tests for the capstone domain, streaming and errors."""
import unittest
from datetime import date
from unittest.mock import patch
from app.domain.models import Region, RecyclingRule, CoachExplanation
from app.domain.services import CoachProviderError, RegionalGuidanceService, RuleNotFoundError
from app.coach import GeminiCoach
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

    @patch("app.coach.request.urlopen")
    def test_gemini_coach_uses_configured_model(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.__enter__.return_value = response
        response.__enter__.return_value.__iter__ = None
        response.read.return_value = b'{"candidates":[{"content":{"parts":[{"text":"Use the yellow bin."}]}}]}'

        # json.load reads the mocked response stream; use a real JSON response shape.
        response.__enter__.return_value.read.return_value = (
            b'{"candidates":[{"content":{"parts":[{"text":"Use the yellow bin."}]}}]}'
        )
        coach = GeminiCoach("test-key", model="gemini-2.5-flash-lite")

        with patch("app.coach.json.load", return_value={
            "candidates": [{"content": {"parts": [{"text": "Use the yellow bin."}]}}]
        }):
            text = coach(rule())

        self.assertEqual(text, "Use the yellow bin.")
        sent_request = urlopen.call_args.args[0]
        self.assertIn("gemini-2.5-flash-lite:generateContent", sent_request.full_url)
        self.assertEqual(sent_request.headers["X-goog-api-key"], "test-key")
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
