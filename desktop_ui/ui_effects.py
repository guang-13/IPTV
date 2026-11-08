"""Small, dependency-light UI effects shared by desktop pages."""

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect

PAGE_FADE_MS = 130


def fade_in_page(widget, duration=PAGE_FADE_MS, start=0.88):
    """Fade a freshly activated page in; a no-op when effects are unsafe.

    macOS keeps native window composition, where a transient graphics effect can
    expose intermediate frames, so the fade is skipped there.
    """
    if widget is None or sys.platform == "darwin":
        return None
    window = widget.window()
    if window is None or not window.isVisible():
        # Offscreen/headless windows gain nothing from a fade and tests must not
        # depend on animation timing.
        return None
    existing = widget.graphicsEffect()
    if existing is not None and not isinstance(existing, QGraphicsOpacityEffect):
        return None
    effect = existing
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(start)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation
