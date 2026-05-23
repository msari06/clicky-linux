from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QObject, QRect, pyqtSignal
from PyQt6.QtGui import QCursor

from .config import settings
from .llm.claude import ClaudeClient, ClaudeRequest, ConversationTurn, LabeledImage
from .llm.claude_code import ClaudeCodeClient, ClaudeCodeError, ClaudeCodeRequest
from .llm.point_parser import PointingResult, parse_point_tag
from .llm.prompts import COMPANION_TEXT_RESPONSE_SYSTEM_PROMPT
from .screen.capture import CapturedScreen, capture_all_screens, capture_region
from .screen.monitors import find_monitor_at_global_point
from .state_store import AgentMode, PersistedState, load_state, save_state
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


# Matches a leading `@<path> rest of prompt`. Supports quoted paths so that
# directories with spaces work too: `@"/tmp/my dir" do X`.
_WORKSPACE_PREFIX_RE = re.compile(r'^@(?:"([^"]+)"|(\S+))\s+(.+)$', re.DOTALL)


class CompanionStateMachine(QObject):
    """Central orchestrator. Equivalent to CompanionManager.swift.

    Two operating modes:
      - vision (default): screenshot + question → OpenAI vision via the
        Cloudflare Worker → streamed answer + [POINT] cursor animation.
      - code: question → spawn `claude -p` as a subprocess in a configured
        workspace → stream Claude Code's progress (text + tool chips) into
        the same bubble.

    The current mode is remembered across runs via the state store.
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
        self._claude_code = ClaudeCodeClient(binary_path=settings.claude_code_path)

        self._persisted: PersistedState = load_state()
        if not self._persisted.claude_code_workspace:
            self._persisted.claude_code_workspace = settings.claude_code_workspace

        self._state = CompanionState.IDLE
        self._history: list[HistoryEntry] = []
        self._current_task: asyncio.Task | None = None

        overlay.prompt_submitted.connect(self._on_prompt_submitted)
        overlay.overlay_dismissed.connect(self._on_overlay_dismissed)
        overlay.mode_changed.connect(self._on_mode_changed)
        overlay.allow_shell_changed.connect(self._on_allow_shell_changed)
        overlay.workspace_changed.connect(self._on_workspace_changed)

        overlay.apply_agent_mode(
            self._persisted.agent_mode,
            workspace=self._persisted.claude_code_workspace or "",
            allow_shell=self._persisted.claude_code_allow_shell,
        )

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
        self._overlay.update_bubble_text("…")
        self._overlay.show_bubble_near_cursor()

        if self._persisted.agent_mode == "code":
            workspace, stripped = self._parse_workspace_prefix(prompt)
            self._current_task = asyncio.ensure_future(
                self._run_claude_code(stripped, workspace)
            )
            return

        cursor_global = QCursor.pos()
        primary_monitor = find_monitor_at_global_point(cursor_global.x(), cursor_global.y())
        primary_index = primary_monitor.index if primary_monitor else None

        self._current_task = asyncio.ensure_future(
            self._run_vision(prompt, primary_index, region)
        )

    def _on_overlay_dismissed(self) -> None:
        self._cancel_current_task()
        self._set_state(CompanionState.IDLE)

    def _on_mode_changed(self, mode: str) -> None:
        if mode not in ("vision", "code"):
            return
        if mode == self._persisted.agent_mode:
            return
        self._persisted.agent_mode = cast(AgentMode, mode)
        save_state(self._persisted)
        logger.info("agent mode → %s", mode)

    def _on_allow_shell_changed(self, allow: bool) -> None:
        if allow == self._persisted.claude_code_allow_shell:
            return
        self._persisted.claude_code_allow_shell = allow
        save_state(self._persisted)
        logger.info("claude code shell access → %s", allow)

    def _on_workspace_changed(self, workspace: str) -> None:
        if not workspace or workspace == self._persisted.claude_code_workspace:
            return
        self._persisted.claude_code_workspace = workspace
        save_state(self._persisted)
        logger.info("claude code workspace → %s", workspace)

    # --- vision pipeline ------------------------------------------------------

    async def _run_vision(
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
            request = self._build_vision_request(prompt, screens)

            self._set_state(CompanionState.RESPONDING)
            accumulated = ""
            async for chunk in self._claude.stream_response(
                request=request,
                system_prompt=COMPANION_TEXT_RESPONSE_SYSTEM_PROMPT,
            ):
                accumulated = chunk
                visible = _trim_partial_point_tag(accumulated)
                self._overlay.update_bubble_text(visible)

            parsed = parse_point_tag(accumulated)
            self._overlay.update_bubble_text(parsed.spoken_text)

            self._history.append(HistoryEntry(user_prompt=prompt, assistant_response=accumulated))

            if parsed.has_coordinate:
                self._point_cursor(parsed, screens, primary_index)

            self._set_state(CompanionState.IDLE)

        except asyncio.CancelledError:
            logger.info("vision task cancelled")
            raise
        except Exception as exc:
            logger.exception("vision pipeline failed")
            self._overlay.update_bubble_text(f"error: {exc}")
            self._set_state(CompanionState.IDLE)

    def _build_vision_request(self, prompt: str, screens: list[CapturedScreen]) -> ClaudeRequest:
        images = [
            LabeledImage(data=screen.image_data, label=screen.labeled_for_claude())
            for screen in screens
        ]
        history = [
            ConversationTurn(user_text=entry.user_prompt, assistant_text=entry.assistant_response)
            for entry in self._history
        ]
        return ClaudeRequest(user_prompt=prompt, images=images, history=history)

    # --- code-mode pipeline ---------------------------------------------------

    async def _run_claude_code(self, prompt: str, workspace_override: str | None) -> None:
        try:
            workspace_str = workspace_override or self._persisted.claude_code_workspace or ""
            workspace = Path(workspace_str).expanduser()

            request = ClaudeCodeRequest(
                prompt=prompt,
                cwd=workspace,
                allow_shell=self._persisted.claude_code_allow_shell,
                model=settings.claude_code_model or None,
                max_turns=settings.claude_code_max_turns or None,
            )

            self._set_state(CompanionState.RESPONDING)
            header = f"workspace: {_friendly_path(workspace)}\n\n"
            accumulated = ""
            async for chunk in self._claude_code.stream_response(request):
                accumulated = chunk
                self._overlay.update_bubble_text(header + accumulated)

            if not accumulated.strip():
                self._overlay.update_bubble_text(header + "(no output)")
            self._set_state(CompanionState.IDLE)

        except ClaudeCodeError as exc:
            logger.warning("claude code error: %s", exc)
            self._overlay.update_bubble_text(str(exc))
            self._set_state(CompanionState.IDLE)
        except asyncio.CancelledError:
            logger.info("claude code task cancelled")
            raise
        except Exception as exc:
            logger.exception("claude code pipeline failed")
            self._overlay.update_bubble_text(f"error: {exc}")
            self._set_state(CompanionState.IDLE)

    def _parse_workspace_prefix(self, prompt: str) -> tuple[str | None, str]:
        """Pull a leading `@/path/to/dir ...` (or `@"path with spaces" ...`) off the prompt.

        Returns (workspace_override_or_None, remaining_prompt).
        """
        match = _WORKSPACE_PREFIX_RE.match(prompt.strip())
        if not match:
            return None, prompt
        quoted, unquoted, rest = match.groups()
        path = quoted or unquoted
        try:
            resolved = str(Path(path).expanduser())
        except (OSError, RuntimeError):
            return None, prompt
        return resolved, rest

    # --- pointer animation ----------------------------------------------------

    def _point_cursor(
        self,
        parsed: PointingResult,
        screens: list[CapturedScreen],
        primary_index: int | None,
    ) -> None:
        target_screen_index = parsed.screen_number or primary_index
        target_screen = next(
            (s for s in screens if s.monitor.index == target_screen_index),
            None,
        )
        if target_screen is None and screens:
            target_screen = screens[0]
        if target_screen is None:
            return

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


def _friendly_path(path: Path) -> str:
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        return "~" + s[len(home):]
    return s


__all__ = ["CompanionState", "CompanionStateMachine"]
