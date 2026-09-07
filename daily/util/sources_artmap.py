from __future__ import annotations

import json
import re

from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()


def collect_artmap(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 아트맵 시작")
    url = cfg["sources"].get("artmap_url")
    captured: list[dict] = []

    def on_response(response) -> None:
        try:
            if "json" not in (response.headers.get("content-type") or ""):
                return
            if response.status != 200:
                return
            data = response.json()
            if isinstance(data, list):
                captured.extend([row for row in data if isinstance(row, dict)])
            elif isinstance(data, dict):
                for key in ("items", "data", "exhibitions", "list"):
                    value = data.get(key)
                    if isinstance(value, list):
                        captured.extend([row for row in value if isinstance(row, dict)])
        except Exception:
            return

    page = browser.page
    page.on("response", on_response)
    try:
        browser.goto(url, wait_ms=5000)
        page.wait_for_timeout(3000)
    except Exception as exc:
        LOGGER.info(f"[수집] 아트맵 이동 실패: {exc}")
        return []
    finally:
        page.remove_listener("response", on_response)

    items = []
    for row in captured:
        title = str(row.get("title") or row.get("name") or row.get("exhibitionName") or "")
        if not title:
            continue
        venue = str(row.get("venue") or row.get("place") or row.get("gallery") or row.get("location") or "")
        address = str(row.get("address") or row.get("addr") or "")
        period = str(row.get("period") or "")
        start = str(row.get("startDate") or row.get("start_date") or "")
        end = str(row.get("endDate") or row.get("end_date") or "")
        if start and end and not period:
            period = f"{start}~{end}"
        image = str(row.get("image") or row.get("imageUrl") or row.get("thumbnail") or "")
        link = str(row.get("url") or row.get("link") or url)
        items.append(
            make_item(
                cfg,
                title=title,
                venue=venue,
                venue_address=address,
                period=period,
                source_url=link,
                reservation_url=link,
                image_url=image,
                raw_text=json.dumps(row, ensure_ascii=False)[:300],
                source_name="아트맵",
            )
        )

    if not items:
        items.extend(_from_dom(cfg, page, url))
    LOGGER.info(f"[수집] 아트맵 후보 {len(items)}건")
    return items


def _from_dom(cfg, page, url: str) -> list[dict]:
    text = page.inner_text("body")
    if "불러오는 중" in text and len(text) < 400:
        LOGGER.info("[수집] 아트맵 목록이 비어 있습니다.")
        return []
    items = []
    pattern = re.compile(
        r"([^\n]{4,80})\n([^\n]{2,60})\n[^\n]*?(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[~\-]\s*20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})"
    )
    for match in pattern.finditer(text):
        items.append(
            make_item(
                cfg,
                title=match.group(1),
                venue=match.group(2),
                period=match.group(3),
                source_url=url,
                reservation_url=url,
                raw_text=match.group(0),
                source_name="아트맵",
            )
        )
    return items
