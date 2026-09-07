from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from util.logger import get_logger
from util.season import palette, season_name

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
        bar = 120
        max_w, max_h = 1100, 1400
        ratio = min(max_w / art.width, (max_h - bar) / art.height)
        art_w = max(1, int(art.width * ratio))
        art_h = max(1, int(art.height * ratio))
        canvas = Image.new("RGB", (art_w, art_h + bar), "#2a1620")
        canvas.paste(art.resize((art_w, art_h), Image.Resampling.LANCZOS), (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, art_h, art_w, art_h + bar), fill="#2a1620")
        title_font = _font(26, bold=True)
        meta_font = _font(18)
        y = art_h + 18
        for line in _wrap(draw, title, title_font, art_w - 48, 2):
            draw.text((24, y), line, font=title_font, fill="#f6efe6")
            y += 32
        draw.text((24, min(y + 2, art_h + bar - 28)), "  ·  ".join(part for part in [venue, period] if part), font=meta_font, fill="#f3c4b5")
    else:
        width, height = 720, 960
        colors = palette()
        canvas = Image.new("RGB", (width, height), colors["bg"])
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((28, 28, width - 28, height - 28), fill=colors["paper"])
        brand = _font(20, bold=True)
        title_font = _font(58, bold=True)
        meta_font = _font(22)
        draw.text((width / 2, 86), "OWNEX", font=brand, fill=colors["accent"], anchor="mm")
        lines = _wrap(draw, title, title_font, width - 120, 4)
        y = 960 / 2 - (len(lines) * 70) / 2
        for line in lines:
            draw.text((width / 2, y), line, font=title_font, fill=colors["ink"], anchor="mm")
            y += 70
        draw.text((width / 2, min(y + 28, 780)), venue, font=meta_font, fill=colors["accent"], anchor="mm")
        draw.text((width / 2, min(y + 64, 820)), period, font=meta_font, fill=colors["ink"], anchor="mm")
        draw.text((width / 2, 890), season_name(), font=_font(16), fill=colors["accent"], anchor="mm")
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def ensure_poster(row: dict, fetch_missing: bool = True, force: bool = False) -> str:
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    path = ROOT / "web" / poster_rel(row)
    art_bytes = None
    if fetch_missing:
        try:
            from util.email_report import find_representative_art

            found_url, found_bytes = find_representative_art(row)
            if found_url:
                row["image_url"] = found_url
                row["has_art"] = True
            art_bytes = found_bytes
        except Exception as exc:
            LOGGER.info(f"[홈] 작품 사진을 찾지 못했습니다: {(row.get('title') or '')[:30]} / {exc}")
    elif (row.get("image_url") or "").startswith("http"):
        try:
            from util.email_report import _download_picture

            loaded = _download_picture(row["image_url"])
            if loaded:
                art_bytes = loaded[0]
        except Exception:
            art_bytes = None

    if path.exists() and path.stat().st_size > 8000 and not force and art_bytes is None:
        return poster_rel(row)

    path.write_bytes(make_poster(row, art_bytes))
    LOGGER.info(f"[홈] {'작품' if art_bytes else '글자'} 포스터 저장: {(row.get('title') or '')[:30]}")
    return poster_rel(row)
