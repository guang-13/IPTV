import unittest
from types import SimpleNamespace
from unittest import mock

from utils import notify


def fake_config(**overrides):
    base = {
        "language": "zh_CN",
        "notify_webhook": "",
        "notify_telegram_bot_token": "",
        "notify_telegram_chat_id": "",
        "notify_on_success": False,
        "notify_on_failure": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class BuildMessageTests(unittest.TestCase):
    def test_chinese_message_contains_status(self):
        with mock.patch.object(notify, "config", fake_config()):
            message = notify.build_message("success", {"run_id": "r1"})
        self.assertIn("成功", message)

    def test_english_message_contains_status(self):
        with mock.patch.object(notify, "config", fake_config(language="en")):
            message = notify.build_message("failed", {"message": "boom"})
        self.assertIn("failed", message)
        self.assertIn("boom", message)

    def test_message_never_contains_source_urls_by_design(self):
        with mock.patch.object(notify, "config", fake_config()):
            message = notify.build_message("success", {"run_id": "r1"})
        self.assertNotIn("http", message)


class SendPolicyTests(unittest.TestCase):
    def test_failure_is_notified_by_default(self):
        with mock.patch.object(notify, "config", fake_config()):
            self.assertTrue(notify._should_send("failed"))

    def test_success_is_quiet_by_default(self):
        with mock.patch.object(notify, "config", fake_config()):
            self.assertFalse(notify._should_send("success"))

    def test_success_can_be_enabled(self):
        with mock.patch.object(notify, "config", fake_config(notify_on_success=True)):
            self.assertTrue(notify._should_send("success"))

    def test_failure_can_be_disabled(self):
        with mock.patch.object(notify, "config", fake_config(notify_on_failure=False)):
            self.assertFalse(notify._should_send("failed"))


class TransportSafetyTests(unittest.TestCase):
    def test_webhook_requires_http_scheme(self):
        with mock.patch.object(notify, "config", fake_config(notify_webhook="file:///tmp/x")):
            self.assertFalse(notify._send_webhook("message", "failed", {}))

    def test_telegram_requires_both_fields(self):
        with mock.patch.object(notify, "config", fake_config(
            notify_telegram_bot_token="token", notify_telegram_chat_id=""
        )):
            self.assertFalse(notify._send_telegram("message"))

    def test_delivery_failure_never_raises(self):
        with mock.patch.object(notify, "config", fake_config(
            notify_webhook="http://127.0.0.1:9/hook"
        )):
            with mock.patch.object(notify, "_post_json", side_effect=OSError("down")):
                reporter = mock.Mock()
                self.assertFalse(notify.notify_run_finished("failed", {}, reporter=reporter))
                reporter.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
