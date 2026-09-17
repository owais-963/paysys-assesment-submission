"""Core diagnostic logic for a single transaction reference.

Deliberately split into:
  - fetch_transactions_by_ref / fetch_callbacks_for_transaction (support.db):
    thin, DB-touching functions.
  - detect_anomalies / recommend_action / build_transaction_diagnosis
    (this module): pure functions over plain dicts/lists, unit-tested
    without any database connection (see tests/test_diagnostics.py).
"""
from datetime import datetime
from typing import Optional

from support import db

ANOMALY_DUPLICATE_REFERENCE = "DUPLICATE_REFERENCE"
ANOMALY_STUCK_IN_PROCESSING = "STUCK_IN_PROCESSING"
ANOMALY_TRANSACTION_FAILED = "TRANSACTION_FAILED"
ANOMALY_MISSING_SUCCESS_CALLBACK = "MISSING_SUCCESS_CALLBACK"
ANOMALY_MISSING_COMPLETION_TIMESTAMP = "MISSING_COMPLETION_TIMESTAMP"

RECOMMENDATIONS = {
    ANOMALY_DUPLICATE_REFERENCE: (
        "Multiple transactions share this reference. Confirm with the "
        "customer whether this was a duplicate submission before taking "
        "any resolution action on either record."
    ),
    ANOMALY_STUCK_IN_PROCESSING: (
        "Transaction has been PROCESSING beyond the expected threshold. "
        "Check upstream processor connectivity and escalate if it does "
        "not resolve on its own."
    ),
    ANOMALY_TRANSACTION_FAILED: (
        "Review the failure_code with the payment processor/acquirer and "
        "confirm the customer was notified. Do not resubmit until the "
        "root cause is understood."
    ),
    ANOMALY_MISSING_SUCCESS_CALLBACK: (
        "Transaction is marked SUCCESS locally but no successful callback "
        "was recorded. Reconcile against the processor's callback logs "
        "before assuming the charge was confirmed end-to-end."
    ),
    ANOMALY_MISSING_COMPLETION_TIMESTAMP: (
        "Transaction is in a terminal state (SUCCESS/FAILED) but has no "
        "completed_at timestamp. This is a data-integrity issue worth "
        "flagging to engineering, independent of the payment outcome."
    ),
}

DEFAULT_RECOMMENDATION = "No anomalies detected; no action required."


def detect_anomalies(
    transaction: dict,
    callbacks: list[dict],
    *,
    duplicate_count: int,
    stuck_processing_minutes: int,
    now: Optional[datetime] = None,
) -> list[str]:
    now = now or datetime.now()
    anomalies: list[str] = []

    if duplicate_count > 1:
        anomalies.append(ANOMALY_DUPLICATE_REFERENCE)

    status = transaction["status"]
    completed_at = transaction.get("completed_at")

    if status == "PROCESSING":
        age_minutes = (now - transaction["created_at"]).total_seconds() / 60
        if age_minutes > stuck_processing_minutes:
            anomalies.append(ANOMALY_STUCK_IN_PROCESSING)

    if status == "FAILED":
        anomalies.append(ANOMALY_TRANSACTION_FAILED)

    if status == "SUCCESS":
        has_success_callback = any(cb["callback_status"] == "SUCCESS" for cb in callbacks)
        if not has_success_callback:
            anomalies.append(ANOMALY_MISSING_SUCCESS_CALLBACK)

    if status in ("SUCCESS", "FAILED") and not completed_at:
        anomalies.append(ANOMALY_MISSING_COMPLETION_TIMESTAMP)

    return anomalies


def recommend_action(anomalies: list[str]) -> str:
    if not anomalies:
        return DEFAULT_RECOMMENDATION
    return " ".join(RECOMMENDATIONS[a] for a in anomalies if a in RECOMMENDATIONS)


def build_transaction_diagnosis(
    transaction: dict,
    callbacks: list[dict],
    *,
    duplicate_count: int,
    stuck_processing_minutes: int,
    now: Optional[datetime] = None,
) -> dict:
    anomalies = detect_anomalies(
        transaction,
        callbacks,
        duplicate_count=duplicate_count,
        stuck_processing_minutes=stuck_processing_minutes,
        now=now,
    )
    return {
        "id": transaction["id"],
        "transaction_ref": transaction["transaction_ref"],
        "customer_id": transaction["customer_id"],
        "customer_ref": transaction.get("customer_ref"),
        "customer_name": transaction.get("customer_name"),
        "amount": str(transaction["amount"]),
        "status": transaction["status"],
        "created_at": transaction["created_at"].isoformat(),
        "completed_at": transaction["completed_at"].isoformat() if transaction.get("completed_at") else None,
        "failure_code": transaction.get("failure_code"),
        "callbacks": [
            {
                "attempt_no": cb["attempt_no"],
                "http_status": cb["http_status"],
                "callback_status": cb["callback_status"],
                "attempted_at": cb["attempted_at"].isoformat() if cb.get("attempted_at") else None,
            }
            for cb in callbacks
        ],
        "anomalies": anomalies,
        "recommended_action": recommend_action(anomalies),
    }


def diagnose_transaction(conn, transaction_ref: str, stuck_processing_minutes: int) -> dict:
    """Orchestrates the DB fetches and builds the full diagnosis result.

    Handles the case where transaction_ref matches more than one row --
    database/schema.sql does not enforce uniqueness on this column, and the
    Objective 1 seed data intentionally contains duplicates (see
    sql/04_duplicate_transaction_references.sql). Every match is diagnosed,
    not just the first/most-recent one.
    """
    rows = db.fetch_transactions_by_ref(conn, transaction_ref)
    duplicate_count = len(rows)
    transactions = [
        build_transaction_diagnosis(
            row,
            db.fetch_callbacks_for_transaction(conn, row["id"]),
            duplicate_count=duplicate_count,
            stuck_processing_minutes=stuck_processing_minutes,
        )
        for row in rows
    ]
    return {
        "query_ref": transaction_ref,
        "match_count": duplicate_count,
        "transactions": transactions,
    }
