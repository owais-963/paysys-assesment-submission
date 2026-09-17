"""Minimal shared-secret authentication: a single API key checked via the
X-API-Key header. No user accounts, sessions, or tokens -- intentionally
the simplest mechanism that still requires a caller to present a credential
before touching customer/payment data. /health stays unauthenticated so it
can be used as an unauthenticated liveness/readiness check.
"""
from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
