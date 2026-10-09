import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Job


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.engine = create_engine(f"sqlite:///{Path(self.temporary.name) / 'api.db'}",
                                    connect_args={"check_same_thread": False}, poolclass=NullPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)

        def database():
            with self.factory() as session:
                yield session

        app.dependency_overrides[get_db] = database
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.payload = {"name": "API fixture", "script": "第一句。第二句。", "voice_id": "fixture-speaker"}

    def test_plan_and_server_side_validation(self):
        response = self.client.post("/workflow/plan", json={"script": "。".join(str(i) for i in range(11))})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["shots"]), 6)
        self.assertTrue(response.json()["estimated"])
        self.assertEqual(self.client.post("/workflow/plan", json={"script": ""}).status_code, 400)
        self.assertEqual(self.client.post("/workflow/projects", json={"script_mode": "auto"}).status_code, 400)
        self.assertEqual(self.client.post("/workflow/projects", json={"script": "test", "image_provider": "unknown"}).status_code, 422)

    def test_missing_credentials_block_before_starting_generation(self):
        with patch.object(settings, "ark_api_key", ""), patch.object(settings, "volc_tts_api_key", ""), \
             patch("app.routers.projects.run_coze_generation") as runner:
            project = self.client.post("/workflow/projects", json=self.payload).json()
            response = self.client.post(f"/projects/{project['id']}/generate")
            self.assertEqual(response.status_code, 400)
            self.assertIn("API Key", response.json()["detail"])
            runner.assert_not_called()
            with self.factory() as db:
                self.assertEqual(db.query(Job).count(), 0)

    def test_duplicate_generation_is_rejected(self):
        with patch("app.routers.projects.readiness", return_value=[]), \
             patch("app.routers.projects.run_coze_generation") as runner:
            response = self.client.post("/workflow/projects", json=self.payload)
            self.assertEqual(response.status_code, 200)
            project = response.json()
            first = self.client.post(f"/projects/{project['id']}/generate")
            self.assertEqual(first.status_code, 200)
            self.assertEqual(self.client.post(f"/projects/{project['id']}/generate").status_code, 409)
            self.assertEqual(self.client.post("/workflow/settings", json={"ark_text_model": "fixture"}).status_code, 409)
            self.assertEqual(runner.call_count, 1)

    def test_saved_keys_are_not_returned(self):
        import app.routers.workflow as router
        original = settings.ark_api_key
        self.addCleanup(setattr, settings, "ark_api_key", original)
        with patch.object(router, "BACKEND_DIR", Path(self.temporary.name)):
            result = self.client.post("/workflow/settings", json={"ark_api_key": "fixture-secret-never-echo"})
            self.assertEqual(result.status_code, 200)
            self.assertNotIn("fixture-secret-never-echo", result.text)
            self.assertTrue(result.json()["keys"]["ark_api_key"])
            result = self.client.post("/workflow/settings", json={"ark_api_key": ""})
            self.assertTrue(result.json()["keys"]["ark_api_key"])
            self.assertNotIn("fixture-secret-never-echo", self.client.get("/workflow/profile").text)


if __name__ == "__main__":
    unittest.main()
