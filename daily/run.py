from __future__ import annotations

import sys
from datetime import date

from util.clock import today_seoul
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from util.logger import setup_logger
from util.pipeline import run_pipeline


def main() -> int:
    logger = setup_logger()
    try:
        rows = run_pipeline()
    except Exception as exc:
        logger.exception(f"[실패] 실행 중 오류: {exc}")
        return 1
    if not rows:
        print("오늘은 넣을 전시가 없습니다. 기록 파일에 No articles found 가 남았습니다.")
        return 0
    print("")
    print("오늘 고른 전시 (메일 한 통에 최소 10개, 달력은 그중 5개)")
    print("-" * 40)
    for index, row in enumerate(rows, start=1):
        tag = f"{row['region_tag']} " if row["region_tag"] else ""
        period = " ~ ".join(part for part in [row["start_date"], row["end_date"]] if part) or "기간 미확인"
        print(f"{index}. {tag}{row['title']}")
        print(f"   장소: {row['venue']} {row['venue_address']}".rstrip())
        print(f"   기간: {period}")
        print(f"   소개: {row['summary']}")
        if row["reservation_url"]:
            print(f"   링크: {row['reservation_url']}")
        print("")
    print("표 파일: data/exhibitions.csv (올해 매일 누적)")
    print(f"연도 보관: data/exhibitions_{today_seoul().year}.csv")
    print("달력 파일: data/exhibitions.ics")
    print("구글 캘린더: 위 목록 중 아직 안 끝난 상위 5개만 Ownex에 올립니다. 끝난 전시는 지웁니다.")
    print("지메일: 위 목록 전체를 보냅니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
