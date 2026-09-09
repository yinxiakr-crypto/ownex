from __future__ import annotations

from datetime import date

# 해마다 유행색만 이 표에서 바꿉니다. 2026은 Pinterest Palette.
YEAR_PALETTES = {
    2026: {
        "winter": {"bg": "#44525c", "paper": "#dce8f0", "ink": "#3d4a54", "accent": "#8fadc0", "btn": "#dce8f0"},
        "spring": {"bg": "#44524a", "paper": "#dde8dc", "ink": "#3d4a42", "accent": "#8fafa0", "btn": "#dde8dc"},
        "summer": {"bg": "#4f5044", "paper": "#ece8d0", "ink": "#44453a", "accent": "#c4b47a", "btn": "#ece8d0"},
        "fall": {"bg": "#53414a", "paper": "#f3ddd8", "ink": "#4c3d44", "accent": "#c48686", "btn": "#f3ddd8"},
    }
}


def season_name(when: date | None = None) -> str:
    month = (when or date.today()).month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def palette(when: date | None = None) -> dict:
    when = when or date.today()
    year = YEAR_PALETTES.get(when.year) or YEAR_PALETTES[max(YEAR_PALETTES)]
    return year[season_name(when)]
