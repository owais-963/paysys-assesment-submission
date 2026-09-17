# MiniPay Support Tool: Reproducible Setup and Run (Linux)

Reproducible steps to set up and run `support_tool.py` on a Linux host,
against the same PostgreSQL database set up and seeded in Objective 1
(`sql/REPRODUCIBLE.md`). Replace every placeholder value before running —
no real credentials or addresses are included here. See `USAGE.md` for
what each file does and `GUIDE.md` for command-by-command usage.

## 1. Define variables

```bash
export REPO_ROOT=<REPO_ROOT>
export DB_HOST=<DB_HOST>
export DB_PORT=<DB_PORT>
export DB_NAME=<DB_NAME>
export DB_USER=<DB_USER>
export DB_PASSWORD=<DB_PASSWORD>
```
- `REPO_ROOT` — absolute path to this repository on the Linux host.
- `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` — connection
  details for the existing database from `sql/REPRODUCIBLE.md`.

## 2. Create a virtual environment and install dependencies

```bash
cd "$REPO_ROOT/python"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- `venv` — isolates this tool's dependencies from the system Python.
- `pip install -r requirements.txt` — installs `psycopg2-binary`,
  `python-dotenv`, and `requests` (runtime dependencies only).

## 3. Configure the tool

```bash
cp "$REPO_ROOT/python/.env.example" "$REPO_ROOT/python/.env"
sed -i \
  -e "s/<DB_HOST>/$DB_HOST/" \
  -e "s/<DB_PORT>/$DB_PORT/" \
  -e "s/<DB_NAME>/$DB_NAME/" \
  -e "s/<DB_USER>/$DB_USER/" \
  -e "s/<DB_PASSWORD>/$DB_PASSWORD/" \
  "$REPO_ROOT/python/.env"
```
- `cp .env.example .env` — starts from the placeholder template.
- `sed -i` — substitutes the real connection values from Step 1 into the
  local, git-ignored `.env` file (`python/.env` is never committed — see
  `.gitignore`).
- `API_BASE_URL` is left unset by default in `.env.example`; set it in
  `python/.env` only if you want `--health` to also check a running
  MiniPay API instance (see `MiniPay/README.md` for running that API).

## 4. Run the tool

```bash
cd "$REPO_ROOT/python"
source .venv/bin/activate

python support_tool.py --transaction TXN000123
python support_tool.py --transaction TXN000123 --json
python support_tool.py --health
python support_tool.py --stuck-summary
```
- Runs the diagnostic report for a given reference (text, then JSON), the
  health check, and the stuck/failed summary. Replace `TXN000123` with a
  real reference from the seeded database (see `sql/REPRODUCIBLE.md` for
  how that data was generated).
- Exit codes are printed to the shell via `$?`; see `README.md`/`GUIDE.md`
  for the full table.

## 5. Run the unit tests

```bash
cd "$REPO_ROOT/python"
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```
- `requirements-dev.txt` adds `pytest` on top of the runtime dependencies.
- `python -m pytest` runs `tests/test_diagnostics.py` and
  `tests/test_report.py` — 19 tests, none of which need a database
  connection (see `USAGE.md` for why).

## Notes

- No credentials or addresses are hard-coded in any file under `python/`;
  `python/.env` (created in Step 3) holds the real values locally and is
  excluded from version control.
- `sed -i` in Step 3 only touches the local `.env` file, never
  `.env.example` — re-running Step 3 from a clean checkout is always safe.
