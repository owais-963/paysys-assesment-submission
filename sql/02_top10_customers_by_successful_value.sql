-- Top 10 customers by successful transaction value.

--AI Generated SQL Query 
-- SELECT
--   c.id             AS customer_id,
--   c.customer_ref,
--   c.name,
--   COUNT(*)         AS successful_transaction_count,
--   SUM(t.amount)    AS successful_transaction_value
-- FROM transactions t
-- JOIN customers c ON c.id = t.customer_id
-- WHERE t.status = 'SUCCESS'
-- GROUP BY c.id, c.customer_ref, c.name
-- ORDER BY successful_transaction_value DESC
-- LIMIT 10;

--Optimized SQL Query
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
JOIN customers c
  ON c.id = tt.customer_id
ORDER BY tt.successful_transaction_value DESC
LIMIT 10;
