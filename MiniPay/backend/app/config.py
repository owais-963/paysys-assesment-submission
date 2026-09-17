"""Environment-based configuration. No hard-coded credentials or addresses."""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


class Settings:
    db_host: str = _require("DB_HOST")
    db_port: int = _int("DB_PORT", 5432)
    db_name: str = _require("DB_NAME")
    db_user: str = _require("DB_USER")
    db_password: str = _require("DB_PASSWORD")

    db_pool_min: int = _int("DB_POOL_MIN", 1)
    db_pool_max: int = _int("DB_POOL_MAX", 10)

    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = _int("API_PORT", 8000)

    cors_allow_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    payments_page_size_default: int = _int("PAYMENTS_PAGE_SIZE_DEFAULT", 20)
    payments_page_size_max: int = _int("PAYMENTS_PAGE_SIZE_MAX", 100)

    # Single shared API key, checked via the X-API-Key header. Deliberately
    # minimal (no user accounts, no tokens/sessions) -- see MiniPay/README.md
    # for why this is the right amount of complexity for this assessment.
    api_key: str = _require("API_KEY")


settings = Settings()
