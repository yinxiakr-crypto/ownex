from __future__ import annotations

import re
from xml.etree import ElementTree

import requests

from util.clock import today_seoul
from util.config_loader import csv_list
from util.logger import get_logger
from util.normalize import parse_period
from util.sources_common import make_item

LOGGER = get_logger()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Ownex/1.0"}
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "m": "http://search.yahoo.com/mrss/",
}

# 도슨트가 월별로 전시 소개를 올리는 유튜브. 정우철을 먼저 봅니다.
DOCENTS = (
    {
        "name": "도슨트 정우철",
        "channel_id": "UC6m45_UH5dfkevVNK21ewdA",
        "page": "https://www.youtube.com/@도슨트정우철",
    },
)
MONTHLY_HINTS = ("전시", "개인전", "추천", "나들이", "가볼", "가야 할", "가야할")


def collect_docents(cfg) -> list[dict]:
    LOGGER.info("[수집] 도슨트 유튜브 시작")
    extra = csv_list((cfg["sources"].get("docent_channel_ids", "") if cfg.has_section("sources") else ""))
    channels = list(DOCENTS)
    for channel_id in extra:
        if channel_id and all(item["channel_id"] != channel_id for item in channels):
            channels.append({"name": "도슨트 유튜브", "channel_id": channel_id, "page": ""})
    items: list[dict] = []
    seen: set[str] = set()
    for channel in channels:
        items.extend(_from_channel(cfg, channel, seen))
    LOGGER.info(f"[수집] 도슨트 유튜브 후보 {len(items)}건")
    return items


def _from_channel(cfg, channel: dict, seen: set[str]) -> list[dict]:
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel["channel_id"]
    try:
        response = requests.get(url, headers=HEADERS, timeout=18)
        if response.status_code >= 400:
            LOGGER.info(f"[수집] {channel['name']} RSS 실패({response.status_code})")
            return []
        root = ElementTree.fromstring(response.content)
    except Exception as exc:
        LOGGER.info(f"[수집] {channel['name']} RSS 오류: {exc}")
        return []
    items: list[dict] = []
    for entry in root.findall("a:entry", NS):
        title = (entry.findtext("a:title", default="", namespaces=NS) or "").strip()
        desc = entry.findtext("m:group/m:description", default="", namespaces=NS) or ""
        if not title:
            continue
        if not any(hint in title for hint in MONTHLY_HINTS) and "📍" not in desc and "전시명" not in desc:
            continue
        link = ""
        alt = entry.find("a:link", NS)
        if alt is not None:
            link = alt.get("href") or ""
        for show in _parse_shows(title, desc):
            key = re.sub(r"[^가-힣A-Za-z0-9]", "", show["title"]).lower()
            if not show["start"] or any(key in old or old in key for old in seen):
                continue
            seen.add(key)
            items.append(
                make_item(
                    cfg,
                    title=show["title"],
                    venue=show["venue"],
                    venue_address=show["address"],
                    reservation_url=show.get("page") or channel.get("page") or link,
                    source_url=link or channel.get("page") or "",
                    start_date=show["start"],
                    end_date=show["end"] or show["start"],
                    raw_text=f"{channel['name']} 월별 전시 소개 {show['title']} {show['venue']}",
                    source_name=channel["name"],
                )
            )
    return items


def _parse_shows(video_title: str, desc: str) -> list[dict]:
    shows: list[dict] = []
    blocks = re.split(r"(?:^|\n)\s*\d+\.\s*", desc or "")
    if len(blocks) <= 2:
        blocks = [desc or ""]
    for block in blocks:
        text = (block or "").strip()
        if not text:
            continue
        titled = re.search(r"《([^》]+)》", text)
        title = (titled.group(1) if titled else "").strip()
        if titled:
            before = text[: titled.start()].split("\n")[0].strip(" ·-:")
            if before and "전시명" not in before and "📍" not in before and len(before) > 3:
                title = f"{before} {title}".strip()
        if not title:
            named = re.search(r"전시명\s*[:：]\s*(.+)", text)
            title = (named.group(1).strip() if named else "")
        title = re.sub(r"\s+", " ", title).strip(" ·-")
        if not title or len(title) < 4:
            continue
        venue_line = ""
        place = re.search(r"장소\s*[:：]\s*(.+)", text)
        if not place:
            place = re.search(r"📍\s*(.+)", text)
        if place:
            venue_line = place.group(1).strip()
        if venue_line in {"전시 정보", "전시정보"}:
            extra = re.search(r"장소\s*[:：]\s*(.+)", text)
            venue_line = extra.group(1).strip() if extra else ""
        venue, address = _split_place(venue_line)
        period_line = ""
        dated = re.search(r"(?:🗓|기간\s*[:：])\s*(.+)", text)
        if dated:
            period_line = dated.group(1).strip()
        period_line = re.sub(r"\s+", "", period_line.replace("년", ".").replace("월", ".").replace("일", ""))
        start, end = parse_period(period_line, today_seoul().year)
        if not start and end:
            start = today_seoul()
        if not start:
            continue
        shows.append({"title": title, "venue": venue, "address": address, "start": start, "end": end, "page": ""})
    if not shows and any(hint in video_title for hint in MONTHLY_HINTS):
        start, end = parse_period(desc, today_seoul().year)
        if start:
            shows.append({"title": video_title, "venue": "", "address": "", "start": start, "end": end, "page": ""})
    return shows


def _split_place(line: str) -> tuple[str, str]:
    text = (line or "").strip()
    if not text:
        return "", ""
    inside = re.search(r"^(.*?)\((.+)\)\s*$", text)
    if inside:
        return inside.group(1).strip(), inside.group(2).strip()
    return text, ""
