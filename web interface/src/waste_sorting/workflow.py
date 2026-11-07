from datetime import timedelta

from .models import Submission, utc_now
from .services.clients import ServiceError


class SortCoordinator:
    def __init__(self, repository, recognition, guidance, is_demo=False):
        self.repository = repository
        self.recognition = recognition
        self.guidance = guidance
        self.is_demo = is_demo

    def identify(self, image, region_id, submission_id):
        image.validate()
        submission = Submission(id=submission_id, region_id=region_id, is_demo=self.is_demo)
        if not self.repository.claim(submission):
            previous = self.repository.get(submission_id)
            if previous.status == "processing" and utc_now() - previous.updated_at > timedelta(minutes=2):
                previous.set_status("failed")
                previous.set_error("This request was interrupted. Start a new identification.")
                self.repository.save(previous)
            return previous
        try:
            recognition = self.recognition.recognize(image, submission.id)
            if recognition.submission_id != submission.id:
                raise ServiceError("Recognition returned a mismatched submission. Please try again.")
            submission.recognition = recognition
            if recognition.status != "recognized" or recognition.confidence < .8:
                if recognition.status == "recognized":
                    recognition = recognition.model_copy(update={"status": "uncertain"})
                submission.set_outcome(recognition)
            else:
                guidance = self.guidance.guide(recognition, region_id)
                if guidance.submission_id != submission.id or guidance.region_id != region_id:
                    raise ServiceError("Local guidance returned a mismatched result. Please try again.")
                if recognition.special and guidance.status == "matched":
                    raise ServiceError("This item needs special disposal guidance. Check with your local provider.")
                submission.set_outcome(recognition, guidance)
                submission.is_demo = submission.is_demo or guidance.is_demo
        except ServiceError as exc:
            submission.set_status("failed")
            submission.set_error(str(exc))
        self.repository.save(submission)
        return submission

    def refine(self, submission_id, answers):
        """Resolve details without repeating the paid image recognition call."""
        from .models import RecognitionResult
        submission = self.repository.get(submission_id)
        if not submission or not submission.guidance or not submission.guidance.needs_details:
            raise ValueError("This submission does not need additional details.")
        if set(answers) != set(submission.guidance.needs_details):
            raise ValueError("Answer the requested details only.")
        if any(value not in ({"yes", "no"} if field == "deposit" else {"clean", "soiled"})
               for field, value in answers.items()):
            raise ValueError("Choose a definite answer or ask your local provider.")
        recognition = RecognitionResult.model_validate({**submission.recognition.model_dump(), **answers})
        try:
            guidance = self.guidance.guide(recognition, submission.region_id)
            if guidance.submission_id != submission.id or guidance.region_id != submission.region_id:
                raise ServiceError("Local guidance returned a mismatched result.")
            if recognition.special and guidance.status == "matched":
                raise ServiceError("This item requires special disposal guidance.")
            submission.set_outcome(recognition, guidance)
            submission.is_demo = submission.is_demo or guidance.is_demo
        except ServiceError as exc:
            # Preserve the unanswered outcome so the user can retry details after an outage.
            raise exc
        self.repository.save(submission)
        return submission
