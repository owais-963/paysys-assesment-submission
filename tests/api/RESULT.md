# MiniPay API Test Results

Command run:

```bash
python -m pytest tests/api
```

Environment: MiniPay backend running locally (`uvicorn`), connected to the
seeded `minipay` PostgreSQL database from Objective 1. Target set via
`MINIPAY_API_BASE_URL=http://127.0.0.1:8010`.

## Outcome

```
======================== 27 passed, 1 skipped in 0.19s ========================
```

## Full output

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Owais backup\paysys-lab-assesment\tests\api
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 28 items

tests\api\test_access_control.py::test_no_authorization_header_required PASSED [  3%]
tests\api\test_access_control.py::test_unsupported_method_on_payments_collection_returns_405 PASSED [  7%]
tests\api\test_access_control.py::test_unsupported_method_on_payment_item_returns_405 PASSED [ 10%]
tests\api\test_access_control.py::test_unsupported_method_on_customers_collection_returns_405 PASSED [ 14%]
tests\api\test_access_control.py::test_unknown_route_returns_404 PASSED  [ 17%]
tests\api\test_customers.py::test_create_customer_success PASSED         [ 21%]
tests\api\test_customers.py::test_customer_response_schema PASSED        [ 25%]
tests\api\test_customers.py::test_create_customer_missing_name_returns_422 PASSED [ 28%]
tests\api\test_customers.py::test_create_customer_empty_ref_returns_422 PASSED [ 32%]
tests\api\test_customers.py::test_create_customer_duplicate_ref_returns_409 PASSED [ 35%]
tests\api\test_error_handling.py::test_malformed_json_body_returns_422 PASSED [ 39%]
tests\api\test_error_handling.py::test_server_error_returns_generic_envelope_when_db_unreachable SKIPPED [ 42%]
tests\api\test_health.py::test_health_returns_ok PASSED                  [ 46%]
tests\api\test_health.py::test_health_response_time_under_threshold PASSED [ 50%]
tests\api\test_payments.py::test_create_payment_success PASSED           [ 53%]
tests\api\test_payments.py::test_payment_response_schema PASSED          [ 57%]
tests\api\test_payments.py::test_create_payment_unknown_customer_returns_404 PASSED [ 60%]
tests\api\test_payments.py::test_create_payment_missing_transaction_ref_returns_422 PASSED [ 64%]
tests\api\test_payments.py::test_create_payment_non_positive_amount_returns_422[0] PASSED [ 67%]
tests\api\test_payments.py::test_create_payment_non_positive_amount_returns_422[-5] PASSED [ 71%]
tests\api\test_payments.py::test_create_payment_customer_id_wrong_type_returns_422 PASSED [ 75%]
tests\api\test_payments.py::test_get_payment_by_id_success PASSED        [ 78%]
tests\api\test_payments.py::test_get_payment_unknown_id_returns_404 PASSED [ 82%]
tests\api\test_payments.py::test_get_payment_response_time_under_threshold PASSED [ 85%]
tests\api\test_payments.py::test_list_customer_payments_success PASSED   [ 89%]
tests\api\test_payments.py::test_payment_list_response_schema PASSED     [ 92%]
tests\api\test_payments.py::test_list_payments_unknown_customer_returns_404 PASSED [ 96%]
tests\api\test_payments.py::test_duplicate_transaction_ref_is_not_idempotent PASSED [100%]

=========================== short test summary info ===========================
SKIPPED [1] tests\api\test_error_handling.py:20: Requires a MiniPay instance whose database has been intentionally stopped/unreachable. Run manually with MINIPAY_TEST_DB_DOWN=1 against such an instance -- see TEST_PLAN.md.
======================== 27 passed, 1 skipped in 0.19s ========================
```

## Summary

| Metric | Value |
|---|---|
| Total collected | 28 |
| Passed | 27 |
| Skipped | 1 (documented, opt-in fault-injection test — see `TEST_PLAN.md`) |
| Failed | 0 |
| Wall-clock time | 0.19s |

All test data created during this run (`customer_ref` / `transaction_ref`
values prefixed `APITEST` / `APITXN`) was deleted from the database
afterward so the seeded Objective 1 dataset is left unmodified.
