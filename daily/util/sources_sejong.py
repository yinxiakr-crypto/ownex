from __future__ import annotations

import re

from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()
SEJONG_ADDRESS = "서울시 종로구 세종대로 175"


def collect_sejong(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 세종문화회관 시작")
    url = cfg["sources"].get("sejong_url")
    try:
        page = browser.goto(url, wait_ms=4000)
        try:
            page.get_by_text("전체", exact=True).first.click(timeout=2000)
            page.wait_for_timeout(1500)
        except Exception:
            pass
    except Exception as exc:
        LOGGER.info(f"[수집] 세종문화회관 이동 실패: {exc}")
        return []

    items = []
    links = page.locator("a")
    count = min(links.count(), 200)
    seen = set()
    for index in range(count):
        link = links.nth(index)
        try:
            title = (link.inner_text() or "").strip()
            href = link.get_attribute("href") or ""
        except Exception:
            continue
        if not title or title in seen:
            continue
        if "전시" not in title and "perform" not in href and "exhibit" not in href:
            continue
        if title in {"전시일정", "전시", "프로그램", "공연일정", "이용안내", "소식"}:
            continue
        if "performList.do" in href and "exhibit" not in href:
            continue
        seen.add(title)
        if href.startswith("/"):
            href = "https://www.sejongpac.or.kr" + href
        nearby = ""
        try:
            nearby = link.evaluate(
                "el => (el.closest('li,tr,div,article') && el.closest('li,tr,div,article').innerText) || el.innerText"
            )
        except Exception:
            nearby = title
        period = ""
        match = re.search(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[~\-]\s*20?\d{0,2}[.\-/]?\d{1,2}[.\-/]?\d{1,2}", nearby)
        if match:
            period = match.group(0)
        items.append(
            make_item(
                cfg,
                title=title.split("\n")[0],
                venue="세종문화회관",
                venue_address=SEJONG_ADDRESS,
                period=period,
                source_url=href or url,
                reservation_url=href or url,
                raw_text=nearby,
                source_name="세종문화회관",
            )
        )
    LOGGER.info(f"[수집] 세종문화회관 후보 {len(items)}건")
    return items
