import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from desktop_ui.ui_effects import fade_in_page


class UiEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the process-wide application when another module already made
        # one; create it only for standalone runs.
        cls.app = QApplication.instance() or QApplication([])

    def test_none_widget_is_safe(self):
        self.assertIsNone(fade_in_page(None))

    def test_hidden_widget_is_not_animated(self):
        widget = QWidget()
        self.assertIsNone(fade_in_page(widget))
        self.assertIsNone(widget.graphicsEffect())


if __name__ == "__main__":
    unittest.main()
