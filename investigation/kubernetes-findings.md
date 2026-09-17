# Kubernetes Findings: `starter/kubernetes/broken-api.yaml`

Scope of this document: diagnosis only. It records every defect found in the
supplied starter manifest and the reasoning behind each finding. It does not
propose or include a corrected manifest — that is a separate, later step.

Source file (unmodified, as supplied):
`paysys-implementation-l2-assessment-main/starter/kubernetes/broken-api.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minipay-api
  namespace: minipay
spec:
  replicas: 2
  selector:
    matchLabels:
      app: minipay-api
  template:
    metadata:
      labels:
        app: minipay-api
    spec:
      containers:
        - name: api
          image: YOUR_IMAGE_HERE
          ports:
            - containerPort: 8080
          env:
            - name: DB_HOST
              value: "minipay-db"
          readinessProbe:
            httpGet:
              path: /health
              port: 8081
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: minipay-api
  namespace: minipay
spec:
  selector:
    app: minipay-backend
  ports:
    - port: 80
      targetPort: 8081
```

## Findings

### 1. Service selector does not match the Deployment's pod labels (critical)

- Deployment pod template labels: `app: minipay-api` (`spec.template.metadata.labels`).
- Service selector: `app: minipay-backend` (`spec.selector`).

These two values must match for the Service to have any endpoints. As
written, `kubectl get endpoints minipay-api -n minipay` would return an
empty endpoint list forever — the Service would route to nothing, even once
every pod is healthy and Ready. This is silent: the Deployment can look
completely healthy (`2/2 Ready`) while the Service is completely unreachable,
which makes it an easy defect to miss without explicitly checking endpoints.

### 2. Readiness probe targets a port nothing listens on (critical)

- Container exposes and is expected to serve on `containerPort: 8080`
  (declared) — the liveness probe correctly targets `8080`.
- The readiness probe instead targets `port: 8081`, a port the container
  neither declares nor (per the application) listens on.

Effect: the readiness probe would fail with connection-refused on every
attempt, so the pod would never be marked Ready. Depending on how the
Deployment is consumed downstream (e.g. gating a rollout, or a Service
that also depends on readiness), this alone would make the workload appear
permanently "not ready" even though the process inside the container is
running and passing its liveness check on 8080.

### 3. Service `targetPort` does not match the container's actual port (critical)

- Service `targetPort: 8081`, but the container's declared port is `8080`
  and nothing in this manifest indicates the application listens on 8081.

Even if Finding #1 (selector mismatch) were fixed in isolation, traffic
forwarded by the Service would still land on port 8081 inside the pod,
where nothing is listening — the Service would return connection-refused
errors end-to-end. This is a second, independent reason the Service is
non-functional, distinct from the selector mismatch.

### 4. Placeholder image reference (blocking)

- `image: YOUR_IMAGE_HERE` is not a resolvable image reference. Applying
  this manifest as-is would leave every pod in `ErrImagePull` /
  `ImagePullBackOff`.
- No `imagePullPolicy` is set either, which matters once a real, tagged
  image is substituted in (e.g. `:latest` defaults to `Always`, a fixed
  version tag defaults to `IfNotPresent` — worth being explicit about
  rather than relying on the implicit default).

### 5. Required application configuration is missing from `env` (critical, application-level)

Only `DB_HOST` is supplied. Cross-referencing the actual MiniPay backend
configuration (`MiniPay/backend/app/config.py`), the application calls a
`_require()` helper at import time for `DB_HOST`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD` — any of these being absent raises
`RuntimeError: Missing required environment variable: ...` during startup,
before the process can even begin serving traffic. As written, this
manifest supplies only 1 of the 4 required values, so the container would
crash immediately on start (`CrashLoopBackOff`), independent of every
networking issue above.

`DB_PASSWORD` in particular is also a defect of *kind*, not just
completeness: it should never be supplied as a plain literal `value:` in a
Deployment spec (visible via `kubectl get pod -o yaml` to anyone with pod
read access); it belongs in a `Secret`, referenced via `secretKeyRef`. The
supplied manifest doesn't yet reach the point of demonstrating this
mistake only because the key is missing entirely, but it's a real
constraint on however this gets filled in.

### 6. Container port vs. the actual built application image (mismatch to reconcile)

This manifest is a generic starter and doesn't reference the MiniPay image
built in Objective 2, but if it is used to deploy that image
(`MiniPay/backend/Dockerfile`), there is an additional, concrete mismatch:
the Dockerfile's `CMD` hard-codes `--port 8000` for uvicorn (the `API_PORT`
environment variable is not actually consulted by the container's start
command), so the image always listens on `8000` regardless of any `API_PORT`
env value injected at deploy time. The manifest assumes `8080` throughout
(`containerPort`, liveness probe). Whichever port is intended, the
Dockerfile's `CMD`, the Deployment's `containerPort`/probes, and the
Service's `targetPort` all need to agree on the same value — currently none
of them do.

### 7. No `Namespace` object is defined for `minipay` (gap)

Both the Deployment and the Service are scoped to `namespace: minipay`, but
no `Namespace` resource is included anywhere in the supplied file (or
elsewhere in `starter/kubernetes/`). Applying this manifest against a
cluster where that namespace doesn't already exist fails outright
(`namespaces "minipay" not found`). This isn't a bug in the two resources
themselves, but it makes the file non-self-contained/non-reproducible on a
fresh cluster.

### 8. No resource requests/limits on the container (gap, not a hard failure)

The container spec has no `resources.requests` / `resources.limits`. This
won't prevent the pod from scheduling on a healthy cluster, but it means:
no scheduling guarantee (the pod competes for node resources with no
guaranteed share), no protection against one runaway pod using unbounded
CPU/memory on the node, and no basis for the cluster's autoscaler (if any)
to make informed decisions. Worth calling out even though it's not a
"broken" defect in the sense of #1–#5.

### 9. `DB_HOST` value assumes an in-cluster dependency that isn't defined here (assumption to verify)

`DB_HOST` is hard-coded to the literal `"minipay-db"`, implying a
same-namespace Service (or DNS-resolvable name) called `minipay-db` is
expected to exist for this to resolve. Per Objective 1/2, the actual
PostgreSQL instance used so far in this assessment is external to any
Kubernetes cluster (a locally-installed/reachable Postgres, not something
deployed as a `minipay-db` Kubernetes Service). Whether `minipay-db` refers
to an in-cluster database Service to be added later, or should instead be
an external hostname/`ExternalName` Service, is not resolved by anything in
this file and needs to be decided explicitly rather than assumed.

## Summary table

| # | Finding | Severity | Symptom if deployed as-is |
|---|---|---|---|
| 1 | Service selector (`minipay-backend`) doesn't match pod labels (`minipay-api`) | Critical | Service has zero endpoints; totally unreachable |
| 2 | Readiness probe port (`8081`) doesn't match the declared container port (`8080`) | Critical | Pod never becomes Ready |
| 3 | Service `targetPort` (`8081`) doesn't match the declared container port (`8080`) | Critical | Connection refused even if selector is fixed |
| 4 | `image: YOUR_IMAGE_HERE` is a placeholder | Blocking | `ErrImagePull` / `ImagePullBackOff` |
| 5 | Only `DB_HOST` is set; `DB_NAME`/`DB_USER`/`DB_PASSWORD` are required by the app and missing | Critical | `CrashLoopBackOff` on startup |
| 6 | Manifest assumes port 8080; the built MiniPay image's `CMD` hard-codes port 8000 | Mismatch | Probes/Service would fail against the real image as currently built |
| 7 | `namespace: minipay` is referenced but never defined in this or any other supplied file | Gap | `kubectl apply` fails on a fresh cluster without the namespace pre-created |
| 8 | No CPU/memory `resources` set | Gap | No scheduling guarantee, no protection from resource contention |
| 9 | `DB_HOST=minipay-db` assumes an in-cluster dependency not defined anywhere | Assumption | Unresolvable hostname unless that Service (or an `ExternalName` alias) is added |
