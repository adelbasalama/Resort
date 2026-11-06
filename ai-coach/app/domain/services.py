"""Use reviewed local rules as the decision source; AI only explains them."""
import logging

from .models import CoachExplanation

logger = logging.getLogger(__name__)


class RuleNotFoundError(LookupError):
    pass


class CoachProviderError(RuntimeError):
    """Raised by an educator adapter when coach generation is unavailable."""


class RegionalGuidanceService:
    def __init__(self, repository, educator=None):
        self.repository = repository
        self.educator = educator

    def get_guidance(self, region_id, item_key, condition="unknown"):
        rule = self.repository.find_rule(region_id, item_key, condition)
        if rule is None:
            raise RuleNotFoundError("No reviewed rule exists for this region and item")
        return rule

    def explain(self, rule):
        fallback = "Place this item in the %s. %s Check the cited local guidance for the latest instructions." % (
            rule.bin_label, rule.preparation)
        text, is_fallback = fallback, True
        if self.educator:
            try:
                proposed = self.educator(rule)
                if isinstance(proposed, str):
                    proposed = proposed.strip()
                    if proposed and len(proposed.split()) <= 100:
                        text, is_fallback = proposed, False
            except CoachProviderError:
                logger.exception("Coach provider failed; using reviewed fallback")
        return CoachExplanation(rule_id=rule.id, text=text, is_fallback=is_fallback)

    def decide_and_explain(self, region_id, item_key, condition="unknown"):
        rule = self.get_guidance(region_id, item_key, condition)
        return {"rule": rule, "explanation": self.explain(rule)}

    def record_decision(self, region_id, item_key, condition, rule,
                        recognition_id=None, recognition_confidence=None, image_ref=None):
        """Persist the exact reviewed rule version used for a decision."""
        if recognition_id is None and recognition_confidence is None and image_ref is None:
            self.repository.save_decision(region_id, item_key, condition, rule.id, rule.version)
            return
        self.repository.save_decision(
            region_id, item_key, condition, rule.id, rule.version,
            recognition_id, recognition_confidence, image_ref
        )
