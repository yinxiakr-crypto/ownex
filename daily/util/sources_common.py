from __future__ import annotations

from datetime import date

from util.config_loader import csv_list
from util.normalize import clean_text, detect_region, parse_period, to_iso


def make_item(cfg, **kwargs) -> dict:
    title = clean_text(kwargs.get("title") or "")
    venue = clean_text(kwargs.get("venue") or "")
    address = clean_text(kwargs.get("venue_address") or "")
    raw = clean_text(kwargs.get("raw_text") or "")
    start, end = parse_period(kwargs.get("period") or "", kwargs.get("default_year"))
    if kwargs.get("start_date"):
        start = start or kwargs.get("start_date")
    if kwargs.get("end_date"):
        end = end or kwargs.get("end_date")
    if end and hasattr(end, "year") and end < date(2026, 6, 1):
        start, end = None, None
    regions = csv_list(cfg["general"].get("priority_regions", ""))
    region_text = " ".join([title, venue, address, raw])
    return {
        "title": title,
        "venue": venue,
        "venue_address": address,
        "region_tag": detect_region(region_text, regions),
        "reservation_url": kwargs.get("reservation_url") or kwargs.get("source_url") or "",
        "source_url": kwargs.get("source_url") or kwargs.get("reservation_url") or "",
        "start_date": to_iso(start) if hasattr(start, "isoformat") else (start or ""),
        "end_date": to_iso(end) if hasattr(end, "isoformat") else (end or ""),
        "reservation_open_date": kwargs.get("reservation_open_date") or "",
        "image_url": kwargs.get("image_url") or "",
        "raw_text": raw,
        "source_name": kwargs.get("source_name") or "",
        "summary": "",
    }
