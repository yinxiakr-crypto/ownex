from __future__ import annotations

from urllib.parse import quote

from util.config_loader import csv_list
from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()


def collect_naver(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 네이버 뉴스 시작")
    keywords = csv_list(cfg["general"].get("search_keywords", "미술전시회"))
    regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    queries = []
    for region in regions:
        queries.append(f"{region} {keywords[0]}")
    queries.append("한가람미술관 전시")
    queries.append("안양 전시회")
    queries.append("퐁피두센터 한화 전시")
    queries.append("국립현대미술관 종로 과천 전시")
    queries.append("리움미술관 전시")
    queries.append("더현대 서울 전시")
    queries.insert(0, "뱅크시 전시 서울")
    items = []
    seen = set()
    for query in queries[:4]:
        url = "https://search.naver.com/search.naver?where=news&sm=tab_jum&query=" + quote(query)
        try:
            page = browser.goto(url, wait_ms=3500)
        except Exception as exc:
            LOGGER.info(f"[수집] 네이버 이동 실패({query}): {exc}")
            continue
        links = page.locator("a")
        count = min(links.count(), 80)
        for index in range(count):
            link = links.nth(index)
            try:
                title = (link.inner_text() or "").strip()
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if not title or title in seen or len(title) < 8:
                continue
            if "news" not in href and "n.news" not in href:
                continue
            if not any(word in title for word in ("전시", "미술관", "미술", "특별전")):
                continue
            seen.add(title)
            items.append(
                make_item(
                    cfg,
                    title=title.split("\n")[0],
                    venue=_guess_venue(title),
                    source_url=href,
                    reservation_url=href,
                    raw_text=title,
                    source_name="네이버",
                )
            )
    LOGGER.info(f"[수집] 네이버 후보 {len(items)}건")
    return items


def _guess_venue(text: str) -> str:
    for word in (
        "한가람미술관",
        "한가람디자인미술관",
        "예술의전당",
        "세종문화회관",
        "서울시립미술관",
        "리움",
        "퐁피두",
        "국립현대미술관",
        "더현대",
        "호암",
    ):
        if word in text:
            return word
    if "안양" in text:
        return "안양"
    if "서울" in text:
        return "서울"
    return ""
