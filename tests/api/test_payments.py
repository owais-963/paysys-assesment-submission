import time

import pytest

RESPONSE_TIME_THRESHOLD_MS = 500


def test_create_payment_success(api_base_url, http, new_customer, unique_ref):
    payload = {
        "transaction_ref": f"APITXN{unique_ref}",
        "customer_id": new_customer["id"],
        "amount": "150.25",
    }
    resp = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10)

    assert resp.status_code == 201
    assert resp.headers["Location"].startswith("/api/payments/")

    body = resp.json()
    assert body["transaction_ref"] == payload["transaction_ref"]
    assert body["customer_id"] == new_customer["id"]
    assert body["amount"] == "150.25"
    assert body["status"] == "PROCESSING"
    assert body["completed_at"] is None
    assert body["failure_code"] is None


def test_payment_response_schema(api_base_url, http, new_customer, unique_ref):
    payload = {
        "transaction_ref": f"APITXN{unique_ref}",
        "customer_id": new_customer["id"],
        "amount": "10.00",
    }
    resp = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10)
    body = resp.json()

    assert set(body.keys()) == {
        "id", "transaction_ref", "customer_id", "amount",
        "status", "created_at", "completed_at", "failure_code",
    }
    assert isinstance(body["id"], int)
    assert isinstance(body["transaction_ref"], str)
    assert isinstance(body["customer_id"], int)
    assert isinstance(body["amount"], str)
    assert body["status"] in ("PROCESSING", "SUCCESS", "FAILED")


def test_create_payment_unknown_customer_returns_404(api_base_url, http, unique_ref):
    payload = {
        "transaction_ref": f"APITXN{unique_ref}",
        "customer_id": 999999999,
        "amount": "10.00",
    }
    resp = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10)
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_create_payment_missing_transaction_ref_returns_422(api_base_url, http, new_customer):
    resp = http.post(
        f"{api_base_url}/api/payments",
        json={"customer_id": new_customer["id"], "amount": "10.00"},
        timeout=10,
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("amount", ["0", "-5"])
def test_create_payment_non_positive_amount_returns_422(api_base_url, http, new_customer, unique_ref, amount):
    resp = http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": f"APITXN{unique_ref}",
            "customer_id": new_customer["id"],
            "amount": amount,
        },
        timeout=10,
    )
    assert resp.status_code == 422


def test_create_payment_customer_id_wrong_type_returns_422(api_base_url, http, unique_ref):
    resp = http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": f"APITXN{unique_ref}",
            "customer_id": "not-a-number",
            "amount": "10.00",
        },
        timeout=10,
    )
    assert resp.status_code == 422


def test_get_payment_by_id_success(api_base_url, http, new_customer, unique_ref):
    create_payload = {
        "transaction_ref": f"APITXN{unique_ref}",
        "customer_id": new_customer["id"],
        "amount": "42.50",
    }
    created = http.post(f"{api_base_url}/api/payments", json=create_payload, timeout=10).json()

    resp = http.get(f"{api_base_url}/api/payments/{created['id']}", timeout=10)
    assert resp.status_code == 200
    assert resp.json() == created


def test_get_payment_unknown_id_returns_404(api_base_url, http):
    resp = http.get(f"{api_base_url}/api/payments/999999999", timeout=10)
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_get_payment_response_time_under_threshold(api_base_url, http, new_customer, unique_ref):
    created = http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": f"APITXN{unique_ref}",
            "customer_id": new_customer["id"],
            "amount": "5.00",
        },
        timeout=10,
    ).json()

    start = time.perf_counter()
    resp = http.get(f"{api_base_url}/api/payments/{created['id']}", timeout=10)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < RESPONSE_TIME_THRESHOLD_MS, (
        f"GET /api/payments/{{id}} took {elapsed_ms:.1f} ms, expected under {RESPONSE_TIME_THRESHOLD_MS} ms"
    )


def test_list_customer_payments_success(api_base_url, http, new_customer, unique_ref):
    http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": f"APITXN{unique_ref}",
            "customer_id": new_customer["id"],
            "amount": "20.00",
        },
        timeout=10,
    )

    resp = http.get(f"{api_base_url}/api/customers/{new_customer['id']}/payments", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["customer_id"] == new_customer["id"]


def test_payment_list_response_schema(api_base_url, http, new_customer):
    resp = http.get(f"{api_base_url}/api/customers/{new_customer['id']}/payments", timeout=10)
    body = resp.json()
    assert set(body.keys()) == {"items", "limit", "offset", "returned_count", "has_more"}
    assert isinstance(body["items"], list)
    assert isinstance(body["limit"], int)
    assert isinstance(body["offset"], int)
    assert isinstance(body["returned_count"], int)
    assert isinstance(body["has_more"], bool)


def test_list_payments_unknown_customer_returns_404(api_base_url, http):
    resp = http.get(f"{api_base_url}/api/customers/999999999/payments", timeout=10)
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_duplicate_transaction_ref_is_not_idempotent(api_base_url, http, new_customer, unique_ref):
    """MiniPay does not enforce uniqueness on transaction_ref (matching the
    supplied database/schema.sql, which allows duplicates by design -- see
    sql/04_duplicate_transaction_references.sql). Submitting the same
    reference twice therefore creates two distinct payment records.
    """
    payload = {
        "transaction_ref": f"APITXN{unique_ref}",
        "customer_id": new_customer["id"],
        "amount": "30.00",
    }
    first = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10)
    second = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["transaction_ref"] == second.json()["transaction_ref"]
