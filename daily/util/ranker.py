from __future__ import annotations

import re

from urllib.parse import urlparse

from util.config_loader import csv_list
from util.logger import get_logger
from util.normalize import clean_text

LOGGER = get_logger()


def _blob(item: dict) -> str:
    return " ".join(
        [
            item.get("title") or "",
            item.get("venue") or "",
            item.get("venue_address") or "",
            item.get("summary") or "",
            item.get("raw_text") or "",
            item.get("source_name") or "",
        ]
    )


JUNK_TITLES = {
    "공연일정",
    "전시일정",
    "프로그램",
    "이용안내",
    "전시",
    "전체",
    "달력",
    "검색",
    "검색어 검색",
    "전시명",
    "장르선택",
    "예약",
    "TICKETS",
    "예약 | TICKETS",
    "The server has not found anything matching the Request-URL.",
}


def merge_items(items: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in items:
        title = clean_text(item.get("title") or "")
        if not title or title in JUNK_TITLES:
            continue
        if title.startswith("20") and "전" not in title and len(title) < 8:
            continue
        lowered = title.lower()
        if any(word in lowered for word in ("ticket", "login", "server has not", "error", "404")):
            continue
        if title in {"예약", "멤버십", "오시는 길", "이용안내", "Learn More", "What's On"}:
            continue
        if any(word in title for word in ("개인정보", "위탁", "이용약관", "저작권", "이메일무단", "쿠키")):
            continue
        if re.fullmatch(r"[\d.\-\s~]+", title):
            continue
        key = title.replace(" ", "").lower()
        if key not in grouped:
            grouped[key] = dict(item)
            grouped[key]["source_names"] = [item.get("source_name") or ""]
            urls = [item.get("reservation_url") or item.get("source_url") or ""]
            grouped[key]["source_url_list"] = [url for url in urls if url]
            continue
        current = grouped[key]
        current["source_names"].append(item.get("source_name") or "")
        extra = item.get("reservation_url") or item.get("source_url") or ""
        if extra and extra not in current["source_url_list"]:
            current["source_url_list"].append(extra)
        for field in ("venue", "venue_address", "image_url", "summary", "start_date", "end_date", "raw_text"):
            if not current.get(field) and item.get(field):
                current[field] = item[field]
    return list(grouped.values())


def _portal_count(item: dict) -> int:
    names = {name for name in item.get("source_names", []) if name}
    hosts = set()
    for url in item.get("source_url_list") or []:
        host = urlparse(url or "").netloc.lower().replace("www.", "")
        if host:
            hosts.add(host)
    return max(len(names), len(hosts))


def rank_items(cfg, items: list[dict], limit: int | None = None) -> list[dict]:
    ranking = cfg["ranking"]
    artists = csv_list(ranking.get("premium_artists", ""))
    korean_favorites = csv_list(ranking.get("korean_favorites", ""))
    world_popular = csv_list(ranking.get("world_popular", ""))
    asian_artists = csv_list(ranking.get("asian_artists", ""))
    period_words = csv_list(ranking.get("period_keywords", ranking.get("movements", "")))
    venues = csv_list(ranking.get("venues_bonus", ""))
    recommend = csv_list(ranking.get("recommend", ""))
    hot_words = csv_list(ranking.get("hot_keywords", ""))
    value_words = csv_list(ranking.get("curator_value", ""))
    news_outlets = csv_list(ranking.get("news_outlets", ""))
    regions = csv_list(cfg["general"].get("priority_regions", ""))
    main_regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    min_results = cfg["general"].getint("min_results", fallback=10)
    max_results = cfg["general"].getint("max_results", fallback=20)
    if limit is None:
        max_results = max(min_results, max_results)
    else:
        max_results = max(min_results, limit)

    scored = []
    for item in items:
        text = _blob(item)
        score = 0
        reasons = []
        if item.get("has_visual") or item.get("image_url") or item.get("image_bytes"):
            score += 50
            reasons.append("시각자료")
        if any(word in text for word in ("대표작", "작품사진", "작품", "회화", "미디어아트", "몰입형", "설치작품", "원화")):
            score += 22
            reasons.append("대표작품")
        portals = _portal_count(item)
        if portals >= 3:
            score += 36
            reasons.append(f"{portals}곳포털홍보")
        elif portals == 2:
            score += 14
            reasons.append("2곳홍보")
        hit_world = [name for name in world_popular if name and name in text]
        if hit_world:
            score += 28
            reasons.append(f"세계인기:{hit_world[0]}")
        hit_korean = [name for name in korean_favorites if name and name in text]
        if hit_korean:
            score += 24
            reasons.append(f"국내선호:{hit_korean[0]}")
        hit_artists = [name for name in artists if name and name in text]
        if hit_artists:
            score += 32
            reasons.append(hit_artists[0])
        hit_asian = [name for name in asian_artists if name and name in text]
        if hit_asian:
            score += 22
            reasons.append(f"아시아작가:{hit_asian[0]}")
        hit_moves = [name for name in period_words if name and name in text]
        if hit_moves:
            score += 16
            reasons.append(hit_moves[0])
        if any(word in text for word in ("회화전", "작품전", "개인전", "회고전")):
            score += 12
            reasons.append("작가작품전")
        hit_value = [name for name in value_words if name and name in text]
        if hit_value:
            score += 14
            reasons.append("미술사가치")
        if any(name in text for name in venues):
            score += 12
            reasons.append("주요미술관")
        if any(word in text for word in hot_words):
            score += 22
            reasons.append("화제전시")
        if any(word in text for word in recommend):
            score += 20
            reasons.append("가볼만함")
        sources = " ".join(item.get("source_names") or [item.get("source_name") or ""])
        source_blob = sources + " " + " ".join(item.get("source_url_list") or [])
        if any(name in source_blob or name in text for name in news_outlets):
            score += 18
            reasons.append("주요뉴스")
        tag = item.get("region_tag") or ""
        if "안양" in tag or "안양" in text:
            score += 28
            reasons.append("안양")
        elif any(
            word in text or word in tag
            for word in (
                "퐁피두",
                "리움",
                "국립현대",
                "더현대",
                "ALT.1",
                "과천",
                "여의도",
                "용산",
                "서울시립",
                "롯데뮤지엄",
                "아모레",
                "디뮤지엄",
                "일민",
                "DDP",
                "소마",
                "공예박물관",
                "세화",
                "신사하우스",
                "국제갤러리",
                "코엑스",
            )
        ):
            score += 26
            reasons.append("지정미술관")
        elif "서울" in tag or "서울" in text or "한가람" in text:
            score += 22
            reasons.append("서울")
        else:
            region_hits = [name for name in regions if name in tag or name in text]
            if region_hits:
                score += 8
                reasons.append(region_hits[0])
        if not any(region in tag or region in text for region in main_regions) and "한가람" not in text:
            score -= 15
        if any(word in text for word in ("교육프로그램", "까지 모집", "워크숍", "모집중")):
            score -= 40
            reasons.append("교육성제외")
        item["score"] = score
        item["score_reason"] = ", ".join(reasons) or "일반전시"
        scored.append(item)

    scored.sort(
        key=lambda row: (
            0 if (row.get("has_visual") or row.get("image_url") or row.get("image_bytes")) else 1,
            -row["score"],
            row.get("title") or "",
        )
    )
    top = scored[:max_results]
    LOGGER.info(f"[순위] 후보 {len(scored)}건 중 상위 {len(top)}건 선택")
    return top
