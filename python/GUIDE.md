# MiniPay Support Tool: Usage Guide

A practical, example-driven guide for an L2 engineer using
`support_tool.py` to investigate a transaction, check dependency health, or
triage a backlog of stuck/failed payments. All example output below is
real, captured from a run against the live seeded Objective 1 database —
nothing here is fabricated.

## Command 1: diagnose a transaction

```bash
python support_tool.py --transaction <TXN_REF>
```

This is the primary interface. It looks up every transaction matching that
reference (see "Why more than one match is possible" below), joins in its
callback/retry history, and reports detected anomalies with a recommended
action for each.

### Example: a clean, healthy transaction

No anomalies, nothing to do — the report says so explicitly rather than
leaving you to infer it from an empty section:

```
$ python support_tool.py --transaction TXN00000001
Transaction reference: TXN00000001

--- Match 1 of 1 (id=1) ---
Customer:            Customer 655 (CUST000655, id=655)
Amount:              11221.97
Status:              SUCCESS
Created at:          2026-09-09T23:59:32
Completed at:        2026-09-10T00:00:01
Callback attempts:   1
  - attempt 1: SUCCESS (http 200) at 2026-09-10T00:00:06
Anomalies:           none
Recommended action:  No anomalies detected; no action required.
```

### Example: a transaction stuck in PROCESSING

```
$ python support_tool.py --transaction TXN00000029 --json
{
  "query_ref": "TXN00000029",
  "match_count": 1,
  "transactions": [
    {
      "id": 29,
      "transaction_ref": "TXN00000029",
      "customer_id": 541,
      "customer_ref": "CUST000541",
      "customer_name": "Customer 541",
      "amount": "87256.06",
      "status": "PROCESSING",
      "created_at": "2026-09-06T03:14:52",
      "completed_at": null,
      "failure_code": null,
      "callbacks": [],
      "anomalies": ["STUCK_IN_PROCESSING"],
      "recommended_action": "Transaction has been PROCESSING beyond the expected threshold. Check upstream processor connectivity and escalate if it does not resolve on its own."
    }
  ]
}
```

**What to do:** check the payment processor's own status page/dashboard for
this reference. If it shows completed on their side but MiniPay still
shows `PROCESSING`, the callback likely never arrived or failed silently —
escalate to whoever owns the processor integration. Don't resubmit the
payment; that risks a duplicate charge.

### Example: a failed transaction

```
$ python support_tool.py --transaction TXN00000010
Transaction reference: TXN00000010
--- Match 1 of 1 (id=10) ---
Customer:            Customer 234 (CUST000234, id=234)
Amount:              77329.53
Status:              FAILED
Created at:          2026-09-01T23:14:27
Completed at:        2026-09-01T23:16:18
Failure code:        UPSTREAM_ERROR
Callback attempts:   1
  - attempt 1: FAILED (http 502) at 2026-09-01T23:16:23
Anomalies:           TRANSACTION_FAILED
Recommended action:  Review the failure_code with the payment processor/acquirer and confirm the customer was notified. Do not resubmit until the root cause is understood.
```

**What to do:** `UPSTREAM_ERROR` plus an HTTP 502 on the callback both point
upstream, not at MiniPay. Check the processor's incident status for the
time window around `2026-09-01T23:16`. Confirm the customer's payment
method wasn't charged despite the failure before telling them it's safe to
retry.

### Example: a duplicated reference

```
$ python support_tool.py --transaction TXN00024999
Transaction reference: TXN00024999
WARNING: 2 transactions share this reference (see DUPLICATE_REFERENCE anomaly on each match below).

--- Match 1 of 2 (id=25000) ---
Customer:            Customer 303 (CUST000303, id=303)
Amount:              2923.35
Status:              SUCCESS
...
Anomalies:           DUPLICATE_REFERENCE
Recommended action:  Multiple transactions share this reference. Confirm with the customer whether this was a duplicate submission before taking any resolution action on either record.

--- Match 2 of 2 (id=24999) ---
Customer:            Customer 14 (CUST000014, id=14)
Amount:              84623.80
Status:              SUCCESS
...
```

**What to do:** these are two *different* customers with two *different*
amounts sharing one reference — almost certainly a reference-generation bug
on the client side, not the same payment retried. Don't assume it's a
harmless duplicate; verify both records independently before closing the
ticket.

### Example: reference not found

```
$ python support_tool.py --transaction TXN99999999; echo "exit: $?"
No transaction found with reference 'TXN99999999'.
exit: 1
```

**What to do:** double-check the reference for typos with the customer /
the calling system first. Exit code `1` is scriptable — see "Scripting
against exit codes" below.

## Command 2: health check

```bash
python support_tool.py --health
```

```
Overall status: ok
Database:       ok
API:            not_configured
```

If `API_BASE_URL` is set in `.env`, `API` reflects the MiniPay API's own
`/health` result instead of `not_configured`. Run this first when a batch
of `--transaction` lookups is failing with dependency errors, to quickly
tell "the database is down" apart from "this one reference genuinely
doesn't exist."

## Command 3: stuck/failed summary (bonus)

```bash
python support_tool.py --stuck-summary --failed-lookback-hours 24
```

Lists every transaction currently `PROCESSING` past the configured
threshold, and every `FAILED` transaction within the lookback window — a
quick daily triage view rather than checking references one at a time.
`--json` gives the same data for piping into another tool or a scheduled
report.

## `--json` for every command

Every command above accepts `--json` and prints the identical underlying
data as JSON instead of the formatted text report — useful for piping into
`jq`, another script, or a monitoring system, without needing a second
"machine mode" to keep in sync with the human-readable one.

## Scripting against exit codes

```bash
python support_tool.py --transaction "$1"
case $? in
  0) echo "found, see report above" ;;
  1) echo "not found — check the reference" ;;
  2) echo "dependency down — check --health" ;;
  3) echo "misconfigured — check .env" ;;
  *) echo "unexpected error — check logs" ;;
esac
```

## Anomaly reference

| Anomaly | What triggered it | What to check |
|---|---|---|
| `STUCK_IN_PROCESSING` | `PROCESSING` longer than `STUCK_PROCESSING_MINUTES` (default 15) | Processor-side status for this reference |
| `TRANSACTION_FAILED` | `status = FAILED` | `failure_code` and the callback's `http_status` |
| `MISSING_SUCCESS_CALLBACK` | `SUCCESS` locally, but no callback recorded as `SUCCESS` | Processor's own callback/webhook logs — possible reconciliation gap |
| `MISSING_COMPLETION_TIMESTAMP` | Terminal status but `completed_at` is null | Data-integrity issue — flag to engineering |
| `DUPLICATE_REFERENCE` | More than one transaction row shares this reference | Whether this is a genuine resubmission or a reference-generation bug |

## Logging

Logs go to **stderr**, never stdout — `--json` output is always clean,
parseable JSON regardless of `LOG_LEVEL`. Set `LOG_LEVEL=DEBUG` in `.env`
for more detail while troubleshooting the tool itself.
