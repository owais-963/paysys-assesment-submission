# Assessment Execution Plan

## Scope and constraints
- Review the repository guidance in `README.md`, `INSTRUCTIONS.md`, `SCORING.md`, and the task files in `requirements/`.
- Keep the existing repository content intact unless a later task explicitly requires new files under the required submission structure.
- Do not silently fix broken or intentionally defective artifacts in the supplied repository; document findings and work around them only when the task calls for it.
- Follow the required submission structure from `INSTRUCTIONS.md`:
  - `README.md`
  - `SETUP.md`
  - `ARCHITECTURE.md`
  - `AI_USAGE.md`
  - `investigation/`
  - `sql/`
  - `kubernetes/`
  - `python/`
  - `tests/api/`
  - `tests/ui/`
  - `evidence/`

## Objective sequence

### Objective 1: Database and SQL
Goal: Build and validate a relational data model, load synthetic data, and answer the required SQL investigation questions.

Tasks:
- Review the supplied schema in `database/schema.sql` and generator in `database/generate_data.py`.
- Set up a local PostgreSQL-compatible database and seed the data with the generator.
- Create SQL scripts for the required reporting questions:
  1. Transaction count and total value by status and day.
  2. Top 10 customers by successful transaction value.
  3. Transactions in `PROCESSING` for more than 15 minutes.
  4. Duplicate transaction references.
  5. Daily success rate percentage.
  6. Reconciliation of successful transaction count/value vs callback success count/value.
  7. Average and p95 processing time.
- Write `sql/PERFORMANCE.md` to capture one poor access pattern and its improvement.
- Document indexing or query changes with evidence and before/after comparison.

Deliverables:
- `sql/*.sql` queries or scripts
- `sql/PERFORMANCE.md`
- Database seed and verification logs if needed

### Objective 2: MiniPay app creation
Goal: Create a minimal but reproducible MiniPay application that exposes the required API/UI behavior.

Tasks:
- Define a small application architecture with database, API, and UI components.
- Implement or adapt a simple service that supports customer/payment workflows.
- Keep the app reproducible for evaluation with local setup instructions.
- Ensure configuration is externalized and not hard-coded where practical.
- Prepare for later automated testing and support tool integration.

Deliverables:
- Application code and configuration under project folders
- Documentation for setup and architecture
- Reproducible run instructions

### Objective 3: API and UI testing automation
Goal: Validate application correctness with automated tests for both REST API and browser UI flows.

Tasks:
- Build or finalize the required API endpoints:
  - `POST /api/customers`
  - `POST /api/payments`
  - `GET /api/payments/{id}`
  - `GET /api/customers/{id}/payments`
  - `GET /health`
- Add pytest-based API tests covering:
  - successful requests
  - missing/invalid fields
  - unknown resources
  - access-control behavior
  - duplicate/idempotent submission
  - error handling
  - schema/content assertions
  - response-time threshold
- Create `tests/api/NOTES.md` with guidance on timeouts, retries, idempotency, and 4xx vs 5xx handling.
- Build a minimal UI and automate:
  1. Login/open app
  2. Search transaction
  3. Submit payment
  4. Validate success state
  5. Validate negative/error scenario
- Run the full suite and retain evidence/report output.

Deliverables:
- `tests/api/...`
- `tests/ui/...`
- `tests/api/NOTES.md`
- Test execution output or report artifact

### Objective 4: Python support CLI tool
Goal: Build a practical L2 support utility for investigating payment transactions.

Tasks:
- Create a Python CLI with a command like:
  - `python support_tool.py --transaction TXN000123`
- Design the tool to retrieve transaction information from application data sources.
- Include support for machine-readable JSON output mode.
- Surface key diagnostic details:
  - customer/reference/amount/status
  - timestamps
  - callback/retry information
  - anomaly detection
  - recommended next action
- Add error handling, timeouts, logging, exit codes, and environment-based configuration.
- Write unit tests for core logic and anomaly detection.
- Optionally add summary or health-check commands for stuck or failed transactions.

Deliverables:
- `python/` implementation and configs
- tests for important support logic
- usage documentation if needed

### Objective 5: Kubernetes and Rancher
Goal: Deploy the application to Kubernetes, identify the defects in the starter manifest, and document operations evidence.

Tasks:
- Inspect the supplied starter manifest at `starter/kubernetes/broken-api.yaml` and identify its configuration defects.
- Create corrected Kubernetes manifests or a minimal Helm/Kustomize deployment that addresses the issues.
- Include deployments, services, config, secrets placeholders, probes, resource requests/limits, persistent storage, and namespace usage.
- Validate workload health and inspect logs with repeatable rollout/restart procedures.
- Set up or document Rancher access to inspect cluster/workloads, pods, logs, scaling, and config.
- Record evidence in `investigation/kubernetes-findings.md` and `evidence/rancher.md`.

Deliverables:
- `kubernetes/` manifests or config
- `investigation/kubernetes-findings.md`
- `evidence/rancher.md`
- Deployment validation notes

### Objective 6: Incident investigations
Goal: Investigate production-style incidents and produce structured RCA documents.

Tasks:
- Review `incidents/INCIDENT-001.md`, `INCIDENT-002.md`, and `INCIDENT-003.md`.
- For each incident, create a clear RCA in `investigation/` with:
  - reproduction steps
  - evidence and logs
  - hypotheses
  - root cause
  - immediate corrective action
  - permanent/preventive action
  - validation after the fix
- Where the app does not naturally reproduce the fault, introduce a realistic defect only for demonstration and document it clearly.
- Keep the investigation focused on evidence, traceability, and operational learning.

Deliverables:
- `investigation/INCIDENT-001-RCA.md`
- `investigation/INCIDENT-002-RCA.md`
- `investigation/INCIDENT-003-RCA.md`

### Objective 7: Linux evidence
Goal: Gather Linux operational evidence and document it in a reusable format.

Tasks:
- Run OS and kernel identification commands.
- Collect CPU, memory, and disk utilization facts.
- Record listening ports and relevant processes.
- Check DNS/network connectivity and application reachability.
- Gather logs from the running application or containers.
- Identify the memory-heavy process and largest disk consumers.
- Create a simple repeatable health-check script.
- Document how to investigate high CPU, low disk space, unreachable APIs, and repeatedly terminating processes.

Deliverables:
- `evidence/linux.md`
- health-check script or documented commands

### Objective 8: Documentation
Goal: Produce the required repository-level documentation that explains setup, architecture, AI usage, and the end-to-end solution.

Tasks:
- Create `README.md` summarizing the solution and how to run it.
- Create `SETUP.md` for environment prerequisites and installation steps.
- Create `ARCHITECTURE.md` describing system components and data flow.
- Create `AI_USAGE.md` covering tools used, prompts, validation, and examples of correcting AI output.
- Keep all documentation clear, evidence-based, and aligned with the implementation.

Deliverables:
- `README.md`
- `SETUP.md`
- `ARCHITECTURE.md`
- `AI_USAGE.md`

## Recommended execution order
1. Review requirements and repo artifacts.
2. Set up the database and data model.
3. Build MiniPay API/app foundation.
4. Implement SQL investigations and validate them.
5. Add support utility and tests.
6. Add API automation and UI automation.
7. Package Kubernetes deployment and Rancher evidence.
8. Investigate the three incidents and document RCAs.
9. Capture Linux evidence and health checks.
10. Finish repository documentation and prepare final submission evidence.
11. Create final Git tag `submission-v1.0` and keep a clean development history.

## Validation checkpoints
- Each objective should have a traceable artifact and runnable proof.
- No unsupported claim should be made without commands, logs, or reproducible output.
- The final submission should be functional enough for an evaluator to clone, run, and inspect.
- Keep the work modular and easy to explain in follow-up interview questions.

## Working notes
- The supplied `starter/` files and `database/` artifacts are intentionally part of the assessment and should be treated as evidence sources rather than silently modified.
- For the incident and Kubernetes sections, the expected work may include demonstrating a defect and then documenting the diagnosis and corrective action clearly.
- The final repository should be public and sharable, with no secrets or personal data exposed.
