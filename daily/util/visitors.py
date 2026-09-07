from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "visitors.json"
WEB_PATH = ROOT / "web" / "visitors.json"
LOCK = threading.Lock()


def _empty() -> dict:
    return {"total": 0, "days": {}}


def _read() -> dict:
    if not PATH.exists():
        return _empty()
    try:
        payload = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(payload, dict):
        return _empty()
    total = payload.get("total")
    days = payload.get("days")
    return {
        "total": int(total) if isinstance(total, int) else 0,
        "days": days if isinstance(days, dict) else {},
    }


def _write(payload: dict) -> dict:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    PATH.write_text(text, encoding="utf-8")
    WEB_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_PATH.write_text(text, encoding="utf-8")
    return payload


def read_visitors() -> dict:
    with LOCK:
        data = _read()
        return {"total": data["total"], "today": int(data["days"].get(date.today().isoformat(), 0) or 0)}


def bump_visitor() -> dict:
    with LOCK:
        data = _read()
        today = date.today().isoformat()
        data["total"] = int(data.get("total") or 0) + 1
        days = data.setdefault("days", {})
        days[today] = int(days.get(today) or 0) + 1
        _write(data)
        return {"total": data["total"], "today": days[today]}
