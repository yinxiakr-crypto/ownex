from __future__ import annotations

from datetime import date

# 해마다 유행색만 이 표에서 바꿉니다. 2026은 Pinterest Palette.
# 겨울 Cool Blue #d7efff, 봄 Jade #aeb8a0, 여름 Wasabi #e9f056,
# 가을 Plum Noir #351e28 + Persimmon #ff5c34.
YEAR_PALETTES = {
    2026: {
        "winter": {"bg": "#1b2a33", "paper": "#d7efff", "ink": "#1b2a33", "accent": "#7aa7c7", "btn": "#d7efff"},
        "spring": {"bg": "#24382e", "paper": "#e7f3ea", "ink": "#24382e", "accent": "#3f7a68", "btn": "#e7f3ea"},
        "summer": {"bg": "#2a2e12", "paper": "#f3f7d4", "ink": "#2a2e12", "accent": "#e9f056", "btn": "#e9f056"},
        "fall": {"bg": "#351e28", "paper": "#f6e4dc", "ink": "#351e28", "accent": "#ff5c34", "btn": "#f6e4dc"},
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
