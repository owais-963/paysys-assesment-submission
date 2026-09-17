# MiniPay SQL Performance Investigation: Transaction Lookup by `transaction_ref`

## Why this access pattern was selected

`transaction_ref` is the natural key an L2 support engineer or an external
caller (webhook retry, reconciliation job, support ticket lookup) uses to
find a specific transaction — for example, the CLI usage pattern
`support_tool.py --transaction TXN000123`. The supplied schema
(`database/schema.sql`) defines `transaction_ref` as a plain
`VARCHAR(50) NOT NULL` column with **no index**:

```sql
CREATE TABLE transactions (
  id BIGSERIAL PRIMARY KEY,
  transaction_ref VARCHAR(50) NOT NULL,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  status VARCHAR(20) NOT NULL CHECK (status IN ('PROCESSING','SUCCESS','FAILED')),
  created_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP NULL,
  failure_code VARCHAR(40) NULL
);
-- Intentionally minimal indexing. Candidate should assess indexing based on workload.
```

Every single-transaction lookup by reference therefore has to scan the
entire table. This is a high-frequency, latency-sensitive access pattern
(support tooling, API `GET` by reference, reconciliation), which makes it a
representative "poor access pattern" to investigate and fix.

## Dataset size used during testing

- Database: PostgreSQL 17, local instance (`127.0.0.1:5432`, database `minipay`)
- Table `transactions`: **50,002 rows** (seeded via `database/generate_data.py`)
- Base table size: `4928 kB`
- The generator intentionally seeds a small number of duplicate
  `transaction_ref` values (every 5,000th transaction reuses the previous
  reference), which is directly relevant to the indexing decision below.

## Original query

```sql
SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code
FROM transactions
WHERE transaction_ref = 'TXN00024999';
```

`TXN00024999` was chosen because it is one of the generator's intentional
duplicate references — it maps to two rows in the table, which is realistic
for this dataset and confirms the query and index behave correctly against
duplicate values, not just unique ones.

## Before optimization: `EXPLAIN (ANALYZE, BUFFERS)`

Captured with no index on `transaction_ref` (the index was dropped for this
test to reproduce the schema's original state):

```
Seq Scan on transactions  (cost=0.00..1241.03 rows=1 width=74) (actual time=2.009..3.961 rows=2 loops=1)
  Filter: ((transaction_ref)::text = 'TXN00024999'::text)
  Rows Removed by Filter: 50000
  Buffers: shared hit=616
Planning:
  Buffers: shared hit=81
Planning Time: 1.126 ms
Execution Time: 3.978 ms
```

**Reading the plan:**

- **Seq Scan on transactions** — PostgreSQL has no way to jump directly to
  the matching rows, so it reads every row in the table in physical order
  and evaluates the filter against each one.
- **Rows Removed by Filter: 50000** — of the 50,002 rows scanned, 50,000
  were read, evaluated, and discarded because they didn't match
  `transaction_ref = 'TXN00024999'`. Only the 2 matching rows were kept.
  This is pure wasted work that scales linearly with table size.
- **Buffers: shared hit=616** — 616 8 KB pages were read from the shared
  buffer cache to satisfy the scan. This corresponds to reading essentially
  the whole table (4928 kB base table size). Every one of those buffer
  reads is I/O/CPU work the engine has to do regardless of how many rows
  actually match.
- **Planning Time: 1.126 ms** — time the planner spent choosing this (only
  available) plan.
- **Execution Time: 3.978 ms** — time actually spent scanning the table and
  returning the 2 matching rows.

**Root cause:** no index exists on `transactions.transaction_ref`. The only
existing index is the primary key on `id` (`transactions_pkey`), which is
useless for a lookup keyed on `transaction_ref`. Without an index, a full
sequential scan is the *only* plan available to PostgreSQL for this
predicate, regardless of how selective the filter is.

## Optimization applied

```sql
CREATE INDEX IF NOT EXISTS idx_transactions_transaction_ref
ON transactions (transaction_ref);
```

**Why non-unique:** a unique index cannot be created on this column,
because the seeded dataset legitimately contains duplicate
`transaction_ref` values by design (verified directly against this
dataset):

```
CREATE UNIQUE INDEX test_unique_check ON transactions (transaction_ref);
ERROR:  could not create unique index "test_unique_check"
DETAIL:  Key (transaction_ref)=(TXN00029999) is duplicated.
```

This duplication is itself one of the intentional investigation points in
this dataset (see `sql/04_duplicate_transaction_references.sql`) — a
duplicate `transaction_ref` most likely represents a retried/re-submitted
payment or a client-side resubmission bug, not something the index layer
should silently reject. A standard (non-unique) B-tree index supports fast
equality lookups without imposing a uniqueness constraint the data doesn't
actually satisfy.

## After optimization: `EXPLAIN (ANALYZE, BUFFERS)`

Same query, same data, after creating the index above:

```
Index Scan using idx_transactions_transaction_ref on transactions  (cost=0.29..8.31 rows=1 width=74) (actual time=0.040..0.040 rows=2 loops=1)
  Index Cond: ((transaction_ref)::text = 'TXN00024999'::text)
  Buffers: shared hit=1 read=2
Planning:
  Buffers: shared hit=102 read=1
Planning Time: 1.345 ms
Execution Time: 0.056 ms
```

**Reading the plan:**

- **Index Scan using idx_transactions_transaction_ref** — the planner now
  navigates the B-tree index directly to the matching key(s) instead of
  reading the whole table. It found the 2 matching rows via the index and
  fetched only those rows from the table.
- **Buffers: shared hit=1 read=2** — only 3 total buffer accesses were
  needed (1 cache hit, 2 reads) to resolve the query, versus 616 buffers
  under the sequential scan. This is the direct, measured cause of the
  execution-time improvement.
- **Planning Time: 1.345 ms** — slightly higher than the before-case
  (1.126 ms); the planner now has an additional index to evaluate as a
  candidate plan, which adds a small, fixed amount of planning overhead.
- **Execution Time: 0.056 ms** — down from 3.978 ms. The engine did a
  handful of index-page/table-page reads instead of scanning the entire
  table.

## Before / after comparison

| Metric | Before (no index) | After (`idx_transactions_transaction_ref`) |
|---|---|---|
| Scan type | Seq Scan | Index Scan |
| Rows examined | 50,002 (50,000 discarded) | 2 (only matching rows) |
| Buffers touched (execution) | 616 | 3 (1 hit + 2 read) |
| Planning Time | 1.126 ms | 1.345 ms |
| Execution Time | 3.978 ms | 0.056 ms |

## Measured performance improvement

Using the actual execution times captured above:

- Execution time improvement: `3.978 ms -> 0.056 ms`
- Reduction: `3.978 - 0.056 = 3.922 ms`
- Relative improvement: `3.922 / 3.978 = 98.6%` faster execution
- Expressed as a speedup factor: `3.978 / 0.056 ≈ 71x` faster

(Planning time increased slightly, from 1.126 ms to 1.345 ms, but this is
negligible next to the execution-time gain and is a fixed per-query cost,
not one that scales with table size.)

## Index trade-offs

- **Disk usage:** the new index (`idx_transactions_transaction_ref`)
  measures `1552 kB` on this 50,002-row table, against a base table size of
  `4928 kB` — roughly an additional ~31% of storage on top of the table
  itself for this table alone. This scales roughly linearly with row count
  and with the length of `transaction_ref` values.
- **INSERT/UPDATE overhead:** every `INSERT` into `transactions`, and every
  `UPDATE` that changes `transaction_ref`, now has to also insert/update an
  entry in this B-tree index, in addition to the heap write. For an
  append-heavy table like `transactions` (50k+ rows seeded, presumably
  growing continuously in production), this is a small, constant
  per-write cost, not a one-time cost — it is paid on every write for the
  life of the table.
- **Net assessment:** for a table where `transaction_ref` is looked up
  far more often than the column is written (typical for payment lookups:
  one write per transaction, potentially many reads per transaction from
  support tooling, retries, and reconciliation), the read-side savings
  measured above vastly outweigh the modest, constant write-side and
  storage overhead.

## Production considerations

- This index should be created with `CREATE INDEX CONCURRENTLY` in a live
  production database to avoid holding a blocking lock on `transactions`
  while the index is built, at the cost of a longer, non-transactional
  build process.
- The index should be monitored over time (`pg_stat_user_indexes`) to
  confirm it is actually being used by the query planner in production,
  and re-evaluated if application query patterns change (for example, if
  lookups start filtering on `transaction_ref` combined with another
  column, a composite index may be more effective than this single-column
  one).
- Because duplicate `transaction_ref` values are possible, any application
  code that assumes a unique result for a reference lookup must explicitly
  handle the multi-row case rather than relying on the database to enforce
  uniqueness.

## Conclusion

The transaction-reference lookup was a full-table sequential scan because
`transactions.transaction_ref` had no supporting index, despite being the
primary key end users and support tooling search on. Measured against this
seeded 50,002-row dataset, adding a standard (non-unique) B-tree index on
`transaction_ref` reduced buffer accesses from 616 to 3 and cut measured
execution time from 3.978 ms to 0.056 ms — roughly a 71x speedup — with a
small, well-understood trade-off in extra index storage (~1552 kB on this
table) and marginally slower writes. A unique index is not viable, because
the dataset (and the underlying business scenario of retried/duplicate
submissions) contains legitimate duplicate `transaction_ref` values, which
was confirmed directly against this database rather than assumed.
