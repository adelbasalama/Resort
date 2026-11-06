from typing import Protocol

import httpx
from pydantic import ValidationError

from ..models import GuidanceResult, RecognitionResult, Region
from ..uploads import ImageUpload


class ServiceError(RuntimeError):
    pass


class RecognitionService(Protocol):
    def recognize(self, image: ImageUpload, submission_id: str) -> RecognitionResult: ...


class GuidanceService(Protocol):
    def regions(self) -> list[Region]: ...
    def guide(self, recognition: RecognitionResult, region_id: str) -> GuidanceResult: ...


class ApiClient:
    def __init__(self, base_url, api_key, timeout, transport=None):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout = timeout
        self.transport = transport

    def request(self, method, path, **kwargs):
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers,
                              transport=self.transport, follow_redirects=False) as client:
                response = client.request(method, self.base_url + path, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise ServiceError("The service took too long. Please try again in a moment.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError("The sorting service is unavailable. Please try again shortly.") from exc


class HttpRecognitionClient(ApiClient):
    def recognize(self, image, submission_id):
        payload = self.request("POST", "/v1/recognitions",
            data={"submission_id": submission_id},
            files={"image": ("upload.png" if image.mime_type == "image/png" else "upload.jpg",
                             image.content, image.mime_type)},
            headers={"Idempotency-Key": submission_id})
        try:
            return RecognitionResult.model_validate(payload)
        except ValidationError as exc:
            raise ServiceError("Recognition returned an invalid response. Please try again.") from exc


class HttpGuidanceClient(ApiClient):
    def regions(self):
        payload = self.request("GET", "/v1/regions")
        try:
            result = [Region.model_validate(region) for region in payload["regions"]]
            if not result or len({r.id for r in result}) != len(result):
                raise ValueError("Empty or duplicate region list")
            return result
        except (ValidationError, TypeError, KeyError, ValueError) as exc:
            raise ServiceError("The region list could not be loaded. Please try again.") from exc

    def guide(self, recognition, region_id):
        payload = self.request("POST", "/v1/guidance", json={
            "submission_id": recognition.submission_id,
            "region_id": region_id,
            "recognition": recognition.model_dump(mode="json"),
        }, headers={"Idempotency-Key": recognition.submission_id})
        try:
            return GuidanceResult.model_validate(payload)
        except ValidationError as exc:
            raise ServiceError("Local guidance returned an invalid response. Please try again.") from exc
