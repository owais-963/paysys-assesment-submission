# INCIDENT-003 — Root Cause Analysis

**Priority:** P2  
**Component:** PostgreSQL / Transaction Search  
**Environment:** Local Development Environment  
**Status:** Resolved

---

## 1. Incident Summary

INCIDENT-003 reports slow transaction investigation when transactions are searched using `transaction_ref`.

The investigation focused on the database execution plan for the transaction lookup rather than assuming the application or network was responsible for the latency.

`EXPLAIN (ANALYZE, BUFFERS)` showed that PostgreSQL was performing a sequential scan of the `transactions` table because no suitable index existed for `transaction_ref`.

Although the assessment dataset is relatively small, the execution plan required PostgreSQL to examine almost the entire table to locate only two matching transactions. This represents a scalability issue because the amount of work increases as transaction volume grows.

A non-unique B-tree index was created on `transactions(transaction_ref)`. After the correction, PostgreSQL changed from a sequential scan to an index scan.

---

# 2. Investigation

The transaction lookup used by the application filters transactions using:

```sql
WHERE transaction_ref = 'TXN00049999'
```

To determine how PostgreSQL executed this lookup, the following query was used:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id,
       transaction_ref,
       customer_id,
       amount,
       status,
       created_at,
       completed_at,
       failure_code
FROM transactions
WHERE transaction_ref = 'TXN00049999';
```

`EXPLAIN ANALYZE` was used because it provides both PostgreSQL's selected execution strategy and actual runtime statistics.

`BUFFERS` was included to show the database pages accessed during execution.

---

# 3. Before-Fix Evidence

Before adding an index on `transaction_ref`, PostgreSQL produced:

```text
Seq Scan on transactions
  (cost=0.00..1241.03 rows=1 width=74)
  (actual time=3.615..3.616 rows=2 loops=1)

  Filter:
  ((transaction_ref)::text = 'TXN00049999'::text)

  Rows Removed by Filter: 50002

  Buffers: shared hit=616

Planning Time: 0.106 ms
Execution Time: 3.637 ms
```

The important findings were:

| Metric | Result |
|---|---:|
| Execution strategy | Sequential Scan |
| Matching rows | 2 |
| Rows removed by filter | 50,002 |
| Shared buffers hit | 616 |
| Planning time | 0.106 ms |
| Execution time | 3.637 ms |

PostgreSQL therefore examined approximately the entire transaction table to locate only two matching records.

---

# 4. Root Cause

The root cause was the absence of an index supporting transaction lookup by:

```sql
transaction_ref
```

The application performs an equality lookup:

```sql
WHERE transaction_ref = ?
```

Without an appropriate index, PostgreSQL had no efficient access path for locating the requested transaction reference.

The execution strategy was therefore:

```text
Transaction Search
        |
        v
WHERE transaction_ref = ?
        |
        v
No suitable index
        |
        v
Sequential Scan
        |
        v
Examine table rows
        |
        v
Discard non-matching rows
```

In the captured execution, PostgreSQL discarded **50,002 rows** to return only **2 matching rows**.

The measured local execution time was only a few milliseconds because the assessment dataset is relatively small and pages were already available in shared buffers. However, the execution strategy does not scale efficiently as transaction volume increases.

---

# 5. Correction

A non-unique index was created:

```sql
CREATE INDEX idx_transactions_transaction_ref
ON transactions(transaction_ref);
```

A **non-unique** index was intentionally used.

The supplied database schema does not define `transaction_ref` as unique, and duplicate transaction references exist in the dataset. The index should therefore optimize lookup without changing the data model or preventing legitimate duplicate values.

Conceptually:

```text
transactions
      |
      +-- Primary Key Index (id)
      |
      +-- idx_transactions_transaction_ref
                     |
                     v
              transaction_ref lookup
```

---

# 6. After-Fix Validation

After creating the index, the exact same query was executed again:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id,
       transaction_ref,
       customer_id,
       amount,
       status,
       created_at,
       completed_at,
       failure_code
FROM transactions
WHERE transaction_ref = 'TXN00049999';
```

PostgreSQL returned:

```text
Index Scan using idx_transactions_transaction_ref on transactions
  (cost=0.29..8.31 rows=1 width=74)
  (actual time=0.062..0.063 rows=2 loops=1)

  Index Cond:
  ((transaction_ref)::text = 'TXN00049999'::text)

  Buffers: shared hit=1 read=2

Planning:
  Buffers: shared hit=16 read=1

Planning Time: 2.109 ms
Execution Time: 0.080 ms
```

PostgreSQL successfully changed its execution strategy from:

```text
Seq Scan
```

to:

```text
Index Scan using idx_transactions_transaction_ref
```

---

# 7. Before vs After Comparison

| Metric | Before | After |
|---|---:|---:|
| Scan type | Sequential Scan | Index Scan |
| Matching rows | 2 | 2 |
| Rows removed by filter | 50,002 | Not required |
| Execution buffers | 616 shared hits | 1 shared hit + 2 reads |
| Planning time | 0.106 ms | 2.109 ms |
| Execution time | 3.637 ms | 0.080 ms |

The measured query execution time decreased from:

```text
3.637 ms
```

to:

```text
0.080 ms
```

This is approximately a **45.5× reduction in measured execution time**, or approximately **97.8% lower execution time** in the captured runs.

The more important improvement is the change in execution strategy. PostgreSQL no longer scans the transaction table and filters tens of thousands of unrelated rows to find the requested reference.

The increased planning time observed in the second individual execution is recorded rather than excluded from the evidence. Planning time can vary between individual executions; the primary optimization demonstrated here is the elimination of the sequential table scan.

---

# 8. Functional Validation

The index is non-unique and therefore does not change the expected application behavior.

For the known duplicate reference:

```text
TXN00049999
```

both matching transactions can still be returned.

The index changes how PostgreSQL locates those rows, not how many matching rows are valid.

Therefore:

```text
Before:
transaction_ref
      ↓
Sequential Scan
      ↓
2 results

After:
transaction_ref
      ↓
Index Scan
      ↓
2 results
```

This preserves the application's existing duplicate-reference handling while improving lookup efficiency.

---

# 9. Why a UNIQUE Index Was Not Used

The following would not be appropriate:

```sql
CREATE UNIQUE INDEX idx_transactions_transaction_ref
ON transactions(transaction_ref);
```

The supplied schema permits duplicate `transaction_ref` values and the dataset contains such duplicates.

Changing the column to effectively enforce uniqueness would alter the application's data contract and could cause existing data or future inserts to fail.

The appropriate optimization is therefore:

```sql
CREATE INDEX idx_transactions_transaction_ref
ON transactions(transaction_ref);
```

rather than a unique index.

---

# 10. Preventive Controls

## Database Query Review

Frequently searched and filtered columns should be reviewed as part of database and application design.

Queries used by operational investigation paths should have execution plans inspected before production release.

## Performance Testing

Representative production-scale datasets should be used for performance testing.

A query that appears fast with thousands of rows may become operationally expensive when the table grows to millions of transactions.

## Execution Plan Validation

Critical queries should periodically be inspected using:

```sql
EXPLAIN (ANALYZE, BUFFERS)
```

This helps identify:

- sequential scans;
- excessive rows filtered;
- inefficient joins;
- unnecessary buffer usage;
- missing or unused indexes.

## Database Monitoring

Production PostgreSQL environments should monitor slow and frequently executed queries using appropriate database observability mechanisms.

Query latency and execution frequency can then be used to identify candidates for optimization.

## Index Review

Indexes should be reviewed against actual application access patterns.

Indexes also have storage and write-maintenance costs, so they should be created based on demonstrated query requirements rather than indexing every column.

---

# 11. Evidence Summary

| Evidence | Finding |
|---|---|
| Lookup field | `transaction_ref` |
| Before scan | Sequential Scan |
| Rows returned | 2 |
| Rows discarded before fix | 50,002 |
| Buffers before | 616 shared hits |
| Execution time before | 3.637 ms |
| Correction | Non-unique B-tree index |
| Index | `idx_transactions_transaction_ref` |
| After scan | Index Scan |
| Buffers after | 1 shared hit + 2 reads |
| Execution time after | 0.080 ms |
| Measured execution-time reduction | ~97.8% |
| Measured speed factor | ~45.5× |
| Application semantics | Unchanged |

---

# 12. Root Cause Statement

INCIDENT-003 was caused by a **missing database index on `transactions.transaction_ref`**, despite `transaction_ref` being used as a transaction-search field.

Without the index, PostgreSQL performed a sequential scan and discarded 50,002 rows to locate two matching transactions.

A non-unique B-tree index was added to `transaction_ref`. After the correction, PostgreSQL selected an index scan and the measured query execution time decreased from `3.637 ms` to `0.080 ms`.

The non-unique index preserves the existing database contract, including duplicate transaction references, while providing an efficient access path for transaction investigation.

---

## Support Engineer Conclusion

The incident was investigated from the database execution layer using `EXPLAIN (ANALYZE, BUFFERS)`.

The initial execution plan demonstrated that transaction-reference searches required a sequential scan of the `transactions` table. This explained why the lookup pattern would become increasingly expensive as transaction volume grew.

A non-unique index on `transaction_ref` was introduced, after which PostgreSQL selected an index scan for the same lookup. The captured execution time improved from `3.637 ms` to `0.080 ms`, while both matching transactions continued to be returned.

The correction improves transaction investigation performance without changing the supplied schema's non-unique transaction-reference semantics.