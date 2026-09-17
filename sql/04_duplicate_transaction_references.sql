-- Duplicate transaction references.
SELECT
  transaction_ref,
  COUNT(*)                      AS occurrence_count,
  ARRAY_AGG(id ORDER BY id)     AS transaction_ids
FROM transactions
GROUP BY transaction_ref
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC, transaction_ref;
