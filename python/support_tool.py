#!/usr/bin/env python3
"""L2 support CLI for investigating MiniPay transactions.

Usage:
  python support_tool.py --transaction TXN000123
  python support_tool.py --transaction TXN000123 --json
  python support_tool.py --health
  python support_tool.py --stuck-summary [--failed-lookback-hours 24]

Configuration is read from the environment (or a local .env file) --
see .env.example. No credentials are hard-coded.

Exit codes:
  0  success (transaction found / health OK / summary produced)
  1  transaction not found
  2  a required dependency (database, or the API when --health checks it)
     could not be reached
  3  configuration error (missing/invalid environment variables)
  4  unexpected/internal error

Note: argparse itself exits with status 2 for malformed CLI arguments
(e.g. an unknown flag), before any of the above logic runs -- that is
argparse's own convention and is not overridden here.
"""
import argparse
import json
import sys

from support import db, diagnostics, health, report, summary
from support.config import load_settings
from support.exceptions import ConfigError, DependencyError, SupportToolError
from support.logging_setup import configure_logging

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_DEPENDENCY_ERROR = 2
EXIT_CONFIG_ERROR = 3
EXIT_UNEXPECTED_ERROR = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="support_tool.py",
        description="L2 support diagnostic tool for MiniPay transactions.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--transaction",
        metavar="TXN_REF",
        help="Transaction reference to diagnose, e.g. TXN000123",
    )
    group.add_argument(
        "--health",
        action="store_true",
        help="Check database (and API, if API_BASE_URL is configured) connectivity",
    )
    group.add_argument(
        "--stuck-summary",
        action="store_true",
        help="Summarize stuck PROCESSING and recently FAILED transactions",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of a text report",
    )
    parser.add_argument(
        "--failed-lookback-hours",
        type=int,
        default=24,
        help="Lookback window in hours for --stuck-summary's failed-transaction count (default: 24)",
    )
    return parser


def _emit(result: dict, *, as_json: bool, text_renderer) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(text_renderer(result))


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    logger = configure_logging(settings.log_level)

    try:
        if args.health:
            logger.info("Running health check")
            result = health.check_health(settings)
            _emit(result, as_json=args.json, text_renderer=report.render_health_report)
            return EXIT_OK if result["overall"] == "ok" else EXIT_DEPENDENCY_ERROR

        if args.stuck_summary:
            logger.info("Building stuck/failed transaction summary")
            conn = db.connect(settings)
            try:
                result = summary.build_summary(
                    conn, settings.stuck_processing_minutes, args.failed_lookback_hours
                )
            finally:
                conn.close()
            _emit(result, as_json=args.json, text_renderer=report.render_summary_report)
            return EXIT_OK

        logger.info("Diagnosing transaction reference: %s", args.transaction)
        conn = db.connect(settings)
        try:
            result = diagnostics.diagnose_transaction(
                conn, args.transaction, settings.stuck_processing_minutes
            )
        finally:
            conn.close()
        _emit(result, as_json=args.json, text_renderer=report.render_text_report)
        return EXIT_OK if result["transactions"] else EXIT_NOT_FOUND

    except DependencyError as exc:
        logger.error("Dependency error: %s", exc)
        print(f"Dependency error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except SupportToolError as exc:
        logger.error("Error: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED_ERROR
    except Exception:
        logger.exception("Unexpected error")
        print("An unexpected error occurred. See logs for details.", file=sys.stderr)
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    sys.exit(main())
