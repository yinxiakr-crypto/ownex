from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from util.normalize import from_iso, to_iso

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "last_run.txt"
EMAIL_STATE_FILE = ROOT / "data" / "last_email.txt"


def read_last_run() -> date | None:
    if not STATE_FILE.exists():
        return None
    return from_iso(STATE_FILE.read_text(encoding="utf-8").strip())


def write_last_run(value: date) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(to_iso(value), encoding="utf-8")


def read_last_email() -> date | None:
    if not EMAIL_STATE_FILE.exists():
        return None
    return from_iso(EMAIL_STATE_FILE.read_text(encoding="utf-8").strip())


def write_last_email(value: date) -> None:
    EMAIL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    EMAIL_STATE_FILE.write_text(to_iso(value), encoding="utf-8")


def email_allowed_by_schedule(cfg, today: date) -> tuple[bool, str]:
    mail = cfg["email"] if cfg.has_section("email") else None
    if mail and mail.get("enabled", "true").lower() != "true":
        return False, "메일 보내기가 꺼져 있습니다."
    daily_from = from_iso((mail.get("daily_from", "") if mail else "") or "2026-09-07")
    daily_until = from_iso((mail.get("daily_until", "") if mail else "") or "2026-09-13")
    weekly_weekday = 0
    if mail:
        raw_weekday = (mail.get("weekly_weekday", "") or "").strip()
        if raw_weekday:
            try:
                weekly_weekday = int(raw_weekday)
            except ValueError:
                weekly_weekday = 0
    if daily_from and daily_until and daily_from <= today <= daily_until:
        return True, f"{daily_from.month}월 {daily_from.day}일부터 {daily_until.month}월 {daily_until.day}일까지 매일 한 통"
    if daily_until and today > daily_until and today.weekday() == weekly_weekday:
        return True, "9월 14일부터는 월요일 오전에 한 통"
    if daily_until and today > daily_until:
        return False, "9월 14일부터는 월요일에만 메일을 보냅니다. 달력은 매일 올립니다."
    return False, "지금은 메일 보내는 날이 아닙니다."


def should_send_email(cfg, today: date) -> tuple[bool, str]:
    allowed, reason = email_allowed_by_schedule(cfg, today)
    if not allowed:
        return False, reason
    if read_last_email() == today:
        return False, "오늘은 이미 메일을 한 통 보냈습니다."
    return True, reason


def resolve_range(cfg, today: date) -> tuple[date, date]:
    test = cfg["test"]
    if test.getboolean("enabled", fallback=False):
        start = from_iso(test.get("start_date", ""))
        end = from_iso(test.get("end_date", ""))
        if start and end:
            return start, end

    collection_start = from_iso(cfg["general"].get("collection_start_date", "")) or today
    last = read_last_run()
    start = last + timedelta(days=1) if last else collection_start
    if start > today:
        start = today
    return start, today
