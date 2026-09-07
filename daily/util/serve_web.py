from __future__ import annotations

import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from util.family_accounts import (
    approve_user,
    enter,
    list_people,
    load_state,
    login,
    logout,
    merge_state,
    signup,
    state_id_for,
    user_from_token,
)
from util.visitors import bump_visitor, read_visitors
from util.mail_list import upsert_subscriber

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SHARED_PATH = WEB / "shared-state.json"
PORT = 8765
PRETTY_HOST = "ownex.localhost"


def _read_shared_state() -> dict:
    if not SHARED_PATH.exists():
        return {"feels": [], "at": ""}
    try:
        payload = json.loads(SHARED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"feels": [], "at": ""}
    if not isinstance(payload, dict):
        return {"feels": [], "at": ""}
    feels = payload.get("feels")
    return {
        "feels": feels if isinstance(feels, list) else [],
        "at": str(payload.get("at") or ""),
    }


def _write_shared_state(payload: dict) -> dict:
    incoming = payload.get("feels") if isinstance(payload.get("feels"), list) else []
    saved = merge_state(None, {"feels": incoming})
    pack = {"feels": saved.get("feels") or incoming, "at": str(payload.get("at") or "")}
    SHARED_PATH.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    return pack


def lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _cookie_token(header: str) -> str:
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == "ownex":
            return value.strip()
    return ""


class OwnexHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def _token(self) -> str:
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return _cookie_token(self.headers.get("Cookie") or "")

    def _user(self):
        return user_from_token(self._token())

    def _secure_cookie(self) -> bool:
        proto = (self.headers.get("X-Forwarded-Proto") or "").lower()
        host = (self.headers.get("Host") or "").lower()
        return proto == "https" or "trycloudflare.com" in host

    def _cookie(self, token: str, clear: bool = False) -> str:
        if clear:
            return "ownex=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
        flags = "Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax"
        if self._secure_cookie():
            flags += "; Secure"
        return f"ownex={token}; {flags}"

    def _json(self, payload: dict, status: int = 200, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("보낸 내용이 올바르지 않습니다.") from exc
        return data if isinstance(data, dict) else {}

    def _serve_data_js(self) -> None:
        raw = (WEB / "data.js").read_text(encoding="utf-8")
        text = raw.replace("window.OWNEX = ", "", 1).strip()
        if text.endswith(";"):
            text = text[:-1]
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            super().do_GET()
            return
        user = self._user()
        if user and not user.get("owner"):
            payload["google"] = {}
            payload["calendar"] = []
            payload["email"] = []
        body = ("window.OWNEX = " + json.dumps(payload, ensure_ascii=False) + ";").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/data.js":
            self._serve_data_js()
            return
        if path == "/api/family/me":
            self._json(self._user() or {"id": "", "name": "", "owner": False, "approved": False})
            return
        if path == "/api/family/people":
            user = self._user()
            if not (user and user.get("id")):
                self._json({"error": "목록을 볼 수 없습니다."}, 401)
                return
            self._json({"people": list_people()})
            return
        if path == "/api/family/state":
            self._json(load_state(state_id_for(self._user())))
            return
        if path == "/shared-state.json":
            self._json(_read_shared_state())
            return
        if path == "/api/visitors":
            self._json(read_visitors())
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/family/signup":
                body = self._read_json()
                user, token = signup(body.get("name", ""), body.get("pin", ""))
                self._json({**user, "token": token}, cookie=self._cookie(token))
                return
            if path == "/api/family/enter":
                body = self._read_json()
                user, token = enter(body.get("name", ""), body.get("pin", ""))
                self._json({**user, "token": token}, cookie=self._cookie(token))
                return
            if path == "/api/family/login":
                body = self._read_json()
                user, token = login(body.get("name", ""), body.get("pin", ""))
                self._json({**user, "token": token}, cookie=self._cookie(token))
                return
            if path == "/api/family/logout":
                logout(self._token())
                self._json({"ok": True}, cookie=self._cookie("", clear=True))
                return
            if path == "/api/family/state":
                saved = merge_state(state_id_for(self._user()), self._read_json())
                self._json(saved)
                return
            if path == "/api/visitors":
                self._json(bump_visitor())
                return
            if path == "/api/mail/subscribe":
                body = self._read_json()
                item = upsert_subscriber(body.get("email", ""), bool(body.get("want")), body.get("name", "") or "")
                if not item:
                    self._json({"error": "받을 이메일을 확인해 주세요."}, 400)
                    return
                self._json({"ok": True, "email": item.get("email"), "want": item.get("want")})
                return
            if path == "/api/family/approve":
                user = self._user()
                if not (user and user.get("owner")):
                    self._json({"error": "승인할 수 없습니다."}, 401)
                    return
                body = self._read_json()
                self._json(approve_user(user["id"], body.get("id", "")))
                return
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"error": "없는 주소입니다."}, 404)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/shared-state.json":
                self._json(_write_shared_state(self._read_json()))
                return
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"error": "없는 주소입니다."}, 404)


def make_server(bind: str, port: int) -> ThreadingHTTPServer | None:
    try:
        return ThreadingHTTPServer((bind, port), OwnexHandler)
    except OSError:
        return None


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    local_80 = make_server("127.0.0.1", 80)
    lan = make_server("0.0.0.0", PORT)
    if lan is None and local_80 is None:
        raise SystemExit("홈페이지 주소를 열 수 없습니다. 이미 켜져 있는지 보세요.")

    if local_80 is not None:
        pc_url = f"http://{PRETTY_HOST}/"
    elif lan is not None:
        pc_url = f"http://{PRETTY_HOST}:{PORT}/"
    else:
        pc_url = f"http://127.0.0.1:{PORT}/"

    phone = f"http://{lan_ip()}:{PORT}/"
    note = ROOT / "아이폰주소.txt"
    note.write_text(
        "OWNEX 주소\n"
        f"이 컴퓨터: {pc_url}\n"
        f"아이폰 사파리: {phone}\n"
        "아이폰과 이 컴퓨터가 같은 와이파이어야 합니다.\n"
        "가족 계정으로 들어가면 Review는 같이 보고, 칭찬 스티커는 각자 모입니다.\n"
        "달력은 첫 번째로 만든 이름만 봅니다.\n"
        "이 까만 창을 닫으면 주소도 닫힙니다.\n",
        encoding="utf-8",
    )
    (ROOT / "ownex-url.txt").write_text(pc_url, encoding="ascii")

    print("")
    print("OWNEX 주소")
    print(f"이 컴퓨터     {pc_url}")
    print(f"아이폰 사파리 {phone}")
    print("아이폰과 이 컴퓨터가 같은 와이파이어야 합니다.")
    print("가족 계정으로 들어가면 Review는 같이 보고, 칭찬 스티커는 각자 모입니다.")
    print("달력은 첫 번째로 만든 이름만 봅니다.")
    print("이 창을 닫으면 주소도 닫힙니다.")
    print("")

    servers = [s for s in (local_80, lan) if s is not None]
    for extra in servers[1:]:
        threading.Thread(target=extra.serve_forever, daemon=True).start()
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
