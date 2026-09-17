# Database Setup, Seed Generation, and Seeding (Linux)

This document describes the exact, repeatable steps to stand up a PostgreSQL
database, generate the synthetic seed data using the supplied generator, and
load that data into the database. Commands are written for a Linux host.
Replace every variable value in Step 3 with real values before running — no
real credentials or addresses are included here.

Source artifacts (supplied, not modified):
- Schema: `paysys-implementation-l2-assessment/database/schema.sql`
- Generator: `paysys-implementation-l2-assessment/database/generate_data.py`

## 1. Install PostgreSQL client/server tooling

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-client python3
```
- `apt-get update` — refreshes the package index so the next install pulls current package metadata.
- `apt-get install postgresql postgresql-client python3` — installs a local PostgreSQL server, the `psql` CLI client used to run SQL files, and Python 3 (required to run `generate_data.py`).

> If PostgreSQL already runs elsewhere (a managed instance, container, etc.), skip installing the `postgresql` server package and only install `postgresql-client` plus `python3`.

## 2. Start the PostgreSQL service (only if running a local server)

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql
```
- `systemctl enable postgresql` — configures the service to start automatically on boot.
- `systemctl start postgresql` — starts the PostgreSQL service now.
- `systemctl status postgresql` — confirms the service is active/running before proceeding.

## 3. Define connection variables

Set these once in the shell session before creating the role/database. Every
later step reuses these variables instead of repeating literal values.

```bash
export DB_HOST=<DB_HOST>
export DB_PORT=<DB_PORT>
export DB_NAME=<DB_NAME>
export DB_USER=<DB_USER>
export DB_PASSWORD=<DB_PASSWORD>
export REPO_ROOT=<REPO_ROOT>
```
- `DB_HOST` — database server hostname/IP.
- `DB_PORT` — database server port (PostgreSQL default is 5432).
- `DB_NAME` — target database name.
- `DB_USER` — database role/user used to connect.
- `DB_PASSWORD` — password for `DB_USER`.
- `REPO_ROOT` — absolute path to this repository on the Linux host.

## 4. Create the database and role

```bash
sudo -u postgres psql -c "CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
```
- `sudo -u postgres psql -c "CREATE ROLE ..."` — runs a single SQL statement as the default `postgres` superuser to create a login role with a password, used later to connect as an application/test user.
- `sudo -u postgres psql -c "CREATE DATABASE ..."` — creates the target database and assigns the new role as its owner.

## 5. Verify connectivity as the new role

```bash
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;"
```
- Connects using the new role's credentials and runs a trivial query, confirming host/port/user/database/password are all correct before loading schema or data.

## 6. Apply the schema

```bash
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -f "$REPO_ROOT/paysys-implementation-l2-assessment/database/schema.sql"
```
- Executes the supplied DDL file, creating the `customers`, `transactions`, and `callbacks` tables (with their constraints) in `$DB_NAME`.

## 7. Generate the seed data file

```bash
cd "$REPO_ROOT/paysys-implementation-l2-assessment/database"
python3 generate_data.py > "$REPO_ROOT/sql/seed.sql"
```
- `cd .../database` — moves into the directory containing the supplied generator so it runs with its expected relative context.
- `python3 generate_data.py > seed.sql` — runs the generator, which deterministically (fixed `random.seed(42)`) emits `BEGIN;` followed by `INSERT` statements for 1,000 customers, 50,000 transactions, and their associated callbacks, then `COMMIT;`, redirecting all of that output into `seed.sql` for later loading.

## 8. Load the seed data into the database

```bash
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -f "$REPO_ROOT/sql/seed.sql"
```
- Executes the generated INSERT script inside a single transaction (`BEGIN`/`COMMIT` as emitted by the generator), populating `customers`, `transactions`, and `callbacks`.

## 9. Verify the seed loaded correctly

```bash
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT
     (SELECT COUNT(*) FROM customers)    AS customers,
     (SELECT COUNT(*) FROM transactions) AS transactions,
     (SELECT COUNT(*) FROM callbacks)    AS callbacks;"
```
- Runs count checks against all three tables to confirm the expected row volumes were inserted (1,000 customers and 50,000 transactions per the generator's constants, with a variable number of callbacks depending on transaction status).

## Notes

- The generator uses a fixed random seed (`42`), so re-running step 7 on an unchanged script produces byte-identical output — safe to regenerate `seed.sql` at any time.
- The generator intentionally introduces a small number of duplicate `transaction_ref` values (every 5,000th transaction reuses the previous reference) — this is expected and used later for the duplicate-reference investigation query, not a bug to fix here.
- No credentials, hostnames, or ports are hard-coded above; the variables in Step 3 are exported once per shell session and are not committed to version control.
