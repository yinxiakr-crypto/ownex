from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from util.logger import get_logger

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "exhibitions.csv"
FIELDS = [
    "collected_date",
    "title",
    "venue",
    "venue_address",
    "region_tag",
    "reservation_url",
    "start_date",
    "end_date",
    "reservation_open_date",
    "summary",
    "image_url",
    "source_urls",
    "score_reason",
]

LOGGER = get_logger()


def yearly_csv_path(year: int) -> Path:
    return DATA_DIR / f"exhibitions_{year}.csv"


def _key(row: dict) -> tuple[str, str, str, str]:
    return (
        (row.get("title") or "").strip(),
        (row.get("venue") or "").strip(),
        (row.get("start_date") or "").strip(),
        (row.get("end_date") or "").strip(),
    )


def _year_of(row: dict, fallback: int) -> int:
    raw = (row.get("collected_date") or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return fallback


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _append_to(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def _rewrite(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _iter_csv_paths() -> list[Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    seen: set[Path] = set()
    for path in [CSV_PATH, *sorted(DATA_DIR.glob("exhibitions_*.csv"))]:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(path)
    return paths


def load_existing_keys() -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for path in _iter_csv_paths():
        for row in _read_rows(path):
            keys.add(_key(row))
    return keys


def load_all_rows() -> list[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    rows: list[dict] = []
    for path in _iter_csv_paths():
        for row in _read_rows(path):
            item_key = _key(row)
            if item_key in seen:
                continue
            seen.add(item_key)
            rows.append({field: row.get(field) or "" for field in FIELDS})
    rows.sort(key=lambda item: (item.get("start_date") or "", item.get("title") or ""), reverse=True)
    return rows


def _archive_into_year_files(today: date) -> None:
    """Copy rows into exhibitions_YYYY.csv. Year files are never deleted."""
    grouped: dict[int, list[dict]] = defaultdict(list)
    for path in _iter_csv_paths():
        for row in _read_rows(path):
            grouped[_year_of(row, today.year)].append(row)

    for year, rows in grouped.items():
        path = yearly_csv_path(year)
        known = {_key(row) for row in _read_rows(path)}
        fresh = []
        seen = set(known)
        for row in rows:
            item_key = _key(row)
            if item_key in seen:
                continue
            seen.add(item_key)
            fresh.append(row)
        if fresh:
            _append_to(path, fresh)
            LOGGER.info(f"[저장] {year}년 보관 파일 {path.name}에 {len(fresh)}건을 모았습니다.")


def _keep_current_file_to_this_year(today: date) -> None:
    """exhibitions.csv holds this year's daily log. Older years stay in year files only."""
    if not CSV_PATH.exists():
        return
    rows = _read_rows(CSV_PATH)
    if not rows:
        return
    this_year = [row for row in rows if _year_of(row, today.year) == today.year]
    older = [row for row in rows if _year_of(row, today.year) != today.year]
    if not older:
        return
    years = sorted({_year_of(row, today.year) for row in older})
    _rewrite(CSV_PATH, this_year)
    LOGGER.info(
        f"[저장] {', '.join(str(year) for year in years)}년 기록은 연도 파일에 남겨 두고, "
        f"{CSV_PATH.name}은 {today.year}년만 이어서 쌓습니다."
    )


def _backfill_current_from_year_file(today: date) -> None:
    yearly = yearly_csv_path(today.year)
    if not yearly.exists():
        return
    known = {_key(row) for row in _read_rows(CSV_PATH)}
    missing = [row for row in _read_rows(yearly) if _key(row) not in known]
    if not missing:
        return
    try:
        _append_to(CSV_PATH, missing)
        LOGGER.info(f"[저장] 올해 표에 빠졌던 {len(missing)}건을 다시 넣었습니다.")
    except OSError as exc:
        LOGGER.info(f"[저장] {CSV_PATH.name}을 열 수 없어 올해 표를 채우지 못했습니다: {exc}")


def append_rows(rows: list[dict], today: date | None = None) -> int:
    today = today or date.today()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _archive_into_year_files(today)
    _keep_current_file_to_this_year(today)
    _backfill_current_from_year_file(today)

    existing = load_existing_keys()
    fresh = [row for row in rows if _key(row) not in existing]
    if not fresh:
        LOGGER.info("[저장] 새로 넣을 전시가 없습니다.")
        return 0

    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in fresh:
        grouped[_year_of(row, today.year)].append(row)

    for year, year_rows in grouped.items():
        _append_to(yearly_csv_path(year), year_rows)
        LOGGER.info(f"[저장] {len(year_rows)}건을 exhibitions_{year}.csv에 추가했습니다.")

    this_year_rows = grouped.get(today.year, [])
    try:
        _append_to(CSV_PATH, this_year_rows)
        if this_year_rows:
            LOGGER.info(f"[저장] {len(this_year_rows)}건을 {CSV_PATH.name}에 추가했습니다.")
    except OSError as exc:
        LOGGER.info(f"[저장] {CSV_PATH.name}을 열 수 없어 연도 파일만 저장했습니다: {exc}")
    return len(fresh)
