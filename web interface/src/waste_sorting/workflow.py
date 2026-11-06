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
            if recognition.status != "recognized" or recognition.confidence < .6:
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
        except ServiceError as exc:
            submission.set_status("failed")
            submission.set_error(str(exc))
        self.repository.save(submission)
        return submission
