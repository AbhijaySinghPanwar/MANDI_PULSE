"""Load config/settings.yaml and .env from the project root."""

from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"

load_dotenv(PROJECT_ROOT / ".env")


@lru_cache
def get_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
