import json
from uuid import uuid4

import httpx
import pytest

from waste_sorting.services.clients import HttpGuidanceClient, HttpRecognitionClient
from waste_sorting.services.demo import DemoRecognitionClient
from waste_sorting.workflow import SortCoordinator


@pytest.mark.parametrize("special,guidance_status,expected", [
    (False, "matched", "completed"), (True, "special", "completed"),
    (True, "matched", "failed"), (False, "missing_rule", "completed"),
])
def test_connected_http_chain(repository, image, special, guidance_status, expected):
    submission_id = str(uuid4())
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/v1/recognitions":
            recognition = DemoRecognitionClient("can").recognize(image, submission_id)
            return httpx.Response(200, json=recognition.model_copy(update={"special": special}).model_dump())
        body = json.loads(request.content)
        assert body["region_id"] == "dortmund"
        assert body["recognition"]["submission_id"] == submission_id
        return httpx.Response(200, json={
            "submission_id": submission_id, "region_id": "dortmund", "status": guidance_status,
            "category": "packaging", "bin_label": "Verified fixture collection",
            "preparation_steps": ["Empty first."], "explanation": "Mocked service advice.",
            "source_url": "https://city.example/rule", "reviewed_at": "2026-10-13", "rule_version": 1,
        })

    transport = httpx.MockTransport(handler)
    result = SortCoordinator(repository,
        HttpRecognitionClient("https://b.example", "", 15, transport),
        HttpGuidanceClient("https://c.example", "", 10, transport)).identify(image, "dortmund", submission_id)
    assert result.status == expected
    assert not result.is_demo
    assert seen == ["/v1/recognitions", "/v1/guidance"]


def test_guidance_outage_preserves_recognition(repository, image):
    def unavailable(request):
        return httpx.Response(503)
    result = SortCoordinator(repository, DemoRecognitionClient("can"),
        HttpGuidanceClient("https://c.example", "", 10, httpx.MockTransport(unavailable))).identify(
            image, "dortmund", str(uuid4()))
    assert result.status == "failed"
    assert repository.get(result.id).recognition.item_name == "Drink can"
    assert result.guidance is None
