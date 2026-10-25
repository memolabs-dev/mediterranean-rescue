"""The production image serves the built frontend next to the API, with a strict policy."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class FrontendTests(SimpleTestCase):
    def setUp(self):
        self.dist = tempfile.TemporaryDirectory()
        Path(self.dist.name, "index.html").write_text("<div id=root></div>", encoding="utf-8")
        self.addCleanup(self.dist.cleanup)

    def test_app_routes_answer_with_the_page(self):
        with override_settings(FRONTEND_DIST=self.dist.name):
            for path in ("/about", "/workspace/history", "/invite"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertIn(b"id=root", b"".join(response.streaming_content))
                self.assertEqual(response["Cache-Control"], "no-cache")

    def test_api_and_admin_paths_are_never_the_page(self):
        with override_settings(FRONTEND_DIST=self.dist.name):
            self.assertEqual(self.client.get("/api/v1/nothing/").status_code, 404)
            self.assertEqual(self.client.get("/static/nothing.js").status_code, 404)
            # An asset of an older release is missing, not the page.
            self.assertEqual(self.client.get("/assets/index-old.js").status_code, 404)

    def test_the_admin_sign_in_is_the_team_sign_in(self):
        response = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual((response.status_code, response["Location"]), (302, "/workspace"))

    def test_an_unknown_api_address_answers_json(self):
        response = self.client.get("/api/v1/nothing/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": "http_404", "detail": "Not found"})

    def test_without_a_built_frontend_nothing_is_served(self):
        with override_settings(FRONTEND_DIST=""):
            self.assertEqual(self.client.get("/about").status_code, 404)

    def test_every_response_carries_the_policy(self):
        with override_settings(FRONTEND_DIST=self.dist.name):
            policy = self.client.get("/about")["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("worker-src 'self' blob:", policy)
        self.assertNotIn("unsafe-eval", policy)
