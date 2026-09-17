# Architecture

## Overview

```
                          ┌─────────────────────────┐
                          │   Browser (MiniPay UI)   │
                          │ static HTML/JS, served   │
                          │ independently of the API │
                          └────────────┬─────────────┘
                                       │ fetch() + X-API-Key
                                       ▼
┌───────────────────────────────────────────────────────────┐
│                    MiniPay API (FastAPI)                   │
│  routes/  →  controllers/  →  models/  (raw parameterized  │
│  (HTTP)      (business        SQL, no ORM)                 │
│               rules)                                        │
│  auth.py: X-API-Key check on every /api/* router           │
│  /health: unauthenticated liveness + DB reachability check │
└───────────────────────────┬─────────────────────────────────┘
                            │ psycopg2 connection pool
                            ▼
┌───────────────────────────────────────────────────────────┐
│                  PostgreSQL (database/schema.sql)           │
│   customers  ──1:N──  transactions  ──1:N──  callbacks       │
└───────┬─────────────────────┬─────────────────────┬─────────┘
        │                     │                     │
        ▼                     ▼                     ▼
  sql/*.sql             python/support_tool.py   tests/api, tests/ui
  (investigation        (L2 diagnostic CLI,      (pytest + Playwright,
   queries, direct       direct read-only         drive the real API/UI
   psql access)          DB access)                over HTTP)
```

Everything above can also run inside Kubernetes (`kubernetes/`): the API
as a `Deployment`+`Service`, the database as a `StatefulSet` with
persistent storage, both in a dedicated `minipay` namespace. See
`kubernetes/USAGE.md` for that topology in detail.

## Data model

Supplied, unmodified, in `database/schema.sql`:

- **`customers`** — `id`, unique `customer_ref`, `name`, `created_at`.
- **`transactions`** — `id`, `transaction_ref` (**not** unique — the seed
  data intentionally contains duplicates, investigated in
  `sql/04_duplicate_transaction_references.sql`), `customer_id` (FK, no
  automatic index — see the performance note below), `amount`, `status`
  (`PROCESSING`/`SUCCESS`/`FAILED`), `created_at`, `completed_at`,
  `failure_code`.
- **`callbacks`** — one row per delivery attempt for a transaction:
  `transaction_id` (FK), `attempt_no`, `http_status`, `callback_status`,
  `attempted_at`.

This shape drives several design decisions documented below (search
returning multiple matches, the reconciliation query, the CLI's anomaly
detection).

## Components

### MiniPay backend (`MiniPay/backend/`)

FastAPI, MVC-style layout, no ORM:

- **`routes/`** — HTTP endpoints only; parses request params, calls a
  controller, returns its result. No business logic here.
- **`controllers/`** — orchestrates model calls with the actual business
  rules (e.g. reject a payment for an unknown `customer_id`; a search with
  no match is a `200` empty list, not a `404`, because it's a
  collection/search endpoint rather than a single-resource fetch).
- **`models/`** — every SQL statement lives here, as plain parameterized
  queries (`%s` placeholders, never string interpolation).
- **`schemas/`** — Pydantic request/response validation. Distinct from
  `database/schema.sql` despite the name overlap — these validate the API
  *contract*, they don't define any database structure (see
  `MiniPay/README.md` for the full explanation of this distinction, which
  came up directly during development).
- **`auth.py`** — a single shared-secret `X-API-Key` check, applied as a
  FastAPI dependency at the router level. Deliberately the simplest
  mechanism that still requires a credential — no user accounts, sessions,
  or tokens.
- **`database.py`** — a `psycopg2` connection pool; `config.py` loads every
  setting from the environment, raising a clear error for anything
  required and missing rather than a confusing downstream failure.

### MiniPay frontend (`MiniPay/frontend/`)

Static HTML/JS, deliberately served independently of the API (a separate
static file server, or nothing more elaborate than
`python -m http.server`), reflecting a real decoupled deployment rather
than a single monolithic dev server. An "API Key" field (persisted in
`localStorage`) supplies `X-API-Key` on every request via a thin
`fetch()` wrapper (`js/api.js`).

### SQL investigations (`sql/`)

Seven queries answering the required reporting questions (transaction
counts by status/day, top customers, stuck-in-processing detection,
duplicate references, success rate, reconciliation against callbacks,
processing-time percentiles), plus `PERFORMANCE.md`: a real before/after
`EXPLAIN (ANALYZE, BUFFERS)` comparison for adding an index on
`transactions.transaction_ref` (a ~71x measured speedup on this dataset).

**Note on `transactions.customer_id`:** it's a foreign key, and
PostgreSQL does not automatically index foreign key columns, so
`GET /api/customers/{id}/payments` runs as a full sequential scan today.
This is deliberate, not an oversight — diagnosing and fixing exactly this
kind of slow-as-volume-grows access pattern is the subject of
`investigation/INCIDENT-003-RCA.md` (Objective 6, not yet written), so no
supplementary index was added preemptively in Objective 2.

### Support CLI (`python/support_tool.py`)

Reads the database directly rather than through the API, because the API
has no endpoint exposing callback/retry history and (until the search
endpoint was added) no lookup by `transaction_ref` at all — and an L2
engineer's starting point is always the reference, not a numeric ID.
Anomaly detection (`support/diagnostics.py`) is pure functions over plain
dicts, separated from the DB-touching fetch functions specifically so it's
unit-testable without a database connection.

### Test suites (`tests/api/`, `tests/ui/`)

Both are black-box: `tests/api/` drives the real HTTP API with `requests`;
`tests/ui/` drives the real static frontend with Playwright, in a real
browser, against the real running API — no mocks anywhere in either
suite. Both suites verify their target is actually reachable (and that
`MINIPAY_API_KEY` is set) before collecting a single test, so a
not-running app produces one clear message instead of dozens of confusing
individual failures.

### Kubernetes (`kubernetes/`)

- `namespace.yaml` — the `minipay` namespace (missing from the supplied
  starter manifest — see `investigation/kubernetes-findings.md`).
- `configmap.yaml` / `secrets.yaml` — non-secret config vs. `DB_PASSWORD`
  and `API_KEY`, shared between the API `Deployment` and the database
  `StatefulSet` so both sides can never drift apart.
- `postgres-statefulset.yaml` — a `StatefulSet` (not a `Deployment`) with
  `volumeClaimTemplates` for genuinely persistent storage, plus a headless
  `Service` giving it the stable DNS name the API's `DB_HOST` expects.
- `deployment.yaml` / `service.yaml` — the corrected API workload; every
  defect found in the starter manifest (wrong probe port, selector/port
  mismatch, placeholder image, missing env vars, no resource limits — see
  `investigation/kubernetes-findings.md`) is fixed here, with a comment
  pointing at which finding it addresses.
- `hpa.yaml` — CPU-based autoscaling for the API.

## Key design decisions and trade-offs

- **No ORM anywhere** (backend, support CLI) — every query is plain,
  parameterized SQL against the supplied schema, kept auditable and
  directly comparable to the `sql/` investigation queries.
- **Minimal auth, added deliberately, not by default** — MiniPay started
  with no authentication (explicit initial instruction, to avoid
  over-engineering a demo). A single shared-secret `X-API-Key` was added
  later once genuinely requested, rather than building a fuller
  session/OAuth system this assessment doesn't call for.
- **Search returns every match, not just one** — because
  `transaction_ref` genuinely isn't unique in this schema/dataset, both
  `GET /api/payments/search` and the support CLI's `--transaction` return
  every matching row and flag `DUPLICATE_REFERENCE`, rather than silently
  picking the first/most-recent one and hiding a real data-quality signal.
- **`transactions.customer_id` left unindexed on purpose** — see the SQL
  section above; the point of Objective 6 is to diagnose this kind of
  problem, not have it pre-solved.
- **Frontend and backend are decoupled** — no single process serves both;
  this matches how a real deployment would separate a static asset host
  from an API, and is why the frontend has its own externalized
  `config.js` for the API's address.

## Known gaps (stated directly, not glossed over)

- `investigation/INCIDENT-00{1,2,3}-RCA.md` do not exist yet (Objective 6).
- `evidence/rancher.md` does not exist yet (Objective 5's Rancher portion).
- `evidence/linux.md`'s command output is still a placeholder awaiting a
  real run on the target Linux host (Objective 7) — the health-check
  script's control flow was verified locally, but its Linux-specific
  commands (`free`, `ss`, `ps -eo`) have not produced real output yet.

See `README.md`'s "Objective status" table for the same information at a
glance.
