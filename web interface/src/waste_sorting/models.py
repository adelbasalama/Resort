from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def utc_now():
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Region(Contract):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    source_url: HttpUrl


class RecognitionResult(Contract):
    submission_id: str
    status: Literal["recognized", "uncertain", "unsupported"]
    item_key: str = Field(min_length=1, max_length=100)
    item_name: str = Field(min_length=1, max_length=150)
    material: str = Field(min_length=1, max_length=100)
    condition: Literal["clean", "soiled", "unknown"]
    confidence: float = Field(ge=0, le=1)
    special: bool = False
    predicted_category: Literal["recyclable", "compostable", "landfill", "special", "unknown"] = "unknown"
    deposit: Literal["yes", "no", "unknown"] = "unknown"


class GuidanceResult(Contract):
    submission_id: str
    region_id: str
    status: Literal["matched", "missing_rule", "special"]
    category: str = Field(min_length=1, max_length=100)
    bin_label: str = Field(min_length=1, max_length=150)
    preparation_steps: list[str] = Field(max_length=20)
    explanation: str = Field(max_length=2000)
    source_url: HttpUrl | None = None
    reviewed_at: str | None = None
    rule_version: int | None = Field(default=None, ge=1)
    is_fallback: bool = False
    is_demo: bool = False
    needs_details: list[Literal["deposit", "condition"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_provenance(self):
        if self.status == "matched" and not all(
            [self.source_url, self.reviewed_at, self.rule_version]
        ):
            raise ValueError("Matched guidance needs source, review date and rule version.")
        return self


class Submission(Contract):
    """One sorting request; identity and timestamps are initialized by Pydantic."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    region_id: str
    status: Literal["processing", "completed", "uncertain", "unsupported", "failed"] = "processing"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_demo: bool = False
    recognition: RecognitionResult | None = None
    guidance: GuidanceResult | None = None
    error: str | None = None

    def __init__(self, **data) -> None:
        # Preserve Pydantic validation, UUID/time defaults and JSON restoration.
        super().__init__(**data)

    def get_id(self) -> str:
        return self.id

    def get_region_id(self) -> str:
        return self.region_id

    def set_region_id(self, region_id: str) -> None:
        self.region_id = region_id
        self.updated_at = utc_now()

    def get_status(self) -> str:
        return self.status

    def set_status(self, status: str) -> None:
        self.status = status
        self.updated_at = utc_now()

    def get_created_at(self) -> datetime:
        return self.created_at

    def get_updated_at(self) -> datetime:
        return self.updated_at

    def get_is_demo(self) -> bool:
        return self.is_demo

    def set_is_demo(self, is_demo: bool) -> None:
        self.is_demo = is_demo
        self.updated_at = utc_now()

    def get_recognition(self) -> RecognitionResult | None:
        return self.recognition

    def get_guidance(self) -> GuidanceResult | None:
        return self.guidance

    def get_error(self) -> str | None:
        return self.error

    def set_error(self, error: str | None) -> None:
        self.error = error
        self.updated_at = utc_now()

    def set_outcome(self, recognition: RecognitionResult, guidance: GuidanceResult | None = None) -> None:
        self.recognition = recognition
        self.guidance = guidance
        self.status = "completed" if guidance else recognition.status
        self.updated_at = utc_now()


class Feedback(Contract):
    """A user's helpful/not-helpful answer for one submission."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    submission_id: str
    helpful: bool
    created_at: datetime = Field(default_factory=utc_now)

    def __init__(self, **data) -> None:
        super().__init__(**data)

    def get_submission_id(self) -> str:
        return self.submission_id

    def get_helpful(self) -> bool:
        return self.helpful

    def set_helpful(self, helpful: bool) -> None:
        self.helpful = helpful
        self.created_at = utc_now()

    def get_created_at(self) -> datetime:
        return self.created_at
