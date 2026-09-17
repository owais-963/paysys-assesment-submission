-- Reconciliation of successful transaction count/value vs callback success
-- count/value.
WITH successful_transactions AS (
  SELECT id, amount
  FROM transactions
  WHERE status = 'SUCCESS'
),
successful_callbacks AS (
  -- A transaction is considered callback-confirmed if it has at least one
  -- callback attempt recorded with callback_status = 'SUCCESS'.
  SELECT DISTINCT transaction_id
  FROM callbacks
  WHERE callback_status = 'SUCCESS'
)
SELECT
  (SELECT COUNT(*) FROM successful_transactions)                         AS successful_transaction_count,
  (SELECT COALESCE(SUM(amount), 0) FROM successful_transactions)         AS successful_transaction_value,
  (SELECT COUNT(*) FROM successful_callbacks)                            AS successful_callback_count,
  (
    SELECT COALESCE(SUM(t.amount), 0)
    FROM successful_transactions t
    JOIN successful_callbacks sc ON sc.transaction_id = t.id
  )                                                                       AS successful_callback_value,
  (
    SELECT COUNT(*)
    FROM successful_transactions t
    LEFT JOIN successful_callbacks sc ON sc.transaction_id = t.id
    WHERE sc.transaction_id IS NULL
  )                                                                       AS successful_tx_without_success_callback;
