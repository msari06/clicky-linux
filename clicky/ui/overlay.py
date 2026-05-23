from __future__ import annotations

from PyQt6.QtCore import QObject, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QKeyEvent, QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .area_selector import AreaSelectorOverlay
from .cursor import BlueCursor
from .design import Colors, Radius
from .effects import DEFAULT_SHADOW_MARGIN, apply_drop_shadow, fade_in
from .response_bubble import ResponseBubble


CARD_INNER_WIDTH = 480


class _InputCard(QWidget):
    """Floating input box anchored near the cursor.

    Top-level frameless top-most window with a frosted-glass card inside.
    A soft drop shadow renders in the surrounding transparent margin, and a
    thin accent stripe on the left edge gives the panel an identity (mirrors
    the bubble's accent so the two read as the same "channel").
    """

    submitted = pyqtSignal(str)
    cancelled = pyqtSignal()
    area_select_requested = pyqtSignal()
    area_cleared = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN, DEFAULT_SHADOW_MARGIN
        )

        self._card = QFrame(self)
        self._card.setObjectName("inputCard")
        self._card.setFixedWidth(CARD_INNER_WIDTH)
        self._card.setStyleSheet(self._stylesheet())
        outer.addWidget(self._card)
        self.setFixedWidth(CARD_INNER_WIDTH + 2 * DEFAULT_SHADOW_MARGIN)

        # Softer, smaller shadow than the previous dark cards — the light
        # metallic surface only needs a gentle lift, not a heavy block shadow.
        apply_drop_shadow(self._card, blur=24, dy=6, alpha=110)

        row = QHBoxLayout(self._card)
        row.setContentsMargins(16, 10, 10, 10)
        row.setSpacing(10)

        self._line_edit = QLineEdit(self._card)
        self._line_edit.setPlaceholderText("ask clicky anything…")
        self._line_edit.returnPressed.connect(self._on_return)
        self._line_edit.setMinimumHeight(28)
        # Qt6 doesn't expose ::placeholder in qss; set placeholder color through
        # the palette so it stays soft against the metallic surface.
        _palette = self._line_edit.palette()
        _palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(Colors.TEXT_ON_METAL_PLACEHOLDER))
        self._line_edit.setPalette(_palette)
        row.addWidget(self._line_edit, stretch=1)

        # Selection badge — only visible when an area has been picked.
        self._badge = QFrame(self._card)
        self._badge.setObjectName("badge")
        badge_layout = QHBoxLayout(self._badge)
        badge_layout.setContentsMargins(8, 2, 4, 2)
        badge_layout.setSpacing(2)
        self._badge_label = QLabel("", self._badge)
        self._badge_label.setObjectName("badgeLabel")
        badge_layout.addWidget(self._badge_label)
        self._badge_clear = QPushButton("×", self._badge)
        self._badge_clear.setObjectName("badgeClear")
        self._badge_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._badge_clear.setFixedSize(18, 18)
        self._badge_clear.setToolTip("seçimi temizle")
        self._badge_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._badge_clear.clicked.connect(self._on_clear_area)
        badge_layout.addWidget(self._badge_clear)
        self._badge.hide()
        row.addWidget(self._badge)

        self._area_btn = QPushButton("◫  alan seç", self._card)
        self._area_btn.setObjectName("areaBtn")
        self._area_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._area_btn.setToolTip("ekranda alan seç (sonra yaz, Enter)")
        self._area_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._area_btn.clicked.connect(self.area_select_requested.emit)
        row.addWidget(self._area_btn)

    def _stylesheet(self) -> str:
        return f"""
            QFrame#inputCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Colors.SURFACE_METAL_TOP},
                    stop:1 {Colors.SURFACE_METAL_BOTTOM}
                );
                border: 1px solid {Colors.SURFACE_METAL_BORDER};
                border-top: 1px solid {Colors.SURFACE_METAL_INNER_HIGHLIGHT};
                border-radius: {Radius.INPUT}px;
            }}
            QLineEdit {{
                background-color: transparent;
                border: none;
                color: {Colors.TEXT_ON_METAL};
                font-size: 15px;
                padding: 0;
                selection-background-color: rgba(31, 111, 208, 120);
                selection-color: {Colors.TEXT_PRIMARY};
            }}
            QPushButton#areaBtn {{
                background-color: rgba(255, 255, 255, 80);
                border: 1px solid rgba(15, 17, 20, 50);
                border-radius: 8px;
                color: {Colors.TEXT_ON_METAL_SECONDARY};
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton#areaBtn:hover {{
                color: {Colors.TEXT_ON_METAL};
                background-color: rgba(255, 255, 255, 140);
                border-color: rgba(15, 17, 20, 100);
            }}
            QPushButton#areaBtn:pressed {{
                background-color: rgba(15, 17, 20, 18);
            }}
            QFrame#badge {{
                background-color: rgba(31, 111, 208, 60);
                border: 1px solid rgba(31, 111, 208, 140);
                border-radius: 8px;
            }}
            QLabel#badgeLabel {{
                color: #0e3b78;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }}
            QPushButton#badgeClear {{
                background: transparent;
                border: none;
                color: #0e3b78;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#badgeClear:hover {{
                color: {Colors.TEXT_ON_METAL};
            }}
        """

    # --- public API --------------------------------------------------------

    def show_at_global(self, global_x: int, global_y: int) -> None:
        # The window is wider than the visible card by 2*shadow_margin so we
        # have to offset the requested position so the *card's* top-left lands
        # at the requested point rather than the window's.
        x = global_x - DEFAULT_SHADOW_MARGIN
        y = global_y - DEFAULT_SHADOW_MARGIN
        x, y = self._clamp_to_screen(x, y)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._line_edit.setFocus()
        fade_in(self)

    def reset_prompt_text(self) -> None:
        self._line_edit.clear()

    def set_selected_area(self, rect: QRect | None) -> None:
        if rect is None or rect.isEmpty():
            self._badge.hide()
            return
        self._badge_label.setText(f"◫ {rect.width()}×{rect.height()}")
        self._badge.show()
        self.adjustSize()

    def _clamp_to_screen(self, gx: int, gy: int) -> tuple[int, int]:
        target_screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if target_screen is None:
            return gx, gy
        avail = target_screen.availableGeometry()
        w = self.sizeHint().width() or self.width()
        h = self.sizeHint().height() or self.height()
        x = min(max(gx, avail.left() - DEFAULT_SHADOW_MARGIN), avail.right() - w + DEFAULT_SHADOW_MARGIN)
        y = min(max(gy, avail.top() - DEFAULT_SHADOW_MARGIN), avail.bottom() - h + DEFAULT_SHADOW_MARGIN)
        return x, y

    def _on_return(self) -> None:
        text = self._line_edit.text().strip()
        if text:
            self.submitted.emit(text)

    def _on_clear_area(self) -> None:
        self.set_selected_area(None)
        self.area_cleared.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


class Overlay(QObject):
    """Coordinator for the floating UI pieces:
      • BlueCursor — the always-on "buddy" that follows the mouse
      • _InputCard — the prompt input bar opened by the hotkey
      • ResponseBubble — the streaming response shown next to the cursor
      • AreaSelectorOverlay — the dim-and-drag region picker
    """

    prompt_submitted = pyqtSignal(str, object)  # (prompt, QRect | None)
    overlay_dismissed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._cursor = BlueCursor()
        self._input_card = _InputCard()
        self._bubble = ResponseBubble()
        self._area_selector = AreaSelectorOverlay()

        self._selected_area: QRect | None = None

        self._input_card.submitted.connect(self._handle_input_submit)
        self._input_card.cancelled.connect(self.dismiss)
        self._input_card.area_select_requested.connect(self._begin_area_selection)
        self._input_card.area_cleared.connect(self._clear_selected_area)
        self._bubble.stop_requested.connect(self.dismiss)
        self._area_selector.area_selected.connect(self._on_area_selected)
        self._area_selector.cancelled.connect(self._on_area_selection_cancelled)

        self._cursor.start_tracking_mouse()

    # --- public API used by the state machine ---------------------------------

    def show_input_near_cursor(self) -> None:
        cursor_pos = QCursor.pos()
        self._bubble.hide()
        self._input_card.reset_prompt_text()
        self._input_card.set_selected_area(self._selected_area)
        self._input_card.show_at_global(cursor_pos.x() + 28, cursor_pos.y() + 4)

    def show_bubble_near_cursor(self) -> None:
        cursor_pos = QCursor.pos()
        self._input_card.hide()
        self._bubble.show_at_global(cursor_pos.x() + 32, cursor_pos.y() + 28)

    def update_bubble_text(self, text: str) -> None:
        self._bubble.set_text(text)

    def show_cursor_at(self, global_x: int, global_y: int) -> None:
        self._cursor.stop_tracking_mouse()
        self._cursor.show_at(global_x, global_y)

    def fly_cursor_to(self, global_x: int, global_y: int) -> None:
        self._cursor.fly_to(global_x, global_y)

    def hide_input(self) -> None:
        self._input_card.hide()

    def dismiss(self) -> None:
        self._input_card.hide()
        self._bubble.hide()
        self._area_selector.hide()
        self._cursor.start_tracking_mouse()
        self.overlay_dismissed.emit()

    # --- area selection -------------------------------------------------------

    def _begin_area_selection(self) -> None:
        self._input_card.hide()
        self._area_selector.begin()

    def _on_area_selected(self, rect: QRect) -> None:
        self._selected_area = rect
        self.show_input_near_cursor()

    def _on_area_selection_cancelled(self) -> None:
        self.show_input_near_cursor()

    def _clear_selected_area(self) -> None:
        self._selected_area = None

    # --- internals ------------------------------------------------------------

    def _handle_input_submit(self, prompt: str) -> None:
        self._input_card.hide()
        region = self._selected_area
        self._selected_area = None
        self.prompt_submitted.emit(prompt, region)
