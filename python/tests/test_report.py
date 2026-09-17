from support.report import render_health_report, render_summary_report, render_text_report


def test_render_text_report_no_match():
    result = {"query_ref": "TXN999999", "match_count": 0, "transactions": []}
    text = render_text_report(result)
    assert "No transaction found" in text
    assert "TXN999999" in text


def test_render_text_report_single_match():
    result = {
        "query_ref": "TXN000123",
        "match_count": 1,
        "transactions": [
            {
                "id": 1,
                "transaction_ref": "TXN000123",
                "customer_id": 10,
                "customer_ref": "CUST000010",
                "customer_name": "Test Customer",
                "amount": "100.00",
                "status": "SUCCESS",
                "created_at": "2026-09-01T12:00:00",
                "completed_at": "2026-09-01T12:00:30",
                "failure_code": None,
                "callbacks": [],
                "anomalies": [],
                "recommended_action": "No anomalies detected; no action required.",
            }
        ],
    }
    text = render_text_report(result)
    assert "TXN000123" in text
    assert "Test Customer" in text
    assert "SUCCESS" in text
    assert "WARNING" not in text


def test_render_text_report_flags_duplicates():
    match = {
        "id": 1,
        "transaction_ref": "TXN000123",
        "customer_id": 10,
        "customer_ref": "CUST000010",
        "customer_name": "Test Customer",
        "amount": "100.00",
        "status": "SUCCESS",
        "created_at": "2026-09-01T12:00:00",
        "completed_at": "2026-09-01T12:00:30",
        "failure_code": None,
        "callbacks": [],
        "anomalies": ["DUPLICATE_REFERENCE"],
        "recommended_action": "Multiple transactions share this reference...",
    }
    result = {"query_ref": "TXN000123", "match_count": 2, "transactions": [match, {**match, "id": 2}]}
    text = render_text_report(result)
    assert "WARNING" in text
    assert "Match 1 of 2" in text
    assert "Match 2 of 2" in text


def test_render_health_report_ok():
    result = {
        "database": {"status": "ok"},
        "api": {"status": "ok", "http_status": 200},
        "overall": "ok",
    }
    text = render_health_report(result)
    assert "Overall status: ok" in text
    assert "Database:       ok" in text


def test_render_health_report_degraded_includes_detail():
    result = {
        "database": {"status": "unreachable", "detail": "connection refused"},
        "api": {"status": "not_configured"},
        "overall": "degraded",
    }
    text = render_health_report(result)
    assert "Overall status: degraded" in text
    assert "connection refused" in text


def test_render_summary_report():
    result = {
        "stuck_processing_threshold_minutes": 15,
        "stuck_processing_count": 1,
        "stuck_processing": [
            {"id": 5, "transaction_ref": "TXN000005", "created_at": "2026-09-01T00:00:00", "amount": "10.00"}
        ],
        "recent_failed_lookback_hours": 24,
        "recent_failed_count": 1,
        "recent_failed": [
            {
                "id": 6,
                "transaction_ref": "TXN000006",
                "created_at": "2026-09-01T00:00:00",
                "amount": "20.00",
                "failure_code": "UPSTREAM_ERROR",
            }
        ],
    }
    text = render_summary_report(result)
    assert "Stuck in PROCESSING (> 15 min): 1" in text
    assert "TXN000005" in text
    assert "Recently FAILED (last 24h): 1" in text
    assert "TXN000006" in text
