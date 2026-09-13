from __future__ import annotations

import json
import os
from pathlib import Path

from util.config_loader import load_config, load_env_file
from util.google_calendar import calendar_for_web
from util.logger import get_logger
from util.storage_csv import FIELDS, load_all_rows
from util.mail_list import load_mail_list, save_mail_list
from util.email_report import _side_program
from util.show_images import reset_used_images
from util.web_posters import ensure_poster

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web" / "data.js"
LOGGER = get_logger()


def load_saved_state() -> dict:
    family = ROOT / "data" / "family"
    notes: dict = {}
    feels: list = []
    feels_path = family / "feels.json"
    if feels_path.exists():
        try:
            payload = json.loads(feels_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = []
        if isinstance(payload, list):
            feels = payload
    if family.exists():
        for path in family.glob("*.json"):
            if path.name in {"users.json", "feels.json"}:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            incoming = payload.get("notes") if isinstance(payload, dict) else {}
            if not isinstance(incoming, dict):
                continue
            for key, note in incoming.items():
                if not isinstance(note, dict):
                    continue
                old = notes.get(key) if isinstance(notes.get(key), dict) else {}
                merged = dict(old)
                merged.update(note)
                merged["visited"] = bool(old.get("visited")) or bool(note.get("visited"))
                notes[key] = merged
    return {"rev": "visits-20260907", "notes": notes, "feels": feels}


def _slim(row: dict) -> dict:
    return {field: (row.get(field) or "") for field in FIELDS}


def _existing_art_flags() -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for path in (WEB_DATA, ROOT / "data" / "ownex-pages" / "data.js"):
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8").replace("window.OWNEX = ", "", 1).strip()
        if raw.endswith(";"):
            raw = raw[:-1]
        try:
            shows = json.loads(raw).get("exhibitions") or []
        except Exception:
            continue
        for row in shows:
            title = (row.get("title") or "").strip()
            if title and "has_art" in row:
                flags[title] = bool(row.get("has_art"))
    return flags


def _existing_google() -> dict:
    if not WEB_DATA.exists():
        return {}
    raw = WEB_DATA.read_text(encoding="utf-8").replace("window.OWNEX = ", "", 1).strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    try:
        return json.loads(raw).get("google") or {}
    except Exception:
        return {}


def write_web_data(
    email_rows: list[dict] | None = None,
    calendar_rows: list[dict] | None = None,
    refresh_google: bool = True,
    fetch_missing: bool = True,
    force_posters: bool = False,
) -> Path:
    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    load_env_file()
    calendar_name = "Ownex"
    try:
        cfg = load_config()
        if cfg.has_section("google_calendar"):
            calendar_name = cfg["google_calendar"].get("calendar_name", "Ownex") or "Ownex"
    except Exception:
        calendar_name = "Ownex"
    exhibitions = []
    reset_used_images()
    rows = list(load_all_rows())

    def _art_order(row: dict) -> tuple[int, str]:
        title = row.get("title") or ""
        if _side_program(title):
            return (2, title)
        if title.startswith("큐비스트:") or title.startswith("건축투어"):
            return (0, title)
        return (1, title)

    art_flags = _existing_art_flags()
    for row in sorted(rows, key=_art_order):
        item = dict(row)
        item["poster"] = ensure_poster(item, fetch_missing=fetch_missing, force=force_posters)
        if "has_art" not in item:
            item["has_art"] = art_flags.get(item.get("title") or "", bool(item.get("image_url")))
        exhibitions.append(item)
    exhibitions.sort(key=lambda item: (item.get("start_date") or "", item.get("title") or ""), reverse=True)
    payload = {
        "exhibitions": exhibitions,
        "email": [_slim(row) for row in (email_rows or [])],
        "calendar": [_slim(row) for row in (calendar_rows or [])],
        "google": calendar_for_web(calendar_name) if refresh_google else _existing_google(),
        "mail": {
            "notify": (os.getenv("GMAIL_ADDRESS") or "").strip(),
        },
        "saved": load_saved_state(),
    }
    WEB_DATA.write_text(
        "window.OWNEX = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    LOGGER.info(f"[홈] {len(payload['exhibitions'])}건을 web/data.js 에 넣었습니다.")
    try:
        save_mail_list(load_mail_list())
    except OSError:
        pass
    return WEB_DATA