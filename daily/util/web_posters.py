from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from util.logger import get_logger
from util.season import palette, season_name
from util.show_images import official_image_for, reset_used_images, take_unique_art

ROOT = Path(__file__).resolve().parent.parent
POSTER_DIR = ROOT / "web" / "posters"
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")
LOGGER = get_logger()


def _font(size: int, bold: bool = False):
    path = FONT_BOLD if bold and FONT_BOLD.exists() else FONT_REGULAR
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def poster_id(row: dict) -> str:
    key = "|".join((row.get("title") or "", row.get("venue") or "", row.get("start_date") or ""))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def poster_rel(row: dict) -> str:
    return f"posters/{poster_id(row)}.jpg"


def _wrap(draw, text: str, font, max_width: int, limit: int = 5) -> list[str]:
    text = (text or "").replace("\n", " ").strip()
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines[:limit]


def _open_art(data: bytes) -> Image.Image | None:
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        if image.width < 200 or image.height < 200:
            return None
        return image
    except Exception:
        return None


def make_poster(row: dict, art_bytes: bytes | None = None) -> bytes:
    title = row.get("title") or "OWNEX"
    venue = row.get("venue") or ""
    period = " ~ ".join(part for part in [row.get("start_date") or "", row.get("end_date") or ""] if part)
    art = _open_art(art_bytes) if art_bytes else None
    if art:
        max_w, max_h = 1600, 1800
        ratio = min(1.0, max_w / art.width, max_h / art.height)
        art_w = max(1, int(art.width * ratio))
        art_h = max(1, int(art.height * ratio))
        if ratio < 0.999:
            canvas = art.resize((art_w, art_h), Image.Resampling.LANCZOS)
        else:
            canvas = art
    else:
        width, height = 900, 1120
        colors = palette()
        digest = int(poster_id(row)[:6], 16)
        papers = ("#f6e4dc", "#d7efff", "#e7f3ea", "#f3f7d4")
        accents = (colors["accent"], "#351e28", "#3f7a68", "#e9f056")
        paper = papers[digest % len(papers)]
        accent = accents[digest % len(accents)]
        canvas = Image.new("RGB", (width, height), colors["bg"])
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((36, 36, width - 36, height - 36), fill=paper)
        draw.rectangle((36, 36, 52, height - 36), fill=accent)
        brand = _font(22, bold=True)
        title_font = _font(46, bold=True)
        meta_font = _font(24)
        season_ko = {"winter": "겨울", "spring": "봄", "summer": "여름", "fall": "가을"}.get(season_name(), "")
        draw.ellipse((width - 360, 90, width - 90, 360), outline=accent, width=6)
        draw.text((88, 92), "OWNEX", font=brand, fill=accent)
        lines = _wrap(draw, title, title_font, width - 200, 5)
        y = 430
        for line in lines:
            draw.text((88, y), line, font=title_font, fill=colors["ink"])
            y += 62
        draw.rectangle((88, min(y + 18, 860), 200, min(y + 24, 866)), fill=accent)
        draw.text((88, min(y + 48, 900)), venue, font=meta_font, fill=accent)
        draw.text((88, min(y + 90, 950)), period, font=meta_font, fill=colors["ink"])
        draw.text((88, 1020), season_ko, font=_font(20), fill=accent)
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def ensure_poster(row: dict, fetch_missing: bool = True, force: bool = False) -> str:
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    path = ROOT / "web" / poster_rel(row)
    want_official = bool(official_image_for(row.get("title") or ""))
    art_bytes = None
    if fetch_missing or want_official:
        try:
            from util.email_report import find_representative_art

            found_url, found_bytes = find_representative_art(row)
            found_bytes = take_unique_art(found_bytes)
            if found_url and found_bytes:
                row["image_url"] = found_url
                row["has_art"] = True
                art_bytes = found_bytes
                opened = _open_art(found_bytes)
                official = official_image_for(row.get("title") or "")
                row["letterbox"] = bool(official and opened and opened.width > opened.height * 1.15)
            else:
                row["image_url"] = ""
                row["has_art"] = False
        except Exception as exc:
            LOGGER.info(f"[홈] 작품 사진을 찾지 못했습니다: {(row.get('title') or '')[:30]} / {exc}")
    elif (row.get("image_url") or "").startswith("http"):
        try:
            from util.email_report import _download_picture

            loaded = _download_picture(row["image_url"])
            art_bytes = take_unique_art(loaded[0] if loaded else None)
        except Exception:
            art_bytes = None

    if path.exists() and path.stat().st_size > 8000 and not force and not want_official and art_bytes is None:
        existing = take_unique_art(path.read_bytes())
        if existing:
            return poster_rel(row)

    path.write_bytes(make_poster(row, art_bytes))
    LOGGER.info(f"[홈] {'작품' if art_bytes else '오넥스 그림'} 포스터 저장: {(row.get('title') or '')[:30]}")
    return poster_rel(row)
