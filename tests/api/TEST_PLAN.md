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
- Every `/api/*` endpoint requires the `X-API-Key` header (see
  `MiniPay/README.md`, `app/auth.py`). `MINIPAY_API_KEY` must be set to the
  value configured on the running MiniPay instance; `conftest.py` aborts
  the whole session up front with a clear message if it's missing, for the
  same reason as the `/health` check above.
- Every test that needs a customer creates its own via the API with a
  random `customer_ref` (see `unique_ref` / `new_customer` fixtures), so the
  suite is repeatable against the same shared database without colliding
  with previous runs or with the seeded Objective 1 data.

## How to run the complete suite

```bash
MINIPAY_API_KEY=<the configured API key> python -m pytest tests/api
```

(Run from the repository root, with `pytest` and `requests` installed —
`pip install -r tests/api/requirements.txt` — `MINIPAY_API_BASE_URL` set if
the API isn't at the default `http://127.0.0.1:8000`, and `MINIPAY_API_KEY`
set to the same value as `API_KEY` in the running instance's configuration.)

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
| 14 | Access-control behavior | `test_access_control.py` | `test_health_requires_no_api_key` | `/health` stays reachable with no credential, by design |
| 15 | Access-control behavior | `test_access_control.py` | `test_protected_endpoint_without_api_key_returns_401` | `POST /api/customers` with no `X-API-Key` is rejected |
| 16 | Access-control behavior | `test_access_control.py` | `test_protected_endpoint_with_wrong_api_key_returns_401` | An incorrect key is rejected, not just a missing one |
| 17 | Access-control behavior | `test_access_control.py` | `test_protected_endpoint_with_correct_api_key_succeeds` | The correct key is accepted |
| 18 | Access-control behavior | `test_access_control.py` | `test_unsupported_method_on_payments_collection_returns_405`, `test_unsupported_method_on_payment_item_returns_405`, `test_unsupported_method_on_customers_collection_returns_405` | Unsupported methods are rejected by routing (405), verified with no API key sent at all, so this isn't mistaken for a 401 |
| 19 | Access-control behavior | `test_access_control.py` | `test_unknown_route_returns_404` | Undefined routes are 404, not exposed as 500s |
| 20 | Duplicate/idempotent submission | `test_payments.py` | `test_duplicate_transaction_ref_is_not_idempotent` | Submitting the same `transaction_ref` twice creates two distinct rows (documents MiniPay's actual, intentional non-idempotent behavior — see Notes) |
| 21 | Duplicate/idempotent submission | `test_customers.py` | `test_create_customer_duplicate_ref_returns_409` | `customer_ref` **is** enforced unique at the DB level; a repeat returns 409, not a silent duplicate |
| 22 | Server/API error behavior | `test_error_handling.py` | `test_malformed_json_body_returns_422` | A syntactically broken JSON body is handled as a clean 4xx, never an unhandled crash, independent of auth |
| 23 | Server/API error behavior | `test_error_handling.py` | `test_server_error_returns_generic_envelope_when_db_unreachable` | Skipped unless `MINIPAY_TEST_DB_DOWN=1` — see Notes |
| 24 | Response schema/content | `test_payments.py` | `test_payment_response_schema` | Asserts field names/types on a payment object |
| 25 | Response schema/content | `test_payments.py` | `test_payment_list_response_schema` | Asserts the pagination envelope (`items`, `limit`, `offset`, `returned_count`, `has_more`) |
| 26 | Response schema/content | `test_customers.py` | `test_customer_response_schema` | Asserts field names/types on a customer object |
| 27 | Response schema/content | `test_search.py` | `test_search_response_schema` | Asserts the search envelope (`query_ref`, `count`, `items`) |
| 28 | Response-time threshold | `test_health.py` | `test_health_response_time_under_threshold` | `/health` responds in under 500 ms |
| 29 | Response-time threshold | `test_payments.py` | `test_get_payment_response_time_under_threshold` | `GET /api/payments/{id}` responds in under 500 ms |
| 30 | New functionality: search by reference | `test_search.py` | `test_search_by_reference_finds_created_payment` | `GET /api/payments/search?transaction_ref=...` finds a payment just created |
| 31 | New functionality: search by reference | `test_search.py` | `test_search_by_reference_no_match_returns_empty_list` | No match is `200` with an empty list, not `404` — this is a search/collection endpoint, not a single-resource fetch |
| 32 | New functionality: search by reference | `test_search.py` | `test_search_by_reference_returns_every_duplicate_match` | A duplicated `transaction_ref` returns every matching row, not just one |
| 33 | New functionality: search by reference | `test_search.py` | `test_search_by_reference_missing_param_returns_422` | The required query parameter is validated |
| 34 | New functionality: search by reference | `test_search.py` | `test_search_by_reference_requires_api_key` | This endpoint is also behind `X-API-Key`, like every other `/api/*` route |

## Notes on categories that needed a documented decision, not just a test

**Access-control / authentication (#14–19).** MiniPay was originally built
with no authentication, then a minimal shared-secret mechanism (a single
`X-API-Key` header, checked in `app/auth.py`) was added to every `/api/*`
route; `/health` stays unauthenticated so it still works as a plain
liveness/readiness check. The suite tests all three states — missing key,
wrong key, correct key — plus confirms method/route rejection (405/404)
happens at the routing layer even with no key sent at all, so those aren't
mistaken for auth failures.

**Duplicate/idempotent submission (#20).** `transaction_ref` on
`transactions` has no uniqueness constraint in `database/schema.sql` — the
Objective 1 seed data deliberately contains duplicate references, and
`sql/04_duplicate_transaction_references.sql` investigates them. Submitting
`POST /api/payments` twice with the same `transaction_ref` is therefore
**not idempotent by current design**: it creates two separate rows with two
different IDs. The test asserts this actual behavior rather than an
idealized one, and `tests/api/NOTES.md` covers how true idempotency would be
added if this were a production payment integration.

**Server/API error behavior (#22–23).** MiniPay's input validation
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
