from __future__ import annotations

import os
from datetime import date, timedelta

from util.browser import HeadlessBrowser
from util.calendar_ics import write_ics
from util.config_loader import load_config
from util.email_report import enrich_visuals, send_exhibition_email
from util.google_calendar import sync_events
from util.logger import get_logger
from util.config_loader import csv_list
from util.normalize import from_iso, is_main_region, overlaps, pick_calendar_rows
from util.ranker import merge_items, rank_items
from util.sources_artbava import collect_artbava
from util.sources_artmap import collect_artmap
from util.sources_featured import collect_featured
from util.sources_google import collect_google
from util.sources_naver import collect_naver
from util.sources_sac import collect_sac
from util.sources_sejong import collect_sejong
from util.sources_seoul_venues import collect_seoul_venues
from util.clock import today_seoul
from util.state import resolve_range, should_send_email, write_last_email, write_last_run
from util.mail_list import ingest_mail_requests
from util.export_web import write_web_data
from util.storage_csv import append_rows
from util.summarizer import summarize

LOGGER = get_logger()


def _in_window(item: dict, start, end, today: date) -> bool:
    show_start = from_iso(item.get("start_date") or "")
    show_end = from_iso(item.get("end_date") or "")
    if not show_start:
        return False
    show_end = show_end or show_start
    if overlaps(show_start, show_end, start, end):
        return True
    if overlaps(show_start, show_end, today, today):
        return True
    if today <= show_start <= today + timedelta(days=180):
        return True
    return False


def run_pipeline(today: date | None = None) -> list[dict]:
    today = today or today_seoul()
    LOGGER.info("===== 전시 수집 시작 =====")
    cfg = load_config()
    start, end = resolve_range(cfg, today)
    LOGGER.info(f"[기간] {start.isoformat()} ~ {end.isoformat()}")

    collected: list[dict] = []
    skip_browser = os.getenv("OWNEX_SKIP_BROWSER", "").strip() in {"1", "true", "yes"} or os.getenv("CI", "").strip() == "true"
    if skip_browser:
        LOGGER.info("[단계] 클라우드에서는 사이트 수집을 건너뛰고 화제 전시를 씁니다.")
    else:
        try:
            with HeadlessBrowser() as browser:
                LOGGER.info("[단계] 예술의전당 수집")
                collected.extend(collect_sac(cfg, browser))
                LOGGER.info("[단계] 아트맵 수집")
                collected.extend(collect_artmap(cfg, browser))
                LOGGER.info("[단계] 아트바바 수집")
                collected.extend(collect_artbava(cfg, browser))
                LOGGER.info("[단계] 세종문화회관 수집")
                collected.extend(collect_sejong(cfg, browser))
                LOGGER.info("[단계] 서울권 주요 미술관 수집")
                collected.extend(collect_seoul_venues(cfg, browser))
                LOGGER.info("[단계] 네이버 검색")
                collected.extend(collect_naver(cfg, browser))
        except Exception as exc:
            LOGGER.info(f"[단계] 브라우저 수집 실패: {exc}")

    LOGGER.info("[단계] 화제 전시 보강")
    collected.extend(collect_featured(cfg))
    LOGGER.info("[단계] 구글 검색")
    collected.extend(collect_google(cfg))

    merged = merge_items(collected)
    LOGGER.info(f"[단계] 정리 후 후보 {len(merged)}건")
    skipped_no_date = sum(1 for item in merged if not from_iso(item.get("start_date") or ""))
    LOGGER.info(f"[단계] 날짜 없는 전시 {skipped_no_date}건은 건너뜁니다.")
    filtered = [item for item in merged if _in_window(item, start, end, today)]
    LOGGER.info(f"[단계] 날짜 있는 기간 맞춤 후보 {len(filtered)}건")
    main_regions = csv_list(cfg["general"].get("main_regions", "서울,안양"))
    min_email = cfg["general"].getint("min_results", fallback=10)
    email_cap = cfg["general"].getint("max_results", fallback=20)
    calendar_limit = min(5, cfg["general"].getint("max_calendar", fallback=5))
    regional = [item for item in filtered if is_main_region(item, main_regions)]
    LOGGER.info(f"[단계] 서울·안양·지정미술관 후보 {len(regional)}건")
    if len(regional) < min_email:
        extras = [item for item in filtered if item not in regional]
        regional.extend(extras)
        LOGGER.info(f"[단계] 최소 {min_email}건을 채우기 위해 날짜 있는 전시를 더함: {len(regional)}건")
    filtered = regional

    if not filtered:
        LOGGER.info("No articles found")
        write_last_run(end)
        try:
            write_web_data()
        except OSError as exc:
            LOGGER.info(f"[홈] 홈페이지 데이터를 쓰지 못했습니다: {exc}")
        LOGGER.info("===== 전시 수집 종료 =====")
        return []

    LOGGER.info("[단계] 우선순위 선정")
    top = rank_items(cfg, filtered, limit=email_cap)
    if len(top) < min_email:
        extras = [item for item in filtered if item not in top]
        top.extend(extras[: min_email - len(top)])
        LOGGER.info(f"[단계] 최소 {min_email}건을 맞추기 위해 전시를 더함: {len(top)}건")
    if len(top) < min_email:
        LOGGER.info(f"[단계] 날짜 있는 전시가 {len(top)}건뿐입니다. 최소 {min_email}건에 못 미쳤습니다.")
    LOGGER.info("[단계] 시각 자료 확인")
    try:
        enrich_visuals(top)
    except Exception as exc:
        LOGGER.info(f"[시각] 사진 확인을 건너뛰고 메일·달력으로 갑니다: {exc}")
    LOGGER.info("[단계] 특징 요약")
    for item in top:
        item["summary"] = summarize(item)
    rows = []
    for item in top:
        open_date = item.get("reservation_open_date") or ""
        if not open_date and item.get("start_date"):
            show_start = from_iso(item["start_date"])
            if show_start:
                open_date = (show_start - timedelta(days=7)).isoformat()
        rows.append(
            {
                "collected_date": today.isoformat(),
                "title": item.get("title") or "",
                "venue": item.get("venue") or "",
                "venue_address": item.get("venue_address") or "",
                "region_tag": item.get("region_tag") or "",
                "reservation_url": item.get("reservation_url") or "",
                "start_date": item.get("start_date") or "",
                "end_date": item.get("end_date") or "",
                "reservation_open_date": open_date,
                "summary": item.get("summary") or "",
                "image_url": item.get("image_url") or "",
                "image_bytes": item.get("image_bytes"),
                "has_visual": item.get("has_visual") or False,
                "source_urls": " | ".join(item.get("source_url_list") or [item.get("source_url") or ""]),
                "score_reason": item.get("score_reason") or "",
            }
        )

    LOGGER.info("[단계] 표 저장")
    try:
        append_rows(rows)
    except OSError as exc:
        LOGGER.info(f"[저장] 표를 열 수 없어 이번만 건너뜁니다: {exc}")
    clip_from = today
    calendar_rows = pick_calendar_rows(rows, today, calendar_limit)
    LOGGER.info(
        f"[단계] 메일은 {len(rows)}건 목록, 달력은 오늘 볼 수 있는 {len(calendar_rows)}건 "
        f"(지난 시작일은 자르고, 남은 기간은 그대로 둡니다)"
    )
    LOGGER.info("[단계] 아이폰 달력 파일 (매일)")
    try:
        write_ics(calendar_rows, clip_from, today=today)
    except Exception as exc:
        LOGGER.info(f"[달력] 아이폰 파일을 쓰지 못했습니다: {exc}")
    gcal = cfg["google_calendar"] if cfg.has_section("google_calendar") else None
    if gcal and gcal.get("enabled", "true").lower() == "true":
        LOGGER.info("[단계] 구글 캘린더 (매일)")
        try:
            sync_events(calendar_rows, gcal.get("calendar_name", "Ownex"), clip_from, today=today)
        except Exception as exc:
            LOGGER.info(f"[달력] 구글 캘린더를 올리지 못했습니다: {exc}")
    send_now, send_reason = should_send_email(cfg, today)
    mail_cfg = cfg["email"] if cfg.has_section("email") else None
    cloud_primary = bool(mail_cfg and mail_cfg.get("cloud_primary", "false").lower() == "true")
    in_cloud = os.getenv("CI", "").strip() == "true" or os.getenv("OWNEX_CLOUD", "").strip() in {"1", "true", "yes"}
    try:
        ingest_mail_requests()
    except Exception as exc:
        LOGGER.info(f"[메일] 신청 반영을 건너뜁니다: {exc}")
    if cloud_primary and not in_cloud:
        LOGGER.info("[단계] 메일은 클라우드에서 보냅니다. 컴퓨터가 꺼져 있어도 아침 8시에 나갑니다.")
    elif send_now:
        LOGGER.info(f"[단계] 지메일 한 통 보내기 ({send_reason})")
        if send_exhibition_email(rows, cfg, clip_from):
            write_last_email(today)
    else:
        LOGGER.info(f"[단계] 메일은 건너뜁니다. {send_reason}")
    write_last_run(end)
    if os.getenv("OWNEX_SKIP_WEB", "").strip() in {"1", "true", "yes"} or os.getenv("CI", "").strip() == "true":
        LOGGER.info("[홈] 클라우드에서는 홈페이지 저장을 건너뜁니다.")
    else:
        try:
            write_web_data(email_rows=rows, calendar_rows=calendar_rows)
        except OSError as exc:
            LOGGER.info(f"[홈] 홈페이지 데이터를 쓰지 못했습니다: {exc}")
    LOGGER.info("===== 전시 수집 종료 =====")
    return rows
