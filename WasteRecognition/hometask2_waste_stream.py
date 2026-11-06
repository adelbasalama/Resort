"""HomeTask2: stream processors that produce HomeTask1 recognition objects."""

from abc import ABC, abstractmethod
from hometask1_waste_recognition import WasteItemType, attempt_from_dict


class StreamProcessor(ABC):
    """Processors return a result dictionary, or None to discard an event."""

    @abstractmethod
    def process(self, event):
        pass

    def __add__(self, other):
        if not isinstance(other, StreamProcessor):
            return NotImplemented
        return Pipeline(self, other)

    def run(self, events):
        for event in events:
            result = self.process(event)
            if result is not None:
                yield result


class ConfidenceFilter(StreamProcessor):
    def __init__(self, threshold=0.80):
        if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                or not 0 <= threshold <= 1):
            raise ValueError("Threshold must be a number between 0 and 1.")
        self.threshold = threshold

    def process(self, event):
        if not isinstance(event, dict):
            raise ValueError("Send a JSON object.")
        confidence = event.get("confidence")
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1):
            raise ValueError("confidence must be a number between 0 and 1.")
        if confidence >= self.threshold:
            return event
        return None


class MaterialTransformer(StreamProcessor):
    def __init__(self):
        self.material_tags = {
            "pet": "PET", "hdpe": "HDPE",
            "aluminum": "Aluminum", "aluminium": "Aluminum",
        }
        self.items = [
            WasteItemType("plastic_bottle", "Plastic bottle", ["bottle", "water bottle"]),
            WasteItemType("plastic_container", "Plastic container", ["container", "detergent container"]),
            WasteItemType("beverage_can", "Beverage can", ["can", "soda can", "drink can"]),
        ]

    def process(self, event):
        if not isinstance(event, dict):
            raise ValueError("Send a JSON object.")
        tags = event.get("visual_tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError("visual_tags must be a list of strings.")
        label = event.get("item_label", event.get("item_key", ""))
        if not isinstance(label, str):
            raise ValueError("item_label must be text.")

        materials = set()
        for tag in tags:
            material = self.material_tags.get(tag.strip().lower())
            if material is not None:
                materials.add(material)

        item_key = ""
        for item in self.items:
            if item.matches(label):
                item_key = item.get_item_key()
                break

        if not materials:
            material, status = "Unknown", "unsupported"
        elif len(materials) > 1:
            material, status = "Unknown", "uncertain"
        else:
            material = materials.pop()
            status = "recognized" if item_key else "uncertain"

        data = event.copy()
        data.update(item_key=item_key, material=material, status=status)
        # The domain class calculates the route from the final facts.
        data.pop("routing_code", None)
        attempt = attempt_from_dict(data)
        return attempt.to_dict()


class Pipeline(StreamProcessor):
    def __init__(self, first, second):
        self.first = first
        self.second = second

    def process(self, event):
        result = self.first.process(event)
        if result is None:
            return None
        return self.second.process(result)


class EventStream:
    def __init__(self, events):
        self.source = iter(events)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.source)


def demo_events():
    """Sample predictions. IDs are supplied here so the examples are repeatable."""
    yield {"attempt_id": "attempt_001", "submission_id": "submission_001",
           "model_id": "demo_model", "confidence": 0.95,
           "item_label": "water bottle", "visual_tags": ["PET"], "condition": "clean"}
    yield {"attempt_id": "attempt_002", "submission_id": "submission_002",
           "model_id": "demo_model", "confidence": 0.60,
           "item_label": "soda can", "visual_tags": ["aluminum"]}
    yield {"attempt_id": "attempt_003", "submission_id": "submission_003",
           "model_id": "demo_model", "confidence": 0.90,
           "item_label": "container", "visual_tags": ["HDPE"]}
    yield {"attempt_id": "attempt_004", "submission_id": "submission_004",
           "model_id": "demo_model", "confidence": 0.88,
           "item_label": "soda can", "visual_tags": ["aluminium"]}
    yield {"attempt_id": "attempt_005", "submission_id": "submission_005",
           "model_id": "demo_model", "confidence": 0.92,
           "item_label": "glass jar", "visual_tags": ["glass"]}
    yield {"attempt_id": "attempt_006", "submission_id": "submission_006",
           "model_id": "demo_model", "confidence": 0.94,
           "item_label": "bottle", "visual_tags": ["PET", "HDPE"]}


if __name__ == "__main__":
    pipeline = ConfidenceFilter(0.80) + MaterialTransformer()
    for result in pipeline.run(EventStream(demo_events())):
        print(f"{result['attempt_id']}: {result['material']}, "
              f"status={result['status']}, route={result['routing_code']}")
