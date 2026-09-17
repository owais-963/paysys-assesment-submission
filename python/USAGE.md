# MiniPay Support Tool: Module Purpose and Requirements Mapping

This document explains what each file does and why, then maps every
requirement in `requirements/04-python-support-tool.md` to exactly where
it's implemented — so nothing on that checklist is left implicit. For
day-to-day command usage and worked examples, see `GUIDE.md`.

## File-by-file

### `support_tool.py`

The CLI entrypoint. Parses arguments (`argparse`, mutually-exclusive group
of `--transaction` / `--health` / `--stuck-summary`, plus `--json` and
`--failed-lookback-hours`), loads configuration, wires the logger, calls
into the relevant `support/*` module, renders the result, and maps outcomes
to exit codes. Deliberately thin: it contains no business logic itself —
every decision (what counts as an anomaly, how to render a report, how to
check health) lives in a dedicated module below, so `support_tool.py`
stays readable as "parse args → call the right thing → print it → return
an exit code."

### `support/config.py`

Loads all configuration from environment variables (optionally via a local
`.env`, using `python-dotenv`). `load_settings()` raises `ConfigError` for
any missing required variable (`DB_HOST`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD`) rather than silently defaulting or crashing with an
unrelated `psycopg2` error later. Optional settings (`API_BASE_URL`,
timeouts, the stuck-processing threshold, log level) have sensible
defaults.

### `support/db.py`

All database access: connection setup (`connect()`, wrapping
`psycopg2.OperationalError` as `DependencyError` so the CLI can map it to
the right exit code) and every query, as plain parameterized SQL (`%s`
placeholders, never string interpolation) — no ORM. Four fetch functions:
transactions by reference (joined to `customers`), callbacks for a
transaction, stuck `PROCESSING` transactions, and recent `FAILED`
transactions.

### `support/diagnostics.py`

The core diagnostic logic for `--transaction`, and the one module with the
most unit test coverage. Split deliberately:
- `diagnose_transaction()` orchestrates the DB fetches (handles the
  duplicate-reference case by diagnosing every match, not just one).
- `detect_anomalies()` and `recommend_action()` are pure functions over
  plain dicts/lists — no database, no I/O — which is what makes them
  directly unit-testable (see `tests/test_diagnostics.py`).
- `build_transaction_diagnosis()` shapes one transaction + its callbacks +
  its anomalies into the final report dict (same shape for both text and
  `--json` output).

### `support/health.py`

Implements `--health` (bonus command): checks the database with a
`SELECT 1`, and — only if `API_BASE_URL` is configured — checks the
MiniPay API's own `/health` endpoint over HTTP with a timeout. Reports
`not_configured` for the API check rather than silently skipping it, so
the absence of that check is visible in the output, not just absent from
it.

### `support/summary.py`

Implements `--stuck-summary` (bonus command): two read-only queries (via
`support/db.py`) for currently-stuck `PROCESSING` transactions and recently
`FAILED` ones, serialized into JSON-safe dicts (`Decimal` → `str`,
`datetime` → ISO string) via `_serialize_row()`.

### `support/report.py`

Renders the human-readable text form of all three commands' results. Kept
separate from the data-producing modules so the exact same result dict
backs both `--json` and the text report — there is only one source of
truth for "what happened," just two ways of printing it.

### `support/logging_setup.py`

Configures a single `support_tool` logger that writes to **stderr** only.
This matters specifically because of `--json`: if logging went to stdout,
`--json` output would no longer be valid, parseable JSON on its own.

### `support/exceptions.py`

Three exception classes (`SupportToolError` base, `ConfigError`,
`DependencyError`) that `support_tool.py`'s `main()` catches explicitly to
choose an exit code, instead of the CLI needing to know about
`psycopg2`/`requests` exception types directly.

### `tests/test_diagnostics.py`, `tests/test_report.py`

Unit tests for the pure logic in `diagnostics.py` and `report.py`. Every
test constructs plain dicts/lists by hand (via `make_transaction()` /
`make_callback()` helpers) — no database connection, no mocking framework
needed, because the functions under test don't touch I/O at all. 19 tests,
all passing (`python -m pytest`, see `REPRODUCIBLE.md`).

## Requirements mapping

Each row is a line from `requirements/04-python-support-tool.md`:

| Requirement | Satisfied by | Detail |
|---|---|---|
| `python support_tool.py --transaction TXN000123` interface | `support_tool.py` | Exact flag name and positional value format |
| Retrieve info from the API and/or database | `support/db.py`, `support/health.py` | Reads the database directly (join across `transactions`/`customers`/`callbacks`); `--health` additionally checks the API's `/health` when configured — see the design note in `GUIDE.md`/`README.md` for why the database is the primary source |
| Report: transaction details | `diagnostics.build_transaction_diagnosis()` | `id`, `transaction_ref`, `customer_id`, `amount`, `status` |
| Report: customer/reference/amount/status | `diagnostics.build_transaction_diagnosis()` | `customer_ref`, `customer_name`, `amount`, `status` fields |
| Report: relevant timestamps | `diagnostics.build_transaction_diagnosis()` | `created_at`, `completed_at`, plus each callback's `attempted_at` |
| Report: callback/retry information | `support/db.py: fetch_callbacks_for_transaction()`, surfaced in `build_transaction_diagnosis()` | Every callback attempt, in order, with HTTP status and outcome |
| Report: detected anomalies / likely failure reason | `diagnostics.detect_anomalies()` | 5 concrete anomaly types (see `GUIDE.md`), including surfacing `failure_code` |
| Report: recommended next action | `diagnostics.recommend_action()` | One concrete, anomaly-specific recommendation per detected anomaly |
| Machine-readable output mode (`--json`) | `support_tool.py: _emit()` | Same result dict as the text report, `json.dumps(..., indent=2)` |
| Configuration via environment/config file, not hard-coded | `support/config.py` | `load_settings()`, backed by `.env` via `python-dotenv`; `.env.example` has only placeholders |
| Error and timeout handling | `support/db.py` (`connect_timeout`), `support/health.py` (`requests` `timeout=`), `support_tool.py` (`try`/`except` around `DependencyError`/`SupportToolError`/generic `Exception`) | Every network call has an explicit timeout; every expected failure mode is caught and reported without a raw traceback to the user |
| Useful exit codes | `support_tool.py` (`EXIT_OK`, `EXIT_NOT_FOUND`, `EXIT_DEPENDENCY_ERROR`, `EXIT_CONFIG_ERROR`, `EXIT_UNEXPECTED_ERROR`) | Documented in `README.md`/`GUIDE.md`, verified live for all 5 cases |
| Logging | `support/logging_setup.py` | stderr-only, `LOG_LEVEL`-configurable |
| Modular/readable code | Package layout under `support/` | Config, DB access, business logic, health, summary, and rendering are five separate, single-purpose modules, not one script |
| Automated unit tests for important logic | `tests/test_diagnostics.py`, `tests/test_report.py` | 19 tests covering every anomaly rule and every report renderer |
| Bonus: summarize stuck/failed transactions | `support/summary.py`, `--stuck-summary` | Counts + row listings for stuck `PROCESSING` and recent `FAILED` |
| Bonus: health check across API/database dependencies | `support/health.py`, `--health` | Database always checked; API checked when `API_BASE_URL` is set |

## Example: live run against the seeded database

Re-run on 2026-09-18 against the same live `minipay` PostgreSQL instance
used throughout this assessment, to confirm the tool still behaves exactly
as documented rather than just trusting an earlier capture. Every block
below is real, unedited command output.

```
$ python support_tool.py --health
Overall status: ok
Database:       ok
API:            not_configured
$ echo $?
0
```

```
$ python support_tool.py --transaction TXN00024999
Transaction reference: TXN00024999
WARNING: 2 transactions share this reference (see DUPLICATE_REFERENCE anomaly on each match below).

--- Match 1 of 2 (id=25000) ---
Customer:            Customer 303 (CUST000303, id=303)
Amount:              2923.35
Status:              SUCCESS
Created at:          2026-09-10T11:40:28
Completed at:        2026-09-10T11:41:25
Callback attempts:   1
  - attempt 1: SUCCESS (http 200) at 2026-09-10T11:41:30
Anomalies:           DUPLICATE_REFERENCE
Recommended action:  Multiple transactions share this reference. Confirm with the customer whether this was a duplicate submission before taking any resolution action on either record.

--- Match 2 of 2 (id=24999) ---
Customer:            Customer 14 (CUST000014, id=14)
Amount:              84623.80
Status:              SUCCESS
Created at:          2026-09-07T12:28:43
Completed at:        2026-09-07T12:29:12
Callback attempts:   1
  - attempt 1: SUCCESS (http 200) at 2026-09-07T12:29:17
Anomalies:           DUPLICATE_REFERENCE
Recommended action:  Multiple transactions share this reference. Confirm with the customer whether this was a duplicate submission before taking any resolution action on either record.
```

```
$ python support_tool.py --transaction TXN00000029 --json
{
  "query_ref": "TXN00000029",
  "match_count": 1,
  "transactions": [
    {
      "id": 29,
      "transaction_ref": "TXN00000029",
      "customer_id": 541,
      "customer_ref": "CUST000541",
      "customer_name": "Customer 541",
      "amount": "87256.06",
      "status": "PROCESSING",
      "created_at": "2026-09-06T03:14:52",
      "completed_at": null,
      "failure_code": null,
      "callbacks": [],
      "anomalies": ["STUCK_IN_PROCESSING"],
      "recommended_action": "Transaction has been PROCESSING beyond the expected threshold. Check upstream processor connectivity and escalate if it does not resolve on its own."
    }
  ]
}
$ echo $?
0
```

```
$ python support_tool.py --stuck-summary
Stuck in PROCESSING (> 15 min): 2445
  - id=43080 ref=TXN00043080 created_at=2026-09-01T00:11:28 amount=95881.63
  - id=44851 ref=TXN00044851 created_at=2026-09-01T00:17:09 amount=97183.90
  - id=8073 ref=TXN00008073 created_at=2026-09-01T00:17:37 amount=76893.20
  ... (2445 total -- truncated here for length)
```

The stuck-`PROCESSING` count (2445) is large because the seed data's
`created_at` values are fixed in the past (early September 2026) while
`STUCK_IN_PROCESSING`/`--stuck-summary` compare against the real current
time — the same effect documented for the equivalent SQL query in
`sql/03_processing_over_15_minutes.sql`, not a bug in this tool.

```
$ python support_tool.py --transaction TXN99999999
No transaction found with reference 'TXN99999999'.
$ echo $?
1
```
