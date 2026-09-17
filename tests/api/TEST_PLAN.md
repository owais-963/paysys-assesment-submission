# MiniPay API Test Plan

Scope: black-box HTTP tests against a running MiniPay backend (Objective 2),
covering `requirements/05-web-services-api-tests.md`. Framework: `pytest` +
`requests`. Tests talk only to the public HTTP API — no direct database
access, no internal imports from `MiniPay/backend/app`.

## Target and preconditions

- The MiniPay backend must already be running and reachable (locally or in
  its Docker container — see `MiniPay/README.md` / `MiniPay/REPRODUCIBLE.md`).
- `MINIPAY_API_BASE_URL` (default `http://127.0.0.1:8000`) points the suite
  at it.
- `conftest.py` calls `GET /health` before any test runs and aborts the
  whole session with a clear message if the API isn't reachable, instead of
  letting every test fail individually with a confusing connection error.
- Every test that needs a customer creates its own via the API with a
  random `customer_ref` (see `unique_ref` / `new_customer` fixtures), so the
  suite is repeatable against the same shared database without colliding
  with previous runs or with the seeded Objective 1 data.

## How to run the complete suite

```bash
python -m pytest tests/api
```

(Run from the repository root, with `pytest` and `requests` installed —
`pip install -r tests/api/requirements.txt` — and `MINIPAY_API_BASE_URL` set
if the API isn't at the default `http://127.0.0.1:8000`.)

## Test case matrix

| # | Requirement category | Test file | Test case | What it proves |
|---|---|---|---|---|
| 1 | Successful requests | `test_health.py` | `test_health_returns_ok` | `GET /health` returns 200 with `{"status":"ok","db":"reachable"}` |
| 2 | Successful requests | `test_customers.py` | `test_create_customer_success` | `POST /api/customers` returns 201 with the created customer, correct `Location` header |
| 3 | Successful requests | `test_payments.py` | `test_create_payment_success` | `POST /api/payments` returns 201, status `PROCESSING`, `completed_at` null |
| 4 | Successful requests | `test_payments.py` | `test_get_payment_by_id_success` | `GET /api/payments/{id}` returns the same record just created |
| 5 | Successful requests | `test_payments.py` | `test_list_customer_payments_success` | `GET /api/customers/{id}/payments` returns the customer's payment(s) |
| 6 | Invalid/missing fields | `test_customers.py` | `test_create_customer_missing_name_returns_422` | Missing required field is rejected before touching the database |
| 7 | Invalid/missing fields | `test_customers.py` | `test_create_customer_empty_ref_returns_422` | Empty string fails `min_length` validation |
| 8 | Invalid/missing fields | `test_payments.py` | `test_create_payment_missing_transaction_ref_returns_422` | Missing required field rejected |
| 9 | Invalid/missing fields | `test_payments.py` | `test_create_payment_non_positive_amount_returns_422` (parametrized `0`, `-5`) | `amount > 0` constraint enforced |
| 10 | Invalid/missing fields | `test_payments.py` | `test_create_payment_customer_id_wrong_type_returns_422` | Non-numeric `customer_id` rejected by type validation |
| 11 | Unknown resources | `test_payments.py` | `test_create_payment_unknown_customer_returns_404` | Referencing a non-existent customer is a 404, not a 500 or silent insert |
| 12 | Unknown resources | `test_payments.py` | `test_get_payment_unknown_id_returns_404` | Unknown payment ID is a 404 |
| 13 | Unknown resources | `test_payments.py` | `test_list_payments_unknown_customer_returns_404` | Unknown customer ID on the history endpoint is a 404 |
| 14 | Access-control behavior | `test_access_control.py` | `test_no_authorization_header_required` | Documents the deliberate no-auth decision (see Notes below) rather than silently having no coverage for this category |
| 15 | Access-control behavior | `test_access_control.py` | `test_unsupported_method_on_payments_collection_returns_405` | `DELETE /api/payments` is rejected at the routing boundary |
| 16 | Access-control behavior | `test_access_control.py` | `test_unsupported_method_on_payment_item_returns_405` | `DELETE /api/payments/{id}` is rejected |
| 17 | Access-control behavior | `test_access_control.py` | `test_unknown_route_returns_404` | Undefined routes are 404, not exposed as 500s |
| 18 | Duplicate/idempotent submission | `test_payments.py` | `test_duplicate_transaction_ref_is_not_idempotent` | Submitting the same `transaction_ref` twice creates two distinct rows (documents MiniPay's actual, intentional non-idempotent behavior — see Notes) |
| 19 | Duplicate/idempotent submission | `test_customers.py` | `test_create_customer_duplicate_ref_returns_409` | `customer_ref` **is** enforced unique at the DB level; a repeat returns 409, not a silent duplicate |
| 20 | Server/API error behavior | `test_error_handling.py` | `test_malformed_json_body_returns_422` | A syntactically broken JSON body is handled as a clean 4xx, never an unhandled crash |
| 21 | Server/API error behavior | `test_error_handling.py` | `test_server_error_returns_generic_envelope_when_db_unreachable` | Skipped unless `MINIPAY_TEST_DB_DOWN=1` — see Notes |
| 22 | Response schema/content | `test_payments.py` | `test_payment_response_schema` | Asserts field names/types on a payment object |
| 23 | Response schema/content | `test_payments.py` | `test_payment_list_response_schema` | Asserts the pagination envelope (`items`, `limit`, `offset`, `returned_count`, `has_more`) |
| 24 | Response schema/content | `test_customers.py` | `test_customer_response_schema` | Asserts field names/types on a customer object |
| 25 | Response-time threshold | `test_health.py` | `test_health_response_time_under_threshold` | `/health` responds in under 500 ms |
| 26 | Response-time threshold | `test_payments.py` | `test_get_payment_response_time_under_threshold` | `GET /api/payments/{id}` responds in under 500 ms |

## Notes on categories that needed a documented decision, not just a test

**Access-control / authentication (#14–17).** MiniPay was built with no
authentication mechanism, by explicit instruction for this assessment (see
`MiniPay/README.md`). There is therefore nothing to test in the
conventional sense of "requires a valid token." To still give this category
real coverage rather than skip it silently, the suite instead verifies the
boundary behavior that *is* present: no endpoint requires any
`Authorization` header (confirming the no-auth design is consistent, not
accidental), and the router correctly rejects unsupported methods (405) and
unknown routes (404) rather than falling through to unexpected behavior.

**Duplicate/idempotent submission (#18).** `transaction_ref` on
`transactions` has no uniqueness constraint in `database/schema.sql` — the
Objective 1 seed data deliberately contains duplicate references, and
`sql/04_duplicate_transaction_references.sql` investigates them. Submitting
`POST /api/payments` twice with the same `transaction_ref` is therefore
**not idempotent by current design**: it creates two separate rows with two
different IDs. The test asserts this actual behavior rather than an
idealized one, and `tests/api/NOTES.md` covers how true idempotency would be
added if this were a production payment integration.

**Server/API error behavior (#20–21).** MiniPay's input validation
(Pydantic types/bounds matching the SQL column constraints) turned out to
be strict enough that common 5xx triggers — oversized amounts, out-of-range
integers — are caught as clean 4xx responses before reaching the database
(verified manually during development: an out-of-`BIGINT`-range ID or
`customer_id` returns 404/422, not a crash, because PostgreSQL compares it
as `numeric` without erroring). A malformed JSON body is covered as an
automated test (#20) and returns 422. Forcing a genuine *unhandled* 500
safely and deterministically requires taking a real dependency down (e.g.
pointing `DB_HOST` at an unreachable address), which isn't something this
suite does automatically against a shared database. `test_error_handling.py`
includes that scenario as a test gated behind `MINIPAY_TEST_DB_DOWN=1`, to
be run manually against an isolated instance whose database has been
intentionally stopped, confirming `/health` returns 503 and the generic
`{"error": "internal_server_error", ...}` envelope is used elsewhere,
without leaking a stack trace.
