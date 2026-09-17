# INCIDENT-001 — Root Cause Analysis

**Priority:** P2  
**Component:** MiniPay API / Transaction Search  
**Environment:** Local Windows Development Environment  
**Status:** Historical / Not Reproducible in Current Implementation  
**RCA Type:** Evidence-Based Analysis with Hypothetical Historical Failure Path

---

## 1. Incident Summary

INCIDENT-001 reports intermittent HTTP `500 Internal Server Error` responses while searching for transactions by `transaction_ref`.

During investigation, the supplied dataset and current MiniPay implementation were examined to identify conditions that could explain why only some transaction-reference searches would fail.

The assessment dataset intentionally contains duplicate `transaction_ref` values. The database schema does not define `transaction_ref` as unique.

However, the current MiniPay implementation already handles this condition by retrieving and returning all transactions matching the supplied reference.

As a result, the originally reported HTTP 500 condition could not be reliably reproduced using the current implementation.

Therefore, this RCA distinguishes between:

- findings directly verified in the current environment; and
- the likely historical failure path inferred from the incident scenario, schema, dataset and existing corrective implementation.

No artificial exception was introduced solely to manufacture RCA evidence.

---

# 2. Current Reproduction Status

The incident is currently **not reproducible** in the implemented MiniPay application.

A known duplicate transaction reference was tested:

```text
TXN00049999
```

The database contains two transactions using this reference:

```text
ID 49999
ID 50000
```

The API request was:

```powershell
curl.exe -i `
  -H "X-API-Key: $API_KEY" `
  "http://127.0.0.1:8080/api/payments/search?transaction_ref=TXN00049999"
```

The current implementation successfully returned:

```text
HTTP/1.1 200 OK
```

with:

```json
{
  "query_ref": "TXN00049999",
  "count": 2,
  "items": [
    {
      "id": 49999,
      "transaction_ref": "TXN00049999"
    },
    {
      "id": 50000,
      "transaction_ref": "TXN00049999"
    }
  ]
}
```

This confirms that the current implementation correctly handles a transaction reference associated with multiple database records.

---

# 3. Investigation Findings

## 3.1 `transaction_ref` Is Not Unique

The database schema defines the transaction reference as:

```sql
transaction_ref VARCHAR(50) NOT NULL
```

It does not define:

```sql
UNIQUE(transaction_ref)
```

Therefore, application logic must not assume that a transaction reference always identifies exactly one database row.

Multiple transactions sharing a reference are valid under the supplied schema.

---

## 3.2 Duplicate References Exist in the Dataset

The assessment dataset contains duplicate transaction references.

A confirmed example is:

```text
TXN00049999
```

which maps to two transaction records.

Therefore, duplicate transaction references are not merely a theoretical database condition; they exist in the supplied assessment data.

---

## 3.3 Current Application Handles Multiple Results

The current implementation contains:

```text
get_payments_by_transaction_ref(...)
```

which returns:

```python
list[dict]
```

The query retrieves every matching transaction rather than treating `transaction_ref` as a unique identifier.

Conceptually, the current behavior is:

```text
transaction_ref
       |
       v
SELECT ... WHERE transaction_ref = ?
       |
       v
0..N rows
       |
       v
Return collection
```

This behavior is consistent with the database schema.

---

# 4. Why the Original Incident Could Not Be Reproduced

The current application already contains behavior that prevents the suspected duplicate-reference failure.

Searching the known duplicate:

```text
TXN00049999
```

returns both matching records with HTTP `200`.

Attempts to reproduce the historical failure using the current implementation therefore do not represent the original application state.

Introducing an arbitrary exception or intentionally unrelated defect merely to obtain an HTTP 500 would not constitute valid incident evidence.

For this reason, the original failure is documented as **not reproducible in the current application state**.

---

# 5. Hypothetical Historical Root Cause

> **Important:** The following section describes the probable historical failure mechanism based on the incident symptoms, database schema, seeded data and current corrective implementation. It was not directly reproduced from the original defective application version.

A likely historical implementation treated `transaction_ref` as though it identified exactly one transaction.

Conceptually:

```text
Search transaction_ref
        |
        v
Application expects
0 or 1 transaction
        |
        v
Database returns multiple transactions
        |
        v
Application cannot handle result cardinality
        |
        v
Unhandled application error
        |
        v
HTTP 500
```

The underlying design mismatch would therefore be:

```text
Application assumption:
transaction_ref = unique transaction identifier

Database contract:
transaction_ref = non-unique searchable field
```

If application code used a single-result assumption while the database returned multiple matching records, duplicate references could trigger an unexpected application error.

---

# 6. Why the Incident Would Be Intermittent

The reported intermittent nature of the incident is consistent with a data-dependent failure.

Most transaction references may occur only once:

```text
Unique transaction_ref
        ↓
1 database row
        ↓
single-result assumption works
        ↓
request succeeds
```

A duplicated reference would produce:

```text
Duplicate transaction_ref
        ↓
2+ database rows
        ↓
single-result assumption violated
        ↓
potential unhandled error
        ↓
HTTP 500
```

Therefore, the endpoint itself could remain generally available while only searches involving specific duplicated references failed.

This would explain why the problem appeared intermittent from the user perspective.

---

# 7. Corrective Action

The application should treat `transaction_ref` as a non-unique search field and return all matching transactions.

The current implementation follows this approach.

Conceptually:

```python
def get_payments_by_transaction_ref(conn, transaction_ref: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id,
                   transaction_ref,
                   customer_id,
                   amount,
                   status,
                   created_at,
                   completed_at,
                   failure_code
            FROM transactions
            WHERE transaction_ref = %s
            ORDER BY id
            """,
            (transaction_ref,),
        )

        return cur.fetchall()
```

The API can then represent the result as:

```json
{
  "query_ref": "TXN00049999",
  "count": 2,
  "items": [...]
}
```

This supports:

```text
0 matches
1 match
multiple matches
```

without incorrectly relying on uniqueness.

---

# 8. Why a UNIQUE Constraint Is Not the Correct Fix

A possible workaround would be to change the database to:

```sql
transaction_ref VARCHAR(50) NOT NULL UNIQUE
```

However, this would change the supplied database contract.

The assessment schema intentionally does not define `transaction_ref` as unique, and the supplied data contains duplicate values.

Therefore, the application should accommodate the database model rather than modify the schema merely to enforce an application assumption.

---

# 9. Indexing Is Not the Root Cause

An index on:

```sql
transactions(transaction_ref)
```

can improve transaction-search performance.

For example:

```sql
CREATE INDEX idx_transactions_transaction_ref
ON transactions(transaction_ref);
```

However, an ordinary PostgreSQL index does not make the column unique.

Therefore:

```text
Non-unique index
      ↓
faster lookup
      ↓
duplicates still allowed
```

Indexing is a performance concern and does not resolve incorrect application assumptions about result cardinality.

The indexing/performance investigation is handled separately from INCIDENT-001.

---

# 10. Validation of Current Correct Behavior

The known duplicate reference was queried against the current application:

```powershell
curl.exe -i `
  -H "X-API-Key: $API_KEY" `
  "http://127.0.0.1:8080/api/payments/search?transaction_ref=TXN00049999"
```

Observed result:

```text
HTTP/1.1 200 OK
```

Response:

```json
{
  "query_ref": "TXN00049999",
  "count": 2,
  "items": [
    {
      "id": 49999,
      "transaction_ref": "TXN00049999",
      "customer_id": 666,
      "amount": "4509.01",
      "status": "FAILED"
    },
    {
      "id": 50000,
      "transaction_ref": "TXN00049999",
      "customer_id": 732,
      "amount": "80257.57",
      "status": "SUCCESS"
    }
  ]
}
```

This confirms that the current application:

- accepts a duplicate transaction reference;
- does not assume uniqueness;
- returns every matching transaction;
- returns the number of matches;
- does not generate HTTP 500 for the tested duplicate condition.

---

# 11. Preventive Controls

## 11.1 Test Duplicate References

Automated API tests should explicitly cover:

```text
0 matches
1 match
2+ matches
```

for `transaction_ref`.

A duplicate-reference test would prevent a future developer from accidentally changing the query back to single-result behavior.

---

## 11.2 Preserve Database Contract in Application Logic

Application developers should verify schema constraints before assuming that a searchable field is unique.

A field should only be treated as a unique identifier when that guarantee exists in the database or documented domain contract.

---

## 11.3 Regression Testing with Seeded Data

The assessment seed dataset contains useful edge cases such as duplicate references.

CI testing should execute transaction-search tests against representative seeded data so data-dependent failures can be detected before release.

---

## 11.4 Structured Exception Logging

Unexpected API exceptions should be logged with sufficient context for troubleshooting, while the public API continues returning a safe generic error response.

Useful diagnostic context includes:

```text
endpoint
transaction_ref
exception type
request/correlation ID
timestamp
```

Sensitive information should not be exposed in the client response.

---

## 11.5 Contract Tests

Tests should verify that the API behavior remains consistent with the database contract:

```text
transaction_ref is searchable
        +
transaction_ref is non-unique
        =
search endpoint returns collection
```

---

# 12. Evidence Summary

| Investigation | Finding |
|---|---|
| Incident | Intermittent HTTP 500 reported during transaction search |
| Database schema | `transaction_ref` is not UNIQUE |
| Seeded dataset | Duplicate references exist |
| Known duplicate | `TXN00049999` |
| Matching records | IDs `49999` and `50000` |
| Current implementation | Returns collection of matching transactions |
| Current API result | HTTP `200 OK` |
| Current result count | `2` |
| Original HTTP 500 | Not reliably reproducible in current implementation |
| Historical failure mechanism | Hypothetical single-result assumption |
| Correct behavior | Return all matching transactions |
| Index relationship | Performance only; does not enforce uniqueness |

---

# 13. Root Cause Statement

The original reported HTTP 500 condition could not be directly reproduced in the current MiniPay implementation because the application already supports multiple transactions sharing the same `transaction_ref`.

Based on the incident symptoms, supplied database schema, duplicate-containing dataset and existing corrective implementation, the probable historical root cause was an **application-level assumption that `transaction_ref` identified a single transaction despite the database providing no uniqueness guarantee**.

This would make the failure data-dependent: searches for references occurring once could succeed, while duplicated references could violate the application's expected result cardinality and potentially produce an unhandled HTTP 500.

Because the original defective implementation was not available in a reliably reproducible state, this historical mechanism is classified as a **hypothetical root cause rather than a directly reproduced finding**.

---

## Support Engineer Conclusion

The investigation verified that duplicate `transaction_ref` values are valid under the supplied database schema and exist in the assessment dataset.

The currently implemented MiniPay transaction-search endpoint correctly treats `transaction_ref` as a non-unique search field. Testing with `TXN00049999` returned both matching transactions and HTTP `200 OK`.

The original intermittent HTTP 500 could therefore not be faithfully reproduced in the current application state.

Rather than manufacture an artificial failure, the incident was analyzed using the available schema, dataset, current implementation and reported symptom. The likely historical failure was a mismatch between application-level single-result assumptions and database-level non-unique transaction references.

The current collection-based query behavior addresses this condition and should be protected through regression tests covering duplicate transaction references.