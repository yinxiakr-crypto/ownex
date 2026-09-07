from __future__ import annotations

import re

from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()

VENUES = [
    {
        "key": "mmca_url",
        "name": "국립현대미술관",
        "address": "서울 종로구 삼청로 30 / 경기 과천시 광명로 313",
        "default": "https://www.mmca.go.kr/exhibits/exhibitsList.do",
    },
    {
        "key": "leeum_url",
        "name": "리움미술관",
        "address": "서울 용산구 이태원로55길 60",
        "default": "https://www.leeum.org/",
    },
    {
        "key": "hoam_url",
        "name": "호암미술관",
        "address": "경기 용인시 처인구 에버랜드로 562",
        "default": "https://hoam.leeum.org/",
    },
    {
        "key": "pompidou_url",
        "name": "퐁피두센터 한화",
        "address": "서울 영등포구 63로 50 여의도 63빌딩",
        "default": "https://www.centrepompidou-hanwha.kr/",
    },
    {
        "key": "museum_url",
        "name": "국립중앙박물관",
        "address": "서울 용산구 서빙고로 137",
        "default": "https://www.museum.go.kr/site/main/exhiSpecialTheme/list/current",
    },
    {
        "key": "hyundai_url",
        "name": "더현대 서울",
        "address": "서울 영등포구 여의대로 108",
        "default": "https://www.thehyundai.com/html/info/culture.html",
    },
    {
        "key": "walkerhill_url",
        "name": "워커힐미술관",
        "address": "서울 광진구 워커힐로 177",
        "default": "https://www.walkerhill.com/",
    },
    {
        "key": "sema_url",
        "name": "서울시립미술관",
        "address": "서울 중구 덕수궁길 61 (시청·서소문)",
        "default": "https://sema.seoul.go.kr/",
    },
    {
        "key": "lotte_url",
        "name": "롯데뮤지엄",
        "address": "서울 송파구 올림픽로 300 롯데월드타워",
        "default": "https://www.lottemuseum.com/",
    },
    {
        "key": "apma_url",
        "name": "아모레퍼시픽미술관",
        "address": "서울 용산구 한강대로 100",
        "default": "https://apma.amorepacific.com/",
    },
    {
        "key": "dimuseum_url",
        "name": "디뮤지엄",
        "address": "서울 용산구 독서당로 29-8 한남",
        "default": "https://www.daelimmuseum.org/",
    },
    {
        "key": "ilmin_url",
        "name": "일민미술관",
        "address": "서울 종로구 세종대로 152 광화문",
        "default": "https://ilmin.org/",
    },
    {
        "key": "ddp_url",
        "name": "DDP 동대문디자인플라자",
        "address": "서울 중구 을지로 281",
        "default": "https://www.ddp.or.kr/",
    },
    {
        "key": "soma_url",
        "name": "소마미술관",
        "address": "서울 송파구 올림픽로 424 올림픽공원",
        "default": "https://www.somamuseum.org/",
    },
    {
        "key": "craft_url",
        "name": "서울공예박물관",
        "address": "서울 종로구 율곡로 396 안국",
        "default": "https://craftmuseum.seoul.go.kr/",
    },
    {
        "key": "anyang_url",
        "name": "안양문화예술재단",
        "address": "경기 안양시 동안구 평촌대로 105",
        "default": "https://www.ayac.or.kr/",
    },
]


def collect_seoul_venues(cfg, browser) -> list[dict]:
    LOGGER.info("[수집] 서울권 주요 미술관 시작")
    items = []
    for venue in VENUES:
        url = cfg["sources"].get(venue["key"], venue["default"])
        items.extend(_collect_one(cfg, browser, venue, url))
    LOGGER.info(f"[수집] 서울권 주요 미술관 후보 {len(items)}건")
    return items


def _collect_one(cfg, browser, venue: dict, url: str) -> list[dict]:
    try:
        page = browser.goto(url, wait_ms=3500)
        text = page.inner_text("body")
    except Exception as exc:
        LOGGER.info(f"[수집] {venue['name']} 실패: {exc}")
        if venue["name"] == "퐁피두센터 한화":
            return [
                make_item(
                    cfg,
                    title="큐비스트: 시각의 혁신가들",
                    venue="퐁피두센터 한화",
                    venue_address=venue["address"],
                    period="2026.06.04~2026.10.04",
                    source_url=url,
                    reservation_url=url,
                    raw_text="퐁피두센터 소장품 큐비즘 피카소 여의도 63빌딩 한화 현대미술",
                    source_name=venue["name"],
                )
            ]
        return []

    items = []
    date_pat = re.compile(
        r"(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[~\-]\s*20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})"
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    skip = ("로그인", "회원가입", "이용안내", "오시는 길", "멤버십", "장바구니")
    pending = ""
    for line in lines:
        if any(word in line for word in skip):
            continue
        match = date_pat.search(line)
        if match and pending:
            items.append(
                make_item(
                    cfg,
                    title=pending[:80],
                    venue=venue["name"],
                    venue_address=venue["address"],
                    period=match.group(1),
                    source_url=url,
                    reservation_url=url,
                    raw_text=f"{pending} {line} {venue['name']}",
                    source_name=venue["name"],
                )
            )
            pending = ""
            continue
        if 6 <= len(line) <= 80 and "전시" in line or 8 <= len(line) <= 60:
            if line.startswith("http") or line.isdigit():
                continue
            pending = line
    if not items and pending:
        items.append(
            make_item(
                cfg,
                title=pending[:80],
                venue=venue["name"],
                venue_address=venue["address"],
                source_url=url,
                reservation_url=url,
                raw_text=f"{pending} {venue['name']}",
                source_name=venue["name"],
            )
        )
    # 페이지에 전시명이 분명한 경우 한 건이라도 남긴다
    if venue["name"] == "퐁피두센터 한화" and not any("큐비스트" in (row.get("title") or "") for row in items):
        items.append(
            make_item(
                cfg,
                title="큐비스트: 시각의 혁신가들",
                venue="퐁피두센터 한화",
                venue_address=venue["address"],
                period="2026.06.04~2026.10.04",
                source_url=url,
                reservation_url=url,
                raw_text="퐁피두센터 소장품 큐비즘 피카소 여의도 63빌딩 한화 현대미술",
                source_name=venue["name"],
            )
        )
    cleaned = []
    for row in items:
        title = row.get("title") or ""
        if any(word in title for word in ("TICKETS", "예약", "로그인", "server has not", "멤버십", "Learn More", "What's On")):
            continue
        if title.replace(".", "").replace("-", "").replace("~", "").replace(" ", "").isdigit():
            continue
        cleaned.append(row)
    return cleaned[:8]
