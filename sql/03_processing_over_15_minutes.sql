-- Transactions in PROCESSING for more than 15 minutes.
--
-- NOTE: generate_data.py seeds transaction created_at timestamps starting
-- from a fixed base of 2026-09-01 (with created times spread across the
-- following 10 days). Because this operational query compares against
-- NOW(), once the current date is past that seed window, almost every
-- PROCESSING row in the seeded dataset will already be more than 15 minutes
-- old and will qualify. That is expected for a live/operational query and
-- is not a defect in the query itself -- it just means this query is only
-- meaningful for genuinely "stuck" transactions when run against live data
-- close to when those transactions were created.
SELECT
  id,
  transaction_ref,
  customer_id,
  amount,
  status,
  created_at,
  NOW() - created_at AS time_in_processing
FROM transactions
WHERE status = 'PROCESSING'
  AND created_at < NOW() - INTERVAL '15 minutes'
ORDER BY created_at ASC;

-- For a reproducible historical investigation against this seeded dataset
-- (so results don't drift as real time passes), pin the "as of" timestamp
-- instead of using NOW(). Example using a fixed analysis timestamp:
--
-- SELECT
--   id,
--   transaction_ref,
--   customer_id,
--   amount,
--   status,
--   created_at,
--   TIMESTAMP '2026-09-11 00:00:00' - created_at AS time_in_processing
-- FROM transactions
-- WHERE status = 'PROCESSING'
--   AND created_at < TIMESTAMP '2026-09-11 00:00:00' - INTERVAL '15 minutes'
-- ORDER BY created_at ASC;
