from __future__ import annotations

import os
from xml.etree import ElementTree

import requests

from util.config_loader import csv_list
from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()


def collect_google(cfg) -> list[dict]:
    LOGGER.info("[수집] 구글 검색 시작")
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_CX", "").strip()
    if api_key and cx:
        items = _from_cse(cfg, api_key, cx)
        if items:
            return items
        LOGGER.info("[수집] 구글 검색 API가 안 되어 뉴스 RSS로 찾습니다.")
    return _from_news_rss(cfg)


def _from_cse(cfg, api_key: str, cx: str) -> list[dict]:
    keywords = csv_list(cfg["general"].get("search_keywords", "미술전시회"))
    regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    items = []
    query = f"{regions[0]} {keywords[0]}"
    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cx, "q": query, "num": 8, "lr": "lang_ko"},
            timeout=15,
        )
        if response.status_code != 200:
            LOGGER.info(f"[수집] 구글 검색 실패({response.status_code})")
            return []
        for row in response.json().get("items", []):
            items.append(
                make_item(
                    cfg,
                    title=row.get("title") or "",
                    venue="",
                    source_url=row.get("link") or "",
                    reservation_url=row.get("link") or "",
                    raw_text=row.get("snippet") or "",
                    source_name="구글",
                )
            )
    except Exception as exc:
        LOGGER.info(f"[수집] 구글 검색 오류: {exc}")
    LOGGER.info(f"[수집] 구글 후보 {len(items)}건")
    return items


def _from_news_rss(cfg) -> list[dict]:
    keywords = csv_list(cfg["general"].get("search_keywords", "미술전시회"))
    regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    query = " OR ".join(f"{region} {keywords[0]}" for region in regions)
    query = (
        f"({query}) OR 뱅크시 전시 서울 OR BANKSY Still Here 더현대 "
        "OR 가우디 전시 서울 OR 서도호 국립현대 OR 바젤리츠 세화 "
        "OR 프리즈 서울 OR 키아프 서울 OR 솔 르윗 전시"
    )
    url = "https://news.google.com/rss/search"
    items = []
    try:
        response = requests.get(
            url,
            params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code != 200:
            LOGGER.info(f"[수집] 구글 뉴스 RSS 실패({response.status_code})")
            return []
        root = ElementTree.fromstring(response.content)
        for entry in root.findall(".//item")[:12]:
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            desc = (entry.findtext("description") or "").strip()
            if not title:
                continue
            items.append(
                make_item(
                    cfg,
                    title=title,
                    venue="",
                    source_url=link,
                    reservation_url=link,
                    raw_text=desc,
                    source_name="구글",
                )
            )
    except Exception as exc:
        LOGGER.info(f"[수집] 구글 뉴스 RSS 오류: {exc}")
    LOGGER.info(f"[수집] 구글 후보 {len(items)}건")
    return items
