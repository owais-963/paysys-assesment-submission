-- Top 10 customers by successful transaction value.

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
