from __future__ import annotations

import configparser
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".config"
ENV_PATH = ROOT / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    load_dotenv(path)
    if not path.exists():
        return
    raw = path.read_bytes()
    if not raw:
        return
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value


def load_config() -> configparser.ConfigParser:
    load_env_file(ENV_PATH)
    parser = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {CONFIG_PATH}")
    parser.read(CONFIG_PATH, encoding="utf-8")
    return parser


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]
