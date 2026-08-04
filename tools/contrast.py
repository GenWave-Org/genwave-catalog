"""WCAG 2.x contrast-ratio math + the theme shelf's AA gate (SPEC F102.8,
STORY-268; ported to the catalog at T180, depends-on T179's kind schema).

Faithful Python port of the app's ONE authored `contrastRatio` implementation
(admin-ui/__specs__/contrast-ratio.ts) — same sRGB linearization, same
relative-luminance channel weights, same `(L1+0.05)/(L2+0.05)` formula — plus
the exact token-pair list `admin-ui/__specs__/theme-shelf-contrast.spec.ts`
asserts against every shipped theme manifest: `ink` on each of the three
grounds (bg/surface/surface-2), `accent-ink` on `accent`, `danger-ink` on
`danger`, and `mute` / `accent-2` on each of the three grounds — 11 pairs,
checked in both `light` and `dark` modes (22 checks per theme). The
`--sched-*` tokens carry no AA constraint in either tool.

`tools/validate.py` is the only caller: a `kind:"theme"` catalog entry's
manifest is checked here as a HARD gate — same posture as its schema check,
not a warning — so a low-contrast theme is rejected before it ever reaches
index.json.
"""
from __future__ import annotations

import re

# WCAG AA minimum contrast ratio for normal-size body text — same constant
# name and value as contrast-ratio.ts's AA_NORMAL_TEXT_MIN_CONTRAST.
AA_NORMAL_TEXT_MIN_CONTRAST = 4.5

# The exact 11 pairs theme-shelf-contrast.spec.ts asserts (STORY-268
# AC3-AC6): ink on every ground, accent-ink on accent, danger-ink on danger,
# and mute / accent-2 on every ground. Order matches the spec file's own
# describe-block order; it has no effect on behavior.
ASSERTED_PAIRS: tuple[tuple[str, str], ...] = (
    ("ink", "bg"),
    ("ink", "surface"),
    ("ink", "surface-2"),
    ("accent-ink", "accent"),
    ("danger-ink", "danger"),
    ("mute", "bg"),
    ("mute", "surface"),
    ("mute", "surface-2"),
    ("accent-2", "bg"),
    ("accent-2", "surface"),
    ("accent-2", "surface-2"),
)

MODES: tuple[str, ...] = ("light", "dark")

_HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})\Z")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parses `#rrggbb` into 0-255 channel values. Raises ValueError on
    anything else (3-digit shorthand, an alpha channel, a non-hex string) —
    mirroring contrast-ratio.ts's own hexToRgb, which is equally strict."""
    match = _HEX_COLOR.match(hex_color)
    if not match:
        raise ValueError(f"not a 6-digit hex color: {hex_color}")
    return (int(match.group(1), 16), int(match.group(2), 16), int(match.group(3), 16))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.x relative luminance of an sRGB triple (0-255 channels)."""

    def linear(channel: int) -> float:
        s = channel / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio (1:1 to 21:1) between two `#rrggbb` colors — the
    ONE contrast implementation, ported faithfully from contrast-ratio.ts.
    Raises ValueError if either value isn't a 6-digit hex color."""
    luminance_a = _relative_luminance(_hex_to_rgb(hex_a))
    luminance_b = _relative_luminance(_hex_to_rgb(hex_b))
    lighter, darker = (luminance_a, luminance_b) if luminance_a >= luminance_b else (luminance_b, luminance_a)
    return (lighter + 0.05) / (darker + 0.05)


def check_theme_aa(modes: object) -> list[str]:
    """Checks every ASSERTED_PAIRS x MODES combination against `modes` (a
    theme manifest's raw, not-yet-schema-validated `modes` value) and
    returns one human-readable finding per failure — naming the mode, the
    pair, and either the measured ratio or the missing token(s).

    Returns no findings (rather than raising) when `modes`, or a `light`/
    `dark` entry within it, isn't shaped like an object — that shape problem
    is theme-manifest.schema.json's to report, and this function must not
    restate it under a different rule name. Likewise, a pair whose token is
    absent from a mode is reported as a finding of ITS OWN here (a missing
    token can't be measured, and a theme author omitting a token is not a
    loophole out of the gate) rather than silently skipped.

    A non-hex-color token value (schema only pins "a string", not "a hex
    colour") also becomes a finding here, via contrast_ratio's ValueError,
    rather than propagating as an unhandled exception.

    Callers (tools/validate.py) are responsible for prefixing each returned
    string with the offending file path and the theme's slug, matching the
    "{path}: {rule}: {message}" idiom the rest of validate.py's checks use.
    """
    if not isinstance(modes, dict):
        return []

    findings: list[str] = []
    for mode in MODES:
        mode_tokens = modes.get(mode)
        if not isinstance(mode_tokens, dict):
            continue
        for foreground, background in ASSERTED_PAIRS:
            fg_value = mode_tokens.get(foreground)
            bg_value = mode_tokens.get(background)
            missing = [
                name
                for name, value in ((foreground, fg_value), (background, bg_value))
                if not isinstance(value, str)
            ]
            if missing:
                findings.append(
                    f"mode '{mode}' pair '{foreground}' on '{background}': missing token(s) {', '.join(missing)}"
                )
                continue
            try:
                ratio = contrast_ratio(fg_value, bg_value)
            except ValueError as exc:
                findings.append(f"mode '{mode}' pair '{foreground}' on '{background}': {exc}")
                continue
            if ratio < AA_NORMAL_TEXT_MIN_CONTRAST:
                findings.append(
                    f"mode '{mode}' pair '{foreground}' on '{background}': measured {ratio:.2f}:1, "
                    f"need at least {AA_NORMAL_TEXT_MIN_CONTRAST}:1"
                )
    return findings
