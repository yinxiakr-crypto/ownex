from __future__ import annotations

import hashlib
import io
import re
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


def _designed_title(title: str) -> str:
    raw = title or "OWNEX"
    marked = re.search(r"[〈《](.+?)[〉》]", raw)
    if marked:
        return marked.group(1).strip()
    clean = raw.replace("〈", "").replace("〉", "").replace("《", "").replace("》", "")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > 34:
        return clean[:32].rstrip() + "…"
    return clean or "OWNEX"


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


def _hex(color: str) -> tuple[int, int, int]:
    value = (color or "").lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _blend(start: tuple[int, int, int], end: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = min(1.0, max(0.0, amount))
    return tuple(int(a + (b - a) * amount) for a, b in zip(start, end))


def _designed_canvas(title: str) -> Image.Image:
    width, height = 900, 1120
    colors = palette()
    season = season_name()
    papers = {
        "winter": ("#d7efff", "#d7efff", "#eaf6ff"),
        "spring": ("#e7f3ea", "#e7f3ea", "#eef6e8"),
        "summer": ("#f3f7d4", "#eef3c4", "#f7f8e4"),
        "fall": ("#f6e4dc", "#fde8df", "#f7ece4"),
    }
    marks = {
        "winter": "#7aa7c7",
        "spring": "#3f7a68",
        "summer": "#8a9220",
        "fall": "#b85a48",
    }
    blush, mist, cream = papers.get(season, papers["fall"])
    ink = "#3a2430" if season == "fall" else colors["ink"]
    mark = marks.get(season, "#b85a48")
    canvas = Image.new("RGB", (width, height), blush)
    draw = ImageDraw.Draw(canvas)
    top, mid, bottom = _hex(blush), _hex(mist), _hex(cream)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = _blend(top, mid, t / 0.55) if t < 0.55 else _blend(mid, bottom, (t - 0.55) / 0.45)
        draw.line((0, y, width, y), fill=color)
    brand = _font(95, bold=True)
    label = "OWNEX"
    gap = 31
    brand_w = sum(draw.textlength(ch, font=brand) for ch in label) + gap * (len(label) - 1)
    x = (width - brand_w) / 2
    for ch in label:
        draw.text((x, 108), ch, font=brand, fill=mark)
        x += draw.textlength(ch, font=brand) + gap
    clean = _designed_title(title)
    max_w, max_h = width - 120, 520
    title_font = _font(39, bold=True)
    lines = _wrap(draw, clean, title_font, max_w, 6)
    line_h = 48
    for size in range(66, 32, -3):
        trial_font = _font(size, bold=True)
        trial_lines = _wrap(draw, clean, trial_font, max_w, 20)
        trial_h = int(size * 1.2)
        widest = max((draw.textlength(line, font=trial_font) for line in trial_lines), default=0)
        if len(trial_lines) > 5:
            continue
        if widest <= max_w and len(trial_lines) * trial_h <= max_h:
            title_font = trial_font
            lines = trial_lines
            line_h = trial_h
            break
    block_h = len(lines) * line_h
    y = 268 + ((height - 310) - block_h) / 2
    for line in lines:
        draw.text(((width - draw.textlength(line, font=title_font)) / 2, y), line, font=title_font, fill=ink)
        y += line_h
    return canvas


def make_poster(row: dict, art_bytes: bytes | None = None) -> bytes:
    art = _open_art(art_bytes) if art_bytes else None
    if art:
        max_w, max_h = 1600, 1800
        ratio = min(1.0, max_w / art.width, max_h / art.height)
        art_w = max(1, int(art.width * ratio))
        art_h = max(1, int(art.height * ratio))
        canvas = art.resize((art_w, art_h), Image.Resampling.LANCZOS) if ratio < 0.999 else art
    else:
        canvas = _designed_canvas(row.get("title") or "OWNEX")
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
