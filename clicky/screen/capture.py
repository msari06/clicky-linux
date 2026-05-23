from __future__ import annotations

import io
from dataclasses import dataclass

import mss
from PIL import Image

from .monitors import MonitorInfo, enumerate_monitors


@dataclass
class CapturedScreen:
    monitor: MonitorInfo
    image_data: bytes  # JPEG-encoded
    width_pixels: int
    height_pixels: int
    is_primary_focus: bool
    is_user_region: bool = False  # True when this came from a manual area selection

    def labeled_for_claude(self) -> str:
        """The text label sent alongside the image so the LLM knows what this is."""
        if self.is_user_region:
            return (
                f"user-selected region "
                f"(image dimensions: {self.width_pixels}x{self.height_pixels} pixels). "
                f"the user explicitly picked this area — focus your answer on what's inside."
            )
        focus = " — primary focus" if self.is_primary_focus else ""
        return (
            f"screen{self.monitor.index}{focus} "
            f"(image dimensions: {self.width_pixels}x{self.height_pixels} pixels)"
        )


def capture_all_screens(
    primary_focus_index: int | None = None,
    jpeg_quality: int = 75,
    max_long_side: int = 1600,
) -> list[CapturedScreen]:
    """Capture every connected monitor as JPEG.

    `primary_focus_index` is the 1-based screen index where the cursor lives — gets
    labeled "primary focus" in its caption so Claude prioritizes it.

    Each screenshot is downscaled so its long edge fits `max_long_side` pixels.
    This keeps payload size reasonable; Claude's vision quality on large screenshots
    is barely affected. The pixel dimensions in the label always match the *downscaled*
    image so Claude's coordinates land in the downscaled space — we rescale them back
    to the monitor's real resolution before pointing the cursor.
    """
    monitors = enumerate_monitors()
    captures: list[CapturedScreen] = []

    with mss.mss() as sct:
        for monitor in monitors:
            grabbed = sct.grab(
                {
                    "left": monitor.x,
                    "top": monitor.y,
                    "width": monitor.width,
                    "height": monitor.height,
                }
            )
            # mss returns BGRA; PIL needs RGB
            image = Image.frombytes("RGB", grabbed.size, grabbed.rgb)

            if max(image.size) > max_long_side:
                scale = max_long_side / max(image.size)
                new_size = (int(image.size[0] * scale), int(image.size[1] * scale))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=jpeg_quality)
            captures.append(
                CapturedScreen(
                    monitor=monitor,
                    image_data=buffer.getvalue(),
                    width_pixels=image.size[0],
                    height_pixels=image.size[1],
                    is_primary_focus=(monitor.index == primary_focus_index),
                )
            )

    return captures


def capture_region(
    global_x: int,
    global_y: int,
    width: int,
    height: int,
    jpeg_quality: int = 80,
    max_long_side: int = 1600,
) -> CapturedScreen:
    """Capture a single rectangular region of the virtual desktop.

    ``global_x, global_y, width, height`` are in the same coordinate space as
    ``MonitorInfo.x/y/width/height`` (i.e. the virtual-desktop coords mss
    reports). The returned ``CapturedScreen`` carries a synthetic ``MonitorInfo``
    whose origin and dimensions match the region — so the existing pointing
    coordinate rescale logic in the state machine maps the LLM's coordinates
    back to global screen coords without any special-casing.
    """
    width = max(1, int(width))
    height = max(1, int(height))

    with mss.mss() as sct:
        grabbed = sct.grab(
            {
                "left": int(global_x),
                "top": int(global_y),
                "width": width,
                "height": height,
            }
        )
        image = Image.frombytes("RGB", grabbed.size, grabbed.rgb)

    if max(image.size) > max_long_side:
        scale = max_long_side / max(image.size)
        new_size = (int(image.size[0] * scale), int(image.size[1] * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=jpeg_quality)

    region_monitor = MonitorInfo(
        index=1,
        x=int(global_x),
        y=int(global_y),
        width=width,
        height=height,
    )
    return CapturedScreen(
        monitor=region_monitor,
        image_data=buffer.getvalue(),
        width_pixels=image.size[0],
        height_pixels=image.size[1],
        is_primary_focus=True,
        is_user_region=True,
    )
