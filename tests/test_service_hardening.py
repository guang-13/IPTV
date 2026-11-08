import unittest
from unittest import mock

from service import app as service_app


class ServiceHardeningTests(unittest.TestCase):
    def setUp(self):
        service_app.app.config.update(TESTING=True)
        self.client = service_app.app.test_client()

    def test_healthz_is_public_and_minimal(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("public_url", payload)

    def test_logs_are_blocked_for_remote_clients(self):
        response = self.client.get(
            "/log/result", environ_base={"REMOTE_ADDR": "203.0.113.9"}
        )
        self.assertEqual(response.status_code, 403)

    def test_local_api_rejects_remote_clients(self):
        response = self.client.post(
            "/api/rtmp/shutdown", environ_base={"REMOTE_ADDR": "203.0.113.9"}
        )
        self.assertEqual(response.status_code, 403)

    def test_local_api_rejects_cross_site_origin(self):
        response = self.client.post(
            "/api/rtmp/shutdown",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(response.status_code, 403)

    def test_hls_proxy_rejects_unknown_channel_without_waiting(self):
        with mock.patch.object(service_app, "get_channel_data", return_value={}):
            response = self.client.get("/hls_proxy/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_hls_proxy_rejects_path_separators(self):
        response = self.client.get("/hls_proxy/%2e%2e%5c%2e%2e%5cwindows")
        self.assertIn(response.status_code, {400, 404})

    def test_on_done_rejects_remote_clients(self):
        response = self.client.post(
            "/on_done",
            data={"name": "x"},
            environ_base={"REMOTE_ADDR": "203.0.113.9"},
        )
        self.assertEqual(response.status_code, 403)

    def test_security_headers_are_present(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")


if __name__ == "__main__":
    unittest.main()
