from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})"),
    re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
    re.compile(r"(?<!\d)(\d{2})\.(\d{1,2})\.(\d{1,2})"),
]


def parse_date(text: str, default_year: Optional[int] = None) -> Optional[date]:
    if not text:
        return None
    cleaned = re.sub(r"\([^)]*\)", "", text)
    match = DATE_PATTERNS[0].search(cleaned) or DATE_PATTERNS[1].search(cleaned)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return _safe_date(year, month, day)
    short_year = DATE_PATTERNS[2].search(cleaned)
    if short_year:
        year = 2000 + int(short_year.group(1))
        return _safe_date(year, int(short_year.group(2)), int(short_year.group(3)))
    year = default_year or date.today().year
    short = re.search(r"(\d{1,2})[.\-/월]\s*(\d{1,2})", cleaned)
    if short:
        return _safe_date(year, int(short.group(1)), int(short.group(2)))
    return None


def parse_period(text: str, default_year: Optional[int] = None) -> tuple[Optional[date], Optional[date]]:
    if not text:
        return None, None
    cleaned = text.replace("～", "~").replace("–", "~").replace("—", "~")
    parts = re.split(r"\s*[~\-]\s*", cleaned, maxsplit=1)
    year = default_year or date.today().year
    start = parse_date(parts[0], year)
    end = parse_date(parts[1], start.year if start else year) if len(parts) > 1 else start
    if start and end and end < start:
        end = _safe_date(end.year + 1, end.month, end.day)
    return start, end


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def to_iso(value: Optional[date]) -> str:
    return value.isoformat() if value else ""


def from_iso(text: str) -> Optional[date]:
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def daterange(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def overlaps(start: Optional[date], end: Optional[date], window_start: date, window_end: date) -> bool:
    if not start and not end:
        return True
    show_start = start or window_start
    show_end = end or show_start
    return show_start <= window_end and show_end >= window_start


def clip_calendar_span(
    start: Optional[date], end: Optional[date], calendar_from: Optional[date]
) -> tuple[Optional[date], Optional[date]]:
    if not start:
        return None, None
    show_end = end or start
    if calendar_from:
        if show_end < calendar_from:
            return None, None
        if start < calendar_from:
            start = calendar_from
    return start, show_end


def exhibition_span(item: dict) -> tuple[Optional[date], Optional[date]]:
    start = from_iso(item.get("start_date") or "")
    end = from_iso(item.get("end_date") or "") or start
    return start, end


def pick_calendar_rows(rows: list[dict], today: date, limit: int = 5) -> list[dict]:
    ongoing: list[dict] = []
    upcoming: list[dict] = []
    for row in rows:
        start, end = exhibition_span(row)
        if not start or not end:
            continue
        if end < today:
            continue
        if start > today:
            upcoming.append(row)
        else:
            ongoing.append(row)
    picked = ongoing[:limit]
    if len(picked) < limit:
        picked.extend(upcoming[: limit - len(picked)])
    return picked


def detect_region(text: str, priority_regions: list[str]) -> str:
    blob = text or ""
    checks = [
        ("익산", ["익산", "전북 익산", "전라북도 익산"]),
        ("과천", ["과천", "국립현대미술관 과천"]),
        ("안양", ["안양", "경기 안양", "경기도 안양", "평촌", "동안구", "만안구"]),
        ("서울", [
            "서울", "서초", "종로", "강남", "용산", "여의도", "영등포", "한남",
            "한가람", "예술의전당", "세종문화", "리움", "DDP", "서울시립",
            "퐁피두", "더현대", "한화", "국립현대", "신사하우스", "세화",
            "국제갤러리", "아트선재", "코엑스", "삼청",
        ]),
    ]
    tags = []
    for label, keywords in checks:
        if label in priority_regions and any(word in blob for word in keywords):
            tags.append(f"[{label}]")
    return " ".join(tags)


OUTSIDE_REGIONS = (
    "부산",
    "대구",
    "광주",
    "대전",
    "울산",
    "제주",
    "강릉",
    "전주",
    "청주",
    "창원",
    "인천",
)


def item_text(item: dict) -> str:
    return " ".join(
        [
            item.get("title") or "",
            item.get("venue") or "",
            item.get("venue_address") or "",
            item.get("region_tag") or "",
            item.get("raw_text") or "",
        ]
    )


def is_main_region(item: dict, main_regions: list[str]) -> bool:
    text = item_text(item)
    tag = item.get("region_tag") or ""
    if any(region in tag for region in main_regions):
        return True
    if any(region in text for region in main_regions):
        return True
    if any(word in text for word in INCLUDED_VENUE_WORDS):
        return True
    if any(word in text for word in OUTSIDE_REGIONS):
        return False
    return True


INCLUDED_VENUE_WORDS = (
    "한가람",
    "예술의전당",
    "세종문화",
    "평촌",
    "여의도",
    "용산",
    "한남",
    "종로",
    "과천",
    "퐁피두",
    "한화",
    "더현대",
    "리움",
    "호암",
    "국립현대",
    "국립중앙박물관",
    "삼성",
    "워커힐",
    "SK",
    "서울시립",
    "롯데뮤지엄",
    "아모레퍼시픽",
    "디뮤지엄",
    "일민",
    "DDP",
    "소마",
    "공예박물관",
    "안양문화",
    "평촌",
    "신사하우스",
    "세화",
    "국제갤러리",
    "아트선재",
    "코엑스",
    "삼청",
)


def is_ongoing(item: dict, today: date | None = None) -> bool:
    today = today or date.today()
    end = from_iso(item.get("end_date") or "") or from_iso(item.get("start_date") or "")
    return bool(end and end >= today)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def clip_summary(text: str, limit: int = 30) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
