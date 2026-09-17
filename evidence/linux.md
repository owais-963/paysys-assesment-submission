# Linux Operational Evidence

This document is the reproducible command set for Objective 7
(`requirements/01-linux-git.md`). Each section names the exact command(s)
to run on the target Linux host and explains what the output shows.

**Target host:** `instance-20260917-081300`, a GCP VM (`k3s`/Ubuntu-based
kernel `7.0.0-1011-gcp`). Sections 1, 2 (disk/memory), 3, 6, and 8 below
contain real output captured on 2026-09-17/18 from that host, via
`evidence/health-check.sh`. Sections 2 (CPU-specific: `uptime`/`nproc`),
4, 5, and 7 have not been run yet on that host and are still left as an
explicit `<PASTE OUTPUT HERE>` placeholder — not fabricated.

> A `<PASTE OUTPUT HERE>` placeholder means that specific command has not
> been run on the target host yet. Do not replace one with invented
> output.

## 1. OS / kernel identification

```bash
uname -a
cat /etc/os-release
```
- `uname -a` — kernel name, version, and architecture.
- `/etc/os-release` — distribution name and version.

```
$ uname -a
Linux instance-20260917-081300 7.0.0-1011-gcp #11-Ubuntu SMP PREEMPT Tue Aug 11 17:32:26 UTC 2026 x86_64 GNU/Linux
```

`/etc/os-release` has not been captured yet on this host:

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

`uptime` and `nproc` have not been captured yet on this host:

```
<PASTE OUTPUT HERE>
```

`free -h` and `df -h`, captured 2026-09-18 via `evidence/health-check.sh`
(full run in section 8):

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.6Gi        10Gi       125Mi       3.9Gi        13Gi
Swap:             0B          0B          0B

$ df -h
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        58G  5.3G   52G  10% /
tmpfs           7.9G  1.1M  7.9G   1% /dev/shm
tmpfs           3.2G  2.6M  3.2G   1% /run
efivarfs        256K   32K  220K  13% /sys/firmware/efi/efivars
tmpfs           7.9G   64M  7.8G   1% /tmp
/dev/sda13      989M   86M  837M  10% /boot
/dev/sda15      105M  6.3M   99M   7% /boot/efi
tmpfs           1.6G  8.0K  1.6G   1% /run/user/1003
```
(Root filesystem `/` at 10% used, 52G available. The full `df -h` output
also lists a large number of `overlay`/`tmpfs`/`shm` mounts under
`/run/k3s/containerd/...` — one per running k3s/containerd sandbox on this
host; each shows the same 10%-used overlay on the shared root disk, so
they're omitted here as redundant with the `/` line above. The complete,
unfiltered listing is in the raw log under section 8.)

## 3. Listening ports and relevant processes

```bash
ss -tulpn
```
(`netstat -tulpn` as a fallback if `ss` isn't available.)
- Lists every TCP/UDP socket in `LISTEN` state, the local address/port, and
  the PID/process name bound to it — confirms the MiniPay API (and
  PostgreSQL, if colocated) are actually listening where expected, and
  surfaces anything unexpected also listening on the host.

Captured 2026-09-18 via `evidence/health-check.sh`, TCP `LISTEN` sockets
only (full output, including UDP, is in section 8):

```
Netid  State   Local Address:Port   Process
tcp    LISTEN  127.0.0.1:44589      containerd (pid 6727)
tcp    LISTEN  127.0.0.1:10248      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10249      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10258      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10259      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10256      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10257      k3s-server (pid 7429)
tcp    LISTEN  127.0.0.1:10010      containerd (pid 7457)
tcp    LISTEN  0.0.0.0:8020         python (pid 55957)      <- MiniPay frontend static server
tcp    LISTEN  127.0.0.1:6444       k3s-server (pid 7429)
tcp    LISTEN  0.0.0.0:22           sshd
tcp    LISTEN  127.0.0.1:5432       postgres (pid 26458)    <- MiniPay database
tcp    LISTEN  127.0.0.54:53        systemd-resolve
tcp    LISTEN  127.0.0.53:53        systemd-resolve
tcp    LISTEN  *:6443               k3s-server (pid 7429)    <- Kubernetes API server
tcp    LISTEN  [::]:22              sshd
tcp    LISTEN  *:10250              k3s-server (pid 7429)
```

**Notable at capture time:** PostgreSQL (`5432`) and the MiniPay frontend
static server (`8020`) were both up; **the MiniPay API itself was not
listening on any port** — consistent with section 8's `curl .../health`
failure below. No process was bound to `8000`/`8080` (the ports MiniPay's
backend uses) at capture time.

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

Captured 2026-09-18 via `evidence/health-check.sh` (top 5 shown; full
command uses `head -n 11` for top 10):

```
    PID    PPID %MEM %CPU CMD
   7429       1  4.3  9.1 /usr/local/bin/k3s server
   7457    7429  1.1  0.8 containerd
   9752    9449  0.6  0.0 traefik traefik --entryPoints...
   6968       1  0.5  0.0 /usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock
   9070    8890  0.4  0.5 /metrics-server --cert-dir=/tmp --secure-port=10250 ...
```

The top memory consumer at capture time is `k3s server` (4.3% of 15Gi ≈
~660MB) — expected, since this host runs a full k3s control plane
alongside MiniPay, not MiniPay-specific memory pressure. Neither
PostgreSQL nor a MiniPay API process appears in the top 5 (the API wasn't
running at capture time — see section 3).

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
it can be wired into a monitoring cron job or CI step directly. It also
mirrors its own output to a timestamped file under
`evidence/health-check-logs/` (git-ignored — runtime output, not source)
via `HEALTH_CHECK_LOG_DIR`/`tee`, so a cron/CI-triggered run still leaves
evidence behind without needing its terminal output captured separately.

Real run, captured 2026-09-18 on `instance-20260917-081300`
(`(.venv) root@instance-20260917-081300:.../evidence# bash ./health-check.sh`):

```
== MiniPay host health check: 2026-09-17T22:47:49Z ==
-- OS / kernel --
Linux instance-20260917-081300 7.0.0-1011-gcp #11-Ubuntu SMP PREEMPT Tue Aug 11 17:32:26 UTC 2026 x86_64 GNU/Linux

-- API health (http://127.0.0.1:8000/health) --
curl: (7) Failed to connect to 127.0.0.1 port 8000 after 0 ms: Could not connect to server
API health check FAILED (unreachable or non-200 response)

-- Disk usage --
[df -h output -- see section 2 above for the deduplicated summary;
 full listing includes one overlay/tmpfs/shm mount per running
 k3s/containerd sandbox, all at the same 10% used as the root disk]

-- Memory --
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.6Gi        10Gi       125Mi       3.9Gi        13Gi
Swap:             0B          0B          0B

-- Top memory-consuming process --
[see section 6 above]

-- Listening ports --
[see section 3 above]

== Overall: ISSUES DETECTED (see WARNING/FAILED lines above) ==
```

**Overall: ISSUES DETECTED — expected and explained, not a real incident:**
the script correctly flagged that `http://127.0.0.1:8000/health` was
unreachable, because the MiniPay API process was not running on this host
at the time of this capture (only PostgreSQL and the static frontend
server were up — section 3). This is exactly the kind of failure this
script is designed to catch; it has not yet been re-run with the MiniPay
API actually started on this host to confirm a clean `== Overall: OK ==`
result, which is the natural next step before treating this host's setup
as fully verified.

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
