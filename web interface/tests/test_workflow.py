from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from uuid import uuid4

import pytest

from waste_sorting.models import Feedback, Submission
from waste_sorting.services.clients import ServiceError
from waste_sorting.services.demo import DemoGuidanceClient, DemoRecognitionClient
from waste_sorting.workflow import SortCoordinator


def test_complete_and_feedback(repository, image):
    coordinator = SortCoordinator(repository, DemoRecognitionClient("can"), DemoGuidanceClient(), True)
    result = coordinator.identify(image, "dortmund", str(uuid4()))
    assert result.status == "completed" and result.is_demo
    assert repository.get(result.id).recognition.item_name == "Drink can"
    repository.save_feedback(Feedback(submission_id=result.id, helpful=True))
    repository.save_feedback(Feedback(submission_id=result.id, helpful=False))
    with repository.connection() as db:
        assert db.execute("SELECT count(*), helpful FROM feedback").fetchone() == (1, 0)
        persisted = db.execute("SELECT outcome_json FROM submissions").fetchone()[0]
        assert "photo.png" not in persisted and "content" not in persisted


def test_uncertain_upload_does_not_call_guidance(repository, image):
    guidance = Mock()
    result = SortCoordinator(repository, DemoRecognitionClient(), guidance).identify(image, "dortmund", str(uuid4()))
    assert result.status == "uncertain"
    guidance.guide.assert_not_called()


def test_low_confidence_is_uncertain(repository, image):
    recognizer = Mock()
    submission_id = str(uuid4())
    recognizer.recognize.return_value = DemoRecognitionClient("can").recognize(image, submission_id).model_copy(update={"confidence": .4})
    guidance = Mock()
    result = SortCoordinator(repository, recognizer, guidance).identify(image, "dortmund", submission_id)
    assert result.status == "uncertain"
    guidance.guide.assert_not_called()


def test_failure_is_saved(repository, image):
    recognizer = Mock()
    recognizer.recognize.side_effect = ServiceError("Please try again.")
    result = SortCoordinator(repository, recognizer, Mock()).identify(image, "dortmund", str(uuid4()))
    assert repository.get(result.id).status == "failed"
    assert result.error == "Please try again."


def test_repeated_and_concurrent_calls_are_idempotent(repository, image):
    recognizer = Mock(wraps=DemoRecognitionClient("can"))
    coordinator = SortCoordinator(repository, recognizer, DemoGuidanceClient())
    submission_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: coordinator.identify(image, "dortmund", submission_id), range(8)))
    assert len({r.id for r in results}) == 1
    recognizer.recognize.assert_called_once()
    assert repository.get(submission_id).status == "completed"


def test_fifty_independent_submissions(repository, image):
    coordinator = SortCoordinator(repository, DemoRecognitionClient("can"), DemoGuidanceClient())
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(lambda _: coordinator.identify(image, "dortmund", str(uuid4())), range(50)))
    assert all(r.status == "completed" for r in results)


def test_reject_feedback_for_unknown_or_incomplete(repository):
    with pytest.raises(ValueError):
        repository.save_feedback(Feedback(submission_id="unknown", helpful=True))
    submission = Submission(region_id="dortmund")
    repository.save(submission)
    with pytest.raises(ValueError):
        repository.save_feedback(Feedback(submission_id=submission.id, helpful=True))


def test_mismatched_recognition_fails(repository, image):
    recognizer = Mock()
    recognizer.recognize.return_value = DemoRecognitionClient("can").recognize(image, "wrong-id")
    result = SortCoordinator(repository, recognizer, DemoGuidanceClient()).identify(image, "dortmund", str(uuid4()))
    assert result.status == "failed"


def test_mismatched_region_fails(repository, image):
    guidance = Mock(wraps=DemoGuidanceClient())
    submission_id = str(uuid4())
    recognition = DemoRecognitionClient("can").recognize(image, submission_id)
    guidance.guide.return_value = DemoGuidanceClient().guide(recognition, "berlin")
    result = SortCoordinator(repository, DemoRecognitionClient("can"), guidance).identify(image, "dortmund", submission_id)
    assert result.status == "failed"
