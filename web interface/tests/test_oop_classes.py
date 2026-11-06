"""Behavioral checks for the public constructors and controlled mutations."""
import pytest
from pydantic import ValidationError

from waste_sorting.models import Feedback, Submission
from waste_sorting.services.demo import DemoRecognitionClient


def test_image_changes_clear_detected_mime_type(image):
    assert image.validate()
    assert image.get_mime_type() == "image/png"
    image.set_filename("changed.jpg")
    assert image.get_mime_type() == ""
    image.filename = "changed.png"
    assert image.validate()
    image.set_content(b"not a photo")
    assert image.mime_type == ""
    assert image.get_content() == b"not a photo"
    assert image.get_filename() == "changed.png"


def test_invalid_image_setter_preserves_content(image):
    original = image.get_content()
    with pytest.raises(TypeError):
        image.set_content("not bytes")
    assert image.get_content() == original
    with pytest.raises(ValueError):
        image.set_mime_type("image/svg+xml")


def test_submission_initialization_and_json_round_trip():
    first = Submission(region_id="dortmund")
    second = Submission(region_id="dortmund")
    assert first.get_id() != second.get_id()
    assert first.get_status() == "processing"
    assert first.get_created_at().utcoffset().total_seconds() == 0
    assert first.get_recognition() is None and first.get_guidance() is None
    assert Submission.model_validate_json(first.model_dump_json()) == first


def test_submission_setters_validate_and_update_timestamp():
    submission = Submission(region_id="dortmund")
    before = submission.get_updated_at()
    submission.set_status("failed")
    submission.set_error("Service unavailable")
    assert submission.get_updated_at() >= before
    assert submission.get_error() == "Service unavailable"
    with pytest.raises(ValidationError):
        submission.set_status("not-a-status")
    assert submission.get_status() == "failed"


def test_outcome_is_saved_and_restored(repository, image):
    submission = Submission(region_id="dortmund")
    recognition = DemoRecognitionClient().recognize(image, submission.get_id())
    submission.set_outcome(recognition)
    repository.save(submission)
    restored = repository.get(submission.get_id())
    assert restored.get_status() == "uncertain"
    assert restored.get_recognition() == recognition


def test_feedback_mutation_preserves_link_and_round_trips():
    feedback = Feedback(submission_id="request-id", helpful=True)
    before = feedback.get_created_at()
    feedback.set_helpful(False)
    assert feedback.get_helpful() is False
    assert feedback.get_submission_id() == "request-id"
    assert feedback.get_created_at() >= before
    with pytest.raises(ValidationError):
        feedback.set_helpful("not-a-boolean")
    assert feedback.get_helpful() is False
    assert Feedback.model_validate_json(feedback.model_dump_json()) == feedback
