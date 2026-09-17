#!/usr/bin/env bash
# Simple, repeatable health check for the host running MiniPay.
# Usage: ./health-check.sh
# Env overrides: MINIPAY_API_BASE_URL (default http://127.0.0.1:8000),
#                DISK_THRESHOLD_PCT (default 90)
set -uo pipefail

API_URL="${MINIPAY_API_BASE_URL:-http://127.0.0.1:8000}"
DISK_THRESHOLD_PCT="${DISK_THRESHOLD_PCT:-90}"
status=0

echo "== MiniPay host health check: $(date -u +%Y-%m-%dT%H:%M:%SZ) =="

echo "-- OS / kernel --"
uname -a

echo
echo "-- API health (${API_URL}/health) --"
if curl -fsS --max-time 5 "${API_URL}/health"; then
  echo
else
  echo "API health check FAILED (unreachable or non-200 response)"
  status=1
fi

echo
echo "-- Disk usage --"
df -h
echo
while read -r target pcent; do
  pct_num=${pcent%%%}
  if [ "$pct_num" -ge "$DISK_THRESHOLD_PCT" ]; then
    echo "WARNING: $target usage is ${pcent}, at or above ${DISK_THRESHOLD_PCT}% threshold"
    status=1
  fi
done < <(df -h --output=target,pcent | tail -n +2)

echo
echo "-- Memory --"
free -h

echo
echo "-- Top memory-consuming process --"
ps -eo pid,ppid,%mem,%cpu,cmd --sort=-%mem | head -n 6

echo
echo "-- Listening ports --"
(ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null) || echo "Neither ss nor netstat available"

echo
if [ "$status" -eq 0 ]; then
  echo "== Overall: OK =="
else
  echo "== Overall: ISSUES DETECTED (see WARNING/FAILED lines above) =="
fi

exit "$status"
