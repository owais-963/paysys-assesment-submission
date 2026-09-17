import time

RESPONSE_TIME_THRESHOLD_MS = 500


def test_health_returns_ok(api_base_url, http):
    resp = http.get(f"{api_base_url}/health", timeout=5)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "db": "reachable"}


def test_health_response_time_under_threshold(api_base_url, http):
    start = time.perf_counter()
    resp = http.get(f"{api_base_url}/health", timeout=5)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < RESPONSE_TIME_THRESHOLD_MS, (
        f"/health took {elapsed_ms:.1f} ms, expected under {RESPONSE_TIME_THRESHOLD_MS} ms"
    )
