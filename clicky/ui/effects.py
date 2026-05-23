"""Small reusable UI effect helpers shared across panels and overlays.

Centralizing these here keeps the styling consistent (one shadow strength, one
fade duration, one accent stripe geometry) so the floating UI feels like one
designed system rather than a pile of independent widgets.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget


# How much breathing room the parent must reserve around a shadowed card.
# Use it as the outer-margin of the layout that holds the card so the shadow
# doesn't get clipped at the top-level window edge.
DEFAULT_SHADOW_MARGIN = 40


def apply_drop_shadow(
    widget: QWidget,
    *,
    blur: int = 36,
    dy: int = 10,
    alpha: int = 150,
    color: str = "#000000",
) -> QGraphicsDropShadowEffect:
    """Attach a soft drop shadow to ``widget`` and return the effect.

    The host top-level window must have a transparent background and enough
    margin around ``widget`` to fit the shadow — use ``DEFAULT_SHADOW_MARGIN``
    on the surrounding layout's contents margins.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    qcolor = QColor(color)
    qcolor.setAlpha(alpha)
    effect.setColor(qcolor)
    widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, *, duration_ms: int = 160) -> QPropertyAnimation:
    """Animate ``windowOpacity`` from 0 → 1 over the given duration.

    Returns the running animation so callers can keep a reference; the
    animation is started immediately. Safe to call on every show() — the
    widget just re-fades in.
    """
    widget.setWindowOpacity(0.0)
    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    # Stash the anim on the widget so Python doesn't garbage-collect it mid-flight.
    widget._fade_in_anim = anim  # type: ignore[attr-defined]
    return anim


class ThinkingDots(QWidget):
    """Three pulsing dots used while waiting on the LLM's first token.

    Each dot's alpha is driven by a phase-shifted sine of a single shared
    QPropertyAnimation, so the three dots breathe in a staggered rhythm
    without three independent timers.
    """

    DOT_SIZE = 6
    DOT_GAP = 6
    DOT_COUNT = 3
    PERIOD_MS = 1200

    def __init__(self, parent: QWidget | None = None, color: str = "#cbd0d6") -> None:
        super().__init__(parent)
        self._color = QColor(color)
        total_width = self.DOT_COUNT * self.DOT_SIZE + (self.DOT_COUNT - 1) * self.DOT_GAP
        self.setFixedSize(total_width, self.DOT_SIZE + 4)
        self._phase = 0.0
        self._anim = QPropertyAnimation(self, b"phase")
        self._anim.setDuration(self.PERIOD_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)

    def start(self) -> None:
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._anim.start()

    def stop(self) -> None:
        self._anim.stop()

    def get_phase(self) -> float:
        return self._phase

    def set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = pyqtProperty(float, fget=get_phase, fset=set_phase)

    def paintEvent(self, event) -> None:  # noqa: ARG002 — Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        y = (self.height() - self.DOT_SIZE) / 2
        for i in range(self.DOT_COUNT):
            phase = (self._phase + i / self.DOT_COUNT) % 1.0
            alpha = 80 + int(160 * (0.5 - 0.5 * math.cos(phase * math.pi * 2)))
            c = QColor(self._color)
            c.setAlpha(alpha)
            painter.setBrush(c)
            x = i * (self.DOT_SIZE + self.DOT_GAP)
            painter.drawEllipse(int(x), int(y), self.DOT_SIZE, self.DOT_SIZE)


class MarchingAntsTicker:
    """Drives a dash-offset counter and repaints a target widget so its border
    pen with a dashed style appears to "march". Single timer per overlay.
    """

    def __init__(
        self,
        target: QWidget,
        *,
        interval_ms: int = 80,
        step: float = 1.0,
    ) -> None:
        self._offset = 0.0
        self._step = step
        self._target = target
        self._timer = QTimer(target)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._offset = (self._offset + self._step) % 1_000_000
        self._target.update()

    @property
    def offset(self) -> float:
        return self._offset
