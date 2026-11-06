"""Domain objects for subsystem C: regional recycling guidance."""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Region:
    id: str
    name: str
    source_url: str

    def __post_init__(self):
        self.set_id(self.id)
        self.set_name(self.name)
        self.set_source_url(self.source_url)

    def get_id(self): return self.id
    def set_id(self, value):
        value = str(value).strip()
        if not value: raise ValueError("Region id is required")
        self.id = value
    def get_name(self): return self.name
    def set_name(self, value):
        value = str(value).strip()
        if not value: raise ValueError("Region name is required")
        self.name = value
    def get_source_url(self): return self.source_url
    def set_source_url(self, value):
        value = str(value).strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("Region source must be an HTTP(S) URL")
        self.source_url = value


@dataclass
class RecyclingRule:
    region_id: str
    item_key: str
    category: str
    bin_label: str
    preparation: str
    source_url: str
    reviewed_on: date
    id: int = 0
    version: int = 1
    condition: str = "any"
    active: bool = True

    def __post_init__(self):
        if int(self.id) < 0: raise ValueError("id cannot be negative")
        self.id = int(self.id)
        self.set_region_id(self.region_id)
        self.set_item_key(self.item_key)
        self.set_category(self.category)
        self.set_bin_label(self.bin_label)
        self.set_preparation(self.preparation)
        self.set_source_url(self.source_url)
        self.set_version(self.version)
        self.set_condition(self.condition)

    def get_region_id(self): return self.region_id
    def set_region_id(self, value): self.region_id = _required(value, "region_id")
    def get_item_key(self): return self.item_key
    def set_item_key(self, value): self.item_key = _required(value, "item_key")
    def get_category(self): return self.category
    def set_category(self, value):
        if value not in ("recyclable", "compostable", "landfill", "special"):
            raise ValueError("Unsupported disposal category")
        self.category = value
    def get_bin_label(self): return self.bin_label
    def set_bin_label(self, value): self.bin_label = _required(value, "bin_label")
    def get_preparation(self): return self.preparation
    def set_preparation(self, value): self.preparation = _required(value, "preparation")
    def get_source_url(self): return self.source_url
    def set_source_url(self, value):
        value = _required(value, "source_url")
        if not value.startswith(("https://", "http://")):
            raise ValueError("Rule source must be an HTTP(S) URL")
        self.source_url = value
    def get_version(self): return self.version
    def set_version(self, value):
        if int(value) < 1: raise ValueError("Rule version must be positive")
        self.version = int(value)
    def get_condition(self): return self.condition
    def set_condition(self, value):
        if value not in ("any", "clean", "soiled", "unknown"):
            raise ValueError("Unsupported item condition")
        self.condition = value
    def matches(self, item_key, condition="unknown"):
        return (self.active and self.item_key == item_key and
                self.condition in ("any", condition, "unknown"))


@dataclass
class CoachExplanation:
    rule_id: int
    text: str
    is_fallback: bool = False

    def __post_init__(self):
        self.set_rule_id(self.rule_id)
        self.set_text(self.text)
    def get_rule_id(self): return self.rule_id
    def set_rule_id(self, value):
        if int(value) < 1: raise ValueError("rule_id must be positive")
        self.rule_id = int(value)
    def get_text(self): return self.text
    def set_text(self, value):
        value = _required(value, "text")
        if len(value.split()) > 100: raise ValueError("Coach explanation must be at most 100 words")
        self.text = value
    def within_limit(self): return len(self.text.split()) <= 100


def _required(value, name):
    value = str(value).strip()
    if not value: raise ValueError("%s is required" % name)
    return value
