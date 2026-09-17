"""Bonus command: health check across the database and (if configured) the API."""
import requests

from support import db
from support.config import Settings
from support.exceptions import DependencyError


def check_health(settings: Settings) -> dict:
    result: dict = {}

    try:
        conn = db.connect(settings)
        try:
            with db.dict_cursor(conn) as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            result["database"] = {"status": "ok"}
        finally:
            conn.close()
    except DependencyError as exc:
        result["database"] = {"status": "unreachable", "detail": str(exc)}

    if settings.api_base_url:
        try:
            resp = requests.get(f"{settings.api_base_url}/health", timeout=settings.api_timeout)
            result["api"] = {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "http_status": resp.status_code,
            }
        except requests.exceptions.RequestException as exc:
            result["api"] = {"status": "unreachable", "detail": str(exc)}
    else:
        result["api"] = {"status": "not_configured"}

    db_ok = result["database"]["status"] == "ok"
    api_ok = result["api"]["status"] in ("ok", "not_configured")
    result["overall"] = "ok" if db_ok and api_ok else "degraded"
    return result
