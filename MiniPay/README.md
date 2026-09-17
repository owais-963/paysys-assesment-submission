# MiniPay

A minimal, production-shaped payments API + static admin console, built for
Objective 2 of the assessment. It connects to the same PostgreSQL database
set up and seeded in Objective 1 (`sql/REPRODUCIBLE.md`) — no ORM, no
separate demo/mock data layer. Every `/api/*` endpoint requires a minimal
shared-secret API key (see "Authentication" below); `/health` does not.

## Structure (MVC)

```
MiniPay/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app: routers, CORS, auth, exception handlers
│   │   ├── config.py            # env-based configuration (no hard-coded values)
│   │   ├── database.py          # psycopg2 connection pool (no ORM)
│   │   ├── auth.py              # X-API-Key dependency, applied to every /api/* router
│   │   ├── exceptions.py        # NotFoundError, ConflictError
│   │   ├── models/              # raw parameterized SQL per table
│   │   │   ├── customer_model.py
│   │   │   └── payment_model.py
│   │   ├── controllers/         # request orchestration / business rules
│   │   │   ├── customer_controller.py
│   │   │   └── payment_controller.py
│   │   ├── schemas/              # Pydantic request/response validation (API layer only, see note below)
│   │   │   ├── customer_schema.py
│   │   │   └── payment_schema.py
│   │   └── routes/               # HTTP endpoints (the "view" layer for an API)
│   │       ├── customer_routes.py
│   │       ├── payment_routes.py
│   │       └── health_routes.py
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   └── .env.example
└── frontend/                    # static HTML/JS, served independently of the API
    ├── index.html
    ├── css/style.css
    └── js/
        ├── config.js            # API base URL (externalized)
        ├── api.js                # fetch wrapper
        └── app.js                # form wiring
```

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/customers` | Required | Create a customer |
| `POST` | `/api/payments` | Required | Submit a payment (creates a `transactions` row, status `PROCESSING`) |
| `GET` | `/api/payments/{id}` | Required | Look up a single payment by its numeric ID |
| `GET` | `/api/payments/search?transaction_ref=...` | Required | Search payments by reference (see "Search by transaction reference" below) |
| `GET` | `/api/customers/{id}/payments` | Required | List a customer's payment history, paginated |
| `GET` | `/health` | None | Liveness + database reachability check |

Validation is enforced at the request boundary via Pydantic (required
fields, string length limits matching the schema's `VARCHAR` sizes, `amount
> 0` with 2 decimal places). Errors map to:

- `422` — request body fails schema validation (missing/invalid fields)
- `404` — referenced customer or payment does not exist
- `409` — `customer_ref` already exists (unique constraint violation)
- `503` — `/health` reports the database is unreachable
- `500` — any unexpected error (logged server-side; response body never
  leaks internals)

`GET /api/customers/{id}/payments` accepts `limit` (default 20, capped at
100 via `PAYMENTS_PAGE_SIZE_MAX`) and `offset` query parameters, and returns
`has_more` instead of a total count, so a customer with a very large
transaction history doesn't force a full `COUNT(*)` scan on every request.

## Authentication

A single shared API key, checked via the `X-API-Key` header on every
`/api/*` request (`app/auth.py`, applied per-router in `main.py`). No user
accounts, sessions, tokens, or OAuth — deliberately the simplest mechanism
that still requires a caller to present a credential before touching
customer/payment data. `/health` stays unauthenticated so it still works as
a plain liveness/readiness check for load balancers/orchestrators.

- Missing or wrong key → `401` with `{"detail": "Invalid or missing API key"}`
- Set the real value via `API_KEY` in `.env` (see `.env.example`); it is
  never hard-coded or committed
- The frontend has an "API Key" field (stored only in that browser's
  `localStorage`) that attaches the header to every request it makes

## Search by transaction reference

`GET /api/payments/search?transaction_ref=TXN000123` — a search/collection
endpoint, distinct from `GET /api/payments/{id}`. Returns `200` with
`{"query_ref": ..., "count": 0, "items": []}` when nothing matches (not
`404` — there's no single resource being fetched, so an empty result set is
a normal, successful search outcome). `transaction_ref` has no uniqueness
constraint in `database/schema.sql`, and the Objective 1 seed data
intentionally contains duplicates (see
`sql/04_duplicate_transaction_references.sql`), so this endpoint returns
**every** matching row, not just the first one found.

## Why no ORM

Every query lives in `app/models/*.py` as plain, parameterized SQL executed
through `psycopg2`, against the existing `database/schema.sql` structure
supplied in Objective 1. Parameters are always passed positionally
(`%s` placeholders) — never string-interpolated — to prevent SQL injection.

## `app/schemas/` vs. `database/schema.sql` — these are not the same thing

`database/schema.sql` (Objective 1) is the **database schema** — the actual
`CREATE TABLE` DDL for `customers`, `transactions`, and `callbacks`. It is
supplied by the assessment and is intentionally left unmodified; MiniPay
does not add, drop, or alter any table or column in it.

`app/schemas/customer_schema.py` and `app/schemas/payment_schema.py` are
something different: Pydantic **request/response models** that live only in
the API layer. They validate what an HTTP client is allowed to send (e.g.
`amount` must be a positive number with at most 2 decimal places,
`transaction_ref` at most 50 characters) and shape what the API returns as
JSON. They mirror the column constraints already present in
`database/schema.sql` so bad input is rejected before it ever reaches a SQL
statement, but they are ordinary Python classes, not a second copy of the
database schema, and they do not run any DDL. "Schema" is just an
overloaded word here — one is a database structure, the other is an API
input/output contract.

## Performance note: `transactions.customer_id` is intentionally left unindexed

`transactions.customer_id` is a foreign key, and PostgreSQL does not
automatically index foreign key columns. `GET /api/customers/{id}/payments`
therefore runs as a full sequential scan of `transactions` today. This is
left as-is on purpose: identifying and fixing exactly this kind of
slow-as-volume-grows access pattern is the subject of
`investigation/INCIDENT-003-RCA.md` (see
`paysys-implementation-l2-assessment-main/incidents/INCIDENT-003.md`), so no
supplementary index is added here in Objective 2.

## Setup and run (local, no container)

```bash
cd MiniPay/backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with the real DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD
# from the database set up in sql/REPRODUCIBLE.md, and set a real API_KEY
# (e.g. `openssl rand -hex 32`)

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Serve the frontend independently (any static file server works):

```bash
cd MiniPay/frontend
python -m http.server 8020
# open http://127.0.0.1:8020 in a browser, then paste the same API_KEY
# into the "API Key" field before using any form
```

Edit `frontend/js/config.js` if the API is not running at
`http://127.0.0.1:8000`.

## Setup and run (containerized)

See `MiniPay/REPRODUCIBLE.md` for the full, placeholder-based Linux steps
to build and run the backend API in Docker against the existing database.

## Verified locally

All 6 endpoints were exercised against the live seeded database during
development: customer creation (including a duplicate `customer_ref`
returning `409` and a missing field returning `422`), payment creation
(including an unknown `customer_id` returning `404` and a non-positive
`amount` returning `422`), payment lookup by ID (including an unknown ID
returning `404`), and search by `transaction_ref` (including a duplicated
reference correctly returning both matches, and an unmatched reference
returning `200` with an empty list). Authentication was verified directly:
no key → `401`, wrong key → `401`, correct key → success; `/health`
reachable with no key at all. See `tests/api/RESULT.md` and
`tests/ui/Report.md` for the full automated-test evidence.
