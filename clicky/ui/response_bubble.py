from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .design import Colors, Radius, Sizes
from .effects import DEFAULT_SHADOW_MARGIN, ThinkingDots, apply_drop_shadow, fade_in


THINKING_SENTINEL = "…"


class ResponseBubble(QWidget):
    """Streaming text bubble shown next to the cursor.

    Top-level frameless top-most window. Renders as a frosted-glass card with
    a leading accent stripe, a soft drop shadow, and a small × stop button.
    Until the first real text token arrives we show three pulsing dots
    instead of the literal "…" string so the loading state feels alive.
    """

    stop_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN
        )

        self._card = QFrame(self)
        self._card.setObjectName("bubble")
        self._card.setStyleSheet(self._stylesheet())
        outer.addWidget(self._card)

        apply_drop_shadow(self._card, blur=24, dy=6, alpha=110)

        inner = QHBoxLayout(self._card)
        inner.setContentsMargins(16, 12, 10, 12)
        inner.setSpacing(10)

        # The text label and the thinking dots share a slot; we swap which one
        # is visible based on whether we've received a real text token yet.
        self._text_stack = QWidget(self._card)
        stack = QStackedLayout(self._text_stack)
        stack.setContentsMargins(0, 0, 0, 0)
        self._stack = stack

        self._label = QLabel("")
        self._label.setObjectName("bubbleText")
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(Sizes.BUBBLE_MAX_WIDTH)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        stack.addWidget(self._label)

        thinking_wrap = QWidget()
        thinking_layout = QHBoxLayout(thinking_wrap)
        thinking_layout.setContentsMargins(0, 6, 0, 6)
        self._thinking = ThinkingDots(color=Colors.TEXT_ON_METAL_SECONDARY)
        thinking_layout.addWidget(self._thinking, alignment=Qt.AlignmentFlag.AlignLeft)
        thinking_layout.addStretch(1)
        stack.addWidget(thinking_wrap)
        self._thinking_index = stack.indexOf(thinking_wrap)
        self._label_index = stack.indexOf(self._label)
        stack.setCurrentIndex(self._label_index)

        inner.addWidget(self._text_stack, stretch=1)

        self._stop = QPushButton("×", self._card)
        self._stop.setObjectName("stopBtn")
        self._stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop.setFixedSize(22, 22)
        self._stop.setToolTip("durdur (Esc)")
        self._stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._stop.clicked.connect(self.stop_requested.emit)
        inner.addWidget(self._stop, alignment=Qt.AlignmentFlag.AlignTop)

        self.hide()

    def _stylesheet(self) -> str:
        return f"""
            QFrame#bubble {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.SURFACE_METAL_TOP},
                    stop:1 {Colors.SURFACE_METAL_BOTTOM}
                );
                border: 1px solid {Colors.SURFACE_METAL_BORDER};
                border-top: 1px solid {Colors.SURFACE_METAL_INNER_HIGHLIGHT};
                border-radius: {Radius.BUBBLE}px;
            }}
            QLabel#bubbleText {{
                color: {Colors.TEXT_ON_METAL};
                font-size: 14px;
                background: transparent;
                line-height: 1.4;
            }}
            QPushButton#stopBtn {{
                color: {Colors.TEXT_ON_METAL_SECONDARY};
                background: rgba(15, 17, 20, 24);
                border: 1px solid rgba(15, 17, 20, 50);
                border-radius: 11px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#stopBtn:hover {{
                color: #b3261e;
                background: rgba(179, 38, 30, 36);
                border-color: rgba(179, 38, 30, 130);
            }}
            QPushButton#stopBtn:pressed {{
                background: rgba(179, 38, 30, 80);
            }}
        """

    # --- public API --------------------------------------------------------

    def set_text(self, text: str) -> None:
        if text == THINKING_SENTINEL:
            self._stack.setCurrentIndex(self._thinking_index)
            self._thinking.start()
            return
        self._thinking.stop()
        self._stack.setCurrentIndex(self._label_index)
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

    def show_at_global(self, global_x: int, global_y: int) -> None:
        x = global_x - DEFAULT_SHADOW_MARGIN
        y = global_y - DEFAULT_SHADOW_MARGIN
        self.adjustSize()
        self.move(x, y)
        self.show()
        self.raise_()
        fade_in(self)

    def hide(self) -> None:
        self._thinking.stop()
        super().hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.stop_requested.emit()
            return
        super().keyPressEvent(event)
