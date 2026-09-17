"""Access control: every /api/* endpoint requires a valid X-API-Key header
(see MiniPay/README.md and app/auth.py); /health does not. Also covers the
router-level boundary behavior: unsupported methods and unknown routes are
rejected before authentication is even checked (verified without sending
any key at all).
"""
import requests


def test_health_requires_no_api_key(api_base_url):
    resp = requests.get(f"{api_base_url}/health", timeout=5)
    assert resp.status_code == 200


def test_protected_endpoint_without_api_key_returns_401(api_base_url):
    resp = requests.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": "SHOULD-NOT-BE-CREATED", "name": "No Key"},
        timeout=10,
    )
    assert resp.status_code == 401


def test_protected_endpoint_with_wrong_api_key_returns_401(api_base_url):
    resp = requests.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": "SHOULD-NOT-BE-CREATED", "name": "Wrong Key"},
        headers={"X-API-Key": "definitely-not-the-real-key"},
        timeout=10,
    )
    assert resp.status_code == 401


def test_protected_endpoint_with_correct_api_key_succeeds(api_base_url, http, unique_ref):
    resp = http.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": f"APITEST{unique_ref}", "name": "Correct Key"},
        timeout=10,
    )
    assert resp.status_code == 201


def test_unsupported_method_on_payments_collection_returns_405(api_base_url):
    # No API key sent at all -- routing rejects the method before auth is
    # ever checked, so this must not be mistaken for a 401.
    resp = requests.delete(f"{api_base_url}/api/payments", timeout=5)
    assert resp.status_code == 405


def test_unsupported_method_on_payment_item_returns_405(api_base_url):
    resp = requests.delete(f"{api_base_url}/api/payments/1", timeout=5)
    assert resp.status_code == 405


def test_unsupported_method_on_customers_collection_returns_405(api_base_url):
    resp = requests.delete(f"{api_base_url}/api/customers", timeout=5)
    assert resp.status_code == 405


def test_unknown_route_returns_404(api_base_url):
    resp = requests.get(f"{api_base_url}/api/does-not-exist", timeout=5)
    assert resp.status_code == 404
