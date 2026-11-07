import io

from openai import APITimeoutError
import httpx
from PIL import Image
import pytest

import app as recognition

PATH = "/v1/recognitions"


def upload(content, submission_id="test-submission"):
    return {"image": (io.BytesIO(content), "photo.png"), "submission_id": submission_id}


@pytest.mark.parametrize(("fields", "message"), [
    ({}, "An image file is required."),
    ({"content": b"image", "submission_id": ""}, "A submission_id of 1 to 100 characters is required."),
    ({"content": b""}, "The image is empty."),
    ({"content": b"not an image"}, "The uploaded file is not a readable image."),
])
def test_invalid_upload_returns_client_error(fields, message):
    response = recognition.app.test_client().post(PATH, data=upload(**fields) if fields else {})
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_oversized_image_returns_413(monkeypatch):
    monkeypatch.setattr(recognition, "MAX_IMAGE_BYTES", 10)
    response = recognition.app.test_client().post(PATH, data=upload(b"x" * 11))
    assert response.status_code == 413


def test_missing_provider_key_is_reported(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    image = io.BytesIO()
    Image.new("RGB", (8, 8)).save(image, format="PNG")

    response = recognition.app.test_client().post(PATH, data=upload(image.getvalue()))
    assert response.status_code == 502
    assert "OPENAI_API_KEY" in response.get_json()["error"]


def test_provider_timeout_returns_504(monkeypatch):
    def time_out(*args):
        raise APITimeoutError(request=httpx.Request("POST", "https://example.org"))

    monkeypatch.setattr(recognition, "recognize_contract", time_out)
    response = recognition.app.test_client().post(PATH, data=upload(b"image"))
    assert response.status_code == 504
    assert response.get_json() == {"error": "Image recognition timed out. Please try again."}
