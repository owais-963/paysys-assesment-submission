"""Environment-based configuration. No hard-coded credentials or addresses."""
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from support.exceptions import ConfigError

load_dotenv()


@dataclass
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_connect_timeout: int
    api_base_url: Optional[str]
    api_timeout: int
    stuck_processing_minutes: int
    log_level: str


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        db_host=_require("DB_HOST"),
        db_port=int(os.environ.get("DB_PORT", 5432)),
        db_name=_require("DB_NAME"),
        db_user=_require("DB_USER"),
        db_password=_require("DB_PASSWORD"),
        db_connect_timeout=int(os.environ.get("DB_CONNECT_TIMEOUT", 5)),
        api_base_url=os.environ.get("API_BASE_URL") or None,
        api_timeout=int(os.environ.get("API_TIMEOUT", 5)),
        stuck_processing_minutes=int(os.environ.get("STUCK_PROCESSING_MINUTES", 15)),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
