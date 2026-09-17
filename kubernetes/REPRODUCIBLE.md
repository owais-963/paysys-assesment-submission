# Kubernetes Deployment: Reproducible Steps (Linux)

Reproducible steps to deploy MiniPay's API and database to a Kubernetes
cluster using the manifests in this directory. Replace every placeholder
value before running — no real registry paths, secrets, or cluster
addresses are included here. See `kubernetes/USAGE.md` for what each file
does and why.

## Prerequisites

```bash
kubectl version --client
kubectl cluster-info
```
- `kubectl version --client` — confirms `kubectl` is installed.
- `kubectl cluster-info` — confirms the current kubeconfig context points
  at a reachable cluster before applying anything to it.

## 1. Define variables

```bash
export REPO_ROOT=<REPO_ROOT>
export KUBE_NAMESPACE=minipay
export MINIPAY_IMAGE=<YOUR_REGISTRY>/minipay-api:<TAG>
export DB_PASSWORD=<REAL_DB_PASSWORD>
export API_KEY=<REAL_API_KEY>
```
- `REPO_ROOT` — absolute path to this repository on the Linux host.
- `KUBE_NAMESPACE` — matches `namespace.yaml`; only needs changing if you
  deliberately rename the namespace everywhere.
- `MINIPAY_IMAGE` — the built-and-pushed image from
  `MiniPay/backend/Dockerfile` (see `MiniPay/REPRODUCIBLE.md` for building
  it), tagged and pushed to a registry the cluster can pull from.
- `DB_PASSWORD` — the real database password. Never written into
  `kubernetes/secrets.yaml`; used only in the imperative command in Step 4.
- `API_KEY` — the real shared secret MiniPay's API requires via
  `X-API-Key` on every `/api/*` request (generate with, e.g.,
  `openssl rand -hex 32`). Same handling as `DB_PASSWORD`.

## 2. Build and push the API image (if not already done)

```bash
cd "$REPO_ROOT/MiniPay/backend"
docker build -t "$MINIPAY_IMAGE" .
docker push "$MINIPAY_IMAGE"
```
- Builds the image per `MiniPay/backend/Dockerfile` and pushes it to the
  registry referenced by `$MINIPAY_IMAGE`, so the cluster can pull it.

## 3. Create the namespace

```bash
kubectl apply -f "$REPO_ROOT/kubernetes/namespace.yaml"
```
- Creates the `minipay` namespace every other resource is scoped into.

## 4. Create the credentials Secret

```bash
kubectl create secret generic minipay-db-credentials \
  --namespace "$KUBE_NAMESPACE" \
  --from-literal=DB_PASSWORD="$DB_PASSWORD" \
  --from-literal=API_KEY="$API_KEY"
```
- Creates the Secret imperatively from the `$DB_PASSWORD`/`$API_KEY` shell
  variables, so neither real value is ever written to
  `kubernetes/secrets.yaml` or committed to this repository. (If you'd
  rather apply the YAML file
  directly, edit an untracked local copy of `kubernetes/secrets.yaml` first
  and replace `CHANGE_ME` with the real value, then
  `kubectl apply -f <that local copy>` instead of this command.)

## 5. Apply the ConfigMap

```bash
kubectl apply -f "$REPO_ROOT/kubernetes/configmap.yaml"
```
- Creates `minipay-api-config`, the non-secret settings both the API and
  the database read from.

## 6. Deploy the database (StatefulSet + persistent storage)

```bash
kubectl apply -f "$REPO_ROOT/kubernetes/postgres-statefulset.yaml"
kubectl rollout status statefulset/minipay-db -n "$KUBE_NAMESPACE"
```
- `kubectl apply` — creates the headless Service and the `StatefulSet`
  (which provisions its own `PersistentVolumeClaim` via
  `volumeClaimTemplates`).
- `kubectl rollout status` — blocks until the single database pod is
  Running and Ready (passing its `pg_isready` readiness probe), or reports
  a failure.

## 7. Load the schema and seed data into the in-cluster database

```bash
kubectl port-forward -n "$KUBE_NAMESPACE" statefulset/minipay-db 5432:5432 &
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U minipay -d minipay \
  -f "$REPO_ROOT/paysys-implementation-l2-assessment-main/database/schema.sql"
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U minipay -d minipay \
  -f "$REPO_ROOT/sql/seed.sql"
kill %1
```
- `kubectl port-forward` — temporarily exposes the in-cluster Postgres pod
  on `127.0.0.1:5432` for this shell session only.
- The two `psql` commands apply the same schema and seed data used in
  Objective 1 (see `sql/REPRODUCIBLE.md` for regenerating `seed.sql` if
  needed), now against the in-cluster database instead of a local one.
- `kill %1` — stops the port-forward background job once loading is done.

## 8. Deploy the API

```bash
sed -i "s#REPLACE_WITH_YOUR_REGISTRY/minipay-api:1.0.0#$MINIPAY_IMAGE#" \
  "$REPO_ROOT/kubernetes/deployment.yaml"
kubectl apply -f "$REPO_ROOT/kubernetes/deployment.yaml"
kubectl rollout status deployment/minipay-api -n "$KUBE_NAMESPACE"
```
- `sed -i` — substitutes the placeholder image reference in
  `deployment.yaml` with the real, pushed image from Step 2. (Revert this
  file, or keep the substitution local/untracked, if you don't want the
  real registry path committed.)
- `kubectl apply` / `kubectl rollout status` — deploys the API and waits
  for both replicas to become Ready.

## 9. Apply the Service and the autoscaler

```bash
kubectl apply -f "$REPO_ROOT/kubernetes/service.yaml"
kubectl apply -f "$REPO_ROOT/kubernetes/hpa.yaml"
```
- `service.yaml` — exposes the API inside the cluster on port 80.
- `hpa.yaml` — enables CPU-based autoscaling (requires `metrics-server`;
  see `kubernetes/USAGE.md`).

## 10. Verify

```bash
kubectl get all -n "$KUBE_NAMESPACE"
kubectl get pvc -n "$KUBE_NAMESPACE"
kubectl get endpoints minipay-api -n "$KUBE_NAMESPACE"
kubectl port-forward -n "$KUBE_NAMESPACE" svc/minipay-api 8000:80 &
curl -s http://127.0.0.1:8000/health
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/api/payments/search?transaction_ref=none"
kill %1
```
- `kubectl get all` — confirms the Deployment, StatefulSet, Services, and
  HPA all show healthy/expected status.
- `kubectl get pvc` — confirms the database's persistent volume claim is
  `Bound`, not `Pending`.
- `kubectl get endpoints minipay-api` — confirms the Service actually has
  pod IPs behind it (this is exactly what was broken in
  `starter/kubernetes/broken-api.yaml` — see
  `investigation/kubernetes-findings.md`).
- `kubectl port-forward` + first `curl .../health` — confirms the API is
  actually reachable end-to-end and can reach the database, expecting
  `{"status":"ok","db":"reachable"}`.
- Second `curl`, with `X-API-Key` — confirms an authenticated `/api/*`
  route works too, expecting `{"query_ref":"none","count":0,"items":[]}`.

## Restart, rollout, and log inspection

See the "Restart and rollout procedures" and "Log inspection and
troubleshooting" sections in `kubernetes/USAGE.md` for the full command
reference (rolling restarts, rollback, scaling, log tailing, and event
inspection).

## Tear down

```bash
kubectl delete namespace "$KUBE_NAMESPACE"
```
- Deletes every resource created above, including the database's
  `PersistentVolumeClaim` (and, depending on the storage class's reclaim
  policy, its underlying storage). Only run this when you intend to
  discard the in-cluster database data.
