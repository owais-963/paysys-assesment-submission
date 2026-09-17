# PaySys L2 Implementation Assessment

This repository is the submission for the PaySys L2 implementation
assessment (`paysys-implementation-l2-assessment-main/`, supplied
unmodified). It builds **MiniPay** — a minimal, production-shaped payments
API + UI — on top of the supplied PostgreSQL schema, then investigates,
tests, deploys, and documents it end to end.

See `PLAN.md` for the objective-by-objective execution plan this
submission follows, `ARCHITECTURE.md` for how the pieces fit together,
`SETUP.md` to actually run everything, and `AI_USAGE.md` for how AI
tooling was used throughout.

## Repository layout

```
├── README.md            you are here
├── SETUP.md              environment prerequisites and run instructions
├── ARCHITECTURE.md       components, data flow, key design decisions
├── AI_USAGE.md           AI tools/prompts/validation for this submission
├── PLAN.md               the objective-by-objective execution plan
├── sql/                  Objective 1: schema investigation queries + performance report
├── MiniPay/              Objective 2/3: the API + UI application itself
├── tests/api/            Objective 3: pytest API test suite, plan, and results
├── tests/ui/             Objective 3: Playwright UI test suite and report
├── python/               Objective 4: L2 support CLI (support_tool.py)
├── kubernetes/           Objective 5: Kubernetes manifests, usage, reproducible steps
├── investigation/        Objective 5/6: Kubernetes findings, incident RCAs
├── evidence/             Objective 5/7: Linux evidence, health-check script, Rancher evidence
└── paysys-implementation-l2-assessment-main/   supplied assessment brief (unmodified)
```

## Quick start

The fastest path to a running system:

1. **Database** — `sql/REPRODUCIBLE.md` (install PostgreSQL, apply
   `database/schema.sql`, generate and load the seed data).
2. **MiniPay API + UI** — `MiniPay/README.md` (local) or
   `MiniPay/REPRODUCIBLE.md` (Docker).
3. **Tests** — `tests/api/TEST_PLAN.md` / `tests/ui/Report.md` for the
   documented single command to run each suite.
4. **Support CLI** — `python/REPRODUCIBLE.md`.
5. **Kubernetes** (optional) — `kubernetes/REPRODUCIBLE.md`.

`SETUP.md` walks through all of the above as one sequence.

## What MiniPay is

A small payments system built directly against the supplied schema
(`database/schema.sql`: `customers`, `transactions`, `callbacks`) — no
ORM, raw parameterized SQL throughout. It exposes:

- `POST /api/customers`, `POST /api/payments`, `GET /api/payments/{id}`,
  `GET /api/payments/search?transaction_ref=...`,
  `GET /api/customers/{id}/payments`, `GET /health`
- a minimal shared-secret API key (`X-API-Key`) on every `/api/*` route
- a static HTML/JS console served independently of the API

See `MiniPay/README.md` for the full design rationale (why no ORM, why
this specific auth mechanism, why `transactions.customer_id` is
deliberately left unindexed).

## Objective status

Written plainly so the actual state of the submission is never in doubt:

| Objective | Status | Where |
|---|---|---|
| 1. Database & SQL | Done — schema seeded, all 7 required queries answered, one access pattern optimized with real before/after `EXPLAIN ANALYZE` evidence | `sql/` |
| 2. MiniPay app | Done — FastAPI backend (MVC layout), static frontend, containerized | `MiniPay/` |
| 3. API & UI test automation | Done — pytest suite (37 tests) and Playwright suite (6 tests), both run against the live app with captured results | `tests/api/`, `tests/ui/` |
| 4. Python support CLI | Done — `--transaction`/`--health`/`--stuck-summary`, unit-tested, verified against live data | `python/` |
| 5. Kubernetes | Manifests + findings done; **`evidence/rancher.md` does not exist yet** — Rancher inspection/evidence is not started | `kubernetes/`, `investigation/kubernetes-findings.md` |
| 6. Incident investigations | **Not started yet** — no `investigation/INCIDENT-00X-RCA.md` files exist yet | `investigation/` |
| 7. Linux evidence | Command set and health-check script written and validated for control-flow correctness; **actual command output on a real Linux host is still a placeholder** in `evidence/linux.md` | `evidence/linux.md` |
| 8. Documentation | This set of documents | repo root |

Nothing above is glossed over: where a deliverable is a template awaiting
real output, or an objective hasn't been started, that is stated directly
rather than implied to be complete.

## Git

Development history is incremental — each feature, fix, and documentation
update is its own commit with a descriptive message, rather than one final
squashed commit (62 commits at the time of writing). The final submission
will carry the `submission-v1.0` tag once every objective above is
actually complete.
