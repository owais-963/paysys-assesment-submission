# INCIDENT-002 — Root Cause Analysis

**Priority:** P1  
**Reported By:** Implementation Team  
**Component:** MiniPay API / Kubernetes  
**Environment:** K3s on Ubuntu  
**Namespace:** `minipay`  
**Status:** Root Cause Identified / Correction Defined

---

## 1. Incident Summary

A new release of the MiniPay API was deployed to Kubernetes. The API Pods appeared to start, but the application was not successfully available to users.

The investigation confirmed that the MiniPay application itself was capable of starting, connecting to PostgreSQL, and responding successfully to `/health` on port `8080`.

The failure was isolated to Kubernetes configuration.

Three primary configuration defects were identified:

1. The readiness probe was configured to use port `8081`, while MiniPay listens on port `8080`.
2. The Kubernetes Service selector used `app=minipay-backend`, while the API Pods were labelled `app=minipay-api`.
3. The Kubernetes Service forwarded traffic to `targetPort: 8081`, while MiniPay listens on port `8080`.

The combination of these defects prevented the API Pods from becoming Ready and prevented the Service from discovering and routing traffic to the MiniPay API Pods.

---

## 2. Impact

The MiniPay API Deployment was configured with two replicas, but Kubernetes reported:

```text
NAME          READY   UP-TO-DATE   AVAILABLE
minipay-api   0/2     1            0
```

The Deployment also exceeded its rollout progress deadline:

```text
error: deployment "minipay-api" exceeded its progress deadline
```

From the user perspective, the application was unavailable through the Kubernetes Service.

The database workload remained available during the final investigation, allowing the API/Kubernetes routing issue to be isolated from the database layer.

---

## 3. Investigation Methodology

The incident was investigated from the outside inward:

```text
Deployment Status
        |
        v
Pod Status / Events
        |
        v
Application Logs
        |
        v
Health Probes
        |
        v
Pod Labels
        |
        v
Service Selector
        |
        v
EndpointSlice
        |
        v
Service Port Mapping
```

The objective was to determine whether the failure originated from:

- the application process;
- database connectivity;
- Pod health;
- readiness/liveness configuration;
- Service discovery; or
- Kubernetes traffic routing.

---

# 4. Investigation and Evidence

## 4.1 Initial Kubernetes State

The namespace was inspected using:

```bash
sudo kubectl get all -n minipay -o wide
```

and:

```bash
sudo kubectl get pods -n minipay -o wide
```

The investigation showed that the PostgreSQL Pod was healthy:

```text
minipay-db-57775fb7dc-mcxbc    1/1    Running
```

while the MiniPay API Pods were not Ready:

```text
minipay-api-66bb567699-6lqhl   0/1    Running
minipay-api-6bd4fcc95f-45wf9   0/1    Running
```

An older ReplicaSet Pod also remained in `CrashLoopBackOff` from earlier reproduction/configuration attempts.

The API Deployment showed:

```text
READY   UP-TO-DATE   AVAILABLE
0/2     1            0
```

### Commands

```bash
sudo kubectl get all -n minipay -o wide

sudo kubectl get pods -n minipay -o wide

sudo kubectl get deployment minipay-api -n minipay
```

### Evidence Files

```text
evidence/incident-002/01-overall-state-before.txt
evidence/incident-002/02-pods-before.txt
evidence/incident-002/03-deployment-before.txt
```

---

## 4.2 Deployment Rollout Failure

The Deployment rollout was checked using:

```bash
sudo kubectl rollout status deployment/minipay-api \
  -n minipay \
  --timeout=30s
```

Kubernetes returned:

```text
error: deployment "minipay-api" exceeded its progress deadline
```

This confirmed that Kubernetes could not successfully complete the release.

### Evidence

```text
evidence/incident-002/04-rollout-before.txt
```

---

## 4.3 Pod Investigation

A current API Pod was selected dynamically:

```bash
API_POD=$(sudo kubectl get pods -n minipay \
  -l app=minipay-api \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1:].metadata.name}')
```

The Pod was then inspected:

```bash
sudo kubectl describe pod "$API_POD" -n minipay
```

The Pod itself was running:

```text
Status: Running
State:  Running
```

but Kubernetes reported:

```text
Ready: False
```

The health probes were configured as:

```text
Liveness:  http-get http://:8080/health
Readiness: http-get http://:8081/health
```

The application uses port `8080`.

The readiness probe therefore targeted the wrong port.

### Evidence

```text
evidence/incident-002/05-pod-describe-before.txt
```

---

## 4.4 Readiness Probe Failure

The Pod events showed repeated readiness failures:

```text
Readiness probe failed:
Get "http://10.42.0.14:8081/health":
dial tcp 10.42.0.14:8081:
connect: connection refused
```

This demonstrated that Kubernetes was attempting to check application readiness on port `8081`, but nothing was listening on that port.

The correct MiniPay application port is:

```text
8080
```

The incorrect readiness probe prevented the Pod from becoming Ready.

### Broken Configuration

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8081
```

### Required Configuration

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
```

---

## 4.5 Application-Level Validation

Application logs were inspected independently:

```bash
sudo kubectl logs "$API_POD" -n minipay
```

The logs showed successful application initialization:

```text
Database connection pool initialized (min=1, max=10)

Application startup complete.

Uvicorn running on http://0.0.0.0:8080
```

More importantly, the application successfully handled health checks:

```text
GET /health HTTP/1.1" 200 OK
```

Multiple successful `200 OK` responses were observed.

This demonstrated that:

- the MiniPay application could start;
- the application could connect to PostgreSQL;
- Uvicorn was listening on port `8080`;
- `/health` was operational;
- the failure was not primarily an application-code failure.

The investigation could therefore continue at the Kubernetes configuration/networking layer.

### Evidence

```text
evidence/incident-002/06-api-logs-before.txt
```

---

# 5. Kubernetes Service Investigation

## 5.1 Pod Labels

The API Pod labels were inspected:

```bash
sudo kubectl get pods -n minipay --show-labels
```

The API Pods were labelled:

```text
app=minipay-api
```

For example:

```text
minipay-api-6bd4fcc95f-45wf9
app=minipay-api
```

---

## 5.2 Service Selector

The Service was inspected:

```bash
sudo kubectl describe svc minipay-api -n minipay
```

The Service configuration showed:

```text
Selector: app=minipay-backend
```

The Service expected:

```text
app=minipay-backend
```

while the Pods actually used:

```text
app=minipay-api
```

Therefore:

```text
Pod Label
app=minipay-api
       |
       | DOES NOT MATCH
       v
Service Selector
app=minipay-backend
```

Because Kubernetes Services discover their backend Pods using label selectors, the Service could not discover the MiniPay API Pods.

### Evidence

```text
evidence/incident-002/08-pod-labels-before.txt
evidence/incident-002/09-service-before.txt
```

---

## 5.3 EndpointSlice Investigation

The Service endpoints were inspected using the current EndpointSlice API:

```bash
sudo kubectl get endpointslice -n minipay \
  -l kubernetes.io/service-name=minipay-api \
  -o wide
```

The result was:

```text
NAME                ADDRESSTYPE   PORTS     ENDPOINTS
minipay-api-tjvvr   IPv4          <unset>   <unset>
```

The Service therefore had no usable API endpoints.

The Service description also showed:

```text
Endpoints:
```

with no backend addresses.

This provided direct evidence that the selector mismatch prevented Kubernetes from associating API Pods with the Service.

### Evidence

```text
evidence/incident-002/10-endpoints-before.txt
```

---

## 5.4 Service Port Investigation

The Service YAML was inspected:

```bash
sudo kubectl get svc minipay-api -n minipay -o yaml
```

The Service contained:

```yaml
ports:
  - port: 80
    protocol: TCP
    targetPort: 8081

selector:
  app: minipay-backend
```

The MiniPay application was confirmed from application logs to listen on:

```text
0.0.0.0:8080
```

Therefore the Service was configured to forward traffic as:

```text
Service :80
     |
     v
targetPort :8081
```

while the application actually accepted traffic on:

```text
Pod :8080
```

Even if the Service selector had been correct, traffic forwarded to port `8081` would not have reached the MiniPay API.

### Evidence

```text
evidence/incident-002/11-service-yaml-before.txt
```

---

# 6. Root Cause Analysis

The incident was caused by multiple independent Kubernetes configuration defects.

## Root Cause 1 — Service Selector Mismatch

### Broken Configuration

```yaml
spec:
  selector:
    app: minipay-backend
```

### Actual Pod Label

```yaml
labels:
  app: minipay-api
```

### Effect

The Kubernetes Service selected zero MiniPay API Pods.

This resulted in an EndpointSlice with no usable endpoints and prevented Service traffic from being routed to the application.

### Correct Configuration

```yaml
spec:
  selector:
    app: minipay-api
```

---

## Root Cause 2 — Incorrect Service Target Port

### Broken Configuration

```yaml
ports:
  - port: 80
    targetPort: 8081
```

### Actual Application Port

```text
8080
```

### Effect

The Service was configured to forward incoming traffic to port `8081`, where the MiniPay application was not listening.

Even after correcting the Service selector, this configuration would still prevent traffic from reaching the application.

### Correct Configuration

```yaml
ports:
  - port: 80
    targetPort: 8080
```

---

## Root Cause 3 — Incorrect Readiness Probe Port

### Broken Configuration

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8081
```

### Actual Application Health Endpoint

```text
http://<pod>:8080/health
```

### Effect

Kubernetes continuously attempted:

```text
http://<pod-ip>:8081/health
```

and received:

```text
connection refused
```

The API containers could therefore be running while the Pods remained:

```text
READY 0/1
```

### Correct Configuration

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
```

---

# 7. Root Cause Summary

The complete failure path was:

```text
MiniPay API
listening on :8080
       |
       +-----------------------------+
       |                             |
       v                             v
Readiness Probe                  Application
configured :8081                itself healthy
       |                             |
       v                             v
Connection Refused              /health = 200
       |
       v
Pod NotReady


Pod label
app=minipay-api
       |
       | selector mismatch
       v
Service expects
app=minipay-backend
       |
       v
No Service Endpoints


Service :80
       |
       v
targetPort :8081
       |
       v
No application listener
```

The application was therefore unavailable because Kubernetes health checking, Service discovery, and Service traffic forwarding were inconsistent with the actual workload configuration.

---

# 8. Additional Findings During Controlled Reproduction

Before isolating the reported Kubernetes routing problem, runtime prerequisites for the MiniPay implementation had to be satisfied.

The application requires:

```text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
API_KEY
```

The initial starter manifest did not contain all application-specific runtime variables.

The required values were subsequently provided through Kubernetes configuration and Secrets.

The following Secrets were created:

```text
minipay-api-secret
minipay-db-secret
```

Sensitive values were referenced through `secretKeyRef` rather than embedded directly into the API Deployment.

A PostgreSQL workload was also deployed behind:

```text
minipay-db:5432
```

and the required database schema was initialized.

After these prerequisites were satisfied, MiniPay successfully initialized its database connection pool and returned successful `/health` responses on port `8080`.

These findings were treated as controlled-reproduction prerequisites and were separated from the primary root causes of the reported running-but-inaccessible Kubernetes incident.

---

# 9. Correction

The Kubernetes Deployment and Service should use consistent labels and ports.

## Corrected Deployment

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
          image: minipay-api:latest
          imagePullPolicy: IfNotPresent

          ports:
            - containerPort: 8080

          env:
            - name: DB_HOST
              value: "minipay-db"

            - name: DB_PORT
              value: "5432"

            - name: DB_NAME
              value: "minipay"

            - name: DB_USER
              value: "minipay"

            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: minipay-db-secret
                  key: POSTGRES_PASSWORD

            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: minipay-api-secret
                  key: api-key

          readinessProbe:
            httpGet:
              path: /health
              port: 8080
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
    app: minipay-api

  ports:
    - port: 80
      targetPort: 8080
```

The important corrections are:

```text
Readiness Probe:
8081 -> 8080

Service Selector:
app=minipay-backend -> app=minipay-api

Service Target Port:
8081 -> 8080
```

---

# 10. Validation Procedure

The corrected manifest should first be validated without modifying the running environment:

```bash
sudo kubectl apply --dry-run=server \
  -f kubernetes/minipay-api.yaml
```

The corrected configuration can then be applied:

```bash
sudo kubectl apply \
  -f kubernetes/minipay-api.yaml
```

The rollout should be monitored:

```bash
sudo kubectl rollout status \
  deployment/minipay-api \
  -n minipay
```

The expected result is:

```text
deployment "minipay-api" successfully rolled out
```

Pod readiness should then be verified:

```bash
sudo kubectl get pods -n minipay -o wide
```

Expected API state:

```text
READY   STATUS
1/1     Running
1/1     Running
```

The Service should then be inspected:

```bash
sudo kubectl describe svc minipay-api -n minipay
```

Expected selector:

```text
Selector: app=minipay-api
```

Expected target port:

```text
TargetPort: 8080
```

The EndpointSlice should then be checked:

```bash
sudo kubectl get endpointslice -n minipay \
  -l kubernetes.io/service-name=minipay-api \
  -o wide
```

The EndpointSlice should contain the ready MiniPay API Pod addresses rather than `<unset>` endpoints.

---

# 11. End-to-End Service Validation

The Kubernetes Service can be validated by forwarding the Service port:

```bash
sudo kubectl port-forward \
  -n minipay \
  svc/minipay-api \
  8080:80
```

From another terminal:

```bash
curl -i http://127.0.0.1:8080/health
```

Successful recovery criteria:

```text
HTTP/1.1 200 OK
```

with a healthy application/database response.

This validates the complete traffic path:

```text
Client
   |
   v
minipay-api Service :80
   |
   | selector=app=minipay-api
   v
MiniPay API Pod :8080
   |
   v
/health
   |
   v
PostgreSQL
```

---

# 12. Preventive Controls

Several controls can detect this class of configuration defect before production.

## 12.1 Server-Side Manifest Validation

Run:

```bash
kubectl apply --dry-run=server -f kubernetes/
```

during CI/CD before deployment.

This validates Kubernetes resource structure against the target API server.

---

## 12.2 Kubernetes Manifest Linting

Use a Kubernetes manifest validation tool such as `kubeconform` during CI.

Example:

```bash
kubeconform -strict kubernetes/
```

This catches invalid or inconsistent manifest definitions earlier in the release process.

---

## 12.3 Named Application Ports

Instead of repeating numeric ports across several resources, define a named port:

```yaml
ports:
  - name: http
    containerPort: 8080
```

Then reference it from probes and Services:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: http
```

and:

```yaml
targetPort: http
```

This reduces the risk of port configuration drift.

---

## 12.4 Automated Rollout Verification

The release pipeline should not consider a Kubernetes deployment successful until:

```bash
kubectl rollout status deployment/minipay-api \
  -n minipay \
  --timeout=120s
```

returns successfully.

A progress-deadline failure should automatically fail the deployment stage.

---

## 12.5 Post-Deployment Smoke Testing

After rollout, CI/CD should perform a health test through the Service rather than directly against the container.

For example:

```bash
curl --fail http://minipay-api/health
```

This verifies:

- Service discovery;
- Service selectors;
- Endpoint creation;
- port routing;
- application health; and
- database connectivity.

---

## 12.6 Endpoint Monitoring

Critical Services should be checked for ready endpoints.

A Service with zero ready endpoints should generate an alert before users report an outage.

---

## 12.7 Pod Readiness Monitoring

Monitoring should alert when:

```text
availableReplicas < desiredReplicas
```

or Pods remain:

```text
READY 0/1
```

for longer than the expected deployment window.

---

## 12.8 Restart Monitoring

Abnormal container restart counts and failed health probes should trigger alerts.

This would have surfaced the probe configuration problem immediately.

---

## 12.9 Configuration Review

Deployment review should verify consistency between:

```text
Application listening port
        =
containerPort
        =
readinessProbe port
        =
livenessProbe port
        =
Service targetPort
```

and:

```text
Deployment Pod labels
        =
Service selectors
```

---

## 12.10 Secret Management

Production credentials and API keys should not be committed directly to source-controlled Kubernetes manifests.

Secrets should be supplied using Kubernetes Secrets or an external secret-management solution.

---

# 13. Evidence Collected

Evidence collected during the investigation is stored under:

```text
investigation/evidence/incident-002/
```

The following evidence files were generated:

```text
01-overall-state-before.txt
02-pods-before.txt
03-deployment-before.txt
04-rollout-before.txt
05-pod-describe-before.txt
06-api-logs-before.txt
07-api-previous-logs.txt
08-pod-labels-before.txt
09-service-before.txt
10-endpoints-before.txt
11-service-yaml-before.txt
12-deployment-ports-before.txt
```

These files provide reproducible command output supporting the investigation and root-cause findings.

---

# 14. Key Evidence Summary

| Investigation | Finding |
|---|---|
| Deployment | `0/2` API replicas available |
| Rollout | Deployment exceeded progress deadline |
| API Pod | Container running but `Ready=False` |
| Application | Successfully started |
| Database | Connection pool initialized successfully |
| Application Port | `8080` |
| `/health` | Returned `200 OK` |
| Liveness Port | `8080` |
| Readiness Port | `8081` — incorrect |
| Pod Label | `app=minipay-api` |
| Service Selector | `app=minipay-backend` — incorrect |
| Service Target Port | `8081` — incorrect |
| EndpointSlice | No usable API endpoints |
| Result | Service unable to route user traffic |

---

# 15. Final Root Cause

The MiniPay outage was caused by **inconsistent Kubernetes Service and readiness configuration**.

The MiniPay application itself was healthy and successfully served `/health` on port `8080`. However:

```text
Readiness Probe :8081
        |
        v
Connection Refused
        |
        v
Pod NotReady
```

At the same time:

```text
Pod Label: app=minipay-api

          !=

Service Selector: app=minipay-backend
        |
        v
No Service Endpoints
```

and:

```text
Service :80
     |
     v
targetPort :8081
     |
     v
MiniPay actually listens :8080
```

Therefore the application process was functional, but Kubernetes could neither mark the workload Ready nor correctly discover and route Service traffic to it.

The required correction is to align the readiness probe and Service target port to `8080` and change the Service selector to `app=minipay-api`.

---

## Support Engineer Conclusion

The incident was investigated by separating application health from Kubernetes workload and networking health.

Application logs demonstrated successful startup, database connectivity, and HTTP `200` health responses. Kubernetes inspection then identified failed readiness checks, followed by a Service selector mismatch and an empty EndpointSlice. Inspection of the Service configuration identified an additional incorrect target port.

This evidence established that the outage originated from Kubernetes configuration rather than application or database failure.

The corrected configuration aligns the MiniPay API workload, health probes, Pod labels, and Service routing so that Kubernetes can correctly determine readiness and route client traffic to healthy API Pods.