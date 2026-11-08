import unittest
from unittest import mock

from utils import net_guard


def resolver_for(*addresses):
    def _resolve(host, port, **kwargs):
        return [(2, 1, 6, "", (address, port)) for address in addresses]

    return _resolve


class CheckUrlTests(unittest.TestCase):
    def test_public_https_host_is_allowed(self):
        url = "https://example.com/list.m3u"
        self.assertEqual(
            net_guard.check_url(url, resolver=resolver_for("93.184.216.34")),
            url,
        )

    def test_loopback_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url(
                "http://localhost/list.m3u", resolver=resolver_for("127.0.0.1")
            )

    def test_private_range_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url(
                "http://example.com/list.m3u", resolver=resolver_for("192.168.1.10")
            )

    def test_link_local_metadata_address_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("http://169.254.169.254/latest/meta-data/")

    def test_metadata_hostname_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_private_allowed_when_opted_in(self):
        url = "http://192.168.1.10/list.m3u"
        self.assertEqual(net_guard.check_url(url, allow_private=True), url)

    def test_file_scheme_requires_opt_in(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("file:///etc/passwd")
        self.assertEqual(
            net_guard.check_url("file:///tmp/clip.mp4", allow_file=True),
            "file:///tmp/clip.mp4",
        )

    def test_unsupported_scheme_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("ftp://example.com/list.m3u")

    def test_empty_url_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("")

    def test_missing_hostname_is_rejected(self):
        with self.assertRaises(net_guard.UnsafeUrlError):
            net_guard.check_url("http:///list.m3u")

    def test_dns_failure_is_left_to_the_request_layer(self):
        def failing_resolver(host, port, **kwargs):
            raise OSError("no such host")

        # Nothing resolves, so there is no address to pin; the fetch itself fails.
        self.assertEqual(
            net_guard.check_url("http://missing.invalid/x", resolver=failing_resolver),
            "http://missing.invalid/x",
        )

    def test_is_safe_url_returns_false_instead_of_raising(self):
        self.assertFalse(net_guard.is_safe_url("http://10.0.0.1/x"))
        self.assertTrue(net_guard.is_safe_url("http://10.0.0.1/x", allow_private=True))


class NoRealNetworkTests(unittest.TestCase):
    """Guard the helper used by tests so CI never depends on DNS."""

    def test_resolver_is_injectable(self):
        with mock.patch("socket.getaddrinfo", side_effect=AssertionError("real DNS used")):
            net_guard.check_url(
                "https://example.com/x", resolver=resolver_for("93.184.216.34")
            )


if __name__ == "__main__":
    unittest.main()
