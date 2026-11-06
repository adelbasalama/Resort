import httpx
import pytest

from waste_sorting.services.clients import HttpGuidanceClient, HttpRecognitionClient, ServiceError
from waste_sorting.services.demo import DemoRecognitionClient


def test_recognition_multipart_and_headers(image):
    image.validate()
    def handler(request):
        assert request.url.path == "/v1/recognitions"
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.headers["Idempotency-Key"] == "test-id"
        assert b"image/png" in request.content and image.content in request.content
        assert b"photo.png" not in request.content
        return httpx.Response(200, json=DemoRecognitionClient("can").recognize(image, "test-id").model_dump())
    client = HttpRecognitionClient("https://b.example", "secret", 15, httpx.MockTransport(handler))
    assert client.recognize(image, "test-id").item_key == "can"


@pytest.mark.parametrize("status,body", [(500, {}), (200, {"status": "bogus"}), (401, {"error": "secret"})])
def test_bad_responses_are_safe(image, status, body):
    client = HttpRecognitionClient("https://b.example", "", 15,
        httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
    with pytest.raises(ServiceError) as error:
        client.recognize(image, "id")
    assert "secret" not in str(error.value)


def test_timeout(image):
    def timeout(request):
        raise httpx.ReadTimeout("private upstream detail", request=request)
    client = HttpRecognitionClient("https://b.example", "", 15, httpx.MockTransport(timeout))
    with pytest.raises(ServiceError, match="too long"):
        client.recognize(image, "id")


def test_malformed_json(image):
    client = HttpRecognitionClient("https://b.example", "", 15,
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"not json")))
    with pytest.raises(ServiceError):
        client.recognize(image, "id")


def test_regions_are_dynamic():
    client = HttpGuidanceClient("https://c.example", "", 10, httpx.MockTransport(lambda _: httpx.Response(200,
        json={"regions": [{"id": "new-city", "name": "New City", "source_url": "https://city.example"}]})))
    assert client.regions()[0].id == "new-city"


def test_guidance_requires_provenance(image):
    recognition = DemoRecognitionClient("can").recognize(image, "id")
    client = HttpGuidanceClient("https://c.example", "", 10, httpx.MockTransport(lambda _: httpx.Response(200,
        json={"submission_id": "id", "region_id": "city", "status": "matched", "category": "metal",
              "bin_label": "Bin", "preparation_steps": [], "explanation": "Test"})))
    with pytest.raises(ServiceError):
        client.guide(recognition, "city")
