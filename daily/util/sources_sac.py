from __future__ import annotations

import re

from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()
SAC_ADDRESS = "서울시 서초구 남부순환로 2406"


def collect_sac(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 예술의전당 시작")
    items = []
    items.extend(_from_presents(cfg, browser))
    items.extend(_from_show_list(cfg, browser))
    items.extend(_from_schedule(cfg, browser))
    LOGGER.info(f"[수집] 예술의전당 후보 {len(items)}건")
    return items


def _from_presents(cfg, browser) -> list[dict]:
    url = "https://www.sac.or.kr/site/main/content/2026_SACpresents"
    try:
        page = browser.goto(url, wait_ms=3000)
        text = page.inner_text("body")
    except Exception as exc:
        LOGGER.info(f"[수집] 예술의전당 기획 프로그램 실패: {exc}")
        return []

    items = []
    blocks = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    venue_lines = ("한가람디자인미술관", "한가람미술관", "서울서예박물관")
    skip = ("콘서트", "리사이틀", "오페라", "발레", "연극", "축제", "시리즈", "교향악")
    date_line = re.compile(r"\d{2}\.\d{1,2}\.\d{1,2}")
    pending_title = ""
    pending_period = ""
    for line in blocks:
        if date_line.search(line) and len(line) < 40:
            pending_period = line
            continue
        if any(line.startswith(name) or line == name for name in venue_lines) or (
            any(name in line for name in venue_lines) and "특별전" not in line and "전 :" not in line
        ):
            if pending_title and not any(word in pending_title for word in skip):
                items.append(
                    make_item(
                        cfg,
                        title=pending_title,
                        venue=line,
                        venue_address=SAC_ADDRESS,
                        period=pending_period,
                        source_url=url,
                        reservation_url="https://www.sac.or.kr/site/main/show/show_list",
                        raw_text=f"{pending_title} {line} {pending_period}",
                        source_name="예술의전당",
                    )
                )
            pending_title = ""
            pending_period = ""
            continue
        if 4 <= len(line) <= 90 and not line.startswith("SAC") and "일정" not in line:
            pending_title = line
    return items


def _from_show_list(cfg, browser) -> list[dict]:
    url = cfg["sources"].get("sac_list_url")
    try:
        page = browser.goto(url, wait_ms=2500)
        for label in ["미술", "전시", "디자인"]:
            loc = page.get_by_text(label, exact=True)
            if loc.count():
                try:
                    loc.first.click(timeout=2000)
                except Exception:
                    pass
        page.wait_for_timeout(1500)
        rows = page.locator("table tr")
        items = []
        count = min(rows.count(), 80)
        for index in range(count):
            row_text = rows.nth(index).inner_text()
            if "기간" in row_text and "장소" in row_text:
                continue
            parts = [part.strip() for part in re.split(r"\t|\n", row_text) if part.strip()]
            if len(parts) < 2:
                continue
            title = parts[0]
            period = next((part for part in parts if "~" in part or "-" in part), "")
            venue = next((part for part in parts if "미술관" in part or "박물관" in part), "예술의전당")
            if any(word in title for word in ["리사이틀", "콘서트", "오페라", "연극"]):
                continue
            if "미술관" not in venue and "박물관" not in venue and "전시" not in title:
                continue
            href = ""
            link = rows.nth(index).locator("a")
            if link.count():
                href = link.first.get_attribute("href") or ""
                if href.startswith("/"):
                    href = "https://www.sac.or.kr" + href
            items.append(
                make_item(
                    cfg,
                    title=title,
                    venue=venue,
                    venue_address=SAC_ADDRESS,
                    period=period,
                    source_url=href or url,
                    reservation_url=href or url,
                    raw_text=row_text,
                    source_name="예술의전당",
                )
            )
        return items
    except Exception as exc:
        LOGGER.info(f"[수집] 예술의전당 목록 실패: {exc}")
        return []


def _from_schedule(cfg, browser) -> list[dict]:
    url = cfg["sources"].get("sac_url")
    try:
        page = browser.goto(url, wait_ms=3000)
        text = page.inner_text("body")
    except Exception as exc:
        LOGGER.info(f"[수집] 예술의전당 일정표 실패: {exc}")
        return []
    items = []
    for match in re.finditer(r"([^\n]{4,80})\n(\d{2}\.\d{2}[^\n]{0,40}~\s*[^\n]{0,40})", text):
        title, period = match.group(1).strip(), match.group(2).strip()
        if any(word in title for word in ["콘서트", "리사이틀", "오페라", "연극", "기획 프로그램", "축제", "음악회"]):
            continue
        items.append(
            make_item(
                cfg,
                title=title,
                venue="예술의전당",
                venue_address=SAC_ADDRESS,
                period=period,
                source_url=url,
                reservation_url=url,
                raw_text=f"{title} {period}",
                source_name="예술의전당",
                default_year=2026,
            )
        )
    return items
