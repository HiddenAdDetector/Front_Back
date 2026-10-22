"""Style and geometry rules for visually hidden illegal-advertising text."""

from __future__ import annotations

import math
import re
from typing import Any

from .models import Element

MIN_CONTRAST_RATIO = 1.1
MAX_HIDDEN_FONT_SIZE_PX = 1.0
OFFSCREEN_THRESHOLD_PX = -1000.0
MAX_CLIPPED_SIZE_PX = 1.0
TRANSPARENT_ALPHA_THRESHOLD = 0.01

COLLECTOR_STYLE_KEYS: tuple[str, ...] = (
    "opacity",
    "ancestorOpacity",
    "color",
    "backgroundColor",
    "effectiveBackground",
    "fontSize",
    "display",
    "ancestorDisplayNone",
    "visibility",
    "position",
    "left",
    "top",
    "clip",
    "clipPath",
    "overflow",
    "textIndent",
    "width",
    "height",
)

ACCESSIBILITY_LOCATION_MARKERS: tuple[str, ...] = (
    "sr-only",
    "visually-hidden",
    "screen-reader-text",
    "screenreader-only",
    "skip-link",
    "skip-to-content",
)

_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
_RGB_RE = re.compile(r"rgba?\((.*)\)", re.IGNORECASE)
_HEX_RE = re.compile(r"#([0-9a-f]{3,8})\Z", re.IGNORECASE)


def is_accessibility_location(location: str) -> bool:
    """Return whether a selector names a common accessibility-only class."""

    folded = location.casefold()
    return any(marker in folded for marker in ACCESSIBILITY_LOCATION_MARKERS)


def _style(element: Element, key: str, default: str = "") -> str:
    value = element.style.get(key, default)
    return default if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    if value is None:
        return None
    match = _NUMBER_RE.search(str(value).strip())
    if match is None:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "none"}


def _channel(value: str) -> float | None:
    value = value.strip()
    number = _number(value)
    if number is None:
        return None
    if value.endswith("%"):
        return max(0.0, min(255.0, number * 2.55))
    return max(0.0, min(255.0, number))


def _alpha(value: str) -> float | None:
    value = value.strip()
    number = _number(value)
    if number is None:
        return None
    if value.endswith("%"):
        number /= 100.0
    return max(0.0, min(1.0, number))


def _parse_color(value: str) -> tuple[float, float, float, float] | None:
    folded = value.strip().casefold()
    if folded == "transparent":
        return 0.0, 0.0, 0.0, 0.0

    rgb_match = _RGB_RE.fullmatch(folded)
    if rgb_match:
        parts = [part.strip() for part in re.split(r"\s*[,/]\s*|\s+", rgb_match.group(1)) if part.strip()]
        if len(parts) not in {3, 4}:
            return None
        channels = [_channel(part) for part in parts[:3]]
        alpha = _alpha(parts[3]) if len(parts) == 4 else 1.0
        if any(channel is None for channel in channels) or alpha is None:
            return None
        return channels[0], channels[1], channels[2], alpha  # type: ignore[return-value]

    hex_match = _HEX_RE.fullmatch(folded)
    if not hex_match:
        return None
    digits = hex_match.group(1)
    if len(digits) in {3, 4}:
        digits = "".join(character * 2 for character in digits)
    if len(digits) not in {6, 8}:
        return None
    red, green, blue = (int(digits[index : index + 2], 16) for index in (0, 2, 4))
    alpha = int(digits[6:8], 16) / 255.0 if len(digits) == 8 else 1.0
    return float(red), float(green), float(blue), alpha


def _relative_luminance(color: tuple[float, float, float]) -> float:
    def linear(channel: float) -> float:
        channel /= 255.0
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(
    foreground: tuple[float, float, float, float],
    background: tuple[float, float, float, float],
) -> float | None:
    if background[3] <= TRANSPARENT_ALPHA_THRESHOLD:
        # TODO: B may later provide the effective ancestor background color.
        return None
    alpha = foreground[3]
    blended = tuple(
        foreground[index] * alpha + background[index] * (1.0 - alpha)
        for index in range(3)
    )
    foreground_luminance = _relative_luminance(blended)
    background_luminance = _relative_luminance(background[:3])
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def is_transparent(element: Element) -> bool:
    """Return whether a nonblank element is effectively transparent."""

    if not element.text.strip():
        return False

    opacity = _number(_style(element, "opacity", "1"))
    if opacity is not None and opacity <= TRANSPARENT_ALPHA_THRESHOLD:
        return True
    if "ancestorOpacity" in element.style:
        ancestor_opacity = _number(_style(element, "ancestorOpacity", "1"))
        if ancestor_opacity is not None and ancestor_opacity <= TRANSPARENT_ALPHA_THRESHOLD:
            return True

    foreground = _parse_color(_style(element, "color"))
    if foreground is not None and foreground[3] <= TRANSPARENT_ALPHA_THRESHOLD:
        return True
    background = _parse_color(_style(element, "backgroundColor"))
    if background is not None and background[3] <= TRANSPARENT_ALPHA_THRESHOLD:
        # B resolves inheritance/compositing by walking ancestors to the first
        # opaque background. If absent, color contrast remains indeterminate.
        effective_background = _parse_color(_style(element, "effectiveBackground"))
        if effective_background is not None:
            background = effective_background
    if foreground is None or background is None:
        return False
    contrast = _contrast_ratio(foreground, background)
    return contrast is not None and contrast < MIN_CONTRAST_RATIO


def _is_fully_clipped(clip: str, clip_path: str) -> bool:
    folded_clip = clip.casefold().strip()
    if folded_clip.startswith("rect("):
        values = [_number(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", folded_clip)]
        if len(values) == 4 and all(value is not None for value in values):
            top, right, bottom, left = values
            if right <= left or bottom <= top:  # type: ignore[operator]
                return True

    folded_path = re.sub(r"\s+", " ", clip_path.casefold().strip())
    if re.fullmatch(r"(?:circle|ellipse)\(0(?:px|%|em|rem)?(?:\s+at\s+[^)]*)?\)", folded_path):
        return True
    inset_match = re.fullmatch(r"inset\(([^)]*)\)", folded_path)
    if inset_match:
        tokens = [token for token in inset_match.group(1).split() if token.endswith("%")]
        if tokens and len(tokens) == len(inset_match.group(1).split()):
            values = [float(token[:-1]) for token in tokens]
            if len(values) == 1:
                top = right = bottom = left = values[0]
            elif len(values) == 2:
                top = bottom = values[0]
                right = left = values[1]
            elif len(values) == 3:
                top, right, bottom = values
                left = right
            elif len(values) == 4:
                top, right, bottom, left = values
            else:
                return False
            if top + bottom >= 100.0 or left + right >= 100.0:
                return True
    polygon_match = re.fullmatch(r"polygon\(([^)]*)\)", folded_path)
    if polygon_match:
        points = [re.sub(r"\s+", " ", point.strip()) for point in polygon_match.group(1).split(",")]
        if len(points) >= 3 and len(set(points)) == 1:
            return True
    return False


def is_offscreen(element: Element) -> bool:
    """Return whether a nonblank element is hidden by layout or geometry."""

    if not element.text.strip():
        return False

    font_size = _number(_style(element, "fontSize"))
    if font_size is not None and font_size <= MAX_HIDDEN_FONT_SIZE_PX:
        return True

    position = _style(element, "position", "static").casefold()
    if position in {"absolute", "fixed"}:
        left = _number(_style(element, "left"))
        top = _number(_style(element, "top"))
        if (left is not None and left <= OFFSCREEN_THRESHOLD_PX) or (
            top is not None and top <= OFFSCREEN_THRESHOLD_PX
        ):
            return True

    if _style(element, "display", "block").casefold() == "none":
        return True
    if _boolean(element.style.get("ancestorDisplayNone", False)):
        return True
    if _style(element, "visibility", "visible").casefold() == "hidden":
        return True
    if _is_fully_clipped(_style(element, "clip"), _style(element, "clipPath")):
        return True

    overflow = _style(element, "overflow", "visible").casefold()
    width = _number(_style(element, "width"))
    height = _number(_style(element, "height"))
    if (
        overflow in {"hidden", "clip"}
        and width is not None
        and height is not None
        and width <= MAX_CLIPPED_SIZE_PX
        and height <= MAX_CLIPPED_SIZE_PX
    ):
        return True

    text_indent = _number(_style(element, "textIndent"))
    if text_indent is not None and text_indent <= OFFSCREEN_THRESHOLD_PX:
        return True

    x = _number(element.bbox.get("x"))
    y = _number(element.bbox.get("y"))
    return bool(
        (x is not None and x <= OFFSCREEN_THRESHOLD_PX)
        or (y is not None and y <= OFFSCREEN_THRESHOLD_PX)
    )
