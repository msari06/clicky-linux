"""Design tokens — colors, radii and sizing used across the UI.

Tuned to feel like a single designed system: dark frosted-glass panels with a
soft drop shadow, a bright cyan accent for active affordances, and a metallic
gray buddy dot. Anything UI-facing should pull values from here so we don't
end up with five subtly different "blacks" scattered across files.
"""

from __future__ import annotations


class Colors:
    # Frosted glass panel surface. The two _TOP/_BOTTOM stops are used as a
    # subtle vertical gradient inside cards — top a touch lighter, bottom a
    # touch deeper — to imply "lit from above".
    BACKGROUND_PANEL = "rgba(18, 19, 23, 232)"
    BACKGROUND_PANEL_TOP = "rgba(28, 30, 36, 232)"
    BACKGROUND_PANEL_BOTTOM = "rgba(14, 15, 18, 232)"
    BACKGROUND_INPUT = "rgba(36, 38, 44, 220)"

    BORDER_SUBTLE = "rgba(255, 255, 255, 28)"
    BORDER_HAIRLINE = "rgba(255, 255, 255, 18)"
    INNER_HIGHLIGHT = "rgba(255, 255, 255, 26)"  # 1px top inner stroke

    TEXT_PRIMARY = "#f5f5f7"
    TEXT_SECONDARY = "#9a9a9e"
    TEXT_MUTED = "#6b6b70"
    TEXT_PLACEHOLDER = "#5a5d63"

    ACCENT_BLUE = "#4d9cff"
    ACCENT_BLUE_BRIGHT = "#7eb6ff"
    ACCENT_BLUE_DEEP = "#1f6fd0"

    CURSOR_BLUE = "#1f9fff"
    CURSOR_GLOW = "#1f9fff"

    METAL_HIGHLIGHT = "#f4f6f8"
    METAL_LIGHT = "#c4c9ce"
    METAL_MID = "#7c8186"
    METAL_DEEP = "#2e3236"
    METAL_RIM = "#15171a"
    METAL_GLOW = "#aab0b6"

    # Soft metallic surfaces used by the input bar and response bubble so they
    # read as cut from the same material as the buddy dot. Vertical gradient
    # top→bottom: a touch lighter on top to imply "lit from above".
    SURFACE_METAL_TOP = "#dde1e5"
    SURFACE_METAL_BOTTOM = "#aab0b6"
    SURFACE_METAL_BORDER = "rgba(15, 17, 20, 80)"
    SURFACE_METAL_INNER_HIGHLIGHT = "rgba(255, 255, 255, 130)"

    TEXT_ON_METAL = "#1a1c1f"
    TEXT_ON_METAL_SECONDARY = "#4a4d52"
    TEXT_ON_METAL_PLACEHOLDER = "#7c8186"

    BUBBLE_BACKGROUND = "rgba(18, 19, 23, 232)"
    BUBBLE_BORDER = "rgba(255, 255, 255, 28)"


class Radius:
    PANEL = 14
    INPUT = 12
    BUBBLE = 16
    BUTTON = 8
    PILL = 999  # for fully rounded "pill" shapes; Qt clamps to height/2 anyway


class Sizes:
    PANEL_WIDTH = 340
    INPUT_HEIGHT = 44
    BUBBLE_MAX_WIDTH = 460
    BUBBLE_MAX_HEIGHT = 360
    CURSOR_SIZE = 48
    ACCENT_STRIPE_WIDTH = 3  # vertical accent on the leading edge of cards
