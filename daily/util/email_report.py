from __future__ import annotations

import base64
import io
import json
import os
import re
import smtplib
import time
from datetime import date
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

from util.config_loader import load_env_file
from util.google_calendar import can_send_gmail, gmail_service, logged_in_email
from util.logger import get_logger
from util.mail_list import mail_heading, wanted_email_groups
from util.normalize import clip_calendar_span, from_iso

LOGGER = get_logger()
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold and FONT_BOLD.exists() else FONT_REGULAR
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
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
    return lines[:6]


def _period(row: dict, calendar_from: date | None) -> str:
    start, end = clip_calendar_span(
        from_iso(row.get("start_date") or ""),
        from_iso(row.get("end_date") or ""),
        calendar_from,
    )
    if not start:
        return "기간 미확인"
    if end and end != start:
        return f"{start.isoformat()} ~ {end.isoformat()}"
    return start.isoformat()


def make_schedule_card(rows: list[dict], calendar_from: date | None, heading: str = "오늘의 전시") -> bytes:
    width = 900
    height = max(1280, 220 + len(rows) * 118)
    image = Image.new("RGB", (width, height), "#1f1a16")
    draw = ImageDraw.Draw(image)
    title_font = _font(42, bold=True)
    item_font = _font(28, bold=True)
    meta_font = _font(22)
    small_font = _font(18)
    draw.rectangle((40, 40, width - 40, height - 40), fill="#f4ead8")
    draw.text((70, 70), heading, font=title_font, fill="#5c2e0a")
    draw.text((70, 130), date.today().isoformat(), font=small_font, fill="#7a5a3a")
    y = 180
    for index, row in enumerate(rows, start=1):
        draw.rectangle((70, y, width - 70, y + 4), fill="#c9a36a")
        y += 20
        title_lines = _wrap(draw, f"{index}. {row.get('title') or ''}", item_font, width - 160)
        for line in title_lines:
            draw.text((70, y), line, font=item_font, fill="#2b1b12")
            y += 36
        venue = " ".join(part for part in [row.get("venue") or "", row.get("venue_address") or ""] if part)
        for line in _wrap(draw, venue, meta_font, width - 160)[:3]:
            draw.text((70, y), line, font=meta_font, fill="#5a4333")
            y += 30
        draw.text((70, y), _period(row, calendar_from), font=meta_font, fill="#8a3b12")
        y += 48
        if y > height - 120:
            break
    draw.text((70, height - 90), "매일 아침 자동으로 보낸 일정입니다.", font=small_font, fill="#7a5a3a")
    buffer = io.BytesIO()
    image.thumbnail((900, 1600))
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


HEADERS = {"User-Agent": "Mozilla/5.0"}
WIKI_HEADERS = {
    "User-Agent": "Ownex/1.0 (personal art-exhibition helper; student project)",
    "Accept": "application/json",
}
SKIP_HINTS = (
    "logo", "icon", "sprite", "favicon", "button",
    "sns", "share", "facebook", "instagram", "youtube", "arrow", "footer",
    "ci-", "symbol", "wa.png", "contact", "menu", "search", "parking",
)
POSTER_HINTS = ("poster", "포스터", "og-image", "key-visual", "main-kv", "/kv-", "sns-")
ART_HINTS = ("/upload/exhibition/", "/upload/notice/", "/imageShow/", "photogallery", "artwork", "work", "작품")
ARTIST_QUERIES = (
    (("큐비스트", "큐비드", "피카소", "브라크", "세잔", "Picasso", "Braque", "Cezanne"),
     ("Cubism", "Pablo Picasso")),
    (("뱅크시", "BANKSY", "Banksy"),
     ("Girl with Balloon", "Banksy")),
    (("가우디", "Gaudi", "Gaudí"),
     ("Sagrada Familia", "Casa Batllo")),
    (("서도호", "Do Ho Suh"),
     ("Do Ho Suh",)),
    (("구정아", "Koo Jeong"),
     ("Koo Jeong A",)),
    (("박서보", "Park Seo-Bo", "Park Seo Bo"),
     ("Park Seo-Bo", "Dansaekhwa")),
    (("유영국", "Yoo Youngkuk", "Yoo Young-kuk"),
     ("Yoo Youngkuk", "유영국")),
    (("솔 르윗", "솔르윗", "LeWitt", "Lewitt"),
     ("Sol LeWitt",)),
    (("바젤리츠", "Baselitz"),
     ("Georg Baselitz",)),
    (("윤형근", "Yun Hyong"),
     ("Yun Hyong-keun", "윤형근")),
    (("김보희", "Kim Bohie", "Kim Bo-hie"),
     ("Kim Bohie",)),
)
ARTWORK_FIRST = ("큐비스트", "큐비드", "피카소", "브라크", "세잔", "Picasso", "뱅크시", "BANKSY", "Banksy", "가우디", "Gaudi", "Gaudí")


def _abs_url(page_url: str, src: str) -> str:
    src = (src or "").strip().split(" ")[0]
    if not src or src.startswith("data:"):
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("http"):
        return src
    from urllib.parse import urljoin
    return urljoin(page_url, src)


def _url_score(url: str) -> int:
    low = url.lower()
    if any(hint in low for hint in SKIP_HINTS) or low.endswith(".svg"):
        return -100
    score = 0
    if any(hint in low for hint in POSTER_HINTS):
        score += 12
    if any(hint in low for hint in ART_HINTS):
        score += 25
    if low.endswith((".jpg", ".jpeg")) or ".jpg" in low or ".jpeg" in low:
        score += 20
    if low.endswith(".png"):
        score += 4
    if "/upload/exhibition/" in low and (".jpg" in low or ".jpeg" in low):
        score += 18
    if "/exhibition/detail" in low:
        score += 8
    return score


def _download_picture(url: str) -> tuple[bytes, int] | None:
    if not url or not url.startswith("http") or _url_score(url) < 0:
        return None
    try:
        headers = WIKI_HEADERS if "wiki" in url.lower() else HEADERS
        response = requests.get(url, timeout=12, headers=headers, allow_redirects=True)
        if response.status_code >= 400 or len(response.content) < 4000:
            return None
        picture = Image.open(io.BytesIO(response.content)).convert("RGB")
        width, height = picture.size
        if min(width, height) < 200:
            return None
        ratio = width / max(height, 1)
        if ratio > 2.6 or ratio < 0.38:
            return None
        score = _url_score(url) + min(width, height) // 40
        if 0.65 <= ratio <= 1.55:
            score += 18
        buffer = io.BytesIO()
        picture.thumbnail((1100, 1100))
        picture.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue(), score
    except Exception:
        return None


def _title_tokens(title: str) -> list[str]:
    skip = {"교육", "프로그램", "서울시립", "상시", "까지", "모집", "해외", "한국문화원", "일본", "전시회"}
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z]{4,}", title or "")
    return [token for token in tokens if token not in skip][:6]


ARTIST_HINTS = (
    "작품", "전경", "대표작", "대표", "피카소", "브라크", "세잔", "들로네",
    "김환기", "유영국", "박래현", "나전", "칠기", "picasso", "braque",
    "cezanne", "painting", "sculpture", "artwork", "collection",
)


def _caption_score(text: str) -> int:
    lowered = (text or "").lower()
    score = 0
    if any(hint in lowered for hint in POSTER_HINTS):
        score += 10
    for hint in ARTIST_HINTS:
        if hint.lower() in lowered:
            score += 22
    return score


def _extract_image_urls(page_url: str, html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []
    for img in soup.find_all(["img", "source"]):
        caption = " ".join(
            part for part in [img.get("alt") or "", img.get("title") or ""] if part
        )
        parent = img.find_parent(["figure", "a", "li", "div"])
        if parent:
            caption += " " + parent.get_text(" ", strip=True)[:80]
        for attr in ("src", "data-src", "data-original", "srcset"):
            value = img.get(attr) or ""
            for part in value.split(","):
                url = _abs_url(page_url, part)
                if url:
                    found.append((url, caption))
    for match in re.findall(r"url\((['\"]?)([^)'\"]+)\1\)", html, flags=re.I):
        url = _abs_url(page_url, match[1])
        if url:
            found.append((url, ""))
    return found


def _related_pages(page_url: str, html: str, tokens: list[str]) -> list[str]:
    from urllib.parse import urljoin, urlparse

    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc
    related: list[str] = []
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = urljoin(page_url, link["href"])
        if urlparse(href).netloc != host:
            continue
        if tokens and any(token in text or token in href for token in tokens):
            related.append(href.split("#")[0])
        if any(part in href for part in ("/exhibition/", "/exhibits", "/press/", "imageShow")):
            related.append(href.split("#")[0])
    return related


def _seed_pages(row: dict) -> list[str]:
    pages = []
    for key in ("reservation_url", "source_urls"):
        value = row.get(key) or ""
        for part in value.split("|"):
            url = part.strip()
            if url.startswith("http"):
                pages.append(url)
    first = pages[0] if pages else ""
    if "centrepompidou-hanwha.kr" in first:
        pages.extend(
            [
                "https://www.centrepompidou-hanwha.kr/exhibition/list",
                "https://www.centrepompidou-hanwha.kr/press/list",
            ]
        )
    try:
        from util.sources_featured import featured_pages_for

        pages.extend(featured_pages_for(row.get("title") or ""))
    except Exception:
        pass
    return pages


def _title_match(row: dict, url: str, caption: str) -> int:
    blob = f"{url} {caption}".lower()
    score = 0
    for token in _title_tokens(row.get("title") or ""):
        if token.lower() in blob:
            score += 36
    return score


def find_visual(row: dict) -> tuple[str, bytes | None]:
    if row.get("image_bytes"):
        return (row.get("image_url") or ""), row.get("image_bytes")
    tokens = _title_tokens(row.get("title") or "")
    pages: list[str] = []
    seen_pages: set[str] = set()
    for seed in _seed_pages(row):
        if seed not in seen_pages:
            pages.append(seed)
            seen_pages.add(seed)
    image_urls: list[tuple[str, str]] = []
    seen_images: set[str] = set()
    for page in pages[:8]:
        try:
            response = requests.get(page, timeout=12, headers=HEADERS)
            html = response.text
        except Exception:
            continue
        for image_url, caption in _extract_image_urls(page, html):
            if image_url not in seen_images:
                image_urls.append((image_url, caption))
                seen_images.add(image_url)
        for related in _related_pages(page, html, tokens):
            if related not in seen_pages and len(pages) < 10:
                if "/exhibition/detail" in related:
                    pages.insert(1, related)
                else:
                    pages.append(related)
                seen_pages.add(related)
    ranked = sorted(
        image_urls,
        key=lambda item: _url_score(item[0]) + _caption_score(item[1]) + _title_match(row, item[0], item[1]),
        reverse=True,
    )
    best: tuple[str, bytes, int] | None = None
    for image_url, caption in ranked[:16]:
        loaded = _download_picture(image_url)
        if not loaded:
            continue
        data, score = loaded
        score += _caption_score(caption)
        if best is None or score > best[2]:
            best = (image_url, data, score)
    if best:
        return best[0], best[1]
    return "", None


def _artist_queries(row: dict) -> list[str]:
    blob = " ".join(
        part
        for part in (
            row.get("title") or "",
            row.get("summary") or "",
            row.get("score_reason") or "",
            row.get("venue") or "",
        )
        if part
    )
    queries: list[str] = []
    lowered = blob.lower()
    for keys, extras in ARTIST_QUERIES:
        if any(key.lower() in lowered or key in blob for key in keys):
            queries.extend(extras)
    title = re.sub(r"[〈〉《》\(\)]", "", row.get("title") or "")
    name = re.split(r"[:：]", title, 1)[0].strip()
    if 2 <= len(name) <= 24 and "교육" not in name:
        queries.extend([f"{name} artwork", f"{name} painting", name])
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique[:6]


def _wiki_thumb(title: str) -> tuple[str, bytes] | None:
    from urllib.parse import quote

    for lang in ("en", "ko"):
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        try:
            data = requests.get(url, timeout=12, headers=WIKI_HEADERS).json()
        except Exception:
            continue
        thumb = (data.get("originalimage") or data.get("thumbnail") or {}).get("source") or ""
        if not thumb:
            continue
        loaded = _download_picture(thumb)
        if loaded:
            return thumb, loaded[0]
    return None


def _commons_image(query: str) -> tuple[str, bytes] | None:
    try:
        data = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            timeout=14,
            headers=WIKI_HEADERS,
            params={
                "action": "query",
                "format": "json",
                "origin": "*",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "iiurlwidth": 1200,
            },
        ).json()
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    ranked = sorted(
        pages.values(),
        key=lambda item: ((item.get("imageinfo") or [{}])[0].get("size") or 0),
        reverse=True,
    )
    for page in ranked:
        info = (page.get("imageinfo") or [{}])[0]
        mime = (info.get("mime") or "").lower()
        if "svg" in mime:
            continue
        url = info.get("thumburl") or info.get("url") or ""
        if any(hint in url.lower() for hint in ("logo", "icon", "map", "flag")):
            continue
        loaded = _download_picture(url)
        if loaded:
            return url, loaded[0]
    return None


def find_representative_art(row: dict) -> tuple[str, bytes | None]:
    if row.get("image_bytes"):
        return (row.get("image_url") or ""), row.get("image_bytes")
    blob = " ".join(
        part
        for part in (row.get("title") or "", row.get("summary") or "", row.get("score_reason") or "")
        if part
    )
    lowered = blob.lower()
    mapped: list[str] = []
    artwork_first = any(key.lower() in lowered or key in blob for key in ARTWORK_FIRST)
    for keys, extras in ARTIST_QUERIES:
        if any(key.lower() in lowered or key in blob for key in keys):
            mapped.extend(extras)
    seen: set[str] = set()

    def wiki_pages(pages: list[str]) -> tuple[str, bytes] | None:
        for query in pages:
            if query in seen:
                continue
            seen.add(query)
            found = _wiki_thumb(query)
            if found:
                LOGGER.info(f"[시각] 대표작: {(row.get('title') or '')[:30]} / {query}")
                return found
        return None

    if artwork_first:
        found = wiki_pages(mapped)
        if found:
            return found
    url, data = find_visual(row)
    if data:
        return url, data
    found = wiki_pages(mapped)
    if found:
        return found
    for query in _artist_queries(row):
        if query in seen:
            continue
        seen.add(query)
        found = _wiki_thumb(query)
        if found:
            LOGGER.info(f"[시각] 대표작 보강: {(row.get('title') or '')[:30]} / {query}")
            return found
    if (row.get("image_url") or "").startswith("http"):
        loaded = _download_picture(row["image_url"])
        if loaded:
            return row["image_url"], loaded[0]
    return "", None


def enrich_visuals(items: list[dict], budget_sec: int = 180) -> None:
    started = time.monotonic()
    for item in items:
        if time.monotonic() - started > budget_sec:
            LOGGER.info("[시각] 시간이 길어 나머지 사진 확인은 건너뛰고 메일·달력으로 갑니다.")
            break
        row = {
            "title": item.get("title") or "",
            "reservation_url": item.get("reservation_url") or item.get("source_url") or "",
            "source_urls": " | ".join(item.get("source_url_list") or [item.get("source_url") or ""]),
            "image_url": item.get("image_url") or "",
            "image_bytes": item.get("image_bytes"),
        }
        try:
            url, data = find_representative_art(row)
        except Exception as exc:
            item["has_visual"] = bool(item.get("image_url") or item.get("image_bytes"))
            LOGGER.info(f"[시각] 건너뜀: {(item.get('title') or '')[:40]} ({exc})")
            continue
        if data:
            item["image_url"] = url or item.get("image_url") or ""
            item["image_bytes"] = data
            item["has_visual"] = True
            LOGGER.info(f"[시각] 작품 사진 있음: {(item.get('title') or '')[:40]}")
        else:
            item["has_visual"] = False
            LOGGER.info(f"[시각] 작품 사진 없음: {(item.get('title') or '')[:40]}")


def collect_posters(rows: list[dict]) -> list[bytes | None]:
    posters: list[bytes | None] = []
    for row in rows:
        if row.get("image_bytes"):
            posters.append(row["image_bytes"])
            LOGGER.info(f"[메일] 전시 느낌의 작품 사진을 넣었습니다: {(row.get('title') or '')[:40]}")
            continue
        url, image_bytes = find_representative_art(row)
        if url:
            row["image_url"] = url
        posters.append(image_bytes)
        if image_bytes:
            LOGGER.info(f"[메일] 전시 느낌의 작품 사진을 넣었습니다: {(row.get('title') or '')[:40]}")
        else:
            LOGGER.info(f"[메일] 작품 사진이 없어 일정 그림을 씁니다: {(row.get('title') or '')[:40]}")
    return posters


PUBLIC_HOME = "https://yinxiakr-crypto.github.io/ownex/"


def _home_url() -> str:
    # Mail must never use ownex.localhost or a PC-only address.
    return PUBLIC_HOME


def _activity_counts() -> tuple[int, int]:
    family = ROOT / "data" / "family"
    reviews = 0
    visits = 0
    feels_path = family / "feels.json"
    if feels_path.exists():
        try:
            payload = json.loads(feels_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = []
        if isinstance(payload, list):
            reviews = len(payload)
    if family.exists():
        for path in family.glob("*.json"):
            if path.name in {"users.json", "feels.json"}:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            notes = payload.get("notes") if isinstance(payload, dict) else {}
            if not isinstance(notes, dict):
                continue
            count = sum(1 for note in notes.values() if isinstance(note, dict) and note.get("visited"))
            if count > visits:
                visits = count
    return visits, reviews


def _html_body(rows: list[dict], calendar_from: date | None, has_card: bool, heading: str = "오늘의 전시") -> str:
    blocks = []
    for index, row in enumerate(rows, start=1):
        url = row.get("reservation_url") or ""
        link = f'<p><a href="{url}">예약/안내 페이지</a></p>' if url else ""
        poster = f'<p><img src="cid:poster{index}" alt="전시 작품" style="max-width:100%;border-radius:8px;"></p>'
        blocks.append(
            f"""
            <div style="margin:0 0 28px 0;padding:0 0 16px 0;border-bottom:1px solid #e6d5b8;">
              <h2 style="margin:0 0 8px 0;font-size:18px;">{index}. {row.get('title') or ''}</h2>
              <p style="margin:0 0 6px 0;color:#555;">{row.get('venue') or ''} {row.get('venue_address') or ''}</p>
              <p style="margin:0 0 10px 0;color:#8a3b12;"><b>{_period(row, calendar_from)}</b></p>
              <p style="margin:0 0 6px 0;color:#666;font-size:13px;">고른 이유: {row.get('score_reason') or ''}</p>
              <p style="margin:0 0 10px 0;">{row.get('summary') or ''}</p>
              {poster}
              {link}
            </div>
            """
        )
    card = (
        '<p><img src="cid:schedulecard" alt="오늘 전시 일정표" style="max-width:100%;border-radius:8px;"></p>'
        if has_card
        else ""
    )
    visits, reviews = _activity_counts()
    home = _home_url()
    glance = f"""
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0 20px 0;">
        <tr>
          <td style="padding:10px 16px;background:#351e28;color:#f6efe6;border-radius:12px;text-align:center;">
            <div style="font-size:22px;font-weight:700;">{visits}</div>
            <div style="font-size:12px;">방문</div>
          </td>
          <td style="width:10px;"></td>
          <td style="padding:10px 16px;background:#351e28;color:#f6efe6;border-radius:12px;text-align:center;">
            <div style="font-size:22px;font-weight:700;">{reviews}</div>
            <div style="font-size:12px;">Review</div>
          </td>
          <td style="width:10px;"></td>
          <td style="background:#e24a1b;border-radius:12px;text-align:center;">
            <a href="{home}" target="_blank" style="display:block;padding:14px 18px;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;">오넥스 홈 · 앱 열기</a>
          </td>
        </tr>
      </table>
    """
    return f"""
    <div style="font-family:'Malgun Gothic',sans-serif;max-width:640px;margin:0 auto;color:#222;">
      <h1 style="font-size:22px;">{heading}</h1>
      <p>나만의 전시를 통해 다른 세상과 만나보세요.</p>
      {glance}
      {card}
      {''.join(blocks)}
      <p style="margin:24px 0 0 0;font-size:12px;color:#888;">오넥스에 들어가 ‘메일수신을 거부합니다’에 표시하면 더 이상 보내지 않습니다.</p>
    </div>
    """


def _smtp_account() -> tuple[str, str]:
    load_env_file()
    address = (os.getenv("GMAIL_ADDRESS") or "").strip()
    password = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    return address, password


def _send_built_message(message: MIMEMultipart, to_address: str, extra: list[str] | None = None) -> None:
    smtp_user, smtp_password = _smtp_account()
    envelope = [to_address] + [addr for addr in (extra or []) if addr and addr.lower() != to_address.lower()]
    if smtp_user and smtp_password:
        message["From"] = smtp_user
        last_error = None
        for attempt in range(3):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, envelope, message.as_bytes())
                return
            except Exception as exc:
                last_error = exc
        raise last_error
    if not can_send_gmail():
        raise RuntimeError("메일 보내기 방법이 아직 없습니다.")
    message["From"] = to_address
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    gmail_service().users().messages().send(userId="me", body={"raw": raw}).execute()


def send_exhibition_email(rows: list[dict], cfg, calendar_from: date | None = None) -> bool:
    mail_cfg = cfg["email"] if cfg.has_section("email") else None
    if mail_cfg and mail_cfg.get("enabled", "true").lower() != "true":
        return False
    if not rows:
        return False
    smtp_user, smtp_password = _smtp_account()
    if not (smtp_user and smtp_password) and not can_send_gmail():
        LOGGER.info("[메일] 지메일 앱 비밀번호가 없어 건너뜁니다.")
        return False
    try:
        owner = (mail_cfg.get("to", "") if mail_cfg else "").strip() or smtp_user or logged_in_email()
        today = date.today()
        groups = wanted_email_groups(owner, today)
        if not groups:
            LOGGER.info("[메일] 오늘 받을 사람이 없어 건너뜁니다.")
            return False
        posters = collect_posters(rows)
        home = _home_url()
        LOGGER.info(f"[메일] 홈 주소는 {home} 입니다.")
        sent_any = False
        for freq, recipients in groups.items():
            heading = mail_heading(freq)
            to_address = recipients[0]
            extra = recipients[1:]
            card = make_schedule_card(rows, calendar_from, heading)
            message = MIMEMultipart("related")
            message["To"] = to_address
            if extra:
                message["Bcc"] = ", ".join(extra)
            message["Subject"] = f"{heading} {today.isoformat()}"
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(f"{heading} {today.isoformat()}\n나만의 전시를 통해 다른 세상과 만나보세요.\n", "plain", "utf-8"))
            alt.attach(MIMEText(_html_body(rows, calendar_from, True, heading), "html", "utf-8"))
            message.attach(alt)
            card_part = MIMEImage(card, _subtype="jpeg")
            card_part.add_header("Content-ID", "<schedulecard>")
            card_part.add_header("Content-Disposition", "inline", filename="today-exhibitions.jpg")
            message.attach(card_part)
            for index, poster in enumerate(posters, start=1):
                payload = poster or make_schedule_card([rows[index - 1]], calendar_from, heading)
                image_part = MIMEImage(payload, _subtype="jpeg")
                image_part.add_header("Content-ID", f"<poster{index}>")
                safe_name = re.sub(r"[^\w가-힣]+", "_", (rows[index - 1].get("title") or "poster")[:40]) or "poster"
                image_part.add_header("Content-Disposition", "inline", filename=f"{safe_name}.png")
                message.attach(image_part)
            _send_built_message(message, to_address, extra)
            LOGGER.info(f"[메일] {heading} 목록 {len(rows)}개를 {len(recipients)}명에게 보냈습니다.")
            sent_any = True
        return sent_any
    except Exception as exc:
        LOGGER.info(f"[메일] 보내기 실패: {exc}")
        return False
