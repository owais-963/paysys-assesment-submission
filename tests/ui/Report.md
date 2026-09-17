# MiniPay UI Test Report (Playwright)

Framework: `pytest-playwright`, driving the real `MiniPay/frontend` static
pages in a browser against a running MiniPay backend. No mocked UI, no
mocked API — every assertion below is against actual application state.

## Command used

```bash
MINIPAY_API_KEY=<the configured API key> python -m pytest tests/ui --browser-channel chrome
```

`--browser-channel chrome` runs against the system-installed Chrome instead
of a Playwright-managed browser binary — used here because this
environment's outbound network access blocked `playwright install`'s
browser download. Where an unrestricted network is available, either
`playwright install chromium` (bundled browser) or `--browser-channel
chrome`/`msedge` (system browser) work identically for these tests, since
none of the tests depend on browser-specific behavior.

## Environment for this run

- Backend: MiniPay API (`uvicorn`) at `http://127.0.0.1:8080`, connected to
  the seeded `minipay` PostgreSQL database from Objective 1. Every `/api/*`
  route now requires the `X-API-Key` header (see `MiniPay/README.md`,
  `app/auth.py`); `/health` remains unauthenticated.
- Frontend: `MiniPay/frontend` served statically at `http://127.0.0.1:8020`
  (`python -m http.server 8020`), with `frontend/js/config.js` pointing at
  the API above.
- `conftest.py` verifies the frontend and API are reachable, and that
  `MINIPAY_API_KEY` is set, before any test runs, exiting the whole session
  with a clear message otherwise.

## Journeys covered

| # | Required journey | Test | Result |
|---|---|---|---|
| 1 | Open/login to the application | `test_open_application` | PASSED |
| 2 | Search for a transaction (by payment ID) | `test_search_transaction_by_id` | PASSED |
| — | New functionality: search by transaction reference | `test_search_transaction_by_reference` | PASSED |
| 3 | Create/submit a test payment | `test_submit_payment_and_validate_success` | PASSED |
| 4 | Validate a successful result | `test_submit_payment_and_validate_success` (same test, second half) | PASSED |
| 5 | Negative/error scenario | `test_submit_payment_negative_scenario` | PASSED |
| — | New functionality: access-control negative scenario | `test_submit_payment_without_api_key_is_rejected` | PASSED |

`test_open_application` covers "open/login": MiniPay now has a minimal
shared-secret mechanism (a single API key, entered into the `#api-key`
field — the closest thing this app has to a login step), so this journey
opens the app, confirms the unauthenticated health check works, and
confirms the API Key field is present for every subsequent journey to use
(via the `authenticated_page` fixture, which fills it before each test that
needs to be authenticated).

## Outcome

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Owais backup\paysys-lab-assesment\tests\ui
configfile: pytest.ini
plugins: anyio-4.15.1, base-url-2.1.0, playwright-0.9.0
collecting ... collected 6 items

tests\ui\test_minipay_ui.py::test_open_application[chromium] PASSED      [ 16%]
tests\ui\test_minipay_ui.py::test_search_transaction_by_id[chromium] PASSED [ 33%]
tests\ui\test_minipay_ui.py::test_search_transaction_by_reference[chromium] PASSED [ 50%]
tests\ui\test_minipay_ui.py::test_submit_payment_and_validate_success[chromium] PASSED [ 66%]
tests\ui\test_minipay_ui.py::test_submit_payment_negative_scenario[chromium] PASSED [ 83%]
tests\ui\test_minipay_ui.py::test_submit_payment_without_api_key_is_rejected[chromium] PASSED [100%]

============================== 6 passed in 3.29s ==============================
```

6 passed, 0 failed.

## Selector strategy

Every assertion targets a stable element `id` already present in
`MiniPay/frontend/index.html` (`#api-key`, `#customer-form`,
`#payment-form`, `#lookup-form`, `#search-form`, `#payment-result`, etc.) or
a structural CSS selector (`#payment-form button[type='submit']`) — never
free text matching or a raw `sleep`. Waiting is handled by Playwright's
built-in auto-retrying `expect(locator)`, which polls the actual
DOM/attribute state until it matches or a timeout elapses, rather than a
fixed delay.

## Evidence

A full-page screenshot was captured for every test at the point it
finished, under `tests/ui/test-results/`:

- `test-minipay-ui-py-test-open-application-chromium/test-finished-1.png`
- `test-minipay-ui-py-test-search-transaction-by-id-chromium/test-finished-1.png`
- `test-minipay-ui-py-test-search-transaction-by-reference-chromium/test-finished-1.png`
- `test-minipay-ui-py-test-submit-payment-and-validate-success-chromium/test-finished-1.png`
- `test-minipay-ui-py-test-submit-payment-negative-scenario-chromium/test-finished-1.png`
- `test-minipay-ui-py-test-submit-payment-without-api-key-is-rejected-chromium/test-finished-1.png`

The negative-scenario screenshot shows the actual rendered error state: a
red-bordered result panel containing
`{"error": "not_found", "message": "customer 999999999 not found"}`. The new
missing-API-key screenshot shows the same red-bordered panel containing the
real `{"detail": "Invalid or missing API key"}` body from `app/auth.py` —
both confirm the UI surfaces the actual API error rather than failing
silently or misreporting success.

Test data created during this run (`customer_ref` / `transaction_ref`
values prefixed `UITEST` / `UITXN`) was deleted from the database
afterward, leaving the seeded Objective 1 dataset unmodified.

## CI integration

- **Every release (smoke gate, blocking merge/deploy):** `test_open_application`
  and `test_submit_payment_and_validate_success` — the minimum proof that
  the app is up, reachable, authenticated correctly, and can complete its
  one core business action (submit a payment) end to end. Fast (seconds),
  stable, and a failure here means the release is genuinely broken.
- **Larger regression suite (scheduled/nightly, or on-demand before a
  bigger release):** the full suite, including both search journeys and
  both negative scenarios (`unknown customer`, `missing API key`), plus
  additional journeys as the UI grows (pagination in the history panel,
  more validation edge cases). These add coverage depth but aren't required
  to gate every single merge.
- **Pipeline shape:** run `tests/api` first (fast, no browser) as a gate,
  then `tests/ui` only if that passes — a broken API makes every UI test
  fail anyway, so failing fast on the API layer saves CI time. Start the
  backend and the static frontend server as background steps before
  invoking `pytest tests/ui --browser-channel chrome` (or
  `playwright install --with-deps chromium` once, then omit
  `--browser-channel`, if the CI runner has unrestricted network access),
  with `MINIPAY_API_KEY` set to the same value the backend was started
  with. Publish `tests/ui/test-results/` (screenshots) as a CI artifact so
  a failure is diagnosable without re-running locally.
