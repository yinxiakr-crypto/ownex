from __future__ import annotations

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
MAIL_HOUR = 8
MAIL_MINUTE = 0


def now_seoul() -> datetime:
    return datetime.now(SEOUL)


def today_seoul() -> date:
    return now_seoul().date()


def seconds_until_seoul(hour: int = MAIL_HOUR, minute: int = MAIL_MINUTE) -> float:
    now = now_seoul()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        return 0.0
    return (target - now).total_seconds()


def wait_until_seoul(hour: int = MAIL_HOUR, minute: int = MAIL_MINUTE) -> float:
    """오늘 한국 시각이 될 때까지 기다립니다. 이미 지났으면 바로 0을 돌려줍니다."""
    waited = 0.0
    while True:
        left = seconds_until_seoul(hour, minute)
        if left <= 0:
            return waited
        chunk = min(left, 20.0)
        time.sleep(chunk)
        waited += chunk
