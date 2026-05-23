from __future__ import annotations

from dataclasses import dataclass

import mss


@dataclass(frozen=True)
class MonitorInfo:
    """A single physical display.

    `index` is 1-based to match Claude's `:screenN` notation.
    `x, y` are the top-left position in the virtual desktop coordinate space.
    """

    index: int
    x: int
    y: int
    width: int
    height: int

    def contains_global_point(self, gx: int, gy: int) -> bool:
        return self.x <= gx < self.x + self.width and self.y <= gy < self.y + self.height

    def global_from_local(self, local_x: int, local_y: int) -> tuple[int, int]:
        """Map screenshot-local coordinates (origin at this monitor's top-left)
        to global virtual-desktop coordinates."""
        return self.x + local_x, self.y + local_y


def enumerate_monitors() -> list[MonitorInfo]:
    """Return one MonitorInfo per physical display, 1-based indices.

    mss returns a 0th entry that's the union of all displays — we skip it.
    """
    with mss.mss() as sct:
        monitors: list[MonitorInfo] = []
        # mss.monitors[0] is the union of all displays; real ones start at index 1.
        for i, monitor in enumerate(sct.monitors[1:], start=1):
            monitors.append(
                MonitorInfo(
                    index=i,
                    x=monitor["left"],
                    y=monitor["top"],
                    width=monitor["width"],
                    height=monitor["height"],
                )
            )
        return monitors


def find_monitor_at_global_point(gx: int, gy: int) -> MonitorInfo | None:
    for monitor in enumerate_monitors():
        if monitor.contains_global_point(gx, gy):
            return monitor
    return None
