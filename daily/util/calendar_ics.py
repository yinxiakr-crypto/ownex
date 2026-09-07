from __future__ import annotations

from datetime import date
from pathlib import Path

from util.logger import get_logger
from util.normalize import clip_calendar_span, from_iso

ROOT = Path(__file__).resolve().parent.parent
ICS_PATH = ROOT / "data" / "exhibitions.ics"
LOGGER = get_logger()


def _escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def write_ics(rows: list[dict], calendar_from: date | None = None, today: date | None = None) -> Path:
    ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = today or date.today()
    if calendar_from is None or calendar_from < today:
        calendar_from = today
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal Exhibition Scheduler//KO",
        "CALSCALE:GREGORIAN",
    ]
    kept = 0
    for row in rows:
        show_end = from_iso(row.get("end_date") or "") or from_iso(row.get("start_date") or "")
        if show_end and show_end < today:
            continue
        start, end = clip_calendar_span(
            from_iso(row.get("start_date") or ""),
            from_iso(row.get("end_date") or ""),
            calendar_from,
        )
        if not start or not end:
            continue
        kept += 1
        end_next = end.toordinal() + 1
        end_exclusive = date.fromordinal(end_next).strftime("%Y%m%d")
        uid = f"{row.get('title', 'show')}-{row.get('start_date', '')}@exhibition-local"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_escape(uid)}",
                f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end_exclusive}",
                f"SUMMARY:{_escape(row.get('title', ''))}",
                f"LOCATION:{_escape((row.get('venue') or '') + ' ' + (row.get('venue_address') or ''))}",
                f"DESCRIPTION:{_escape((row.get('summary') or '') + ' ' + (row.get('reservation_url') or ''))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    ICS_PATH.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    LOGGER.info(f"[달력] 아이폰용 달력 파일 저장: {ICS_PATH.name} ({kept}건, 끝난 전시는 제외)")
    return ICS_PATH
