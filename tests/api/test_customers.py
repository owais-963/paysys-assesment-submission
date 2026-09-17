def test_create_customer_success(api_base_url, http, unique_ref):
    payload = {"customer_ref": f"APITEST{unique_ref}", "name": "Ada Lovelace"}
    resp = http.post(f"{api_base_url}/api/customers", json=payload, timeout=10)

    assert resp.status_code == 201
    assert resp.headers["Location"].startswith("/api/customers/")

    body = resp.json()
    assert body["customer_ref"] == payload["customer_ref"]
    assert body["name"] == payload["name"]
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_customer_response_schema(new_customer):
    assert set(new_customer.keys()) == {"id", "customer_ref", "name", "created_at"}
    assert isinstance(new_customer["id"], int)
    assert isinstance(new_customer["customer_ref"], str)
    assert isinstance(new_customer["name"], str)
    assert isinstance(new_customer["created_at"], str)


def test_create_customer_missing_name_returns_422(api_base_url, http, unique_ref):
    resp = http.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": f"APITEST{unique_ref}"},
        timeout=10,
    )
    assert resp.status_code == 422


def test_create_customer_empty_ref_returns_422(api_base_url, http):
    resp = http.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": "", "name": "No Ref"},
        timeout=10,
    )
    assert resp.status_code == 422


def test_create_customer_duplicate_ref_returns_409(api_base_url, http, new_customer):
    resp = http.post(
        f"{api_base_url}/api/customers",
        json={"customer_ref": new_customer["customer_ref"], "name": "Duplicate Attempt"},
        timeout=10,
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "conflict"
