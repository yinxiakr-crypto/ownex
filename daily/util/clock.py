from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def now_seoul() -> datetime:
    return datetime.now(SEOUL)


def today_seoul() -> date:
    return now_seoul().date()
