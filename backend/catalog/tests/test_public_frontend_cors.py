"""Only deliberately allowed origins can read the published-only API."""

import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from rescue.settings import _public_frontend_origins


@override_settings(
    PUBLIC_FRONTEND_ORIGINS=frozenset({"https://atlas.partner.example"}),
    SECURE_SSL_REDIRECT=False,
)
class ExternalFrontendTests(SimpleTestCase):
    ORIGIN = "https://atlas.partner.example"

    def test_public_api_get_and_404_are_accessible(self):
        response = self.client.get("/api/v1/no-such-endpoint/", HTTP_ORIGIN=self.ORIGIN)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Access-Control-Allow-Origin"], self.ORIGIN)
        self.assertIn("Origin", response["Vary"])
        self.assertNotIn("Access-Control-Allow-Credentials", response)

    def test_untrusted_origin_never_receives_cors(self):
        response = self.client.get(
            "/api/v1/events/", HTTP_ORIGIN="https://untrusted.example"
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_allowed_read_only_preflight(self):
        response = self.client.options(
            "/api/v1/events/",
            HTTP_ORIGIN=self.ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="accept, content-type",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Access-Control-Allow-Origin"], self.ORIGIN)
        self.assertEqual(response["Access-Control-Allow-Methods"], "GET, HEAD, OPTIONS")
        self.assertNotIn("Access-Control-Allow-Credentials", response)

    def test_write_or_custom_header_preflight_is_refused(self):
        for method, headers in (("POST", ""), ("GET", "authorization")):
            response = self.client.options(
                "/api/v1/events/",
                HTTP_ORIGIN=self.ORIGIN,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD=method,
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
            )
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_private_api_and_session_stay_same_origin(self):
        for path in ("/api/private/v1/me/", "/api/csrf/", "/admin/"):
            response = self.client.get(path, HTTP_ORIGIN=self.ORIGIN)
            self.assertNotIn("Access-Control-Allow-Origin", response, path)

    def test_no_read_cors_on_unsupported_write(self):
        response = self.client.post(
            "/api/v1/events/",
            data="{}",
            content_type="application/json",
            HTTP_ORIGIN=self.ORIGIN,
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)


class OriginValidationTests(SimpleTestCase):
    def test_unset_means_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_public_frontend_origins(), frozenset())

    def test_https_exact_origins(self):
        with patch.dict(
            os.environ,
            {"PUBLIC_FRONTEND_ORIGINS": "https://atlas.example,https://map.example:8443"},
        ):
            self.assertEqual(
                _public_frontend_origins(),
                frozenset({"https://atlas.example", "https://map.example:8443"}),
            )

    def test_wildcards_and_unsafe_origins_refused(self):
        for origin in (
            "*",
            "https://*.example.org",
            "https://example.org/",
            "http://example.org",
            "https://user:pass@example.org",
            "https://example.org/path",
            "https://example.org?token=abc",
            "https://example.org:bad",
        ):
            with self.subTest(origin=origin):
                with patch.dict(os.environ, {"PUBLIC_FRONTEND_ORIGINS": origin}):
                    with self.assertRaises(ImproperlyConfigured):
                        _public_frontend_origins()
