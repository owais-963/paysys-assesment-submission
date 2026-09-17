"""Unit tests for the pure diagnostic logic in support/diagnostics.py.

No database connection is used anywhere in this file -- every input is a
plain dict/list, matching the shape support/db.py's fetch functions return.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from support.diagnostics import (
    ANOMALY_DUPLICATE_REFERENCE,
    ANOMALY_MISSING_COMPLETION_TIMESTAMP,
    ANOMALY_MISSING_SUCCESS_CALLBACK,
    ANOMALY_STUCK_IN_PROCESSING,
    ANOMALY_TRANSACTION_FAILED,
    DEFAULT_RECOMMENDATION,
    build_transaction_diagnosis,
    detect_anomalies,
    recommend_action,
)


def make_transaction(**overrides):
    base = {
        "id": 1,
        "transaction_ref": "TXN000123",
        "customer_id": 10,
        "customer_ref": "CUST000010",
        "customer_name": "Test Customer",
        "amount": Decimal("100.00"),
        "status": "SUCCESS",
        "created_at": datetime(2026, 9, 1, 12, 0, 0),
        "completed_at": datetime(2026, 9, 1, 12, 0, 30),
        "failure_code": None,
    }
    base.update(overrides)
    return base


def make_callback(**overrides):
    base = {
        "attempt_no": 1,
        "http_status": 200,
        "callback_status": "SUCCESS",
        "attempted_at": datetime(2026, 9, 1, 12, 0, 30),
    }
    base.update(overrides)
    return base


def test_no_anomalies_for_clean_success():
    tx = make_transaction()
    callbacks = [make_callback()]
    anomalies = detect_anomalies(
        tx, callbacks, duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert anomalies == []
    assert recommend_action(anomalies) == DEFAULT_RECOMMENDATION


def test_stuck_in_processing_detected_past_threshold():
    tx = make_transaction(status="PROCESSING", completed_at=None)
    now = tx["created_at"] + timedelta(minutes=20)
    anomalies = detect_anomalies(
        tx, [], duplicate_count=1, stuck_processing_minutes=15, now=now
    )
    assert ANOMALY_STUCK_IN_PROCESSING in anomalies


def test_processing_within_threshold_is_not_flagged():
    tx = make_transaction(status="PROCESSING", completed_at=None)
    now = tx["created_at"] + timedelta(minutes=5)
    anomalies = detect_anomalies(
        tx, [], duplicate_count=1, stuck_processing_minutes=15, now=now
    )
    assert ANOMALY_STUCK_IN_PROCESSING not in anomalies


def test_failed_status_is_flagged():
    tx = make_transaction(status="FAILED", failure_code="UPSTREAM_ERROR")
    anomalies = detect_anomalies(
        tx, [], duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_TRANSACTION_FAILED in anomalies


def test_success_without_success_callback_is_flagged():
    tx = make_transaction(status="SUCCESS")
    callbacks = [make_callback(callback_status="FAILED", http_status=500)]
    anomalies = detect_anomalies(
        tx, callbacks, duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_MISSING_SUCCESS_CALLBACK in anomalies


def test_success_with_success_callback_is_not_flagged():
    tx = make_transaction(status="SUCCESS")
    callbacks = [make_callback()]
    anomalies = detect_anomalies(
        tx, callbacks, duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_MISSING_SUCCESS_CALLBACK not in anomalies


def test_missing_completion_timestamp_flagged_for_terminal_status():
    tx = make_transaction(status="SUCCESS", completed_at=None)
    anomalies = detect_anomalies(
        tx, [make_callback()], duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_MISSING_COMPLETION_TIMESTAMP in anomalies


def test_missing_completion_timestamp_not_flagged_while_processing():
    tx = make_transaction(status="PROCESSING", completed_at=None)
    anomalies = detect_anomalies(
        tx, [], duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_MISSING_COMPLETION_TIMESTAMP not in anomalies


def test_duplicate_reference_flagged_when_multiple_rows_matched():
    tx = make_transaction()
    anomalies = detect_anomalies(
        tx, [make_callback()], duplicate_count=2, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_DUPLICATE_REFERENCE in anomalies


def test_duplicate_reference_not_flagged_for_single_match():
    tx = make_transaction()
    anomalies = detect_anomalies(
        tx, [make_callback()], duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert ANOMALY_DUPLICATE_REFERENCE not in anomalies


def test_recommend_action_joins_multiple_anomalies():
    action = recommend_action([ANOMALY_TRANSACTION_FAILED, ANOMALY_DUPLICATE_REFERENCE])
    assert "failure_code" in action or "acquirer" in action
    assert "duplicate submission" in action


def test_build_transaction_diagnosis_shapes_output():
    tx = make_transaction()
    callbacks = [make_callback()]
    diagnosis = build_transaction_diagnosis(
        tx, callbacks, duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert diagnosis["transaction_ref"] == "TXN000123"
    assert diagnosis["amount"] == "100.00"
    assert diagnosis["created_at"] == tx["created_at"].isoformat()
    assert diagnosis["completed_at"] == tx["completed_at"].isoformat()
    assert diagnosis["anomalies"] == []
    assert diagnosis["recommended_action"] == DEFAULT_RECOMMENDATION
    assert len(diagnosis["callbacks"]) == 1
    assert diagnosis["callbacks"][0]["callback_status"] == "SUCCESS"


def test_build_transaction_diagnosis_handles_no_completed_at():
    tx = make_transaction(status="PROCESSING", completed_at=None)
    diagnosis = build_transaction_diagnosis(
        tx, [], duplicate_count=1, stuck_processing_minutes=15, now=tx["created_at"]
    )
    assert diagnosis["completed_at"] is None
