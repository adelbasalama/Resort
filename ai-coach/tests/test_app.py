import unittest
from unittest.mock import patch

from app.main import create_app
from app.domain.errors import PersistenceError


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_guidance_requires_region_and_item(self):
        response = self.client.post("/api/guidance", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_guidance_request")

    def test_guidance_rejects_non_object_json(self):
        response = self.client.post("/api/guidance", json=["demo-dortmund", "battery"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["message"], "request body must be an object")

    def test_guidance_rejects_unknown_condition(self):
        response = self.client.post(
            "/api/guidance",
            json={"region_id": "demo-dortmund", "item_key": "battery", "condition": "wet"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("condition must be", response.get_json()["message"])

    def test_guidance_rejects_invalid_recognition_confidence(self):
        response = self.client.post(
            "/api/guidance",
            json={
                "region_id": "demo-dortmund",
                "item_key": "battery",
                "recognition_confidence": 1.5,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("recognition_confidence", response.get_json()["message"])

    def test_admin_rule_changes_require_token(self):
        response = self.client.post("/api/admin/rules", json={})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "admin_unauthorized")

    def test_index_remains_available_when_database_is_unavailable(self):
        with patch(
            "app.web.routes.service.repository.list_regions",
            side_effect=PersistenceError("database unavailable"),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
