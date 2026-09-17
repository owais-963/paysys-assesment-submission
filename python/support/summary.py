"""Bonus command: summarize stuck PROCESSING and recently FAILED transactions."""
from decimal import Decimal

from support import db


def _serialize_row(row: dict) -> dict:
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, Decimal):
            out[key] = str(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


def build_summary(conn, stuck_processing_minutes: int, failed_lookback_hours: int) -> dict:
    stuck = db.fetch_stuck_processing(conn, stuck_processing_minutes)
    failed = db.fetch_recent_failed(conn, failed_lookback_hours)
    return {
        "stuck_processing_threshold_minutes": stuck_processing_minutes,
        "stuck_processing_count": len(stuck),
        "stuck_processing": [_serialize_row(r) for r in stuck],
        "recent_failed_lookback_hours": failed_lookback_hours,
        "recent_failed_count": len(failed),
        "recent_failed": [_serialize_row(r) for r in failed],
    }
