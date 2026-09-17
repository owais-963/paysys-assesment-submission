-- Average and p95 processing time (created_at -> completed_at), in seconds,
-- for transactions that have completed (SUCCESS or FAILED).
SELECT
  ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - created_at))), 3)                          AS avg_processing_seconds,
  ROUND(
    PERCENTILE_CONT(0.95) WITHIN GROUP (
      ORDER BY EXTRACT(EPOCH FROM (completed_at - created_at))
    )::numeric,
    3
  )                                                                                        AS p95_processing_seconds
FROM transactions
WHERE completed_at IS NOT NULL;
