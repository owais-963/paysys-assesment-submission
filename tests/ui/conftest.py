"""Shared fixtures for the MiniPay UI (Playwright) test suite.

Drives the real MiniPay/frontend static pages in a browser, against a
running MiniPay backend. Configure targets with:
  MINIPAY_UI_BASE_URL  (default http://127.0.0.1:8020) - static frontend
  MINIPAY_API_BASE_URL (default http://127.0.0.1:8080) - backend API
  MINIPAY_API_KEY       - required; the API key configured on that backend

Preconditions (a customer / a payment to search for) are created directly
via the API with `requests`, so the UI tests only drive the browser for the
actual user journey being verified, not for unrelated setup data.
"""
import os
import uuid

import pytest
import requests

DEFAULT_UI_BASE_URL = "http://127.0.0.1:8020"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"


def pytest_sessionstart(session):
    ui_base_url = os.environ.get("MINIPAY_UI_BASE_URL", DEFAULT_UI_BASE_URL)
    api_base_url = os.environ.get("MINIPAY_API_BASE_URL", DEFAULT_API_BASE_URL)

    try:
        resp = requests.get(f"{ui_base_url}/index.html", timeout=5)
        assert resp.status_code == 200
    except Exception as exc:
        pytest.exit(
            f"MiniPay frontend is not reachable at {ui_base_url} ({exc}). "
            "Serve it first (see MiniPay/README.md) or set MINIPAY_UI_BASE_URL.",
            returncode=2,
        )

    try:
        resp = requests.get(f"{api_base_url}/health", timeout=5)
        assert resp.status_code == 200
    except Exception as exc:
        pytest.exit(
            f"MiniPay API is not reachable at {api_base_url} ({exc}). "
            "Start it first (see MiniPay/README.md) or set MINIPAY_API_BASE_URL.",
            returncode=2,
        )

    if not os.environ.get("MINIPAY_API_KEY"):
        pytest.exit(
            "MINIPAY_API_KEY is not set. The MiniPay UI now requires an API "
            "key for every action except the health check -- set "
            "MINIPAY_API_KEY to the same value configured on the running "
            "backend (see MiniPay/backend/.env) before running this suite.",
            returncode=2,
        )


@pytest.fixture(scope="session")
def ui_base_url():
    return os.environ.get("MINIPAY_UI_BASE_URL", DEFAULT_UI_BASE_URL)


@pytest.fixture(scope="session")
def api_base_url():
    return os.environ.get("MINIPAY_API_BASE_URL", DEFAULT_API_BASE_URL)


@pytest.fixture(scope="session")
def api_key():
    return os.environ["MINIPAY_API_KEY"]


@pytest.fixture
def unique_ref():
    return uuid.uuid4().hex[:12]


@pytest.fixture
def api_customer(api_base_url, api_key, unique_ref):
    """Creates a customer directly via the API, for tests that need one to
    already exist before the browser journey under test begins.
    """
    payload = {"customer_ref": f"UITEST{unique_ref}", "name": "UI Test Customer"}
    resp = requests.post(
        f"{api_base_url}/api/customers",
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def api_payment(api_base_url, api_key, api_customer, unique_ref):
    """Creates a payment directly via the API, for the "search for a
    transaction" journey to look up.
    """
    payload = {
        "transaction_ref": f"UITXN{unique_ref}",
        "customer_id": api_customer["id"],
        "amount": "75.50",
    }
    resp = requests.post(
        f"{api_base_url}/api/payments",
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def authenticated_page(page, ui_base_url, api_key):
    """Navigates to the app and fills in the API Key field -- the precondition
    every journey except the negative "no key" scenario needs before it can
    do anything against the backend.
    """
    page.goto(ui_base_url)
    page.locator("#api-key").fill(api_key)
    return page
