from __future__ import annotations

from datetime import date

from util.clock import today_seoul
from util.logger import get_logger
from util.sources_common import make_item

LOGGER = get_logger()

# 작가전·시대별 회화전·뉴스에 오른 전시를 빠지지 않게 넣습니다.
# 기간이 지난 전시는 모을 때 건너뜁니다.
FEATURED_SHOWS = [
    {
        "title": "뱅크시 : Still Here",
        "venue": "더현대 서울 ALT.1",
        "venue_address": "서울 영등포구 여의대로 108 여의도 6층",
        "start": date(2026, 7, 22),
        "end": date(2026, 11, 3),
        "raw": "BANKSY Still Here 거리예술 그래피티 현대미술 세계인기 여의도 특별전 화제",
        "reservation": "https://korean.visitseoul.net/exhibition/BANKSY-still-here/KOPx0x7wx",
        "portals": [
            ("서울관광", "https://korean.visitseoul.net/exhibition/BANKSY-still-here/KOPx0x7wx"),
            ("오픈갤러리", "https://www.opengallery.co.kr/exhibition/5362/"),
            ("아트코포스트", "https://artcopost.com/%eb%8d%94%ed%98%84%eb%8c%80-%ec%84%9c%ec%9a%b8-%eb%b1%85%ed%81%ac%ec%8b%9c-%ec%a0%84%ec%8b%9c-%ea%b4%80%eb%9e%8c-%ea%b8%b0%ea%b0%84-%ec%8b%9c%ea%b0%84-%ea%b0%80%ea%b2%a9/"),
        ],
    },
    {
        "title": "가우디: 서울에서 다시 태어나다",
        "venue": "신사하우스",
        "venue_address": "서울 강남구 강남대로162길 27",
        "start": date(2026, 8, 1),
        "end": date(2026, 10, 31),
        "raw": "가우디 Gaudi 서거 100주기 건축 르네상스이후 근현대 사그라다파밀리아 월드투어 연합뉴스 화제",
        "reservation": "https://gaudiseoul.com/",
        "portals": [
            ("가우디서울", "https://gaudiseoul.com/"),
            ("연합뉴스", "https://www.yna.co.kr/view/AKR20260724056500005"),
            ("디자인플러스", "https://design.co.kr/article/168795/"),
        ],
    },
    {
        "title": "서도호",
        "venue": "국립현대미술관 서울",
        "venue_address": "서울 종로구 삼청로 30",
        "start": date(2026, 8, 27),
        "end": date(2027, 2, 9),
        "raw": "서도호 Do Ho Suh 개인전 한국 유명작가 집 설치 국립현대 서울아트위크 화제 500점",
        "reservation": "https://www.mmca.go.kr/exhibits/exhibitsList.do",
        "portals": [
            ("국립현대미술관", "https://www.mmca.go.kr/exhibits/exhibitsList.do"),
            ("K-ARTNOW", "https://k-artnow.com/ko/posts.php?co_id=1787640916"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
        ],
    },
    {
        "title": "구정아: 우스모스",
        "venue": "리움미술관",
        "venue_address": "서울 용산구 이태원로55길 60-16",
        "start": date(2026, 9, 5),
        "end": date(2026, 12, 27),
        "raw": "구정아 Koo Jeong A OUSSSMOS 베니스비엔날레 한국관 리움 개인전 화제",
        "reservation": "https://www.leeum.org/",
        "portals": [
            ("리움", "https://www.leeum.org/"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10857554"),
            ("K-ARTNOW", "https://k-artnow.com/ko/posts.php?co_id=1787640916"),
        ],
    },
    {
        "title": "유영국: 산은 내 안에 있다",
        "venue": "서울시립미술관 서소문본관",
        "venue_address": "서울 중구 덕수궁길 61",
        "start": date(2026, 5, 19),
        "end": date(2026, 10, 25),
        "raw": "유영국 한국 추상 근대거장 회화전 서울시립 산은 내 안에 있다 화제",
        "reservation": "https://sema.seoul.go.kr/",
        "portals": [
            ("서울시립미술관", "https://sema.seoul.go.kr/"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
            ("데일리아트", "https://www.d-art.co.kr/news/articleView.html?idxno=6220"),
        ],
    },
    {
        "title": "솔 르윗: Open Structure",
        "venue": "아모레퍼시픽미술관",
        "venue_address": "서울 용산구 한강대로 100",
        "start": date(2026, 9, 1),
        "end": date(2027, 2, 28),
        "raw": "솔르윗 Sol LeWitt 개념미술 근현대 미국 작가전 월드로잉 국내첫 화제",
        "reservation": "https://www.apma.amorepacific.com/",
        "portals": [
            ("아모레퍼시픽미술관", "https://www.apma.amorepacific.com/"),
            ("디자인플러스", "https://design.co.kr/article/172277/"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
        ],
    },
    {
        "title": "박서보: 변하는 변하지 않는",
        "venue": "국제갤러리",
        "venue_address": "서울 종로구 삼청로 54",
        "start": date(2026, 8, 24),
        "end": date(2026, 10, 18),
        "raw": "박서보 단색화 한국 거장 회고전 회화전 국제갤러리 화제",
        "reservation": "https://www.kukjegallery.com/",
        "portals": [
            ("국제갤러리", "https://www.kukjegallery.com/"),
            ("디자인플러스", "https://design.co.kr/article/172277/"),
            ("아주경제", "https://www.ajupress.com/view/20260824060470344"),
        ],
    },
    {
        "title": "큐비스트: 시각의 혁신가들",
        "venue": "퐁피두센터 한화",
        "venue_address": "서울 영등포구 63로 50",
        "start": date(2026, 6, 4),
        "end": date(2026, 10, 4),
        "raw": "큐비스트 피카소 브라크 르네상스이후 근현대 유럽 회화전 퐁피두 개관전 화제",
        "reservation": "https://www.centrepompidou-hanwha.kr/",
        "portals": [
            ("퐁피두센터한화", "https://www.centrepompidou-hanwha.kr/"),
            ("서울신문", "https://www.seoul.co.kr/news/life/exhibition/2026/05/20/20260520016003"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
        ],
    },
    {
        "title": "게오르그 바젤리츠",
        "venue": "세화미술관",
        "venue_address": "서울 종로구 새문안로 68 흥국생명빌딩",
        "start": date(2026, 8, 13),
        "end": date(2026, 12, 27),
        "raw": "바젤리츠 Baselitz 독일 근현대 회화전 회고전 세화미술관 타계후첫 화제 매진",
        "reservation": "https://sehwamuseum.org/exhibition/%ea%b2%8c%ec%98%a4%eb%a5%b4%ea%b7%b8-%eb%b0%94%ec%a0%a4%eb%a6%ac%ec%b8%a0/",
        "portals": [
            ("세화미술관", "https://sehwamuseum.org/exhibition/%ea%b2%8c%ec%98%a4%eb%a5%b4%ea%b7%b8-%eb%b0%94%ec%a0%a4%eb%a6%ac%ec%b8%a0/"),
            ("데일리아트", "https://www.d-art.co.kr/news/articleView.html?idxno=6158"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
        ],
    },
    {
        "title": "키아프·프리즈 서울 2026",
        "venue": "코엑스",
        "venue_address": "서울 강남구 영동대로 513",
        "start": date(2026, 9, 2),
        "end": date(2026, 9, 6),
        "raw": "키아프 프리즈 KIAF Frieze 서울아트위크 화제 뉴스 아트페어 세계미술",
        "reservation": "https://mediahub.seoul.go.kr/archives/2019208",
        "portals": [
            ("내손안에서울", "https://mediahub.seoul.go.kr/archives/2019208"),
            ("디자인플러스", "https://design.co.kr/article/172277/"),
            ("코리아헤럴드", "https://www.koreaherald.com/article/10854378"),
        ],
    },
    {
        "title": "함양아: 정의되지 않은 파노라마",
        "venue": "아트선재센터",
        "venue_address": "서울 종로구 율곡로3길 87",
        "start": date(2026, 7, 31),
        "end": date(2026, 10, 4),
        "raw": "함양아 개인전 근현대 한국 작가전 아트선재 화제",
        "reservation": "https://www.artsonje.org/",
        "portals": [
            ("아트선재", "https://www.artsonje.org/"),
            ("K-ARTNOW", "https://k-artnow.com/ko/posts.php?co_id=1787640916"),
        ],
    },
    {
        "title": "김희천: 두더지들",
        "venue": "서울시립 서서울미술관",
        "venue_address": "서울 금천구 시흥대로79길 65",
        "start": date(2026, 8, 20),
        "end": date(2026, 11, 8),
        "raw": "김희천 개인전 미디어 회화전 한국 동시대 서울시립 화제",
        "reservation": "https://sema.seoul.go.kr/",
        "portals": [
            ("서울시립미술관", "https://sema.seoul.go.kr/"),
            ("디자인플러스", "https://design.co.kr/article/172277/"),
        ],
    },
    {
        "title": "윤형근을 다시 상상하다",
        "venue": "PKM갤러리",
        "venue_address": "서울 종로구 삼청로7길 40",
        "start": date(2026, 8, 26),
        "end": date(2026, 10, 3),
        "raw": "윤형근 단색화 한국 거장 회화전 개인전 PKM 화제",
        "reservation": "https://www.pkmgallery.com/",
        "portals": [
            ("PKM갤러리", "https://www.pkmgallery.com/"),
            ("K-ARTNOW", "https://k-artnow.com/ko/posts.php?co_id=1787640916"),
        ],
    },
    {
        "title": "김보희: TOWARDS There Was Light",
        "venue": "갤러리현대",
        "venue_address": "서울 종로구 삼청로 14",
        "start": date(2026, 8, 26),
        "end": date(2026, 10, 18),
        "raw": "김보희 한국화 회화전 개인전 갤러리현대 제주 화제",
        "reservation": "https://www.galleryhyundai.com/",
        "portals": [
            ("갤러리현대", "https://www.galleryhyundai.com/"),
            ("K-ARTNOW", "https://k-artnow.com/ko/posts.php?co_id=1787640916"),
        ],
    },
]


def featured_pages_for(title: str) -> list[str]:
    title = (title or "").strip()
    pages: list[str] = []
    for show in FEATURED_SHOWS:
        show_title = show["title"]
        if title == show_title or title in show_title or show_title in title:
            pages.append(show["reservation"])
            pages.extend(url for _, url in show["portals"])
            break
    return pages


def collect_featured(cfg) -> list[dict]:
    LOGGER.info("[수집] 화제 전시 보강")
    today = today_seoul()
    items = []
    skipped = 0
    for show in FEATURED_SHOWS:
        if show["end"] < today:
            skipped += 1
            continue
        for source_name, url in show["portals"]:
            items.append(
                make_item(
                    cfg,
                    title=show["title"],
                    venue=show["venue"],
                    venue_address=show["venue_address"],
                    reservation_url=show["reservation"],
                    source_url=url,
                    start_date=show["start"],
                    end_date=show["end"],
                    raw_text=show["raw"],
                    source_name=source_name,
                    image_url="",
                )
            )
    LOGGER.info(f"[수집] 화제 전시 후보 {len(items)}건 (기간 끝난 {skipped}건은 건너뜀)")
    return items
