"""Human-readable text renderers. --json bypasses these entirely and dumps
the same underlying dict with json.dumps, so both modes report identical
information.
"""


def render_text_report(result: dict) -> str:
    if not result["transactions"]:
        return f"No transaction found with reference '{result['query_ref']}'."

    lines = [f"Transaction reference: {result['query_ref']}"]
    if result["match_count"] > 1:
        lines.append(
            f"WARNING: {result['match_count']} transactions share this reference "
            "(see DUPLICATE_REFERENCE anomaly on each match below)."
        )
    lines.append("")

    for i, tx in enumerate(result["transactions"], start=1):
        lines.append(f"--- Match {i} of {result['match_count']} (id={tx['id']}) ---")
        lines.append(f"Customer:            {tx['customer_name']} ({tx['customer_ref']}, id={tx['customer_id']})")
        lines.append(f"Amount:              {tx['amount']}")
        lines.append(f"Status:              {tx['status']}")
        lines.append(f"Created at:          {tx['created_at']}")
        lines.append(f"Completed at:        {tx['completed_at'] or '(not completed)'}")
        if tx["failure_code"]:
            lines.append(f"Failure code:        {tx['failure_code']}")
        lines.append(f"Callback attempts:   {len(tx['callbacks'])}")
        for cb in tx["callbacks"]:
            lines.append(
                f"  - attempt {cb['attempt_no']}: {cb['callback_status']} "
                f"(http {cb['http_status']}) at {cb['attempted_at']}"
            )
        lines.append(f"Anomalies:           {', '.join(tx['anomalies']) if tx['anomalies'] else 'none'}")
        lines.append(f"Recommended action:  {tx['recommended_action']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_health_report(result: dict) -> str:
    lines = [f"Overall status: {result['overall']}"]
    lines.append(f"Database:       {result['database']['status']}")
    if result["database"].get("detail"):
        lines.append(f"  detail:       {result['database']['detail']}")
    lines.append(f"API:            {result['api']['status']}")
    if result["api"].get("http_status") is not None:
        lines.append(f"  http_status:  {result['api']['http_status']}")
    if result["api"].get("detail"):
        lines.append(f"  detail:       {result['api']['detail']}")
    return "\n".join(lines)


def render_summary_report(result: dict) -> str:
    lines = [
        f"Stuck in PROCESSING (> {result['stuck_processing_threshold_minutes']} min): "
        f"{result['stuck_processing_count']}",
    ]
    for row in result["stuck_processing"]:
        lines.append(f"  - id={row['id']} ref={row['transaction_ref']} created_at={row['created_at']} amount={row['amount']}")

    lines.append("")
    lines.append(
        f"Recently FAILED (last {result['recent_failed_lookback_hours']}h): "
        f"{result['recent_failed_count']}"
    )
    for row in result["recent_failed"]:
        lines.append(
            f"  - id={row['id']} ref={row['transaction_ref']} created_at={row['created_at']} "
            f"amount={row['amount']} failure_code={row['failure_code']}"
        )

    return "\n".join(lines).rstrip()
