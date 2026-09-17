# AI Usage

## Tools used

**Claude Code** (Anthropic's agentic CLI, running Claude Sonnet 5) for
essentially the entire build: reading the assessment brief, writing code
and SQL, running commands (`psql`, `pytest`, `docker`, `kubectl`,
Playwright-driven browser sessions), and writing this documentation set.
It had direct tool access — shell, file read/write/edit, and browser
automation — rather than being used purely as a chat-based code generator
copy-pasted by hand.

## Tasks it was used for

- Reviewing the supplied schema/generator and drafting the SQL
  investigation queries (Objective 1).
- Designing and implementing the MiniPay backend (FastAPI, MVC layout, no
  ORM) and static frontend (Objective 2).
- Designing and implementing the pytest API suite and Playwright UI suite,
  and running both against the live application (Objective 3).
- Designing, implementing, and unit-testing the L2 support CLI
  (Objective 4).
- Diagnosing the supplied broken Kubernetes manifest and writing the
  corrected manifests (Objective 5).
- Writing the Linux evidence template and health-check script
  (Objective 7).
- Writing this documentation set (Objective 8).

## Representative prompts / interaction summaries

1. *"Create the reproducible.md file to set up the database, generate the
   seed file, and seed it into the database. Do not use any credentials or
   addresses, keep placeholders."* — produced `sql/REPRODUCIBLE.md` with
   exported shell variables and a per-command explanation, no real
   credentials.

2. *"Move to MiniPay application development... a production grade
   client-facing app which can handle query over large data... do not
   build any authentication mechanism, avoid any complexity."* — this
   design constraint (no auth, keep it simple) was followed literally for
   the initial build, and only reversed later when explicitly requested
   (see the correction example below).

3. *"There is a little issue in MiniPay App — the app lacks the
   functionality search by transaction_ref and authentication. Build API
   and UI for the functionality, then include the test cases in API and UI
   tests, and modify RESULT.md accordingly."* — a single prompt that drove
   backend changes (new endpoint, new auth dependency), frontend changes,
   new/rewritten tests in both suites, and documentation updates, all
   cross-checked for consistency (e.g. route registration order for
   `/api/payments/search` vs. `/api/payments/{id}` was deliberately
   verified, not assumed).

4. *"Diagnose the starter/kubernetes/broken-api.yaml... Identify the
   defects rather than simply replacing the file without explanation... Do
   only the instructed job, do not create the required Kubernetes
   manifests."* — a scope-limiting instruction that was followed exactly:
   `investigation/kubernetes-findings.md` was written with nine numbered
   findings and no accompanying fix, and the corrected manifests were only
   written in a later, separate prompt.

5. *"Commit every change in the exact sequence you make the changes."* —
   resulted in per-unit commits (config change, then the new dependency
   file, then the router wiring, then the schema, then the model, etc.)
   rather than one bundled commit per feature, so the git history itself
   reflects the actual build order.

## How generated output was validated

The consistent pattern throughout was **run it against something real, not
just read it**:

- Every SQL query was executed against the actual seeded PostgreSQL
  database, not just visually checked (e.g. `sql/PERFORMANCE.md`'s
  before/after numbers are from real `EXPLAIN (ANALYZE, BUFFERS)` runs,
  including dropping and recreating the index to capture a genuine
  "before" state, and a real failed `CREATE UNIQUE INDEX` attempt to prove
  a uniqueness constraint isn't viable — not asserted from memory).
- Every API/UI change was smoke-tested with real `curl` calls or a real
  Playwright browser session, including deliberately provoking the error
  paths (missing/wrong API key, unknown customer, malformed JSON) to
  confirm the actual response, not the expected one.
- Kubernetes manifests were validated with `yaml.safe_load` (structural
  correctness) and a live `kubectl apply --dry-run=client` attempt; the
  latter failed only because this environment's kubeconfig pointed at an
  unreachable cluster, which was reported as a limitation rather than
  glossed over.
- Both test suites (pytest, Playwright) were actually executed, their
  real pass/fail output captured into `tests/api/RESULT.md` and
  `tests/ui/Report.md`, and test data cleaned up afterward — with that
  cleanup later corrected (see below) to accurately describe it as
  manual, not automated.
- The support CLI's documented example output was captured from a live
  re-run against the seeded database, not written from expectation.

## Example of correcting/rejecting AI-generated output

Several concrete corrections happened during this build; the most
material ones:

- **A preemptive index that would have defeated a later objective.** An
  index on `transactions.customer_id` was added (with a real
  before/after `EXPLAIN` showing it worked) to make the customer-payments
  endpoint fast. This was then identified as wrong and reverted: that
  exact "slow query as data grows" scenario is the subject of
  `INCIDENT-003.md` in the supplied brief, and pre-solving it in
  Objective 2 would have removed the problem the later objective is meant
  to investigate. The index was dropped from the live database and the
  supporting file deleted.

- **A fabricated example passed off as real.** `python/GUIDE.md`
  initially included a "clean, healthy transaction" example with an
  invented customer name, amount, and timestamps. Running the actual
  command against the seeded database showed different values entirely.
  The fabricated example was replaced with the real captured output, and
  going forward every documented example was captured from an actual run
  before being written down.

- **An unsupported claim about evidence.** A test report claimed
  screenshot evidence had been "captured," but the screenshot files were
  still sitting as untracked, uncommitted local files — meaning nothing
  was actually visible in the repository. This was caught directly ("where
  is the screenshot — do not make false claims"), verified against disk
  and git status, and fixed by committing the actual files rather than
  editing the claim to be vaguer.

- **A misleading description of test cleanup.** `tests/api/RESULT.md` and
  `tests/ui/Report.md` both stated that test data created during a run
  "was deleted from the database afterward," which read as if an automated
  teardown fixture did it. There is no such fixture in either
  `conftest.py`. This was flagged directly, verified against the database
  (confirming zero leftover rows, so cleanup genuinely had happened — just
  manually), and both documents were corrected to say so explicitly,
  including a note that re-running the suites without the manual step
  will leave new rows behind.

- **A real bug surfaced by testing the documentation, not just the code.**
  While verifying that `python/REPRODUCIBLE.md`'s exact setup steps
  actually worked end-to-end, `--health` failed with `Invalid URL` because
  `.env.example`'s `API_BASE_URL=<API_BASE_URL>` placeholder was truthy
  and got treated as "configured." This was a genuine implementation bug,
  not a documentation-only issue; it was fixed in `config.py`'s consuming
  code path by commenting the optional setting out by default in
  `.env.example`, then the full reproducible sequence was re-run to
  confirm the fix.

## What this means for follow-up review

Every generated artifact in this repository — SQL, application code, test
code, Kubernetes manifests, and this documentation — was either run
directly or cross-checked against something that was run, and the
corrections above are left visible in the git history rather than
squashed away, so the actual back-and-forth is inspectable, not just this
summary of it.
