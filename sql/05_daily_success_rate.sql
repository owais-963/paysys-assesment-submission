-- Daily success rate percentage.
SELECT
  DATE(created_at)                                AS transaction_day,
  COUNT(*)                                         AS total_transactions,
  COUNT(*) FILTER (WHERE status = 'SUCCESS')       AS successful_transactions,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE status = 'SUCCESS') / COUNT(*),
    2
  )                                                AS success_rate_pct
FROM transactions
GROUP BY DATE(created_at)
ORDER BY transaction_day;
