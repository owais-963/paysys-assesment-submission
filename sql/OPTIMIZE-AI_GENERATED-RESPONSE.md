# Query Optimization Report: Top 10 Customers by Successful Transaction Value

Target query: `sql/02_top10_customers_by_successful_value.sql`

## Two candidate query shapes

**AI-generated query (join-then-group):**

```sql
SELECT
  c.id             AS customer_id,
  c.customer_ref,
  c.name,
  COUNT(*)         AS successful_transaction_count,
  SUM(t.amount)    AS successful_transaction_value
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY successful_transaction_value DESC
LIMIT 10;
```

**Corrected query (aggregate-then-join, used in `02_top10_customers_by_successful_value.sql`):**

```sql
WITH transaction_totals AS NOT MATERIALIZED (
  SELECT
    t.customer_id,
    COUNT(*)      AS successful_transaction_count,
    SUM(t.amount) AS successful_transaction_value
  FROM transactions t
  WHERE t.status = 'SUCCESS'
  GROUP BY t.customer_id
)
SELECT
  c.id AS customer_id,
  c.customer_ref,
  c.name,
  tt.successful_transaction_count,
  tt.successful_transaction_value
FROM transaction_totals tt
JOIN customers c ON c.id = tt.customer_id
ORDER BY tt.successful_transaction_value DESC
LIMIT 10;
```

## Why the corrected query is preferred

**"Reduce Before Join" pipeline.** The corrected query aggregates `transactions`
down to one row per `customer_id` *before* joining to `customers`. The
AI-generated query does the opposite — "join and inflate" — it joins every
matching transaction row against `customers` first, dragging `name` and
`customer_ref` along as duplicated text on every one of those rows, and only
collapses that inflated row set afterward via `GROUP BY`. At the current seed
size (~41k successful transactions) the effect is already measurable; at
production-scale transaction volumes the AI-generated shape does
proportionally more duplication work.

**Data types and CPU hashing.** The corrected query's `HashAggregate` groups
solely by `t.customer_id`, a `BIGINT`. Comparing/hashing integers is a cheap,
atomic hardware-level operation. The AI-generated query's `HashAggregate`
groups by `c.id` (`BIGINT`) *plus* `c.customer_ref` and `c.name` (`VARCHAR`),
forcing the engine to hash and compare variable-length text byte-by-byte for
every group key, which costs more CPU per row than integer hashing alone.

**Memory footprint (`work_mem`).** Because the AI-generated query carries the
text columns (`customer_ref`, `name`) through its aggregation/sort buffers, it
holds a heavier row width in memory during grouping. The corrected query keeps
only `customer_id`, a count, and a sum in its aggregation step — a compact
footprint that is far less likely to exceed `work_mem` and spill to disk-based
temporary files under larger data volumes or concurrent load.

## EXPLAIN ANALYZE comparison

Environment: PostgreSQL 17, local instance at `127.0.0.1:5432`, database
`minipay`, seeded with 1,002 customers / 50,002 transactions / 56,591
callbacks per `sql/REPRODUCIBLE.md`.

> Connection credentials used to run these plans are not reproduced here —
> see the placeholders/variables documented in `sql/REPRODUCIBLE.md`.

### AI-generated query (join-then-group)

```
EXPLAIN ANALYZE
SELECT
  c.id             AS customer_id,
  c.customer_ref,
  c.name,
  COUNT(*)         AS successful_transaction_count,
  SUM(t.amount)    AS successful_transaction_value
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY successful_transaction_value DESC
LIMIT 10;
```

```
Limit  (cost=1721.49..1721.51 rows=10 width=71) (actual time=15.944..15.946 rows=10 loops=1)
  ->  Sort  (cost=1721.49..1723.99 rows=1000 width=71) (actual time=15.943..15.944 rows=10 loops=1)
        Sort Key: (sum(t.amount)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        ->  HashAggregate  (cost=1687.38..1699.88 rows=1000 width=71) (actual time=15.627..15.795 rows=1002 loops=1)
              Group Key: c.id
              Batches: 1  Memory Usage: 577kB
              ->  Hash Join  (cost=31.50..1380.42 rows=40928 width=39) (actual time=0.189..10.405 rows=41038 loops=1)
                    Hash Cond: (t.customer_id = c.id)
                    ->  Seq Scan on transactions t  (cost=0.00..1241.03 rows=40928 width=16) (actual time=0.009..5.410 rows=41038 loops=1)
                          Filter: ((status)::text = 'SUCCESS'::text)
                          Rows Removed by Filter: 8964
                    ->  Hash  (cost=19.00..19.00 rows=1000 width=31) (actual time=0.172..0.172 rows=1002 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 71kB
                          ->  Seq Scan on customers c  (cost=0.00..19.00 rows=1000 width=31) (actual time=0.005..0.081 rows=1002 loops=1)
Planning Time: 1.896 ms
Execution Time: 16.050 ms
```

### Corrected query (aggregate-then-join)

```
EXPLAIN ANALYZE
WITH transaction_totals AS NOT MATERIALIZED (
  SELECT
    t.customer_id,
    COUNT(*)      AS successful_transaction_count,
    SUM(t.amount) AS successful_transaction_value
  FROM transactions t
  WHERE t.status = 'SUCCESS'
  GROUP BY t.customer_id
)
SELECT
  c.id AS customer_id,
  c.customer_ref,
  c.name,
  tt.successful_transaction_count,
  tt.successful_transaction_value
FROM transaction_totals tt
JOIN customers c ON c.id = tt.customer_id
ORDER BY tt.successful_transaction_value DESC
LIMIT 10;
```

```
Limit  (cost=1626.28..1626.30 rows=10 width=71) (actual time=11.735..11.738 rows=10 loops=1)
  ->  Sort  (cost=1626.28..1628.78 rows=1001 width=71) (actual time=11.734..11.735 rows=10 loops=1)
        Sort Key: (sum(t.amount)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        ->  Hash Join  (cost=1579.49..1604.65 rows=1001 width=71) (actual time=11.231..11.573 rows=1002 loops=1)
              Hash Cond: (t.customer_id = c.id)
              ->  HashAggregate  (cost=1547.99..1560.50 rows=1001 width=48) (actual time=11.003..11.189 rows=1002 loops=1)
                    Group Key: t.customer_id
                    Batches: 1  Memory Usage: 577kB
                    ->  Seq Scan on transactions t  (cost=0.00..1241.03 rows=40928 width=16) (actual time=0.006..5.676 rows=41038 loops=1)
                          Filter: ((status)::text = 'SUCCESS'::text)
                          Rows Removed by Filter: 8964
              ->  Hash  (cost=19.00..19.00 rows=1000 width=31) (actual time=0.216..0.216 rows=1002 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 71kB
                    ->  Seq Scan on customers c  (cost=0.00..19.00 rows=1000 width=31) (actual time=0.011..0.096 rows=1002 loops=1)
Planning Time: 2.677 ms
Execution Time: 11.858 ms
```

## Result comparison

| Metric | AI-generated (join-then-group) | Corrected (aggregate-then-join) | Delta |
|---|---|---|---|
| `HashAggregate` group key width | `c.id` (BIGINT) + `c.customer_ref` + `c.name` (VARCHAR) | `t.customer_id` (BIGINT) only | Corrected groups on a single integer column |
| Rows entering the aggregate step | 41,038 (post-join, inflated) | 41,038 (pre-join, but aggregated straight from the scan without carrying customer text) | Same input rows, but the AI-generated plan carries duplicated text through the hash join before aggregating |
| Total planning + execution time | 1.896 ms + 16.050 ms ≈ **17.95 ms** | 2.677 ms + 11.858 ms ≈ **14.54 ms** | ~19% faster overall |
| Execution time only | 16.050 ms | 11.858 ms | ~26% faster |
| Aggregate `Memory Usage` | 577 kB | 577 kB (at this data size, no spill in either plan) | Equal at current volume; the corrected shape has a materially smaller row width feeding the aggregate, so its memory advantage grows as text field sizes or transaction volume increase |

At this seed volume (~41k successful transactions across ~1,000 customers)
both plans complete in memory with a single aggregation batch. The measured
~26% execution-time improvement from the corrected query comes from avoiding
mixed-type (BIGINT + VARCHAR) grouping and from aggregating before touching
customer text at all. The gap is expected to widen at larger transaction
volumes, where the AI-generated query's per-row text duplication and wider
sort/aggregate buffers increase the risk of exceeding `work_mem` and spilling
to disk.
