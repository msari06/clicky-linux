from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum, auto

from PyQt6.QtCore import QObject, QRect, pyqtSignal
from PyQt6.QtGui import QCursor

from .config import settings
from .llm.claude import ClaudeClient, ClaudeRequest, ConversationTurn, LabeledImage
from .llm.point_parser import PointingResult, parse_point_tag
from .llm.prompts import COMPANION_TEXT_RESPONSE_SYSTEM_PROMPT
from .screen.capture import CapturedScreen, capture_all_screens, capture_region
from .screen.monitors import find_monitor_at_global_point
from .ui.overlay import Overlay


logger = logging.getLogger(__name__)


class CompanionState(Enum):
    IDLE = auto()
    AWAITING_PROMPT = auto()
    PROCESSING = auto()
    RESPONDING = auto()


@dataclass
class HistoryEntry:
    user_prompt: str
    assistant_response: str


class CompanionStateMachine(QObject):
    """Central orchestrator. Equivalent to CompanionManager.swift.

    Coordinates: hotkey → overlay shows input → user types → screenshot + send to Claude →
    stream response into bubble → parse [POINT] → fly cursor.

    History is preserved across invocations within the same app session.
    """

    state_changed = pyqtSignal(CompanionState)

    def __init__(self, overlay: Overlay, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlay = overlay
        self._claude = ClaudeClient(
            endpoint_url=settings.chat_endpoint(),
            model=settings.openai_model,
            max_tokens=settings.max_tokens,
        )

        self._state = CompanionState.IDLE
        self._history: list[HistoryEntry] = []
        self._current_task: asyncio.Task | None = None

        overlay.prompt_submitted.connect(self._on_prompt_submitted)
        overlay.overlay_dismissed.connect(self._on_overlay_dismissed)

    @property
    def state(self) -> CompanionState:
        return self._state

    def _set_state(self, new_state: CompanionState) -> None:
        if new_state == self._state:
            return
        self._state = new_state
        self.state_changed.emit(new_state)

    # --- entry points called by the app ---------------------------------------

    def trigger_open_input(self) -> None:
        """Called when the hotkey fires or the tray icon is clicked."""
        if self._state in (CompanionState.PROCESSING, CompanionState.RESPONDING):
            self._cancel_current_task()
            self._overlay.dismiss()
        self._set_state(CompanionState.AWAITING_PROMPT)
        self._overlay.show_input_near_cursor()

    async def aclose(self) -> None:
        self._cancel_current_task()
        await self._claude.aclose()

    # --- slots ----------------------------------------------------------------

    def _on_prompt_submitted(self, prompt: str, region: QRect | None) -> None:
        self._set_state(CompanionState.PROCESSING)
        # Bubble shows immediately with a loading placeholder so the user gets feedback.
        self._overlay.update_bubble_text("…")
        self._overlay.show_bubble_near_cursor()

        cursor_global = QCursor.pos()
        primary_monitor = find_monitor_at_global_point(cursor_global.x(), cursor_global.y())
        primary_index = primary_monitor.index if primary_monitor else None

        self._current_task = asyncio.ensure_future(
            self._send_and_stream(prompt, primary_index, region)
        )

    def _on_overlay_dismissed(self) -> None:
        self._cancel_current_task()
        self._set_state(CompanionState.IDLE)

    # --- pipeline -------------------------------------------------------------

    async def _send_and_stream(
        self,
        prompt: str,
        primary_index: int | None,
        region: QRect | None,
    ) -> None:
        try:
            if region is not None and not region.isEmpty():
                screen = await asyncio.to_thread(
                    capture_region,
                    region.x(),
                    region.y(),
                    region.width(),
                    region.height(),
                )
                screens = [screen]
            else:
                screens = await asyncio.to_thread(capture_all_screens, primary_index)
            request = self._build_request(prompt, screens)

            self._set_state(CompanionState.RESPONDING)
            accumulated = ""
            async for chunk in self._claude.stream_response(
                request=request,
                system_prompt=COMPANION_TEXT_RESPONSE_SYSTEM_PROMPT,
            ):
                accumulated = chunk
                # Hide the trailing [POINT:...] tag while streaming if it has started to appear.
                visible = _trim_partial_point_tag(accumulated)
                self._overlay.update_bubble_text(visible)

            parsed = parse_point_tag(accumulated)
            self._overlay.update_bubble_text(parsed.spoken_text)

            self._history.append(HistoryEntry(user_prompt=prompt, assistant_response=accumulated))

            if parsed.has_coordinate:
                self._point_cursor(parsed, screens, primary_index)

            self._set_state(CompanionState.IDLE)

        except asyncio.CancelledError:
            logger.info("response task cancelled")
            raise
        except Exception as exc:
            logger.exception("response pipeline failed")
            self._overlay.update_bubble_text(f"error: {exc}")
            self._set_state(CompanionState.IDLE)

    def _build_request(self, prompt: str, screens: list[CapturedScreen]) -> ClaudeRequest:
        images = [
            LabeledImage(data=screen.image_data, label=screen.labeled_for_claude())
            for screen in screens
        ]
        history = [
            ConversationTurn(user_text=entry.user_prompt, assistant_text=entry.assistant_response)
            for entry in self._history
        ]
        return ClaudeRequest(user_prompt=prompt, images=images, history=history)

    def _point_cursor(
        self,
        parsed: PointingResult,
        screens: list[CapturedScreen],
        primary_index: int | None,
    ) -> None:
        # Choose the screen Claude referred to (or fall back to where the cursor was).
        target_screen_index = parsed.screen_number or primary_index
        target_screen = next(
            (s for s in screens if s.monitor.index == target_screen_index),
            None,
        )
        # For a region capture there's only one synthetic screen and the user
        # might never have a matching index here — fall back to it so pointing
        # still works within the cropped region.
        if target_screen is None and screens:
            target_screen = screens[0]
        if target_screen is None:
            return

        # Claude's coordinates are in the *downscaled image* space — rescale to the
        # monitor's real pixel size before mapping to global virtual-desktop coords.
        scale_x = target_screen.monitor.width / target_screen.width_pixels
        scale_y = target_screen.monitor.height / target_screen.height_pixels
        monitor_local_x = int(parsed.x * scale_x)
        monitor_local_y = int(parsed.y * scale_y)
        global_x, global_y = target_screen.monitor.global_from_local(monitor_local_x, monitor_local_y)

        cursor_pos = QCursor.pos()
        self._overlay.show_cursor_at(cursor_pos.x(), cursor_pos.y())
        self._overlay.fly_cursor_to(global_x, global_y)

    def _cancel_current_task(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self._current_task = None


def _trim_partial_point_tag(text: str) -> str:
    """Hide a half-written [POINT...] from the visible bubble while streaming."""
    idx = text.rfind("[POINT")
    if idx == -1:
        return text
    return text[:idx].rstrip()
