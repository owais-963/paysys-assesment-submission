"""MiniPay intentionally has no authentication mechanism (see MiniPay/README.md).
These tests document that decision and cover the access-control-equivalent
boundary behavior that does exist: consistent no-auth across endpoints, and
correct rejection of unsupported methods / unknown routes at the router.
"""


def test_no_authorization_header_required(api_base_url, http):
    resp = http.get(f"{api_base_url}/health", timeout=5)
    assert resp.status_code == 200


def test_unsupported_method_on_payments_collection_returns_405(api_base_url, http):
    resp = http.delete(f"{api_base_url}/api/payments", timeout=5)
    assert resp.status_code == 405


def test_unsupported_method_on_payment_item_returns_405(api_base_url, http):
    resp = http.delete(f"{api_base_url}/api/payments/1", timeout=5)
    assert resp.status_code == 405


def test_unsupported_method_on_customers_collection_returns_405(api_base_url, http):
    resp = http.delete(f"{api_base_url}/api/customers", timeout=5)
    assert resp.status_code == 405


def test_unknown_route_returns_404(api_base_url, http):
    resp = http.get(f"{api_base_url}/api/does-not-exist", timeout=5)
    assert resp.status_code == 404
