# MiniPay API Test Results

Command run:

```bash
MINIPAY_API_KEY=<the configured API key> python -m pytest tests/api
```

Environment: MiniPay backend running locally (`uvicorn`), connected to the
seeded `minipay` PostgreSQL database from Objective 1. Target set via
`MINIPAY_API_BASE_URL=http://127.0.0.1:8080`. This run reflects two new
additions since the previous recorded run: a required `X-API-Key` header on
every `/api/*` endpoint, and a new `GET /api/payments/search` endpoint for
searching by `transaction_ref`.

## Outcome

```
======================== 36 passed, 1 skipped in 0.51s ========================
```

## Full output

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Owais backup\paysys-lab-assesment\tests\api
configfile: pytest.ini
plugins: anyio-4.15.1, base-url-2.1.0, playwright-0.9.0
collecting ... collected 37 items

tests\api\test_access_control.py::test_health_requires_no_api_key PASSED [  2%]
tests\api\test_access_control.py::test_protected_endpoint_without_api_key_returns_401 PASSED [  5%]
tests\api\test_access_control.py::test_protected_endpoint_with_wrong_api_key_returns_401 PASSED [  8%]
tests\api\test_access_control.py::test_protected_endpoint_with_correct_api_key_succeeds PASSED [ 10%]
tests\api\test_access_control.py::test_unsupported_method_on_payments_collection_returns_405 PASSED [ 13%]
tests\api\test_access_control.py::test_unsupported_method_on_payment_item_returns_405 PASSED [ 16%]
tests\api\test_access_control.py::test_unsupported_method_on_customers_collection_returns_405 PASSED [ 18%]
tests\api\test_access_control.py::test_unknown_route_returns_404 PASSED  [ 21%]
tests\api\test_customers.py::test_create_customer_success PASSED         [ 24%]
tests\api\test_customers.py::test_customer_response_schema PASSED        [ 27%]
tests\api\test_customers.py::test_create_customer_missing_name_returns_422 PASSED [ 29%]
tests\api\test_customers.py::test_create_customer_empty_ref_returns_422 PASSED [ 32%]
tests\api\test_customers.py::test_create_customer_duplicate_ref_returns_409 PASSED [ 35%]
tests\api\test_error_handling.py::test_malformed_json_body_returns_422 PASSED [ 37%]
tests\api\test_error_handling.py::test_server_error_returns_generic_envelope_when_db_unreachable SKIPPED [ 40%]
tests\api\test_health.py::test_health_returns_ok PASSED                  [ 43%]
tests\api\test_health.py::test_health_response_time_under_threshold PASSED [ 45%]
tests\api\test_payments.py::test_create_payment_success PASSED           [ 48%]
tests\api\test_payments.py::test_payment_response_schema PASSED          [ 51%]
tests\api\test_payments.py::test_create_payment_unknown_customer_returns_404 PASSED [ 54%]
tests\api\test_payments.py::test_create_payment_missing_transaction_ref_returns_422 PASSED [ 56%]
tests\api\test_payments.py::test_create_payment_non_positive_amount_returns_422[0] PASSED [ 59%]
tests\api\test_payments.py::test_create_payment_non_positive_amount_returns_422[-5] PASSED [ 62%]
tests\api\test_payments.py::test_create_payment_customer_id_wrong_type_returns_422 PASSED [ 64%]
tests\api\test_payments.py::test_get_payment_by_id_success PASSED        [ 67%]
tests\api\test_payments.py::test_get_payment_unknown_id_returns_404 PASSED [ 70%]
tests\api\test_payments.py::test_get_payment_response_time_under_threshold PASSED [ 72%]
tests\api\test_payments.py::test_list_customer_payments_success PASSED   [ 75%]
tests\api\test_payments.py::test_payment_list_response_schema PASSED     [ 78%]
tests\api\test_payments.py::test_list_payments_unknown_customer_returns_404 PASSED [ 81%]
tests\api\test_payments.py::test_duplicate_transaction_ref_is_not_idempotent PASSED [ 83%]
tests\api\test_search.py::test_search_by_reference_finds_created_payment PASSED [ 86%]
tests\api\test_search.py::test_search_by_reference_no_match_returns_empty_list PASSED [ 89%]
tests\api\test_search.py::test_search_by_reference_returns_every_duplicate_match PASSED [ 91%]
tests\api\test_search.py::test_search_by_reference_missing_param_returns_422 PASSED [ 94%]
tests\api\test_search.py::test_search_by_reference_requires_api_key PASSED [ 97%]
tests\api\test_search.py::test_search_response_schema PASSED             [100%]

=========================== short test summary info ===========================
SKIPPED [1] tests\api\test_error_handling.py:26: Requires a MiniPay instance whose database has been intentionally stopped/unreachable. Run manually with MINIPAY_TEST_DB_DOWN=1 against such an instance -- see TEST_PLAN.md.
======================== 36 passed, 1 skipped in 0.51s ========================
```

## Summary

| Metric | Value |
|---|---|
| Total collected | 37 |
| Passed | 36 |
| Skipped | 1 (documented, opt-in fault-injection test — see `TEST_PLAN.md`) |
| Failed | 0 |
| Wall-clock time | 0.51s |

## What's new in this run

- **Authentication (`test_access_control.py`):** replaced the old
  "documents no-auth" tests with real coverage of the new `X-API-Key`
  requirement — missing key (401), wrong key (401), correct key (201), and
  `/health` remaining reachable with no key at all. Also confirmed 405/404
  routing rejections happen independent of authentication, so they aren't
  mistaken for auth failures.
- **Search by reference (`test_search.py`, new file):** 6 tests covering
  the new `GET /api/payments/search?transaction_ref=...` endpoint — finds a
  just-created payment, returns an empty list (not 404) for no match,
  returns **every** row for a duplicated reference, validates the required
  query parameter, requires the API key like every other `/api/*` route,
  and asserts the response envelope shape.

The suite itself does not delete anything it creates -- there is no
teardown fixture in `conftest.py`. All test data created during this run
(`customer_ref` / `transaction_ref` values prefixed `APITEST` / `APITXN`)
was removed manually afterward with a one-off `DELETE` run directly
against the database, so the seeded Objective 1 dataset is left
unmodified. Running the suite again without that manual step will leave
new `APITEST`/`APITXN` rows in place.
