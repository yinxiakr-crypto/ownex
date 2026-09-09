from __future__ import annotations

import hashlib

# 1순위: 그 작가·전시의 대표 작품만 적습니다. 인물 사진은 넣지 않습니다.
CURATED_ARTWORKS = (
    {
        "keys": ("바젤리츠", "Baselitz"),
        "images": (
            "https://commons.wikimedia.org/wiki/Special:FilePath/Baselitz_Yellow_Song_001.jpg",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Untitled_sculpture_by_Georg_Baselitz.jpg",
        ),
    },
    {
        "keys": ("솔 르윗", "Open Structure"),
        "images": (
            "https://cdn.bkn24.com/news/photo/202608/20818_25861_5058.jpg",
        ),
    },
    {
        "keys": ("유영국", "산은 내 안에"),
        "images": (
            "https://img.etoday.co.kr/pto_db/2026/08/20260826104110_2378468_1200_927.jpg",
        ),
    },
    {
        "keys": ("함양아", "정의되지 않은 파노라마"),
        "images": (
            "https://image.fnnews.com/resource/media/image/2026/08/10/202608101833210058_l.jpg",
        ),
    },
    {
        "keys": ("건축투어",),
        "images": (
            "https://www.ddp.or.kr/usr/upload/board_thumb/zboardphotogallery105/20260402034626796.jpg",
        ),
    },
)

# 그 전시의 공식 페이지와 대표 그림만 적습니다. 다른 전시 사진은 넣지 않습니다.
OFFICIAL_SHOWS = (
    {
        "keys": ("옻나무에서 칠기로", "漆-"),
        "page": "https://craftmuseum.seoul.go.kr/exhibit/plan/view/161",
        "image": "https://craftmuseum.seoul.go.kr/common/exhibition/filedown?idx=1722",
    },
    {
        "keys": ("안동별궁", "시간의 겹"),
        "page": "https://craftmuseum.seoul.go.kr/exhibit/plan/view/184",
        "image": "https://craftmuseum.seoul.go.kr/common/exhibition/filedown?idx=1900",
    },
    {
        "keys": ("나전장의 도안실",),
        "page": "https://craftmuseum.seoul.go.kr/exhibit/plan/view/190",
        "image": "https://craftmuseum.seoul.go.kr/common/exhibition/filedown?idx=1967",
    },
)

_used_hashes: set[str] = set()


def reset_used_images() -> None:
    _used_hashes.clear()


def _match(title: str) -> dict | None:
    text = title or ""
    for item in OFFICIAL_SHOWS:
        if any(key in text for key in item["keys"]):
            return item
    return None


def official_pages_for(title: str) -> list[str]:
    item = _match(title)
    return [item["page"]] if item else []


def official_image_for(title: str) -> str:
    item = _match(title)
    return item["image"] if item else ""


def curated_artworks_for(title: str) -> list[str]:
    text = title or ""
    for item in CURATED_ARTWORKS:
        if any(key in text for key in item["keys"]):
            return list(item["images"])
    return []


def art_hash(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def take_unique_art(data: bytes | None) -> bytes | None:
    if not data:
        return None
    digest = art_hash(data)
    if digest in _used_hashes:
        return None
    _used_hashes.add(digest)
    return data
