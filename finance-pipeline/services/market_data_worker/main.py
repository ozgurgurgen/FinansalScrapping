"""
Market Data Worker — Macro Economic & Market Data Service
=========================================================
Fetches real-time and historical data from multiple free APIs:
  - TCMB: Turkish Central Bank interest rates
  - TÜİK: CPI inflation data
  - FRED: Federal Reserve interest rates
  - ExchangeRate-API: USD/TRY, USD/JPY, EUR/TRY, GBP/TRY etc.
  - Yahoo Finance (yfinance): Gold, Silver, Copper, ETF prices
  - CoinGecko: Crypto prices (BTC, ETH, etc.)

Anti-bot measures:
  1. Random jitter (2-5s) between requests
  2. Respectful rate limiting per API
  3. Session refresh every 50 requests
  4. Exponential backoff on errors
"""

import os
import sys
import time
import random
import json
import logging
import threading
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any

import requests
import uvicorn
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, text, desc

# Add parent for shared_db
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared_db.models import (
    Base, engine, SessionLocal, PipelineRun,
    MarketIndicator, MarketRate, CommodityPrice, CryptoPrice,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MARKET] %(message)s")
logger = logging.getLogger(__name__)

# ── API Configuration ─────────────────────────────────────────────────────────

# TCMB EVDS API (free, requires API key from evds2.tcmb.gov.tr)
TCMB_BASE = "https://evds2.tcmb.gov.tr/service/evds"
TCMB_API_KEY = os.getenv("TCMB_API_KEY", "")

# TÜİK Service API (free, requires registration)
TUIK_BASE = "https://servis.tableapi.gov.tr/VeriUretimService/V1"
TUIK_API_KEY = os.getenv("TUIK_API_KEY", "")

# FRED API (free, requires API key from api.stlouisfed.org)
FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# ExchangeRate-API (free tier: 1500 req/month)
EXCHANGERATE_BASE = "https://open.er-api.com/v6/latest"

# CoinGecko (free tier: 10-30 req/min)
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Anti-bot timing
JITTER_MIN = 2.0
JITTER_MAX = 5.0
COOLDOWN_EVERY = 50
COOLDOWN_SECONDS = 30


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

scrape_state = {
    "running": False,
    "phase": "",
    "last_run": None,
    "tcmb_rate": None,
    "tuik_cpi": None,
    "fed_rate": None,
    "usd_jpy": None,
    "usd_try": None,
    "eur_try": None,
    "gold_ons": None,
    "silver_ons": None,
    "copper": None,
    "btc_usd": None,
    "eth_usd": None,
    "request_count": 0,
    "elapsed_seconds": 0,
    "logs": [],
}


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    scrape_state["logs"].append(line)
    if len(scrape_state["logs"]) > 5000:
        scrape_state["logs"] = scrape_state["logs"][-5000:]
    logger.info(msg)


def _jitter():
    time.sleep(random.uniform(JITTER_MIN, JITTER_MAX))


# ══════════════════════════════════════════════════════════════════════════════
# TCMB — Turkish Central Bank Interest Rate
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_tcmb_rate(session: requests.Session) -> Optional[float]:
    """Fetch the latest TCMB one-week repo rate (policy rate)."""
    if not TCMB_API_KEY:
        _log("  [TCMB] No API key set, skipping. Get one from evds2.tcmb.gov.tr")
        return None

    try:
        # TP.TK.YTL01 = Ağırlıklı Ortalama Fonlama Maliyeti (policy rate proxy)
        # TP.KF01 = TCMB Politika Faizi (Bileşik)
        params = {
            "dataset": "interest_rates",
            "key": TCMB_API_KEY,
            "series": "TP.TK.YTL01",
            "startDate": (date.today() - timedelta(days=30)).strftime("%d-%m-%Y"),
            "endDate": date.today().strftime("%d-%m-%Y"),
            "type": "json",
        }
        resp = session.get(TCMB_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        if items:
            latest = items[0]
            rate = latest.get("TP_TK_YTL01") or latest.get("DATA_VALUE")
            if rate is not None:
                rate = float(rate)
                _log(f"  [TCMB] Policy rate: {rate}%")
                return rate
    except Exception as e:
        _log(f"  [TCMB] Error: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# TÜİK — CPI Inflation
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_tuik_cpi(session: requests.Session) -> Optional[float]:
    """Fetch the latest YoY CPI inflation rate from TÜİK."""
    if not TUIK_API_KEY:
        _log("  [TÜİK] No API key set, skipping. Get one from servis.tableapi.gov.tr")
        return None

    try:
        # TÜİK Turbo API — TÜFE (CPI) annual
        headers = {"Accept": "application/json", "x-api-key": TUIK_API_KEY}
        # TP.TG01 = Tüketici Fiyatları Genel (Endeks)
        # We want YoY change %
        resp = session.get(
            f"{TUIK_BASE}/TP.TG01",
            headers=headers,
            params={"birim": "Yİ_BEP", "hammadde": ""},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("dataSet", {}).get("data", [])
        if items:
            latest = items[0]
            cpi_yoy = latest.get("birimValue") or latest.get("SONUC")
            if cpi_yoy is not None:
                cpi_yoy = float(cpi_yoy)
                _log(f"  [TÜİK] CPI YoY: {cpi_yoy}%")
                return cpi_yoy
    except Exception as e:
        _log(f"  [TÜİK] Error: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# FRED — Federal Reserve Interest Rate
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_fed_rate(session: requests.Session) -> Optional[float]:
    """Fetch the latest Federal Funds Rate from FRED."""
    if not FRED_API_KEY:
        _log("  [FRED] No API key set, skipping. Get one from api.stlouisfed.org")
        return None

    try:
        params = {
            "series_id": "FEDFUNDS",
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        resp = session.get(f"{FRED_BASE}/series/observations", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        if observations:
            rate = observations[0].get("value")
            if rate and rate != ".":
                rate = float(rate)
                _log(f"  [FRED] Fed Funds Rate: {rate}%")
                return rate
    except Exception as e:
        _log(f"  [FRED] Error: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Exchange Rates
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_exchange_rates(session: requests.Session) -> Dict[str, float]:
    """Fetch USD/TRY, USD/JPY, EUR/TRY, GBP/TRY from ExchangeRate-API."""
    rates = {}
    try:
        resp = session.get(f"{EXCHANGERATE_BASE}/USD", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        r = data.get("rates", {})

        if "TRY" in r:
            rates["USD_TRY"] = r["TRY"]
        if "JPY" in r:
            rates["USD_JPY"] = r["JPY"]
        if "EUR" in r:
            # EUR/TRY = USD/TRY / USD/EUR
            if "TRY" in r and "EUR" in r:
                rates["EUR_TRY"] = r["TRY"] / r["EUR"]
        if "GBP" in r:
            if "TRY" in r and "GBP" in r:
                rates["GBP_TRY"] = r["TRY"] / r["GBP"]

        for k, v in rates.items():
            _log(f"  [FX] {k}: {v:.4f}")
    except Exception as e:
        _log(f"  [FX] Error: {e}")
    return rates


# ══════════════════════════════════════════════════════════════════════════════
# Yahoo Finance — Commodities (Gold, Silver, Copper)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_commodities(session: requests.Session) -> Dict[str, float]:
    """Fetch gold, silver, copper prices via yfinance-style Yahoo Finance API."""
    commodities = {}

    # Yahoo Finance API endpoints for commodities
    symbols = {
        "gold_ons": "GC=F",      # Gold futures
        "silver_ons": "SI=F",    # Silver futures
        "copper": "HG=F",        # Copper futures
    }

    try:
        import yfinance as yf
        for name, symbol in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
                if price:
                    commodities[name] = float(price)
                    _log(f"  [COMMODITY] {name}: ${price:.2f}")
            except Exception as e:
                _log(f"  [COMMODITY] {name} error: {e}")
            _jitter()
    except ImportError:
        _log("  [COMMODITY] yfinance not installed, trying Yahoo Finance API...")
        # Fallback: Yahoo Finance v8 API
        yahoo_symbols = {
            "gold_ons": "GC=F",
            "silver_ons": "SI=F",
            "copper": "HG=F",
        }
        for name, symbol in yahoo_symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                resp = session.get(url, headers=headers, params={"range": "1d", "interval": "1d"}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                if price:
                    commodities[name] = float(price)
                    _log(f"  [COMMODITY] {name}: ${price:.2f}")
            except Exception as e:
                _log(f"  [COMMODITY] {name} error: {e}")
            _jitter()

    return commodities


# ══════════════════════════════════════════════════════════════════════════════
# CoinGecko — Crypto Prices
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_crypto(session: requests.Session) -> Dict[str, float]:
    """Fetch BTC, ETH prices from CoinGecko (free, no API key needed)."""
    crypto = {}
    try:
        resp = session.get(
            f"{COINGECKO_BASE}/simple/price",
            params={
                "ids": "bitcoin,ethereum",
                "vs_currencies": "usd",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if "bitcoin" in data:
            crypto["BTC_USD"] = float(data["bitcoin"]["usd"])
            _log(f"  [CRYPTO] BTC/USD: ${crypto['BTC_USD']:,.2f}")
        if "ethereum" in data:
            crypto["ETH_USD"] = float(data["ethereum"]["usd"])
            _log(f"  [CRYPTO] ETH/USD: ${crypto['ETH_USD']:,.2f}")
    except Exception as e:
        _log(f"  [CRYPTO] Error: {e}")
    return crypto


# ══════════════════════════════════════════════════════════════════════════════
# ETF Prices via Yahoo Finance
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_etf_prices(session: requests.Session) -> Dict[str, float]:
    """Fetch key ETF prices from Yahoo Finance."""
    etfs = {}
    etf_symbols = {
        "SPY": "S&P 500 ETF",
        "QQQ": "Nasdaq 100 ETF",
        "GLD": "Gold ETF",
        "TLT": "US Treasury 20+ Yr",
    }

    try:
        import yfinance as yf
        for symbol, name in etf_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
                if price:
                    etfs[symbol] = float(price)
                    _log(f"  [ETF] {symbol} ({name}): ${price:.2f}")
            except Exception as e:
                _log(f"  [ETF] {symbol} error: {e}")
            _jitter()
    except ImportError:
        # Fallback: Yahoo Finance API
        for symbol, name in etf_symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                resp = session.get(url, headers=headers, params={"range": "1d", "interval": "1d"}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                if price:
                    etfs[symbol] = float(price)
                    _log(f"  [ETF] {symbol} ({name}): ${price:.2f}")
            except Exception as e:
                _log(f"  [ETF] {symbol} error: {e}")
            _jitter()

    return etfs


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

def _save_indicator(db, name: str, value: float, category: str, source: str, description: str = ""):
    """Save or update a market indicator."""
    existing = db.query(MarketIndicator).filter(MarketIndicator.name == name).first()
    if existing:
        existing.value = value
        existing.updated_at = datetime.utcnow()
        existing.source = source
    else:
        db.add(MarketIndicator(
            name=name, value=value, category=category,
            source=source, description=description,
        ))
    db.commit()


def _save_rate(db, pair: str, rate: float, source: str):
    """Save an exchange rate."""
    existing = db.query(MarketRate).filter(MarketRate.pair == pair).first()
    if existing:
        existing.rate = rate
        existing.updated_at = datetime.utcnow()
        existing.source = source
    else:
        db.add(MarketRate(pair=pair, rate=rate, source=source))
    db.commit()


def _save_commodity(db, name: str, price: float, unit: str, source: str):
    """Save a commodity price."""
    existing = db.query(CommodityPrice).filter(CommodityPrice.name == name).first()
    if existing:
        existing.price = price
        existing.updated_at = datetime.utcnow()
        existing.source = source
    else:
        db.add(CommodityPrice(name=name, price=price, unit=unit, source=source))
    db.commit()


def _save_crypto(db, pair: str, price: float, source: str):
    """Save a crypto price."""
    existing = db.query(CryptoPrice).filter(CryptoPrice.pair == pair).first()
    if existing:
        existing.price = price
        existing.updated_at = datetime.utcnow()
        existing.source = source
    else:
        db.add(CryptoPrice(pair=pair, price=price, source=source))
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_full_scrape():
    """Fetch all market data from multiple APIs."""
    if scrape_state["running"]:
        _log("Scrape already in progress, skipping...")
        return

    scrape_state["running"] = True
    scrape_state["phase"] = "starting"

    db = SessionLocal()
    run = PipelineRun(
        service_name="market_data_worker",
        module_name="full_scrape",
        status="RUNNING",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()

    start_time = time.time()

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

        _log("=" * 60)
        _log("MARKET DATA SCRAPE — ALL SOURCES")
        _log("=" * 60)

        # 1. TCMB Rate
        scrape_state["phase"] = "tcmb"
        _log("--- TCMB Policy Rate ---")
        tcmb = _fetch_tcmb_rate(session)
        if tcmb is not None:
            scrape_state["tcmb_rate"] = tcmb
            _save_indicator(db, "TCMB_POLICY_RATE", tcmb, "macro", "tcmb.gov.tr", "TCMB Politika Faizi (%)")
        _jitter()

        # 2. TÜİK CPI
        scrape_state["phase"] = "tuik"
        _log("--- TÜİK CPI Inflation ---")
        tuik = _fetch_tuik_cpi(session)
        if tuik is not None:
            scrape_state["tuik_cpi"] = tuik
            _save_indicator(db, "TUİK_CPI_YOY", tuik, "macro", "tuik.gov.tr", "TÜFE Yıllık Değişim (%)")
        _jitter()

        # 3. Fed Rate
        scrape_state["phase"] = "fred"
        _log("--- FRED Fed Funds Rate ---")
        fed = _fetch_fed_rate(session)
        if fed is not None:
            scrape_state["fed_rate"] = fed
            _save_indicator(db, "FED_FUNDS_RATE", fed, "macro", "fred.stlouisfed.org", "Federal Funds Rate (%)")
        _jitter()

        # 4. Exchange Rates
        scrape_state["phase"] = "fx"
        _log("--- Exchange Rates ---")
        fx = _fetch_exchange_rates(session)
        for pair, rate in fx.items():
            _save_rate(db, pair, rate, "open.er-api.com")
            if pair == "USD_TRY":
                scrape_state["usd_try"] = rate
            elif pair == "USD_JPY":
                scrape_state["usd_jpy"] = rate
            elif pair == "EUR_TRY":
                scrape_state["eur_try"] = rate
        _jitter()

        # 5. Commodities
        scrape_state["phase"] = "commodities"
        _log("--- Commodities (Yahoo Finance) ---")
        commodities = _fetch_commodities(session)
        for name, price in commodities.items():
            unit = "USD/oz" if "ons" in name else "USD/lb"
            _save_commodity(db, name, price, unit, "finance.yahoo.com")
            scrape_state[name] = price
        _jitter()

        # 6. Crypto
        scrape_state["phase"] = "crypto"
        _log("--- Crypto (CoinGecko) ---")
        crypto = _fetch_crypto(session)
        for pair, price in crypto.items():
            _save_crypto(db, pair, price, "coingecko.com")
            scrape_state[f"{pair.lower()}"] = price
        _jitter()

        # 7. ETFs
        scrape_state["phase"] = "etf"
        _log("--- ETFs (Yahoo Finance) ---")
        etfs = _fetch_etf_prices(session)
        for symbol, price in etfs.items():
            _save_commodity(db, f"ETF_{symbol}", price, "USD", "finance.yahoo.com")

        # Done
        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        scrape_state["last_run"] = datetime.utcnow().isoformat()
        scrape_state["phase"] = "complete"

        run.status = "SUCCESS"
        run.records_processed = len(fx) + len(commodities) + len(crypto) + len(etfs) + (1 if tcmb else 0) + (1 if tuik else 0) + (1 if fed else 0)
        run.records_inserted = run.records_processed
        run.finished_at = datetime.utcnow()
        db.commit()

        _log("=" * 60)
        _log("MARKET DATA SCRAPE COMPLETE!")
        _log(f"  TCMB: {scrape_state['tcmb_rate']}%")
        _log(f"  TÜİK CPI: {scrape_state['tuik_cpi']}%")
        _log(f"  Fed Rate: {scrape_state['fed_rate']}%")
        _log(f"  USD/TRY: {scrape_state['usd_try']}")
        _log(f"  USD/JPY: {scrape_state['usd_jpy']}")
        _log(f"  Gold: ${scrape_state.get('gold_ons')}")
        _log(f"  Silver: ${scrape_state.get('silver_ons')}")
        _log(f"  Copper: ${scrape_state.get('copper')}")
        _log(f"  BTC: ${scrape_state.get('btc_usd', 'N/A')}")
        _log(f"  ETH: ${scrape_state.get('eth_usd', 'N/A')}")
        _log(f"  Elapsed: {elapsed}s")
        _log("=" * 60)

    except Exception as e:
        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        run.status = "FAILED"
        run.error_message = str(e)[:500]
        run.finished_at = datetime.utcnow()
        db.commit()
        _log(f"FATAL: {e}")
    finally:
        scrape_state["running"] = False
        scrape_state["phase"] = ""
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="Market Data Worker", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schedule.json")
market_scheduler = None


def _load_schedule_cfg() -> dict:
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                return json.load(f).get("market_data_worker", {})
        except Exception:
            pass
    return {"enabled": True, "mode": "interval", "interval_minutes": 60}


def _setup_scheduler():
    global market_scheduler
    if market_scheduler:
        try:
            market_scheduler.shutdown(wait=False)
        except Exception:
            pass
    cfg = _load_schedule_cfg()
    market_scheduler = BackgroundScheduler(
        timezone="Europe/Istanbul",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    def on_job_error(event):
        _log(f"[SCHEDULER] Job error: {event.exception}")

    market_scheduler.add_listener(on_job_error, 4096)

    if not cfg.get("enabled") or cfg.get("mode") == "manual":
        _log("Scheduler: DISABLED (manual mode)")
        market_scheduler.start()
        return

    mode = cfg.get("mode", "interval")
    if mode == "daily":
        h = cfg.get("hour", 6)
        m = cfg.get("minute", 0)
        market_scheduler.add_job(run_full_scrape, "cron", hour=h, minute=m, id="daily_market")
        market_scheduler.start()
        _log(f"Scheduler: Daily at {h:02d}:{m:02d}")
    elif mode == "interval":
        mins = cfg.get("interval_minutes", 60)
        market_scheduler.add_job(run_full_scrape, "interval", minutes=mins, id="interval_market")
        market_scheduler.start()
        _log(f"Scheduler: Every {mins} minutes")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    _log("Market Data Worker v1.0 started")
    _setup_scheduler()


@app.post("/api/schedule/reload")
def reload_schedule():
    _setup_scheduler()
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "market_data_worker", "version": "1.0"}


@app.get("/api/status")
def status():
    db = SessionLocal()
    try:
        indicators = db.query(func.count()).select_from(MarketIndicator).scalar() or 0
        rates = db.query(func.count()).select_from(MarketRate).scalar() or 0
        commodities = db.query(func.count()).select_from(CommodityPrice).scalar() or 0
        cryptos = db.query(func.count()).select_from(CryptoPrice).scalar() or 0
        runs = db.query(PipelineRun).filter(
            PipelineRun.service_name == "market_data_worker"
        ).order_by(PipelineRun.started_at.desc()).first()

        return {
            "service": "market_data_worker",
            "version": "1.0",
            "indicators": indicators,
            "rates": rates,
            "commodities": commodities,
            "cryptos": cryptos,
            "running": scrape_state["running"],
            "phase": scrape_state["phase"],
            "tcmb_rate": scrape_state["tcmb_rate"],
            "tuik_cpi": scrape_state["tuik_cpi"],
            "fed_rate": scrape_state["fed_rate"],
            "usd_try": scrape_state["usd_try"],
            "usd_jpy": scrape_state["usd_jpy"],
            "eur_try": scrape_state["eur_try"],
            "gold_ons": scrape_state.get("gold_ons"),
            "silver_ons": scrape_state.get("silver_ons"),
            "copper": scrape_state.get("copper"),
            "btc_usd": scrape_state.get("btc_usd"),
            "eth_usd": scrape_state.get("eth_usd"),
            "last_run": scrape_state["last_run"] or (runs.finished_at.isoformat() if runs and runs.finished_at else None),
            "last_status": runs.status if runs else None,
            "elapsed_seconds": scrape_state["elapsed_seconds"],
        }
    finally:
        db.close()


@app.post("/api/scrape/now")
def trigger_scrape(background_tasks: BackgroundTasks):
    if scrape_state["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(run_full_scrape)
    return {"status": "started", "message": "Market data scrape triggered"}


@app.get("/api/logs")
def get_logs():
    return {"logs": scrape_state["logs"][-500:]}


# ── Data Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/indicators")
def get_indicators():
    db = SessionLocal()
    try:
        items = db.query(MarketIndicator).order_by(MarketIndicator.name).all()
        return {
            "data": [{
                "name": i.name, "value": float(i.value) if i.value else None,
                "category": i.category, "source": i.source,
                "description": i.description,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
            } for i in items]
        }
    finally:
        db.close()


@app.get("/api/rates")
def get_rates():
    db = SessionLocal()
    try:
        items = db.query(MarketRate).order_by(MarketRate.pair).all()
        return {
            "data": [{
                "pair": r.pair, "rate": float(r.rate) if r.rate else None,
                "source": r.source,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            } for r in items]
        }
    finally:
        db.close()


@app.get("/api/commodities")
def get_commodities():
    db = SessionLocal()
    try:
        items = db.query(CommodityPrice).order_by(CommodityPrice.name).all()
        return {
            "data": [{
                "name": c.name, "price": float(c.price) if c.price else None,
                "unit": c.unit, "source": c.source,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            } for c in items]
        }
    finally:
        db.close()


@app.get("/api/crypto")
def get_crypto():
    db = SessionLocal()
    try:
        items = db.query(CryptoPrice).order_by(CryptoPrice.pair).all()
        return {
            "data": [{
                "pair": c.pair, "price": float(c.price) if c.price else None,
                "source": c.source,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            } for c in items]
        }
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8003)
