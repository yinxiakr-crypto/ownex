from __future__ import annotations

import imaplib
import json
import os
import re
from datetime import date
from email import message_from_bytes
from email.header import decode_header
from pathlib import Path

from util.config_loader import load_env_file
from util.logger import get_logger

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "family"
PATH = DIR / "mail_subscribers.json"
WEB_PATH = ROOT / "web" / "mail-subscribers.json"
PAGES_PATH = ROOT / "data" / "ownex-pages" / "mail-subscribers.json"
LOGGER = get_logger()
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def _empty() -> dict:
    return {"subscribers": [], "seen": []}


def _read(path: Path) -> dict:
    if not path.exists():
        return _empty()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if isinstance(payload, list):
        return {"subscribers": payload, "seen": []}
    if not isinstance(payload, dict):
        return _empty()
    subs = payload.get("subscribers")
    seen = payload.get("seen")
    return {
        "subscribers": subs if isinstance(subs, list) else [],
        "seen": seen if isinstance(seen, list) else [],
    }


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mail_list() -> dict:
    bag = _empty()
    seen_email = {}
    seen_ids = set()
    for path in (PATH, WEB_PATH, PAGES_PATH):
        incoming = _read(path)
        for item in incoming["subscribers"]:
            if not isinstance(item, dict):
                continue
            email = clean_email(item.get("email") or "")
            if not email:
                continue
            old = seen_email.get(email) or {}
            merged = dict(old)
            merged.update(item)
            merged["email"] = email
            if "want" in item:
                merged["want"] = bool(item.get("want"))
            seen_email[email] = merged
        for mid in incoming["seen"]:
            if mid:
                seen_ids.add(str(mid))
    bag["subscribers"] = list(seen_email.values())
    bag["seen"] = sorted(seen_ids)
    return bag


def save_mail_list(payload: dict) -> None:
    data = {
        "subscribers": payload.get("subscribers") or [],
        "seen": payload.get("seen") or [],
    }
    _write(PATH, data)
    _write(WEB_PATH, data)
    try:
        _write(PAGES_PATH, data)
    except OSError:
        pass


def clean_email(value: str) -> str:
    text = str(value or "").strip().lower()
    if not EMAIL_RE.fullmatch(text):
        found = EMAIL_RE.search(text)
        text = found.group(0).lower() if found else ""
    return text


def upsert_subscriber(email: str, want: bool, name: str = "") -> dict | None:
    addr = clean_email(email)
    if not addr:
        return None
    data = load_mail_list()
    found = None
    for item in data["subscribers"]:
        if clean_email(item.get("email") or "") == addr:
            found = item
            break
    if not found:
        found = {"email": addr, "name": "", "want": True, "at": ""}
        data["subscribers"].append(found)
    found["email"] = addr
    found["want"] = bool(want)
    if name:
        found["name"] = str(name).strip()
    found["at"] = date.today().isoformat()
    save_mail_list(data)
    return found


def wanted_emails(owner: str = "") -> list[str]:
    owner_addr = clean_email(owner)
    out = []
    seen = set()
    if owner_addr:
        out.append(owner_addr)
        seen.add(owner_addr)
    for item in load_mail_list().get("subscribers") or []:
        if not item.get("want"):
            continue
        addr = clean_email(item.get("email") or "")
        if not addr or addr in seen:
            continue
        seen.add(addr)
        out.append(addr)
    return out


def _decode_header(value: str) -> str:
    parts = []
    for chunk, enc in decode_header(value or ""):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts)


def _body_text(msg) -> str:
    if msg.is_multipart():
        bits = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in {"text/plain", "text/html"}:
                raw = part.get_payload(decode=True) or b""
                bits.append(raw.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(bits)
    raw = msg.get_payload(decode=True) or b""
    return raw.decode(msg.get_content_charset() or "utf-8", errors="replace")


def ingest_mail_requests() -> int:
    load_env_file()
    user = (os.getenv("GMAIL_ADDRESS") or "").strip()
    password = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not (user and password):
        return 0
    added = 0
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as box:
            box.login(user, password)
            box.select("INBOX")
            try:
                status, data = box.search("UTF-8", '(OR SUBJECT "오넥스 메일" SUBJECT "OWNEX mail")')
            except Exception:
                status, data = box.search(None, '(OR SUBJECT "OWNEX mail" SUBJECT "ownex mail")')
            if status != "OK":
                return 0
            ids = (data[0] or b"").split()
            store = load_mail_list()
            seen = set(store.get("seen") or [])
            for raw_id in ids[-40:]:
                mid = raw_id.decode("ascii", errors="ignore")
                if mid in seen:
                    continue
                status, fetched = box.fetch(raw_id, "(RFC822)")
                if status != "OK" or not fetched:
                    continue
                payload = b""
                for item in fetched:
                    if isinstance(item, tuple) and len(item) >= 2:
                        payload = item[1]
                        break
                if not payload:
                    continue
                msg = message_from_bytes(payload)
                subject = _decode_header(msg.get("Subject") or "")
                blob = subject + "\n" + _body_text(msg)
                want = True
                if re.search(r"거부|UNSUB|WANT[_\s=:]*NO|\bno\b", blob, re.I):
                    want = False
                if re.search(r"신청|WANT[_\s=:]*YES|\byes\b", blob, re.I):
                    want = True
                addr = ""
                mail_line = re.search(r"email[:\s]+([^\s<]+@[^\s>]+)", blob, re.I)
                if mail_line:
                    addr = clean_email(mail_line.group(1))
                if not addr:
                    addr = clean_email(blob)
                if addr and addr != clean_email(user):
                    upsert_subscriber(addr, want)
                    added += 1
                seen.add(mid)
            store = load_mail_list()
            store["seen"] = sorted(seen)
            save_mail_list(store)
    except Exception as exc:
        LOGGER.info(f"[메일] 신청 편지함을 읽지 못했습니다: {exc}")
        return 0
    if added:
        LOGGER.info(f"[메일] 신청/거부 {added}건을 목록에 반영했습니다.")
    return added
