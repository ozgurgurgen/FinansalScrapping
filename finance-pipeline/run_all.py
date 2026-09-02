"""
Run All Pipelines — SQLite Mode (No PostgreSQL Required)
========================================================
Initializes a local SQLite database and runs all pipelines:
1. KAP Pipeline (12 modules)
2. TEFAS Pipeline (fund data)
3. Market Data Worker (macro data)

Usage:
    python run_all.py              # Run everything
    python run_all.py --kap        # KAP only
    python run_all.py --tefas      # TEFAS only
    python run_all.py --market     # Market data only
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Set SQLite as default database
os.environ.setdefault("DATABASE_URL", "sqlite:///finance.db")
os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_all")


def init_kap_db():
    """Initialize KAP pipeline database."""
    logger.info("=" * 60)
    logger.info("INITIALIZING KAP DATABASE")
    logger.info("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kap-pipeline"))
    from database import init_db, Base

    init_db()
    logger.info("KAP database initialized with %d tables", len(Base.metadata.tables))


def init_finance_db():
    """Initialize finance pipeline database."""
    logger.info("=" * 60)
    logger.info("INITIALIZING FINANCE DATABASE")
    logger.info("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))
    from shared_db.models import Base
    from sqlalchemy import create_engine

    db_url = os.environ.get("DATABASE_URL", "sqlite:///finance.db")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    logger.info("Finance database initialized with %d tables", len(Base.metadata.tables))


def run_kap_pipeline():
    """Run the KAP pipeline (12 modules)."""
    logger.info("=" * 60)
    logger.info("STARTING KAP PIPELINE (12 modules)")
    logger.info("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kap-pipeline"))

    from pipeline import run_full_pipeline

    results = run_full_pipeline(
        limit_companies=50,  # Start with 50 companies for testing
    )

    logger.info("=" * 60)
    logger.info("KAP PIPELINE COMPLETE")
    for module, count in results.items():
        logger.info("  %s: %d records", module, count)
    logger.info("=" * 60)


def run_tefas_pipeline():
    """Run the TEFAS pipeline."""
    logger.info("=" * 60)
    logger.info("STARTING TEFAS PIPELINE")
    logger.info("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "finance-pipeline", "services", "tefas_worker"))

    try:
        from main import run_full_scrape
        run_full_scrape(years_back=1)  # 1 year for testing
    except Exception as e:
        logger.error("TEFAS pipeline error: %s", e)
        logger.info("TEFAS requires PostgreSQL. Skipping in SQLite mode.")


def run_market_data():
    """Run the market data worker."""
    logger.info("=" * 60)
    logger.info("STARTING MARKET DATA WORKER")
    logger.info("=" * 60)

    market_dir = os.path.join(os.path.dirname(__file__), "services", "market_data_worker")
    sys.path.insert(0, market_dir)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

    try:
        # Need to import from the correct path
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "market_data_main",
            os.path.join(market_dir, "main.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run_full_scrape()
    except Exception as e:
        logger.error("Market data error: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Run all data pipelines")
    parser.add_argument("--kap", action="store_true", help="Run KAP pipeline only")
    parser.add_argument("--tefas", action="store_true", help="Run TEFAS pipeline only")
    parser.add_argument("--market", action="store_true", help="Run market data only")
    args = parser.parse_args()

    start_time = datetime.now()

    # Initialize databases
    init_kap_db()
    init_finance_db()

    # Run pipelines
    run_any = args.kap or args.tefas or args.market

    if not run_any or args.kap:
        try:
            run_kap_pipeline()
        except Exception as e:
            logger.error("KAP pipeline failed: %s", e)

    if not run_any or args.tefas:
        try:
            run_tefas_pipeline()
        except Exception as e:
            logger.error("TEFAS pipeline failed: %s", e)

    if not run_any or args.market:
        try:
            run_market_data()
        except Exception as e:
            logger.error("Market data failed: %s", e)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("ALL PIPELINES COMPLETE — %.1f seconds", elapsed)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
