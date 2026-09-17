"""GET /api/payments/search?transaction_ref=... -- a collection/search
endpoint, distinct from GET /api/payments/{id}. No match is a valid 200
with an empty list, not a 404 (there is no single resource being fetched).
"""


def test_search_by_reference_finds_created_payment(api_base_url, http, new_customer, unique_ref):
    transaction_ref = f"APITXN{unique_ref}"
    create_resp = http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": transaction_ref,
            "customer_id": new_customer["id"],
            "amount": "42.00",
        },
        timeout=10,
    )
    created = create_resp.json()

    resp = http.get(
        f"{api_base_url}/api/payments/search",
        params={"transaction_ref": transaction_ref},
        timeout=10,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["query_ref"] == transaction_ref
    assert body["count"] == 1
    assert body["items"] == [created]


def test_search_by_reference_no_match_returns_empty_list(api_base_url, http, unique_ref):
    resp = http.get(
        f"{api_base_url}/api/payments/search",
        params={"transaction_ref": f"NOMATCH{unique_ref}"},
        timeout=10,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["items"] == []


def test_search_by_reference_returns_every_duplicate_match(
    api_base_url, http, new_customer, unique_ref
):
    """transaction_ref has no uniqueness constraint (see
    sql/04_duplicate_transaction_references.sql); submitting the same
    reference twice must surface both matches, not just one.
    """
    transaction_ref = f"APITXN{unique_ref}"
    payload = {
        "transaction_ref": transaction_ref,
        "customer_id": new_customer["id"],
        "amount": "15.00",
    }
    first = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10).json()
    second = http.post(f"{api_base_url}/api/payments", json=payload, timeout=10).json()

    resp = http.get(
        f"{api_base_url}/api/payments/search",
        params={"transaction_ref": transaction_ref},
        timeout=10,
    )
    body = resp.json()
    assert body["count"] == 2
    returned_ids = {item["id"] for item in body["items"]}
    assert returned_ids == {first["id"], second["id"]}


def test_search_by_reference_missing_param_returns_422(api_base_url, http):
    resp = http.get(f"{api_base_url}/api/payments/search", timeout=10)
    assert resp.status_code == 422


def test_search_by_reference_requires_api_key(api_base_url):
    import requests

    resp = requests.get(
        f"{api_base_url}/api/payments/search",
        params={"transaction_ref": "TXN00000001"},
        timeout=10,
    )
    assert resp.status_code == 401


def test_search_response_schema(api_base_url, http, new_customer, unique_ref):
    transaction_ref = f"APITXN{unique_ref}"
    http.post(
        f"{api_base_url}/api/payments",
        json={
            "transaction_ref": transaction_ref,
            "customer_id": new_customer["id"],
            "amount": "5.00",
        },
        timeout=10,
    )
    resp = http.get(
        f"{api_base_url}/api/payments/search",
        params={"transaction_ref": transaction_ref},
        timeout=10,
    )
    body = resp.json()
    assert set(body.keys()) == {"query_ref", "count", "items"}
    assert isinstance(body["count"], int)
    assert isinstance(body["items"], list)
    for item in body["items"]:
        assert set(item.keys()) == {
            "id", "transaction_ref", "customer_id", "amount",
            "status", "created_at", "completed_at", "failure_code",
        }
