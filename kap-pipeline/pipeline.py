"""
Pipeline Orchestrator — Main Entry Point
-----------------------------------------
Coordinates all 7 modules, logs pipeline runs, handles errors,
and provides both one-shot and scheduled execution modes.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import List, Optional

from config import CONFIG
from database import PipelineRun, get_session, init_db

logger = logging.getLogger("kap_pipeline")


# ── Module Runner ────────────────────────────────────────────────────────────

def _run_module(
    module_name: str,
    module_func,
    *args,
    **kwargs,
) -> int:
    """
    Run a single module with pipeline logging.
    Records start/end time, status, and record count.
    """
    session = get_session()
    run_record = PipelineRun(
        module_name=module_name,
        started_at=datetime.utcnow(),
        status="RUNNING",
    )
    session.add(run_record)
    session.commit()

    count = 0
    try:
        logger.info("▶ Starting module: %s", module_name)
        count = module_func(*args, **kwargs)
        run_record.status = "SUCCESS"
        run_record.records_processed = count
        run_record.records_inserted = count
        run_record.finished_at = datetime.utcnow()
        logger.info("✓ Module %s completed — %d records", module_name, count)
    except Exception as e:
        run_record.status = "FAILED"
        run_record.error_message = str(e)[:2000]
        run_record.finished_at = datetime.utcnow()
        logger.error("✗ Module %s failed: %s", module_name, e, exc_info=True)
    finally:
        session.commit()
        session.close()

    return count


# ── Full Pipeline ────────────────────────────────────────────────────────────

def run_full_pipeline(
    skip_modules: Optional[List[str]] = None,
    only_modules: Optional[List[str]] = None,
    enrich_companies: bool = False,
    limit_companies: Optional[int] = None,
    disclosure_from: Optional[str] = None,
    disclosure_to: Optional[str] = None,
) -> dict:
    """
    Run the complete 7-module pipeline.

    Args:
        skip_modules: List of module names to skip (e.g., ["module6"])
        only_modules: If set, run only these modules
        enrich_companies: Whether to fetch detailed company info (slower)
        limit_companies: Limit number of companies to process (for testing)
        disclosure_from: Start date for disclosure search (YYYY-MM-DD)
        disclosure_to: End date for disclosure search (YYYY-MM-DD)

    Returns dict with module_name → record_count.
    """
    logger.info("=" * 60)
    logger.info("  KAP PIPELINE — Full Run Starting")
    logger.info("  Time: %s", datetime.utcnow().isoformat())
    logger.info("=" * 60)

    results = {}

    # Import modules lazily to avoid circular imports
    from module1_seeds import run_module1_seed_data
    from module2_financials import run_module2_financials
    from module3_disclosures import run_module3_disclosures
    from module4_corporate import run_module4_corporate_actions
    from module5_buybacks import run_module5_buybacks
    from module6_ipo import run_module6_ipo
    from module7_ownership import run_module7_ownership
    from module8_cashflow import run_module8_cashflow
    from module9_management import run_module9_management
    from module10_subsidiaries import run_module10_subsidiaries
    from module11_portfolio_reports import run_module11_portfolio_reports
    from module12_notes import run_module12_notes

    modules = [
        ("module1_seeds", lambda: run_module1_seed_data(enrich_details=enrich_companies)),
        ("module2_financials", lambda: run_module2_financials(limit=limit_companies)),
        ("module3_disclosures", lambda: run_module3_disclosures(
            from_date=disclosure_from, to_date=disclosure_to
        )),
        ("module4_corporate", lambda: run_module4_corporate_actions()),
        ("module5_buybacks", lambda: run_module5_buybacks()),
        ("module6_ipo", lambda: run_module6_ipo()),
        ("module7_ownership", lambda: run_module7_ownership()),
        ("module8_cashflow", lambda: run_module8_cashflow(limit=limit_companies)),
        ("module9_management", lambda: run_module9_management(limit=limit_companies)),
        ("module10_subsidiaries", lambda: run_module10_subsidiaries(limit=limit_companies)),
        ("module11_portfolio_reports", lambda: run_module11_portfolio_reports()),
        ("module12_notes", lambda: run_module12_notes()),
    ]

    for module_name, module_func in modules:
        # Check skip/only filters
        if skip_modules and module_name in skip_modules:
            logger.info("⊘ Skipping module: %s", module_name)
            continue
        if only_modules and module_name not in only_modules:
            continue

        count = _run_module(module_name, module_func)
        results[module_name] = count

    logger.info("=" * 60)
    logger.info("  KAP PIPELINE — Full Run Complete")
    logger.info("  Results: %s", results)
    logger.info("=" * 60)

    return results


# ── Individual Module Runners ────────────────────────────────────────────────

def run_seed_only(enrich: bool = False) -> int:
    """Run only Module 1 (company list)."""
    from module1_seeds import run_module1_seed_data
    return _run_module("module1_seeds", run_module1_seed_data, enrich_details=enrich)


def run_financials_only(limit: Optional[int] = None) -> int:
    """Run only Module 2 (financials)."""
    from module2_financials import run_module2_financials
    return _run_module("module2_financials", run_module2_financials, limit=limit)


def run_disclosures_only(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> int:
    """Run only Module 3 (disclosures / live feed)."""
    from module3_disclosures import run_module3_disclosures
    return _run_module(
        "module3_disclosures", run_module3_disclosures,
        from_date=from_date, to_date=to_date,
    )


def run_live_feed_cron() -> int:
    """
    Cron-friendly wrapper for Module 3.
    Fetches disclosures from the last 24 hours.
    """
    from datetime import timedelta
    from module3_disclosures import run_module3_disclosures

    from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = datetime.utcnow().strftime("%Y-%m-%d")

    return _run_module(
        "module3_live_feed", run_module3_disclosures,
        from_date=from_date, to_date=to_date,
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for the KAP pipeline."""
    parser = argparse.ArgumentParser(
        description="KAP Data Pipeline — Scrape & Store Turkish Stock Market Data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py full                          # Run all modules
  python pipeline.py full --skip module2 module6   # Skip specific modules
  python pipeline.py seed                          # Only fetch company list
  python pipeline.py seed --enrich                 # Fetch + enrich company details
  python pipeline.py financials --limit 10         # Financials for 10 companies
  python pipeline.py disclosures                   # Last 30 days of disclosures
  python pipeline.py disclosures --from 2024-01-01 --to 2024-12-31
  python pipeline.py cashflow --limit 10          # Cash flow for 10 companies
  python pipeline.py management --limit 10        # Management board info
  python pipeline.py subsidiaries --limit 10       # Subsidiaries info
  python pipeline.py portfolio-reports             # Portfolio distribution reports
  python pipeline.py notes                         # Financial notes
  python pipeline.py cron                          # Live feed (last 24h)
        """,
    )
    parser.add_argument(
        "command",
        choices=["full", "seed", "financials", "disclosures", "corporate", "buybacks", "ipo", "ownership", "cashflow", "management", "subsidiaries", "portfolio-reports", "notes", "cron"],
        help="Which pipeline module(s) to run",
    )
    parser.add_argument("--skip", nargs="*", help="Modules to skip (full mode only)")
    parser.add_argument("--only", nargs="*", help="Run only these modules (full mode)")
    parser.add_argument("--limit", type=int, help="Limit companies to process")
    parser.add_argument("--enrich", action="store_true", help="Enrich company details (slower)")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Initialize database
    init_db()
    logger.info("Database initialized.")

    # Run the requested command
    if args.command == "full":
        run_full_pipeline(
            skip_modules=args.skip,
            only_modules=args.only,
            enrich_companies=args.enrich,
            limit_companies=args.limit,
            disclosure_from=args.from_date,
            disclosure_to=args.to_date,
        )
    elif args.command == "seed":
        run_seed_only(enrich=args.enrich)
    elif args.command == "financials":
        run_financials_only(limit=args.limit)
    elif args.command == "disclosures":
        run_disclosures_only(from_date=args.from_date, to_date=args.to_date)
    elif args.command == "corporate":
        _run_module("module4_corporate", __import__("module4_corporate").run_module4_corporate_actions)
    elif args.command == "buybacks":
        _run_module("module5_buybacks", __import__("module5_buybacks").run_module5_buybacks)
    elif args.command == "ipo":
        _run_module("module6_ipo", __import__("module6_ipo").run_module6_ipo)
    elif args.command == "ownership":
        _run_module("module7_ownership", __import__("module7_ownership").run_module7_ownership)
    elif args.command == "cashflow":
        from module8_cashflow import run_module8_cashflow
        _run_module("module8_cashflow", run_module8_cashflow, limit=args.limit)
    elif args.command == "management":
        from module9_management import run_module9_management
        _run_module("module9_management", run_module9_management, limit=args.limit)
    elif args.command == "subsidiaries":
        from module10_subsidiaries import run_module10_subsidiaries
        _run_module("module10_subsidiaries", run_module10_subsidiaries, limit=args.limit)
    elif args.command == "portfolio-reports":
        from module11_portfolio_reports import run_module11_portfolio_reports
        _run_module("module11_portfolio_reports", run_module11_portfolio_reports)
    elif args.command == "notes":
        from module12_notes import run_module12_notes
        _run_module("module12_notes", run_module12_notes)
    elif args.command == "cron":
        run_live_feed_cron()


if __name__ == "__main__":
    main()
