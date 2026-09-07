from __future__ import annotations

from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()


def collect_artbava(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 아트바바 시작")
    from util.config_loader import csv_list

    base = cfg["sources"].get("artbava_url").rstrip("/")
    regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    urls = [base + "/"] + [f"{base}/?q={region}" for region in regions]
    items = []
    seen = set()
    for url in urls:
        items.extend(_collect_page(cfg, browser, url, seen))
    LOGGER.info(f"[수집] 아트바바 후보 {len(items)}건")
    return items


def _collect_page(cfg, browser, url: str, seen: set[str]) -> list[dict]:
    try:
        page = browser.goto(url, wait_ms=3500)
    except Exception as exc:
        LOGGER.info(f"[수집] 아트바바 이동 실패: {exc}")
        return []

    items = []
    cards = page.locator("a").all()
    for link in cards[:250]:
        try:
            href = link.get_attribute("href") or ""
            title = (link.inner_text() or "").strip()
        except Exception:
            continue
        if "/exhibit" not in href and "/exhibits" not in href:
            continue
        if not title or title in seen or len(title) < 4:
            continue
        seen.add(title)
        if href.startswith("/"):
            href = "https://www.artbava.com" + href
        parent_text = ""
        try:
            parent_text = link.evaluate("el => (el.parentElement && el.parentElement.innerText) || el.innerText")
        except Exception:
            parent_text = title
        image = ""
        try:
            img = link.locator("img")
            if img.count():
                image = img.first.get_attribute("src") or ""
        except Exception:
            pass
        items.append(
            make_item(
                cfg,
                title=title.split("\n")[0],
                venue=_guess_venue(parent_text),
                period=_guess_period(parent_text),
                source_url=href,
                reservation_url=href,
                image_url=image,
                raw_text=parent_text,
                source_name="아트바바",
            )
        )
    return items


def _guess_venue(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if any(word in line for word in ["미술관", "갤러리", "박물관", "센터", "문화회관"]):
            return line
    return ""


def _guess_period(text: str) -> str:
    for line in (text or "").splitlines():
        if "~" in line or "–" in line:
            return line.strip()
    return ""
