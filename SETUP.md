# Setup

End-to-end instructions to get the database, MiniPay app, test suites, and
support CLI running on a Linux host. Each step links to the detailed,
placeholder-based `REPRODUCIBLE.md` for that component rather than
duplicating every command here — this file is the sequence to follow, not
a replacement for those documents.

## Prerequisites

- Linux host (the assessment's target environment; see `evidence/linux.md`)
- PostgreSQL 17 (or a compatible version) and its client tools (`psql`)
- Python 3.12 and `pip`
- (Optional, for containerized deployment) Docker
- (Optional, for Kubernetes) `kubectl` and access to a cluster

## 1. Clone the repository

```bash
git clone <this repository's URL>
cd <repository directory>
```

## 2. Set up the database

Follow **`sql/REPRODUCIBLE.md`** in full: install PostgreSQL, create the
database/role, apply `database/schema.sql`, generate `seed.sql` from
`database/generate_data.py`, and load it. This is a hard prerequisite for
every other step below.

## 3. Run the MiniPay API and UI

Follow **`MiniPay/README.md`** ("Setup and run (local, no container)") for
a plain Python/`uvicorn` run, or **`MiniPay/REPRODUCIBLE.md`** to build and
run the same backend as a Docker container. Both need:

- `MiniPay/backend/.env` populated from `.env.example` (database
  connection details from step 2, plus a real `API_KEY` you generate
  yourself — e.g. `openssl rand -hex 32`)
- the static frontend served separately (`python -m http.server` is
  enough), with `frontend/js/config.js` pointing at wherever the API ends
  up running, and the same `API_KEY` pasted into the UI's "API Key" field
  before using any form

Confirm it's up: `curl http://<api-host>:<port>/health` should return
`{"status":"ok","db":"reachable"}`.

## 4. Run the automated test suites

**API tests** (`tests/api/`): install `tests/api/requirements.txt`, set
`MINIPAY_API_BASE_URL` and `MINIPAY_API_KEY` to match the running instance
from step 3, then:

```bash
MINIPAY_API_KEY=<your key> python -m pytest tests/api
```

See `tests/api/TEST_PLAN.md` for what's covered and `tests/api/RESULT.md`
for the last recorded run.

**UI tests** (`tests/ui/`): install `tests/ui/requirements.txt` and
Playwright's browser (`python -m playwright install chromium`, or use
`--browser-channel chrome`/`msedge` against a system browser if outbound
downloads are blocked), set `MINIPAY_UI_BASE_URL`, `MINIPAY_API_BASE_URL`,
and `MINIPAY_API_KEY`, then:

```bash
MINIPAY_API_KEY=<your key> python -m pytest tests/ui --browser-channel chrome
```

See `tests/ui/Report.md` for what's covered, the last recorded run, and
screenshot evidence.

## 5. Set up the support CLI

Follow **`python/REPRODUCIBLE.md`**: its own virtualenv, its own `.env`
(same database connection details as step 2), then:

```bash
cd python
python support_tool.py --transaction TXN000123
python support_tool.py --health
python support_tool.py --stuck-summary
```

See `python/GUIDE.md` for worked examples and `python/USAGE.md` for a live
re-run's actual output.

## 6. Kubernetes deployment (optional)

Follow **`kubernetes/REPRODUCIBLE.md`**: build/push the MiniPay image,
create the namespace, create the `minipay-db-credentials` Secret
(`DB_PASSWORD` + `API_KEY`) imperatively (never commit real values into
`kubernetes/secrets.yaml`), apply the ConfigMap, the database StatefulSet,
load the schema/seed into it, then the API Deployment/Service/HPA. See
`kubernetes/USAGE.md` for what every manifest does and how it maps to the
assessment's requirements, plus restart/rollout and log-inspection
commands.

## 7. Linux evidence and health checks (optional)

`evidence/health-check.sh` is a standalone, repeatable script (OS/kernel,
API health, disk/memory, top memory consumer, listening ports):

```bash
chmod +x evidence/health-check.sh
MINIPAY_API_BASE_URL=<api url> ./evidence/health-check.sh
```

`evidence/linux.md` documents the full command set this script is built
from, plus investigation playbooks for high CPU, low disk space, an
unreachable API, and a crash-looping process.

## Troubleshooting a fresh setup

- **`/health` returns connection refused** — the API process isn't
  running, or isn't listening on the port you're checking. See
  `evidence/linux.md` section 3 (`ss -tulpn`).
- **`/health` returns `{"status":"degraded",...}`** — the API is up but
  can't reach PostgreSQL. Re-check `DB_HOST`/`DB_PORT`/`DB_USER`/
  `DB_PASSWORD` in `MiniPay/backend/.env` against step 2.
- **Every `/api/*` call returns `401`** — missing or wrong `X-API-Key`.
  Confirm `API_KEY` in `.env` matches what you're sending (via `curl -H`,
  the UI's "API Key" field, or `MINIPAY_API_KEY` for the test suites).
- **Test suite exits immediately with a clear message instead of running
  tests** — this is deliberate: both `tests/api/conftest.py` and
  `tests/ui/conftest.py` check reachability and required env vars before
  collecting any test, specifically to avoid dozens of confusing individual
  failures when the real problem is "nothing is running yet."
