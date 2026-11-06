"""HomeTask1: shared domain classes for waste recognition."""

from uuid import uuid4

# These names and demonstration routes are shared by all three homeworks.
MATERIAL_ROUTES = {
    "PET": "LANE_1",
    "HDPE": "LANE_2",
    "Aluminum": "LANE_3",
    "Unknown": "REVIEW",
}


class WasteItemType:
    """A standard waste item and its alternative names."""

    def __init__(self, item_key, name, synonyms=None):
        self.__item_key = item_key
        self.__name = name
        self.initialize_synonyms(synonyms)

    def initialize_synonyms(self, synonyms=None):
        self.set_synonyms([] if synonyms is None else synonyms)

    def get_item_key(self):
        return self.__item_key

    def set_item_key(self, item_key):
        self.__item_key = item_key

    def get_name(self):
        return self.__name

    def set_name(self, name):
        self.__name = name

    def get_synonyms(self):
        return self.__synonyms.copy()

    def set_synonyms(self, synonyms):
        self.__synonyms = synonyms.copy()

    def matches(self, label):
        if not isinstance(label, str):
            return False
        names = [self.__item_key, self.__name] + self.__synonyms
        return any(label.strip().lower() == name.strip().lower() for name in names)


class RecognitionResult:
    """Stores recognition facts and derives the demonstration routing code."""

    def __init__(self, status="uncertain", material="Unknown", special=False,
                 item_key="", condition="unknown", confidence=0.0):
        self.__status = status
        self.__material = material
        self.__special = special
        self.__item_key = item_key
        self.__condition = condition
        self.__confidence = confidence

    def get_status(self):
        return self.__status

    def set_status(self, status):
        self.__status = status

    def get_material(self):
        return self.__material

    def set_material(self, material):
        self.__material = material

    def get_special(self):
        return self.__special

    def set_special(self, special):
        self.__special = special

    def get_item_key(self):
        return self.__item_key

    def set_item_key(self, item_key):
        self.__item_key = item_key

    def get_condition(self):
        return self.__condition

    def set_condition(self, condition):
        self.__condition = condition

    def get_confidence(self):
        return self.__confidence

    def set_confidence(self, confidence):
        self.__confidence = confidence

    def get_routing_code(self):
        # Routing is calculated, so it cannot contradict status or material.
        if self.__status != "recognized" or self.__special:
            return "REVIEW"
        return MATERIAL_ROUTES.get(self.__material, "REVIEW")

    def validate(self):
        if self.__status not in ("recognized", "uncertain", "unsupported"):
            return False
        if self.__material not in tuple(MATERIAL_ROUTES):
            return False
        if not isinstance(self.__special, bool):
            return False
        if not isinstance(self.__item_key, str) or len(self.__item_key) > 100:
            return False
        if self.__item_key != self.__item_key.strip():
            return False
        if self.__condition not in ("clean", "soiled", "unknown"):
            return False
        if (isinstance(self.__confidence, bool)
                or not isinstance(self.__confidence, (int, float))
                or not 0 <= self.__confidence <= 1):
            return False
        if self.__status == "recognized":
            return bool(self.__item_key) and self.__material != "Unknown"
        if self.__status == "unsupported":
            return self.__material == "Unknown"
        return True

    def to_dict(self):
        return {
            "item_key": self.__item_key,
            "material": self.__material,
            "confidence": self.__confidence,
            "status": self.__status,
            "condition": self.__condition,
            "special": self.__special,
            "routing_code": self.get_routing_code(),
        }


class RecognitionAttempt:
    """Links a string attempt ID, submission and model to one result."""

    def __init__(self, attempt_id, submission_id, model_id):
        self.__id = attempt_id
        self.__submission_id = submission_id
        self.__model_id = model_id
        self.__result = None

    def get_id(self):
        return self.__id

    def set_id(self, attempt_id):
        self.__id = attempt_id

    def get_submission_id(self):
        return self.__submission_id

    def set_submission_id(self, submission_id):
        self.__submission_id = submission_id

    def get_model_id(self):
        return self.__model_id

    def set_model_id(self, model_id):
        self.__model_id = model_id

    def get_result(self):
        return self.__result

    def set_result(self, result):
        self.record_outcome(result)

    def record_outcome(self, result):
        if not isinstance(result, RecognitionResult) or not result.validate():
            raise ValueError("Invalid result. Check material, item_key, confidence, status, condition and special.")
        self.__result = result

    def validate(self):
        for value in (self.__id, self.__submission_id, self.__model_id):
            if not isinstance(value, str) or not 1 <= len(value) <= 100:
                return False
            if value != value.strip():
                return False
        # Attempt IDs are also used in URLs.
        if not all(char.isascii() and (char.isalnum() or char in "_-") for char in self.__id):
            return False
        return isinstance(self.__result, RecognitionResult) and self.__result.validate()

    def to_dict(self):
        if not self.validate():
            raise ValueError("A valid attempt and result are required.")
        data = {
            "attempt_id": self.__id,
            "submission_id": self.__submission_id,
            "model_id": self.__model_id,
        }
        data.update(self.__result.to_dict())
        return data


def attempt_from_dict(data):
    """One shared conversion and validation function for stream and API input."""
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object.")
    result = RecognitionResult(
        status=data.get("status", "recognized"),
        material=data.get("material", "Unknown"),
        special=data.get("special", False),
        item_key=data.get("item_key", ""),
        condition=data.get("condition", "unknown"),
        confidence=data.get("confidence"),
    )
    attempt = RecognitionAttempt(
        data.get("attempt_id", str(uuid4())),
        data.get("submission_id"),
        data.get("model_id"),
    )
    attempt.record_outcome(result)
    if not attempt.validate():
        raise ValueError("Valid attempt_id, submission_id and model_id are required (1 to 100 characters). Attempt IDs use letters, numbers, _ or -.")
    if "routing_code" in data and data["routing_code"] != result.get_routing_code():
        raise ValueError("routing_code does not match the result.")
    return attempt


def demo():
    item = WasteItemType("beverage_can", "Beverage can", ["soda can", "drink can"])
    attempt = RecognitionAttempt("attempt_004", "submission_004", "demo_model")
    if item.matches("Soda can"):
        result = RecognitionResult(
            status="recognized", material="Aluminum", special=False,
            item_key=item.get_item_key(), condition="unknown", confidence=0.88,
        )
        attempt.record_outcome(result)
        print(attempt.to_dict())


if __name__ == "__main__":
    demo()
