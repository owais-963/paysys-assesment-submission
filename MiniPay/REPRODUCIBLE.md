# MiniPay: Containerized Build and Run (Linux)

Reproducible steps to build the MiniPay backend API into a Docker image and
run it as a container on a Linux host, connecting to the same PostgreSQL
database set up and seeded in Objective 1 (`sql/REPRODUCIBLE.md`). Replace
every variable value in Step 1 with real values before running — no real
credentials or addresses are included here.

The frontend is static HTML/JS and is not containerized here; it can be
served by any static file server (see `MiniPay/README.md`).

## Prerequisites

```bash
docker --version
```
- Confirms Docker Engine is installed and the current shell can reach it.
  Install it first (e.g. via your distribution's package manager or
  Docker's official install script) if this command fails.

## 1. Define variables

Set these once in the shell session; every later command reuses them.

```bash
export REPO_ROOT=<REPO_ROOT>
export DB_HOST=<DB_HOST>
export DB_PORT=<DB_PORT>
export DB_NAME=<DB_NAME>
export DB_USER=<DB_USER>
export DB_PASSWORD=<DB_PASSWORD>
export MINIPAY_IMAGE=minipay-api:latest
export MINIPAY_CONTAINER=minipay-api
export MINIPAY_PORT=8000
```
- `REPO_ROOT` — absolute path to this repository on the Linux host.
- `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` — connection
  details for the existing PostgreSQL database from `sql/REPRODUCIBLE.md`.
- `MINIPAY_IMAGE` — name:tag to give the built image.
- `MINIPAY_CONTAINER` — name to give the running container.
- `MINIPAY_PORT` — host port the API will be reachable on.

## 2. Build the image

```bash
cd "$REPO_ROOT/MiniPay/backend"
docker build -t "$MINIPAY_IMAGE" .
```
- `cd .../MiniPay/backend` — moves into the directory containing the
  `Dockerfile`, `requirements.txt`, and `app/` source.
- `docker build -t $MINIPAY_IMAGE .` — builds the image from the
  `Dockerfile` in the current directory, installing dependencies from
  `requirements.txt` and copying in the application code. `.dockerignore`
  excludes the local virtualenv, `__pycache__`, and any local `.env` file
  from the build context, so no local secrets or artifacts end up in the
  image.

## 3. Run the container

```bash
docker run -d \
  --name "$MINIPAY_CONTAINER" \
  --network host \
  -e DB_HOST="$DB_HOST" \
  -e DB_PORT="$DB_PORT" \
  -e DB_NAME="$DB_NAME" \
  -e DB_USER="$DB_USER" \
  -e DB_PASSWORD="$DB_PASSWORD" \
  -e API_HOST=0.0.0.0 \
  -e API_PORT="$MINIPAY_PORT" \
  -e CORS_ALLOW_ORIGINS="*" \
  -e PAYMENTS_PAGE_SIZE_DEFAULT=20 \
  -e PAYMENTS_PAGE_SIZE_MAX=100 \
  "$MINIPAY_IMAGE"
```
- `docker run -d` — starts the container in the background (detached).
- `--name $MINIPAY_CONTAINER` — gives the container a stable name for later
  `docker logs` / `docker stop` commands.
- `--network host` — runs the container on the host's own network stack,
  so if PostgreSQL is reachable at `127.0.0.1:<DB_PORT>` on this Linux host
  (as set up in `sql/REPRODUCIBLE.md`), the container can reach it the same
  way, with no extra Docker networking/DNS setup. If the database instead
  runs on a separate host or in its own container/network, replace this
  with normal port publishing (`-p $MINIPAY_PORT:8000`) and point `DB_HOST`
  at that database's actual reachable address instead.
- `-e ...` — passes configuration into the container as environment
  variables (matching `MiniPay/backend/.env.example`), never baked into the
  image itself.

## 4. Verify the container is healthy

```bash
docker ps --filter "name=$MINIPAY_CONTAINER"
curl -s http://127.0.0.1:$MINIPAY_PORT/health
```
- `docker ps --filter ...` — confirms the container is running and shows
  its status.
- `curl .../health` — calls the API's health endpoint; expect
  `{"status":"ok","db":"reachable"}` once the database connection succeeds.

## 5. Inspect logs

```bash
docker logs -f "$MINIPAY_CONTAINER"
```
- Streams the container's stdout/stderr, showing FastAPI/uvicorn startup
  messages and any request or error logging emitted by the app.

## 6. Stop and remove the container

```bash
docker stop "$MINIPAY_CONTAINER"
docker rm "$MINIPAY_CONTAINER"
```
- `docker stop` — sends a graceful shutdown signal to the running
  container.
- `docker rm` — removes the stopped container so the name can be reused on
  the next `docker run`.

## Notes

- No credentials or database addresses are hard-coded in the `Dockerfile`
  or the image; they are supplied at `docker run` time via `-e` flags (or
  an env file passed with `--env-file`), matching the placeholder pattern
  used in `sql/REPRODUCIBLE.md`.
- The frontend is intentionally not containerized in this step — it is
  static HTML/JS meant to be served independently (see "Setup and run
  (local, no container)" in `MiniPay/README.md`); update
  `frontend/js/config.js` to point at wherever this container is reachable.
- This Dockerfile builds the API only. Objective 5 (Kubernetes) is expected
  to reuse this same image rather than redefine how the app is built.
