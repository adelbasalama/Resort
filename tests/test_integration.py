"""Exercise real A/B/C/D adapters over local HTTP; mock only paid recognition."""
import importlib.util
import io
from pathlib import Path
import sys
import threading
from uuid import uuid4

import httpx
from PIL import Image
import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
for directory in ["WasteRecognition", "subsystem4_dashboard", "ai-coach", "web interface/src"]:
    sys.path.insert(0, str(ROOT / directory))

from app.main import create_app
from app.web import routes
from app.sqlite_db import SQLiteRuleRepository
from app.domain.models import Region
from app.domain.services import RegionalGuidanceService
from waste_sorting.models import Feedback
from waste_sorting.services.clients import HttpRecognitionClient, HttpGuidanceClient
from waste_sorting.services.demo import DemoRecognitionClient
from waste_sorting.storage import Repository
from waste_sorting.uploads import ImageUpload
from waste_sorting.workflow import SortCoordinator


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recognition = load_module("recognition_server", "WasteRecognition/app.py")
dashboard = load_module("dashboard_server", "subsystem4_dashboard/app.py")


@pytest.fixture
def image():
    stream = io.BytesIO()
    Image.new("RGB", (48, 48), "green").save(stream, format="PNG")
    return ImageUpload(stream.getvalue(), "private-photo.png")


@pytest.fixture
def services(tmp_path, monkeypatch):
    rules = SQLiteRuleRepository(tmp_path / "rules.sqlite3")
    # A synthetic non-demo region lets us verify live/demo analytics separation.
    rules.create_region(Region("test-city", "Integration test city", "https://example.org/rules"))
    demo = rules.find_rule("demo-dortmund", "beverage_can")
    demo.region_id = "test-city"
    rules.create_rule_revision(demo)
    battery = rules.find_rule("demo-dortmund", "battery")
    battery.region_id = "test-city"
    rules.create_rule_revision(battery)
    monkeypatch.setattr(routes, "service", RegionalGuidanceService(rules))
    repository = Repository(str(tmp_path / "submissions.sqlite3"))
    monkeypatch.setenv("DATABASE_PATH", repository.path)
    servers, threads, urls = [], [], []
    for application in [recognition.app, create_app(), dashboard.app]:
        server = make_server("127.0.0.1", 0, application, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        threads.append(thread)
        urls.append(f"http://127.0.0.1:{server.server_port}")
    yield repository, rules, urls
    for server, thread in zip(servers, threads):
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def prediction(**updates):
    return {"item_label": "beverage_can", "visual_tags": ["aluminum"], "condition": "clean",
            "confidence": .97, "special": False, "model_id": "test-provider", "deposit": "no", **updates}


def coordinator(services):
    repository, _, (b, c, _) = services
    return SortCoordinator(repository, HttpRecognitionClient(b, "", 5), HttpGuidanceClient(c, "", 5))


def test_photo_to_guidance_storage_feedback_and_dashboard(services, image, monkeypatch):
    calls = []
    def provider(content):
        calls.append(content)
        return prediction()
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", provider)
    repository, rules, (_, _, d) = services
    workflow = coordinator(services)
    request_id = str(uuid4())
    result = workflow.identify(image, "test-city", request_id)
    assert result.status == "completed" and not result.is_demo, result.error
    assert result.recognition.item_key == "beverage_can"
    assert result.guidance.rule_version == 1 and result.guidance.is_fallback
    assert repository.get(request_id) == result
    assert workflow.identify(image, "test-city", request_id) == result
    assert len(calls) == 1
    repository.save_feedback(Feedback(submission_id=request_id, helpful=True))
    stats = httpx.get(d + "/api/stats").json()
    assert stats["total"] == 1 and stats["counts"] == {"recyclable": 1}
    assert httpx.get(d + "/api/stats", params={"region": "different-city"}).json()["total"] == 0
    assert httpx.get(d + "/").status_code == 200
    assert httpx.get(d + "/static/plotly.js").status_code == 200
    with rules.connection() as db:
        row = db.execute("SELECT recognition_id, rule_version FROM guidance_decisions").fetchone()
        assert tuple(row) == (request_id, 1)
    with repository.connection() as db:
        serialized = db.execute("SELECT outcome_json FROM submissions").fetchone()[0]
        assert "private-photo" not in serialized and "image_bytes" not in serialized


@pytest.mark.parametrize("confidence,label,tags,status", [
    (.4, "beverage_can", ["aluminum"], "uncertain"),
    (.79, "beverage_can", ["aluminum"], "uncertain"),
    (.97, "unknown", ["unknown"], "unsupported"),
    (.97, "beverage_can", ["pet", "aluminum"], "uncertain"),
    (.97, "beverage_can", ["organic"], "uncertain"),
])
def test_uncertain_results_skip_coaching(services, image, monkeypatch, confidence, label, tags, status):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction(confidence=confidence, item_label=label, visual_tags=tags))
    result = coordinator(services).identify(image, "test-city", str(uuid4()))
    assert result.status == status and result.guidance is None
    with services[1].connection() as db:
        assert db.execute("SELECT COUNT(*) FROM guidance_decisions").fetchone()[0] == 0


def test_special_items_use_special_collection(services, image, monkeypatch):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction(item_label="battery", visual_tags=["battery"]))
    result = coordinator(services).identify(image, "test-city", str(uuid4()))
    assert result.recognition.special
    assert result.guidance.status == "special" and result.guidance.category == "special"


def test_missing_rule_is_a_structured_outcome(services, image, monkeypatch):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction(item_label="plastic_bottle", visual_tags=["pet"]))
    result = coordinator(services).identify(image, "test-city", str(uuid4()))
    assert result.status == "completed" and result.guidance.status == "missing_rule"
    assert httpx.get(services[2][2] + "/api/stats").json()["total"] == 0


def test_demo_rules_are_marked_and_excluded_by_default(services, image, monkeypatch):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction())
    result = coordinator(services).identify(image, "demo-dortmund", str(uuid4()))
    assert result.is_demo and services[0].get(result.id).is_demo
    d = services[2][2]
    assert httpx.get(d + "/api/stats").json()["total"] == 0
    assert httpx.get(d + "/api/stats?include_demo=1").json()["total"] == 1


def test_real_image_validation_and_missing_key_errors(services, image, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = services[2][0]
    invalid = httpx.post(b + "/v1/recognitions", data={"submission_id": "bad"}, files={"image": ("bad.png", b"not an image")})
    assert invalid.status_code == 400
    result = coordinator(services).identify(image, "test-city", str(uuid4()))
    assert result.status == "failed" and "unavailable" in result.error
    assert services[0].get(result.id).status == "failed"


def test_guidance_rejects_mismatch_and_malformed_facts(services, image):
    c = services[2][1]
    facts = DemoRecognitionClient("can").recognize(image, "request").model_dump()
    response = httpx.post(c + "/v1/guidance", json={"submission_id": "other", "region_id": "test-city", "recognition": facts})
    assert response.status_code == 400
    for body in [None, [], {"recognition": {}},
                 {"submission_id": "request", "region_id": "test-city", "recognition": {**facts, "confidence": True}},
                 {"submission_id": "request", "region_id": "test-city", "recognition": {**facts, "condition": []}}]:
        assert httpx.post(c + "/v1/guidance", json=body).status_code == 400


def test_connected_example_uses_real_coach_and_dashboard(services, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _, _, (b, c, d) = services
    monkeypatch.setenv("SERVICE_MODE", "http")
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_HTTP", "true")
    monkeypatch.setenv("RECOGNITION_API_URL", b)
    monkeypatch.setenv("GUIDANCE_API_URL", c)
    app = AppTest.from_file(str(ROOT / "web interface/app.py"), default_timeout=30).run()
    assert not app.exception
    app.radio[0].set_value("Try an example").run()
    app.button[0].click().run()
    assert not app.exception
    result = app.session_state["result"]
    assert result.status == "completed" and result.is_demo
    assert result.guidance.rule_version == 1
    assert httpx.get(d + "/api/stats?include_demo=1").json()["total"] == 1


def test_sqlite_revisions_preserve_history_and_rollback(tmp_path):
    from app.domain.errors import PersistenceError
    repo = SQLiteRuleRepository(tmp_path / "rules.sqlite3")
    old = repo.find_rule("demo-dortmund", "beverage_can")
    old.bin_label = "Revised test label"
    new_id, version = repo.create_rule_revision(old)
    assert version == 2
    assert repo.find_rule("demo-dortmund", "beverage_can").id == new_id
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM recycling_rules WHERE item_key='beverage_can' AND region_id='demo-dortmund'").fetchone()[0] == 2
    old.region_id = "missing-region"
    with pytest.raises(PersistenceError):
        repo.create_rule_revision(old)
    assert repo.find_rule("demo-dortmund", "beverage_can").version == 2
    repo.deactivate_rule(new_id)
    assert SQLiteRuleRepository(repo.path).find_rule("demo-dortmund", "beverage_can") is None


def test_provider_request_uses_sanitized_image_and_structured_schema(image, monkeypatch):
    import base64
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import image_recognizer
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.parse.return_value = SimpleNamespace(
        status="completed", model="test-provider", output_parsed=image_recognizer.ImagePrediction(
            **{k: v for k, v in prediction().items() if k != "model_id"}))
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setattr(image_recognizer, "OpenAI", lambda **kwargs: client)
    result = image_recognizer.recognize_contract(image.content, "request")
    assert result["status"] == "recognized"
    options = client.responses.parse.call_args.kwargs
    assert options["store"] is False and options["text_format"] is image_recognizer.ImagePrediction
    data_url = options["input"][0]["content"][1]["image_url"]
    encoded = data_url.split(",", 1)[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as sanitized:
        assert sanitized.format == "JPEG" and not sanitized.getexif()
        assert max(sanitized.size) <= 1024


def test_service_url_configuration_requires_explicit_http_opt_in(monkeypatch):
    from waste_sorting.config import Settings
    monkeypatch.setenv("SERVICE_MODE", "http")
    monkeypatch.setenv("RECOGNITION_API_URL", "http://127.0.0.1:5001")
    monkeypatch.setenv("GUIDANCE_API_URL", "http://127.0.0.1:5002")
    monkeypatch.delenv("ALLOW_INSECURE_LOCAL_HTTP", raising=False)
    with pytest.raises(ValueError, match="HTTPS"):
        Settings.from_env()
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_HTTP", "true")
    assert Settings.from_env().mode == "http"
    monkeypatch.setenv("GUIDANCE_API_URL", "http://user:password@localhost:5002")
    with pytest.raises(ValueError, match="credentials"):
        Settings.from_env()


@pytest.mark.parametrize("label,tags,category", [
    ("diaper", ["hygiene"], "landfill"), ("used_tissue", ["hygiene"], "landfill"),
    ("coffee_grounds", ["organic"], "compostable"), ("cardboard", ["paper"], "recyclable"),
])
def test_expanded_ai_catalogue_reaches_real_regional_rules(services, image, monkeypatch, label, tags, category):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction(
        item_label=label, visual_tags=tags, predicted_category=category))
    result = coordinator(services).identify(image, "dortmund", str(uuid4()))
    assert result.status == "completed" and not result.is_demo
    assert result.recognition.predicted_category == category
    assert result.guidance.category == category


def test_followup_resolves_deposit_without_second_recognition(services, image, monkeypatch):
    import image_recognizer
    from unittest.mock import Mock
    provider = Mock(return_value=prediction(deposit="unknown"))
    monkeypatch.setattr(image_recognizer, "recognize_image", provider)
    workflow = coordinator(services)
    pending = workflow.identify(image, "dortmund", str(uuid4()))
    assert pending.guidance.needs_details == ["deposit"]
    assert httpx.get(services[2][2] + "/api/stats").json()["total"] == 0
    result = workflow.refine(pending.id, {"deposit": "yes"})
    assert result.guidance.status == "matched" and "Pfand" in result.guidance.bin_label
    assert result.recognition.deposit == "yes"
    provider.assert_called_once()
    assert services[0].get(result.id).guidance.needs_details == []
    assert httpx.get(services[2][2] + "/api/stats").json()["total"] == 1


def test_followup_resolves_paper_condition(services, image, monkeypatch):
    import image_recognizer
    monkeypatch.setattr(image_recognizer, "recognize_image", lambda _: prediction(
        item_label="paper_bag", visual_tags=["paper"], condition="unknown"))
    workflow = coordinator(services)
    result = workflow.identify(image, "hagen", str(uuid4()))
    assert result.guidance.needs_details == ["condition"]
    result = workflow.refine(result.id, {"condition": "soiled"})
    assert result.guidance.category == "landfill"


def test_admin_page_changes_require_token_and_preserve_version(services, monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "private-test-token")
    c = services[2][1]
    assert httpx.get(c + "/admin").status_code == 200
    form = {"action": "rule", "region_id": "dortmund", "item_key": "diaper", "category": "landfill",
            "bin_label": "Test residual bin", "preparation": "Wrap it.", "condition": "any",
            "source_url": "https://example.org", "reviewed_on": "2026-11-07"}
    assert httpx.post(c + "/admin", data=form).status_code == 401
    response = httpx.post(c + "/admin", data={**form, "token": "private-test-token"})
    assert response.status_code == 200 and "version 2" in response.text
    assert "private-test-token" not in response.text
    assert services[1].find_rule("dortmund", "diaper").version == 2


def test_streamlit_followup_updates_advice_without_new_photo_call(services, image, monkeypatch):
    import image_recognizer
    from unittest.mock import Mock
    from streamlit.testing.v1 import AppTest
    provider = Mock(return_value=prediction(deposit="unknown"))
    monkeypatch.setattr(image_recognizer, "recognize_image", provider)
    pending = coordinator(services).identify(image, "dortmund", str(uuid4()))
    monkeypatch.setenv("SERVICE_MODE", "http")
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_HTTP", "true")
    monkeypatch.setenv("RECOGNITION_API_URL", services[2][0])
    monkeypatch.setenv("GUIDANCE_API_URL", services[2][1])
    app = AppTest.from_file(str(ROOT / "web interface/app.py"), default_timeout=30)
    app.session_state["result"] = pending
    app.run()
    assert not app.exception
    app.radio[0].set_value("Yes").run()
    next(button for button in app.button if button.label == "Update disposal advice").click().run()
    assert not app.exception
    assert "Pfand" in app.session_state["result"].guidance.bin_label
    provider.assert_called_once()
