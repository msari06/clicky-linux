from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .design import Colors, Radius, Sizes
from .effects import DEFAULT_SHADOW_MARGIN, ThinkingDots, apply_drop_shadow, fade_in


THINKING_SENTINEL = "…"

# Pixel slack used to decide "is the user effectively at the bottom?" — if the
# vertical scrollbar value is within this many px of its max, we treat the
# bubble as auto-following the stream and snap to bottom after new text.
AUTO_FOLLOW_SLACK_PX = 12


class ResponseBubble(QWidget):
    """Streaming text bubble shown next to the cursor.

    Top-level frameless top-most window. Renders as a frosted-glass card with
    a leading accent stripe, a soft drop shadow, and a small × stop button.
    Until the first real text token arrives we show three pulsing dots
    instead of the literal "…" string so the loading state feels alive.

    Long responses scroll inside the card: the label sits in a QScrollArea
    capped at `Sizes.BUBBLE_MAX_HEIGHT`. While streaming we auto-follow the
    bottom; if the user scrolls up to re-read something we leave them put
    until they return to the bottom.
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
        inner.setContentsMargins(16, 12, 6, 12)
        inner.setSpacing(8)

        # The scrollable text area and the thinking dots share a slot; we swap
        # which one is visible based on whether we've received a real text
        # token yet.
        self._text_stack = QWidget(self._card)
        stack = QStackedLayout(self._text_stack)
        stack.setContentsMargins(0, 0, 0, 0)
        self._stack = stack

        self._label = QLabel("")
        self._label.setObjectName("bubbleText")
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(Sizes.BUBBLE_MAX_WIDTH)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

        self._scroll = QScrollArea(self._text_stack)
        self._scroll.setObjectName("bubbleScroll")
        self._scroll.setWidget(self._label)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setMaximumHeight(Sizes.BUBBLE_MAX_HEIGHT)
        self._scroll.setMaximumWidth(Sizes.BUBBLE_MAX_WIDTH + 14)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        stack.addWidget(self._scroll)

        thinking_wrap = QWidget()
        thinking_layout = QHBoxLayout(thinking_wrap)
        thinking_layout.setContentsMargins(0, 6, 0, 6)
        self._thinking = ThinkingDots(color=Colors.TEXT_ON_METAL_SECONDARY)
        thinking_layout.addWidget(self._thinking, alignment=Qt.AlignmentFlag.AlignLeft)
        thinking_layout.addStretch(1)
        stack.addWidget(thinking_wrap)
        self._thinking_index = stack.indexOf(thinking_wrap)
        self._scroll_index = stack.indexOf(self._scroll)
        stack.setCurrentIndex(self._scroll_index)

        inner.addWidget(self._text_stack, stretch=1)

        self._stop = QPushButton("×", self._card)
        self._stop.setObjectName("stopBtn")
        self._stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop.setFixedSize(22, 22)
        self._stop.setToolTip("stop (Esc)")
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
            QScrollArea#bubbleScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#bubbleScroll > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(15, 17, 20, 70);
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(15, 17, 20, 130);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                border: none;
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
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
            # Reset any leftover sizing from a previous long response so the
            # bubble shrinks back down to dots-only height.
            self._label.clear()
            self._scroll.setFixedHeight(28)
            self._stack.setCurrentIndex(self._thinking_index)
            self._thinking.start()
            self.adjustSize()
            return
        self._thinking.stop()
        self._stack.setCurrentIndex(self._scroll_index)

        sb = self._scroll.verticalScrollBar()
        # "At bottom" means the user is following the stream — preserve that
        # after we re-layout. If they've scrolled up to read, leave them put.
        was_following = sb.value() >= sb.maximum() - AUTO_FOLLOW_SLACK_PX

        self._label.setText(text)
        # QLabel.heightForWidth gives a stable height for the wrapped text at
        # our fixed wrap width. The scroll area itself doesn't grow with its
        # inner widget in widgetResizable mode, so we set its height by hand —
        # capped at BUBBLE_MAX_HEIGHT, which is when the scrollbar kicks in.
        wrap_w = Sizes.BUBBLE_MAX_WIDTH
        content_h = max(self._label.heightForWidth(wrap_w), self._label.sizeHint().height())
        target_h = min(content_h + 4, Sizes.BUBBLE_MAX_HEIGHT)
        self._scroll.setFixedHeight(target_h)
        self.adjustSize()

        if was_following:
            # Snap now using the current scrollbar range, then again on the
            # next event-loop tick — the label may still be laying out after
            # the text change, which would otherwise leave us short of bottom.
            sb.setValue(sb.maximum())
            QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

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
