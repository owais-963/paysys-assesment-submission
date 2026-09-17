"""Shared fixtures for the MiniPay API test suite.

The suite runs as black-box HTTP tests against a running MiniPay instance.
Configure the target with the MINIPAY_API_BASE_URL environment variable;
it defaults to http://127.0.0.1:8000, matching MiniPay/backend/.env.example.
"""
import os
import uuid

import pytest
import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def pytest_sessionstart(session):
    base_url = os.environ.get("MINIPAY_API_BASE_URL", DEFAULT_BASE_URL)
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
    except requests.exceptions.RequestException as exc:
        pytest.exit(
            f"MiniPay API is not reachable at {base_url} ({exc}). "
            "Start it first (see MiniPay/README.md) or set MINIPAY_API_BASE_URL.",
            returncode=2,
        )
    if resp.status_code != 200:
        pytest.exit(
            f"MiniPay API health check at {base_url}/health returned "
            f"{resp.status_code}, expected 200. Aborting test run.",
            returncode=2,
        )


@pytest.fixture(scope="session")
def api_base_url():
    return os.environ.get("MINIPAY_API_BASE_URL", DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def http():
    with requests.Session() as s:
        yield s


@pytest.fixture
def unique_ref():
    """A short, collision-resistant token for building test-only ref values."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def new_customer(api_base_url, http, unique_ref):
    """Creates a fresh customer via the API for tests that need one."""
    payload = {"customer_ref": f"APITEST{unique_ref}", "name": "API Test Customer"}
    resp = http.post(f"{api_base_url}/api/customers", json=payload, timeout=10)
    assert resp.status_code == 201, resp.text
    return resp.json()
