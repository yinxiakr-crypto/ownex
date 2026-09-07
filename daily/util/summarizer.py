from __future__ import annotations

import os
import re

import requests

from util.logger import get_logger
from util.normalize import clip_summary

LOGGER = get_logger()
_GEMINI_DISABLED = False


def rule_summary(item: dict) -> str:
    text = " ".join(
        [
            item.get("title") or "",
            item.get("raw_text") or "",
            item.get("venue") or "",
        ]
    )
    artist = ""
    for name in ["반 고흐", "고흐", "모네", "피카소", "세잔", "르누아르", "보테로", "고야", "이중섭", "김환기"]:
        if name in text:
            artist = name
            break
    movement = ""
    for name in ["인상파", "현대미술", "르네상스", "추상"]:
        if name in text:
            movement = name
            break
    collection = ""
    museum = re.search(r"([가-힣A-Za-z]+미술관|[가-힣A-Za-z]+박물관)", text)
    if museum:
        collection = museum.group(1)
    bits = [part for part in [artist, movement, collection] if part]
    if not bits:
        bits = [item.get("title") or "미술전시"]
    return clip_summary(" ".join(bits), 30)


def gemini_summary(item: dict) -> str | None:
    global _GEMINI_DISABLED
    if _GEMINI_DISABLED:
        return None
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return None
    prompt = (
        "다음 한국 미술 전시를 한글 30자 안팎으로 요약하세요. "
        "작가명, 작품 시기, 소장 미술관만 쓰고 없는 것은 생략하세요. "
        "따옴표 없이 한 줄만 답하세요.\n"
        f"제목: {item.get('title', '')}\n"
        f"장소: {item.get('venue', '')}\n"
        f"설명: {item.get('raw_text', '')}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    try:
        response = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20,
        )
        if response.status_code != 200:
            _GEMINI_DISABLED = True
            LOGGER.info(f"[요약] Gemini 사용 불가({response.status_code}), 짧은 규칙 요약을 씁니다.")
            return None
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return clip_summary(text, 32)
    except Exception as exc:
        _GEMINI_DISABLED = True
        LOGGER.info(f"[요약] Gemini 실패, 규칙 요약으로 대체: {exc}")
        return None


def summarize(item: dict) -> str:
    return gemini_summary(item) or rule_summary(item)
