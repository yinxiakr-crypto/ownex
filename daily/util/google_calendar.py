from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote

from util.logger import get_logger
from util.normalize import clip_calendar_span, from_iso

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = ROOT / "data" / "google_credentials.json"
TOKEN_PATH = ROOT / "data" / "google_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
SOURCE_KEY = "exhibition-local"
LOGGER = get_logger()


def is_connected() -> bool:
    return CREDENTIALS_PATH.exists() and TOKEN_PATH.exists()


def _google_modules():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    return Request, Credentials, InstalledAppFlow, build


def _has_scopes(creds, needed: list[str]) -> bool:
    have = set(creds.scopes or [])
    return set(needed).issubset(have)


def _token_file_scopes() -> set[str]:
    import json

    if not TOKEN_PATH.exists():
        return set()
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return set(data.get("scopes") or [])


def _read_creds():
    Request, Credentials, InstalledAppFlow, build = _google_modules()
    if not TOKEN_PATH.exists():
        return None
    return Credentials.from_authorized_user_file(str(TOKEN_PATH))


def connect() -> None:
    if set(SCOPES).issubset(_token_file_scopes()):
        creds = _usable_creds(need=SCOPES, interactive=False)
        if creds:
            return
    _login_interactive()


def _save_creds(creds) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def _refresh_creds(creds):
    Request, Credentials, InstalledAppFlow, build = _google_modules()
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
    return creds


def _login_interactive():
    Request, Credentials, InstalledAppFlow, build = _google_modules()
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError("구글 연결 파일이 없습니다.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    _save_creds(creds)
    return creds


def _usable_creds(*, need: list[str] | None = None, interactive: bool = False):
    creds = _read_creds()
    if creds:
        try:
            creds = _refresh_creds(creds)
        except Exception:
            creds = None
    needed = need or ["https://www.googleapis.com/auth/calendar"]
    if creds and creds.valid and _has_scopes(creds, needed):
        return creds
    if interactive:
        return _login_interactive()
    return creds if creds and creds.valid else None


def can_send_gmail() -> bool:
    creds = _read_creds()
    if not creds:
        return False
    try:
        creds = _refresh_creds(creds)
    except Exception:
        return False
    return GMAIL_SEND in _token_file_scopes() and bool(creds and creds.valid)


def _service():
    Request, Credentials, InstalledAppFlow, build = _google_modules()
    creds = _usable_creds(need=["https://www.googleapis.com/auth/calendar"], interactive=False)
    if not creds:
        raise FileNotFoundError("구글 연결 파일이 없습니다.")
    return build("calendar", "v3", credentials=creds)


def gmail_service():
    Request, Credentials, InstalledAppFlow, build = _google_modules()
    creds = _usable_creds(need=[GMAIL_SEND], interactive=False)
    if not creds or not _has_scopes(creds, [GMAIL_SEND]):
        raise RuntimeError("메일 보내기 권한이 없습니다.")
    return build("gmail", "v1", credentials=creds)


def logged_in_email() -> str:
    try:
        primary = _service().calendars().get(calendarId="primary").execute()
        cal_id = primary.get("id") or ""
        if "@" in cal_id:
            return cal_id
    except Exception:
        return ""
    return ""


OLD_CALENDAR_NAMES = ("전시(자동)",)


def _list_calendars(service) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        result = service.calendarList().list(pageToken=page_token).execute()
        items.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return items


def _ensure_calendar(service, calendar_name: str) -> str:
    calendars = _list_calendars(service)
    for item in calendars:
        if item.get("summary") == calendar_name:
            return item["id"]
    for item in calendars:
        if item.get("summary") in OLD_CALENDAR_NAMES:
            calendar_id = item["id"]
            service.calendars().patch(
                calendarId=calendar_id,
                body={"summary": calendar_name},
            ).execute()
            LOGGER.info(f"[달력] 달력 이름을 '{item.get('summary')}'에서 '{calendar_name}'으로 바꿨습니다.")
            return calendar_id
    created = service.calendars().insert(
        body={"summary": calendar_name, "timeZone": "Asia/Seoul"}
    ).execute()
    return created["id"]


def _all_events(service, calendar_id: str) -> list[dict]:
    events: list[dict] = []
    page_token = None
    while True:
        result = service.events().list(
            calendarId=calendar_id,
            pageToken=page_token,
            maxResults=100,
            singleEvents=True,
        ).execute()
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return events


def _managed_events(service, calendar_id: str) -> list[dict]:
    events: list[dict] = []
    page_token = None
    while True:
        result = service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty=f"source={SOURCE_KEY}",
            pageToken=page_token,
            maxResults=100,
        ).execute()
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return events


def _ensure_public_reader(service, calendar_id: str) -> None:
    rules = service.acl().list(calendarId=calendar_id).execute().get("items", [])
    if any(
        rule.get("scope", {}).get("type") == "default" and rule.get("role") in ("reader", "writer", "owner")
        for rule in rules
    ):
        return
    service.acl().insert(
        calendarId=calendar_id,
        body={"role": "reader", "scope": {"type": "default"}},
    ).execute()
    LOGGER.info("[달력] 홈페이지에 보이도록 Ownex 달력 제목을 읽기 공개로 두었습니다.")


def calendar_for_web(calendar_name: str = "Ownex") -> dict:
    empty = {
        "connected": False,
        "name": calendar_name,
        "events": [],
        "embed_src": "",
        "open_url": "https://calendar.google.com",
    }
    if not is_connected():
        return empty
    try:
        service = _service()
        calendar_id = _ensure_calendar(service, calendar_name)
        try:
            _ensure_public_reader(service, calendar_id)
        except Exception as exc:
            LOGGER.info(f"[달력] 홈 공개 설정을 건너뜁니다: {exc}")
        events = []
        for item in _all_events(service, calendar_id):
            start = (item.get("start") or {}).get("date") or ((item.get("start") or {}).get("dateTime") or "")[:10]
            end = (item.get("end") or {}).get("date") or ((item.get("end") or {}).get("dateTime") or "")[:10]
            events.append(
                {
                    "title": item.get("summary") or "",
                    "start": start,
                    "end": end,
                    "location": item.get("location") or "",
                    "html_link": item.get("htmlLink") or "",
                }
            )
        events.sort(key=lambda row: row.get("start") or "")
        src = quote(calendar_id, safe="@.")
        return {
            "connected": True,
            "name": calendar_name,
            "events": events,
            "embed_src": (
                f"https://calendar.google.com/calendar/embed?src={src}"
                "&ctz=Asia/Seoul&mode=MONTH&showPrint=0&showTz=0&showCalendars=0"
                "&bgcolor=%23D7EFFF"
            ),
            "open_url": f"https://calendar.google.com/calendar/u/0/r?cid={src}",
        }
    except Exception as exc:
        LOGGER.info(f"[홈] 구글 달력을 읽지 못했습니다: {exc}")
        return empty


def sync_events(
    rows: list[dict],
    calendar_name: str = "Ownex",
    calendar_from: date | None = None,
    today: date | None = None,
) -> int:
    if not is_connected():
        LOGGER.info("[달력] 구글 캘린더가 아직 연결되지 않아 건너뜁니다.")
        return 0
    today = today or date.today()
    clip_from = today
    if calendar_from and calendar_from > today:
        clip_from = calendar_from
    dated = []
    skipped_ended = 0
    for row in rows:
        show_end = from_iso(row.get("end_date") or "") or from_iso(row.get("start_date") or "")
        if show_end and show_end < today:
            skipped_ended += 1
            continue
        start, end = clip_calendar_span(
            from_iso(row.get("start_date") or ""),
            from_iso(row.get("end_date") or ""),
            clip_from,
        )
        if not start or not end:
            continue
        dated.append((row, start, end))
    try:
        service = _service()
        calendar_id = _ensure_calendar(service, calendar_name)
        old_events = _all_events(service, calendar_id)
        for event in old_events:
            service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
        for row, start, end in dated:
            end_exclusive = date.fromordinal(end.toordinal() + 1)
            service.events().insert(
                calendarId=calendar_id,
                body={
                    "summary": row.get("title") or "",
                    "location": f"{row.get('venue') or ''} {row.get('venue_address') or ''}".strip(),
                    "description": f"{row.get('summary') or ''}\n{row.get('reservation_url') or ''}".strip(),
                    "start": {"date": start.isoformat()},
                    "end": {"date": end_exclusive.isoformat()},
                    "extendedProperties": {"private": {"source": SOURCE_KEY}},
                },
            ).execute()
        LOGGER.info(
            f"[달력] 구글 캘린더 '{calendar_name}'에 {len(dated)}건을 올렸습니다. "
            f"이전 일정 {len(old_events)}건은 지웠고, 끝난 전시 {skipped_ended}건은 넣지 않았습니다."
        )
        return len(dated)
    except Exception as exc:
        LOGGER.info(f"[달력] 구글 캘린더 올리기 실패: {exc}")
        return 0
