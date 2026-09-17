import os

import pytest
import requests


def test_malformed_json_body_returns_422(api_base_url):
    """A syntactically broken JSON body must be handled as a clean 4xx by
    FastAPI's request parsing, never surfaced as an unhandled crash.

    Deliberately sent without an X-API-Key at all: body parsing rejects
    this with 422 independent of authentication, verified manually to
    return the same 422 with or without a valid key -- so this also
    confirms request parsing isn't gated behind auth in a way that would
    turn a malformed-body bug into a confusing 401 instead.
    """
    resp = requests.post(
        f"{api_base_url}/api/customers",
        data="{not valid json",
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    assert resp.status_code == 422


@pytest.mark.skipif(
    os.environ.get("MINIPAY_TEST_DB_DOWN") != "1",
    reason=(
        "Requires a MiniPay instance whose database has been intentionally "
        "stopped/unreachable. Run manually with MINIPAY_TEST_DB_DOWN=1 "
        "against such an instance -- see TEST_PLAN.md."
    ),
)
def test_server_error_returns_generic_envelope_when_db_unreachable(api_base_url, http):
    health = http.get(f"{api_base_url}/health", timeout=5)
    assert health.status_code == 503
    assert health.json()["status"] == "degraded"

    resp = http.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": "SHOULDFAIL", "name": "Should Fail"},
        timeout=10,
    )
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "internal_server_error"
    assert "message" in body
