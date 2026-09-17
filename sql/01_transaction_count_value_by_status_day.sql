-- Transaction count and total value by status and day.
SELECT
  DATE(created_at)   AS transaction_day,
  status,
  COUNT(*)           AS transaction_count,
  SUM(amount)        AS total_value
FROM transactions
GROUP BY DATE(created_at), status
ORDER BY transaction_day, status;
