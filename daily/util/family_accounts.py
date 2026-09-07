from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "family"
USERS_PATH = DIR / "users.json"
FEELS_PATH = DIR / "feels.json"
OWNER_STATE_ID = "owner"
LOCK = threading.Lock()
SESSION_DAYS = 30


def _now() -> float:
    return time.time()


def _empty() -> dict:
    return {"users": [], "sessions": {}}


def _read() -> dict:
    if not USERS_PATH.exists():
        return _empty()
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    data.setdefault("users", [])
    data.setdefault("sessions", {})
    return data


def _write(data: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    USERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return payload


def _write_json(path: Path, payload) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def _clean_name(name: str) -> str:
    cleaned = " ".join(str(name or "").split())
    if "@" in cleaned:
        cleaned = cleaned.lower()
    if not 1 <= len(cleaned) <= 64:
        raise ValueError("이름 또는 이메일은 1~64자로 해 주세요.")
    if any(ch in cleaned for ch in '/\\:*?"<>|'):
        raise ValueError("이름에 쓸 수 없는 글자가 있습니다.")
    return cleaned


def _clean_pin(pin: str) -> str:
    value = str(pin or "")
    if len(value) < 4:
        raise ValueError("비밀번호는 4자 이상으로 해 주세요.")
    if len(value) > 32:
        raise ValueError("비밀번호가 너무 깁니다.")
    return value


def _public(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "owner": bool(user.get("owner")),
        "approved": bool(user.get("approved", user.get("owner"))),
    }


def _state_path(user_id: str) -> Path:
    return DIR / f"{user_id}.json"


def _prune(data: dict) -> None:
    cutoff = _now() - SESSION_DAYS * 24 * 3600
    data["sessions"] = {
        token: info
        for token, info in data.get("sessions", {}).items()
        if info.get("exp", 0) >= cutoff
    }


def _find_user(data: dict, user_id: str) -> dict | None:
    for user in data["users"]:
        if user.get("id") == user_id:
            return user
    return None


def _find_by_name(data: dict, name: str) -> dict | None:
    for user in data["users"]:
        if user.get("name") == name:
            return user
    return None


def _new_session(data: dict, user_id: str) -> str:
    token = secrets.token_hex(16)
    data["sessions"][token] = {
        "user_id": user_id,
        "exp": _now() + SESSION_DAYS * 24 * 3600,
    }
    return token


def _feel_key(item: dict) -> tuple:
    return (
        item.get("id"),
        item.get("title"),
        item.get("body"),
        item.get("at"),
        item.get("by"),
    )


def _union_feels(current: list, incoming: list) -> list:
    feels = [item for item in current if isinstance(item, dict)]
    seen = {_feel_key(item) for item in feels}
    for item in incoming:
        if not isinstance(item, dict):
            continue
        key = _feel_key(item)
        if key in seen:
            continue
        feels.append(item)
        seen.add(key)
    return feels


def _load_notes_file(user_id: str) -> dict:
    payload = _read_json(_state_path(user_id), {})
    if not isinstance(payload, dict):
        return {}
    notes = payload.get("notes")
    return notes if isinstance(notes, dict) else {}


def _save_notes_file(user_id: str, notes: dict) -> dict:
    bundle = {"notes": notes if isinstance(notes, dict) else {}}
    _write_json(_state_path(user_id), bundle)
    return bundle["notes"]


def _load_feels_file() -> list:
    payload = _read_json(FEELS_PATH, [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        feels = payload.get("feels")
        return feels if isinstance(feels, list) else []
    return []


def _save_feels_file(feels: list) -> list:
    clean = [item for item in feels if isinstance(item, dict)]
    _write_json(FEELS_PATH, clean)
    return clean


def _ensure_migrated_unlocked(data: dict) -> None:
    feels = _load_feels_file()
    changed = False
    if DIR.exists():
        for path in DIR.glob("*.json"):
            if path.name in {"users.json", "feels.json"}:
                continue
            payload = _read_json(path, {})
            if not isinstance(payload, dict):
                continue
            extra = payload.get("feels")
            if isinstance(extra, list) and extra:
                feels = _union_feels(feels, extra)
                notes = payload.get("notes") if isinstance(payload.get("notes"), dict) else {}
                _write_json(path, {"notes": notes})
                changed = True
    if changed or not FEELS_PATH.exists():
        _save_feels_file(feels)

    owner = next((user for user in data["users"] if user.get("owner")), None)
    if not owner:
        return
    legacy = _load_notes_file(OWNER_STATE_ID)
    current = _load_notes_file(owner["id"])
    if legacy and not current:
        _save_notes_file(owner["id"], legacy)


def user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    with LOCK:
        data = _read()
        _prune(data)
        info = data["sessions"].get(token)
        if not info:
            return None
        user = _find_user(data, info.get("user_id", ""))
        if not user:
            return None
        return _public(user)


def signup(name: str, pin: str) -> tuple[dict, str]:
    cleaned = _clean_name(name)
    secret = _clean_pin(pin)
    with LOCK:
        data = _read()
        _prune(data)
        _ensure_migrated_unlocked(data)
        if _find_by_name(data, cleaned):
            raise ValueError("이미 있는 이름입니다.")
        salt = secrets.token_hex(8)
        is_owner = not any(item.get("owner") for item in data["users"])
        user = {
            "id": "u" + secrets.token_hex(4),
            "name": cleaned,
            "salt": salt,
            "pin_hash": _hash_pin(secret, salt),
            "owner": is_owner,
            "approved": True,
        }
        data["users"].append(user)
        token = _new_session(data, user["id"])
        _write(data)
        notes = _load_notes_file(OWNER_STATE_ID) if is_owner else {}
        if not _state_path(user["id"]).exists():
            _save_notes_file(user["id"], notes if isinstance(notes, dict) else {})
        return _public(user), token


def enter(name: str, pin: str) -> tuple[dict, str]:
    cleaned = _clean_name(name)
    with LOCK:
        data = _read()
        exists = bool(_find_by_name(data, cleaned))
    if exists:
        return login(name, pin)
    return signup(name, pin)


def login(name: str, pin: str) -> tuple[dict, str]:
    cleaned = _clean_name(name)
    secret = _clean_pin(pin)
    with LOCK:
        data = _read()
        _prune(data)
        user = _find_by_name(data, cleaned)
        if not user or user.get("pin_hash") != _hash_pin(secret, user.get("salt", "")):
            raise ValueError("이름 또는 비밀번호가 다릅니다.")
        if not user.get("approved", user.get("owner")):
            raise ValueError("아직 승인을 기다리고 있습니다.")
        token = _new_session(data, user["id"])
        _write(data)
        _ensure_migrated_unlocked(data)
        return _public(user), token


def logout(token: str | None) -> None:
    if not token:
        return
    with LOCK:
        data = _read()
        data["sessions"].pop(token, None)
        _write(data)


def load_feels() -> list:
    with LOCK:
        data = _read()
        _ensure_migrated_unlocked(data)
        return _load_feels_file()


def load_state(user_id: str | None) -> dict:
    with LOCK:
        data = _read()
        _ensure_migrated_unlocked(data)
        notes = _load_notes_file(user_id) if user_id else {}
        return {"notes": notes, "feels": _load_feels_file()}


def list_people() -> list[dict]:
    with LOCK:
        data = _read()
        return [_public(user) for user in data["users"]]


def approve_user(owner_id: str, target_id: str) -> dict:
    with LOCK:
        data = _read()
        owner = _find_user(data, owner_id)
        if not owner or not owner.get("owner"):
            raise ValueError("승인할 수 있는 사람이 아닙니다.")
        user = _find_user(data, target_id)
        if not user:
            raise ValueError("그 이름을 찾을 수 없습니다.")
        user["approved"] = True
        _write(data)
        return _public(user)


def state_id_for(user: dict | None) -> str | None:
    if user and user.get("id") and user.get("approved", user.get("owner")):
        return user["id"]
    return None


def save_state(user_id: str | None, payload: dict) -> dict:
    notes_in = payload.get("notes") if isinstance(payload.get("notes"), dict) else {}
    feels_in = payload.get("feels") if isinstance(payload.get("feels"), list) else []
    with LOCK:
        data = _read()
        _ensure_migrated_unlocked(data)
        feels = _save_feels_file(_union_feels(_load_feels_file(), feels_in))
        notes = {}
        if user_id:
            notes = _save_notes_file(user_id, notes_in)
        return {"notes": notes, "feels": feels}


def _merge_notes_unlocked(user_id: str, incoming_notes: dict) -> dict:
    notes = dict(_load_notes_file(user_id))
    incoming = incoming_notes if isinstance(incoming_notes, dict) else {}
    for key, note in incoming.items():
        if not isinstance(note, dict):
            continue
        old = notes.get(key) if isinstance(notes.get(key), dict) else {}
        merged = dict(old)
        merged.update(note)
        merged["visited"] = bool(note.get("visited")) if "visited" in note else bool(old.get("visited"))
        if not merged.get("at"):
            merged["at"] = old.get("at") or note.get("at") or ""
        notes[key] = merged
    return _save_notes_file(user_id, notes)


def merge_state(user_id: str | None, payload: dict) -> dict:
    incoming_notes = payload.get("notes") if isinstance(payload.get("notes"), dict) else {}
    incoming_feels = payload.get("feels") if isinstance(payload.get("feels"), list) else []
    with LOCK:
        data = _read()
        _ensure_migrated_unlocked(data)
        feels = _save_feels_file(_union_feels(_load_feels_file(), incoming_feels))
        notes = {}
        if user_id:
            notes = _merge_notes_unlocked(user_id, incoming_notes)
        return {"notes": notes, "feels": feels}
