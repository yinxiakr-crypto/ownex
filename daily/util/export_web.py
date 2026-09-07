from __future__ import annotations

import json
import os
from pathlib import Path

from util.config_loader import load_config, load_env_file
from util.google_calendar import calendar_for_web
from util.logger import get_logger
from util.storage_csv import FIELDS, load_all_rows
from util.mail_list import load_mail_list, save_mail_list
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
    for row in load_all_rows():
        item = dict(row)
        item["poster"] = ensure_poster(item, fetch_missing=fetch_missing, force=force_posters)
        exhibitions.append(item)
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