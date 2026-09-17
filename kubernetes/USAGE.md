# Kubernetes Manifests: Purpose, Behavior, and Requirements Mapping

This document explains what each file in `kubernetes/` does and why it's
written the way it is, then maps every requirement from
`requirements/03-kubernetes-rancher.md` to the specific manifest(s) that
satisfy it — so nothing on that checklist is left implicit.

## Apply order

```
namespace.yaml → configmap.yaml → secrets.yaml → postgres-statefulset.yaml → deployment.yaml → service.yaml → hpa.yaml
```

(See `kubernetes/REPRODUCIBLE.md` for the actual commands.)

## File-by-file

### `namespace.yaml`

Creates the `minipay` namespace that every other resource in this directory
is scoped into (`metadata.namespace: minipay`). The supplied
`starter/kubernetes/broken-api.yaml` referenced this namespace without ever
defining it (see `investigation/kubernetes-findings.md`, finding #7) — on a
fresh cluster, applying that file alone fails with
`namespaces "minipay" not found`. This file exists purely to close that
gap and make the manifest set self-contained.

### `configmap.yaml`

A `ConfigMap` named `minipay-api-config` holding every **non-secret**
setting the application needs: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
connection pool sizing, the API's own host/port, CORS, and pagination
limits. These map 1:1 to `MiniPay/backend/.env.example`, minus the password.

It's consumed two ways:
- `deployment.yaml` pulls the whole thing in via `envFrom.configMapRef`, so
  the container gets every key as an environment variable without listing
  them one by one.
- `postgres-statefulset.yaml` reads two individual keys
  (`DB_NAME`, `DB_USER`) via `valueFrom.configMapKeyRef` to set
  `POSTGRES_DB`/`POSTGRES_USER` on the database container — so the API and
  the database always agree on the same database name and username,
  defined in exactly one place.

### `secrets.yaml`

A `Secret` named `minipay-db-credentials` holding two values: `DB_PASSWORD`
and `API_KEY` (the latter added once MiniPay's API started requiring a
shared-secret `X-API-Key` on every `/api/*` request — see
`MiniPay/README.md`). The committed file contains only the literal
placeholder `CHANGE_ME` for each, never a real credential — the header
comment explains how to either edit an untracked local copy or create the
Secret imperatively with `kubectl create secret generic ... --from-literal=...`
instead, so real values never have to touch this repository at all.

`DB_PASSWORD` is consumed two ways, both reading the *same* key so the API
and the database can never authenticate with different passwords:
- `deployment.yaml`: `env: DB_PASSWORD` via `valueFrom.secretKeyRef`.
- `postgres-statefulset.yaml`: `env: POSTGRES_PASSWORD` via
  `valueFrom.secretKeyRef` against the identical `minipay-db-credentials` /
  `DB_PASSWORD` reference.

`API_KEY` is consumed once, by `deployment.yaml`'s `env: API_KEY`, and read
by the application itself (`app/config.py`) to validate the `X-API-Key`
header on incoming requests.

### `postgres-statefulset.yaml`

Two resources in one file:

1. A **headless Service** (`clusterIP: None`) named `minipay-db`. Headless
   because a `StatefulSet`'s pods need individually addressable, stable
   DNS names (`minipay-db-0.minipay-db.minipay.svc.cluster.local`), not a
   single load-balanced ClusterIP — there's only one database pod here, but
   the headless Service is also what makes `DB_HOST=minipay-db` (from the
   ConfigMap) resolve at all inside the cluster, closing finding #9 from
   `investigation/kubernetes-findings.md` (the starter manifest assumed
   this hostname existed without anything defining it).
2. A **StatefulSet** (not a Deployment) running `postgres:16`, because a
   database needs a stable identity and stable storage tied to that
   identity across restarts/rescheduling — a `Deployment`'s interchangeable,
   identical-replica model is the wrong fit for stateful data.
   - `volumeClaimTemplates` provisions a dedicated `PersistentVolumeClaim`
     (2Gi, `ReadWriteOnce`) per pod, so data on disk survives pod restarts,
     rescheduling to a different node, and even the pod being deleted and
     recreated — this is the "persistent database storage" requirement.
   - `readinessProbe`/`livenessProbe` both run `pg_isready` against the
     database itself (not just "is the process alive") — a database that's
     up but not yet accepting connections correctly stays out of rotation.
   - `resources.requests`/`limits` reserve a guaranteed CPU/memory share
     and cap the maximum.

### `deployment.yaml`

The corrected `minipay-api` `Deployment`. This is the direct fix for
findings #1–#6 and #8 in `investigation/kubernetes-findings.md`:

| Finding | Fix in this file |
|---|---|
| #2 readiness probe hit the wrong port (8081) | `readinessProbe.httpGet.port: 8000` |
| #4 `image: YOUR_IMAGE_HERE` placeholder | Real (registry-placeholder) image reference with an explicit tag, plus a comment telling the operator exactly what to replace it with |
| #5 only `DB_HOST` was supplied; app requires more | `envFrom.configMapRef` (all non-secret settings) + `env.DB_PASSWORD`/`env.API_KEY` from the Secret |
| #6 manifest assumed port 8080; the built image listens on 8000 | `containerPort`, `readinessProbe`, and `livenessProbe` all use `8000`, matching `MiniPay/backend/Dockerfile`'s `CMD` |
| #8 no resource requests/limits | `resources.requests`/`limits` added |

`replicas: 2` plus the `readinessProbe` together mean a rolling update or a
single crashed pod never drops the API to zero available replicas.

### `service.yaml`

The corrected `minipay-api` `Service`. Fixes findings #1 and #3: `selector`
now matches the Deployment's actual pod label (`app: minipay-api`, not the
starter's `minipay-backend`), and `targetPort` now matches the container's
real port (`8000`, not `8081`). Exposes port `80` inside the cluster,
forwarding to `8000` on whichever pod it selects.

### `hpa.yaml`

A `HorizontalPodAutoscaler` (`autoscaling/v2`) targeting the `minipay-api`
`Deployment`, scaling between 2 and 5 replicas on 70% average CPU
utilization. Not explicitly named in the requirements checklist, but
included because it was asked for directly; it depends on the cluster
running `metrics-server` (noted in the file itself), which is worth
checking (`kubectl top pods -n minipay`) if replica count doesn't respond
to load.

## Requirements mapping

Each row is a bullet from `requirements/03-kubernetes-rancher.md`:

| Requirement | Satisfied by | Detail |
|---|---|---|
| Deployments | `deployment.yaml` | `minipay-api` `Deployment`, 2 replicas |
| StatefulSets | `postgres-statefulset.yaml` | `minipay-db` `StatefulSet`, 1 replica |
| Services | `service.yaml`, `postgres-statefulset.yaml` | `minipay-api` (ClusterIP) and `minipay-db` (headless) |
| ConfigMaps | `configmap.yaml` | `minipay-api-config`, consumed by both the API and the DB |
| Secrets without committing real values | `secrets.yaml` | `DB_PASSWORD`/`API_KEY` placeholders `CHANGE_ME`; header comment documents the imperative `kubectl create secret` alternative |
| Readiness and liveness probes | `deployment.yaml` (`httpGet /health` on 8000), `postgres-statefulset.yaml` (`pg_isready` exec probes) | Both resources define both probe types |
| CPU/memory requests and limits | `deployment.yaml`, `postgres-statefulset.yaml` | Every container has `resources.requests` and `resources.limits` |
| Persistent database storage | `postgres-statefulset.yaml` | `volumeClaimTemplates`, 2Gi `ReadWriteOnce` PVC per pod |
| Namespaces | `namespace.yaml` | `minipay`, referenced by every other resource |
| Restart/rollout procedures | This file, "Restart and rollout procedures" section below | Documented commands, not a manifest |
| Log inspection/troubleshooting | This file, "Log inspection and troubleshooting" section below | Documented commands, not a manifest |

The last two rows are procedures, not YAML — they're documented here
rather than as a manifest file, since there's nothing to apply.

## Restart and rollout procedures

```bash
# Roll every pod in the Deployment (e.g. after updating a ConfigMap/Secret,
# which does not automatically trigger a restart on its own):
kubectl rollout restart deployment/minipay-api -n minipay

# Watch a rollout (new image, new replica count, or the restart above)
# until it finishes or fails:
kubectl rollout status deployment/minipay-api -n minipay

# See prior revisions of the Deployment:
kubectl rollout history deployment/minipay-api -n minipay

# Roll back to the previous revision if a rollout is bad:
kubectl rollout undo deployment/minipay-api -n minipay

# Scale manually (the HPA normally does this automatically between 2 and 5):
kubectl scale deployment/minipay-api -n minipay --replicas=3

# Restart the database StatefulSet's single pod (e.g. to pick up a changed
# Secret) -- StatefulSet pods restart one at a time, preserving order:
kubectl rollout restart statefulset/minipay-db -n minipay
```

## Log inspection and troubleshooting

```bash
# Overall workload status at a glance:
kubectl get deployments,statefulsets,pods,svc,pvc,hpa -n minipay

# Why is a specific pod not Ready/Running? Shows events (image pull errors,
# probe failures, scheduling failures) at the bottom of the output:
kubectl describe pod <pod-name> -n minipay

# Tail logs from a running pod:
kubectl logs -f <pod-name> -n minipay

# Logs from a crashed container's last run (essential for CrashLoopBackOff):
kubectl logs <pod-name> -n minipay --previous

# Logs from every minipay-api pod at once, without naming them individually:
kubectl logs -n minipay -l app=minipay-api --all-containers --prefix -f

# Cluster-level events for the namespace, most recent last -- useful for
# catching probe failures, OOMKills, and scheduling issues in one place:
kubectl get events -n minipay --sort-by=.lastTimestamp

# Confirm the Service actually has endpoints (catches a selector/port
# mismatch like the ones in investigation/kubernetes-findings.md before it
# becomes a mystery "connection refused"):
kubectl get endpoints minipay-api -n minipay

# Get a shell inside a running container for direct inspection:
kubectl exec -it <pod-name> -n minipay -- sh

# Confirm the PVC bound to real storage (persistent storage requirement):
kubectl get pvc -n minipay
```
