# Linux Operational Evidence

This document is the reproducible command set for Objective 7
(`requirements/01-linux-git.md`). Each section names the exact command(s)
to run on the target Linux host and explains what the output shows. The
commands were written and reviewed on this (non-Linux) development
environment; **actual output has not been captured yet** and is left as an
explicit placeholder below each command, to be pasted in from a real run
on the target Linux host rather than fabricated here.

> Every output block below reads `<PASTE OUTPUT HERE>` until filled in.
> Do not replace a placeholder with invented output — leave it as-is if a
> command hasn't been run yet.

## 1. OS / kernel identification

```bash
uname -a
cat /etc/os-release
```
- `uname -a` — kernel name, version, and architecture.
- `/etc/os-release` — distribution name and version.

```
<PASTE OUTPUT HERE>
```

## 2. CPU, memory, and disk utilization

```bash
uptime
nproc
free -h
df -h
```
- `uptime` — load averages (1/5/15 min) alongside how long the system has
  been up.
- `nproc` — number of available CPU cores, for interpreting the load
  averages above (a load of 4 means something different on a 2-core vs.
  16-core host).
- `free -h` — total/used/available memory and swap, human-readable.
- `df -h` — used/available space per mounted filesystem.

```
<PASTE OUTPUT HERE>
```

## 3. Listening ports and relevant processes

```bash
ss -tulpn
```
(`netstat -tulpn` as a fallback if `ss` isn't available.)
- Lists every TCP/UDP socket in `LISTEN` state, the local address/port, and
  the PID/process name bound to it — confirms the MiniPay API (and
  PostgreSQL, if colocated) are actually listening where expected, and
  surfaces anything unexpected also listening on the host.

```
<PASTE OUTPUT HERE>
```

## 4. DNS / network connectivity checks

```bash
getent hosts <DB_HOST>
curl -v --max-time 5 http://127.0.0.1:8000/health
curl -v --max-time 5 <MINIPAY_API_PUBLIC_URL>/health
```
- `getent hosts` — confirms the configured database hostname actually
  resolves from this host (DNS working, or `/etc/hosts` entry present).
- The two `curl` calls — confirm the API is reachable both locally (loop
  back) and via whatever address external callers would actually use;
  comparing the two isolates "the process isn't listening" from "something
  in front of it (firewall/proxy/security group) is blocking external
  access."

```
<PASTE OUTPUT HERE>
```

## 5. Application/container logs

```bash
# If running via systemd:
journalctl -u <minipay-service-name> -n 200 --no-pager

# If running via Docker:
docker logs --tail 200 <minipay-container-name>

# If running via Kubernetes (see kubernetes/USAGE.md for the full reference):
kubectl logs -n minipay -l app=minipay-api --all-containers --tail=200
```
- Pulls the most recent application log lines from whichever supervisor
  is actually running MiniPay on this host, for correlating a reported
  incident against what the application itself recorded at that time.

```
<PASTE OUTPUT HERE>
```

## 6. Identifying the process consuming the most memory

```bash
ps -eo pid,ppid,%mem,%cpu,cmd --sort=-%mem | head -n 11
```
- Lists the top 10 processes by resident memory share (`%mem`), with PID,
  parent PID, CPU share, and the command line — the starting point for
  "why is this host low on memory."

```
<PASTE OUTPUT HERE>
```

## 7. Disk usage by directory

```bash
du -h --max-depth=1 / 2>/dev/null | sort -rh | head -n 20
```
- Summarizes disk usage one level below `/`, sorted largest-first, so a
  full disk can be traced to the specific top-level directory responsible
  before drilling down further (`du -h --max-depth=1 <that directory>`,
  repeated) — usually logs, container image layers, or a growing data
  directory.

```
<PASTE OUTPUT HERE>
```

## 8. Simple, repeatable health-check script

`evidence/health-check.sh` (checked into this repository, executable,
re-runnable on demand):

```bash
chmod +x evidence/health-check.sh
./evidence/health-check.sh
```

The script itself checks: OS/kernel identification, the MiniPay API's
`/health` endpoint (via `curl`, with a timeout), disk usage against a
configurable threshold (default 90%, flagged with `WARNING`), memory
(`free -h`), the top memory-consuming process, and listening ports — then
exits `0` if everything looked fine or `1` if any check failed/warned, so
it can be wired into a monitoring cron job or CI step directly.

```
<PASTE OUTPUT HERE>
```

## Investigation playbooks

Brief, on the assumption that logs/metrics from the sections above are
already being collected — these describe the next step once a symptom is
reported, not a one-off command.

### High CPU

1. `top`/`htop` (or `ps -eo pid,%cpu,cmd --sort=-%cpu | head`) to identify
   the specific process, not just "the host is at 100%."
2. If it's the MiniPay API process: check whether it correlates with a
   traffic spike (application logs, `ss -tan | grep :8000 | wc -l` for
   connection count) versus a single request stuck in a loop (a request
   that's been running far longer than the others).
3. If it's PostgreSQL: `SELECT * FROM pg_stat_activity WHERE state =
   'active';` to find the specific slow/runaway query, then `EXPLAIN
   ANALYZE` it (see `sql/PERFORMANCE.md` for the same technique applied to
   a real slow query in this project).
4. Check for a sudden deploy/config change immediately before the CPU
   spike started (correlate with `journalctl`/deploy logs), rather than
   assuming it's purely load-driven.

### Low disk space

1. `df -h` to confirm which filesystem is actually full (not necessarily
   `/`).
2. `du -h --max-depth=1 <mount point>` repeated downward (per section 7
   above) to find the specific directory.
3. Common culprits worth checking specifically: log files that were never
   rotated (`/var/log`), Docker image/layer buildup (`docker system df`,
   `docker image prune`), and a database's own growth (`\l+` in `psql` to
   see per-database size).
4. Free space carefully — never delete a file a running process still has
   open without checking first (`lsof <file>`), since that can hide the
   space usage without freeing it until the process exits.

### Unreachable API

1. Is the process even running? (`ps aux | grep uvicorn`, or the
   Docker/Kubernetes equivalent from section 5.)
2. Is it listening on the expected port? (Section 3, `ss -tulpn`.)
3. Can it be reached locally but not externally? (Section 4's two `curl`
   calls — isolates the process itself from a firewall/proxy/security
   group/DNS problem in front of it.)
4. `curl .../health` specifically: does it return `503` (the process is up
   but its database dependency is down — see `app/routes/health_routes.py`)
   or does the connection fail entirely (the process isn't listening, or
   nothing is in front of it to route the request)? These have different
   root causes and different fixes.
5. Check `MiniPay/backend` logs (section 5) for a crash immediately before
   the reported outage window.

### A process that keeps terminating (crash-looping)

1. Check exit status/restart count: `systemctl status <service>` (for
   `Restart=`/`NRestarts`), `docker inspect --format='{{.State}}'
   <container>`, or `kubectl get pods -n minipay` (look at `RESTARTS`) and
   `kubectl describe pod <pod> -n minipay` (the `Last State` and its
   `Reason`, e.g. `OOMKilled`).
2. Read the *previous* run's logs, not the current (empty/just-started)
   one: `journalctl -u <service> -n 200` naturally includes prior runs;
   `docker logs <container>` after a restart still shows the last run's
   output; `kubectl logs <pod> -n minipay --previous` explicitly targets
   the crashed instance rather than the newly restarted one.
3. `OOMKilled` specifically points back to section 6 (memory) and to
   whether `resources.limits.memory` (see `kubernetes/deployment.yaml`) is
   set too low for actual usage, rather than a genuine application bug.
4. If it crashes immediately on every start (not after running a while),
   suspect a configuration/environment problem (missing/invalid env var --
   see `MiniPay/backend/app/config.py`'s `_require()` checks) over a
   runtime bug, since it never gets far enough to hit one.
