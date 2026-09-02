"""
TEFAS Max Data Worker — Anti-Ban Edition
=========================================
Fetches ALL available data from tefas.gov.tr:
  - ALL 2591+ fund codes (from fonUnvanAra)
  - Fund details: price, return, shares, market cap, category, ranking, investor count
  - 5-year price history per fund
  - Fund groups and sub-types (reference data)
  - TEFAS announcements
  - Trading volume, market data (from working endpoints)

Anti-bot measures:
  1. Random jitter (3.5-7.2s) between requests
  2. Dynamic User-Agent rotation (fake-useragent)
  3. 2-min cooldown every 20 requests
  4. Exponential backoff on 429/500 errors
  5. New session every 5 requests (identity refresh)
"""

import os
import sys
import time
import random
import json
import logging
import threading
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_db.models import (
    Base, engine, SessionLocal,
    TefasFund, TefasFundPrice, TefasFundAllocation,
    TefasFundGroup, TefasFundSubType,
    TefasAnnouncement, PipelineRun,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TEFAS] %(message)s")
logger = logging.getLogger(__name__)

# ── TEFAS API Config ────────────────────────────────────────────────────────
TEFAS_BASE = "https://www.tefas.gov.tr"

# All discovered working endpoints
ENDPOINTS = {
    "fund_list":      "/api/funds/fonUnvanAra",         # ALL fund codes + names
    "fund_info":      "/api/funds/fonBilgiGetir",       # Fund details (price, return, cap, etc.)
    "fund_prices":    "/api/funds/fonFiyatBilgiGetir",  # Historical prices
    "fund_groups":    "/api/funds/fonGrupGetir",        # 8 fund groups
    "fund_types":     "/api/funds/fonTurGetir",         # 12 fund sub-types
    "announcements":  "/api/funds/fonTefasDuyuruGetir", # TEFAS announcements
    "fund_type_info": "/api/funds/fonTipiGetir",        # Fund type code (F/P/B)
}

# Anti-ban timing
JITTER_MIN = 3.5
JITTER_MAX = 7.2
COOLDOWN_EVERY = 20
COOLDOWN_SECONDS = 120
SESSION_REFRESH = 5


# ══════════════════════════════════════════════════════════════════════════════
# ANTI-BAN SESSION FACTORY
# ══════════════════════════════════════════════════════════════════════════════

_ua = UserAgent()

def create_safe_session() -> requests.Session:
    """Create a fresh session with rotating User-Agent and retry logic."""
    session = requests.Session()

    retries = Retry(
        total=5, backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    session.headers.update({
        "User-Agent": _ua.random,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.tefas.gov.tr/",
        "Origin": "https://www.tefas.gov.tr",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })

    # Visit homepage to get session cookies
    try:
        session.get(TEFAS_BASE, timeout=15)
    except Exception:
        pass

    return session


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

scrape_state = {
    "running": False,
    "phase": "",
    "last_run": None,
    "total_funds": 0,
    "funds_scraped": 0,
    "funds_with_prices": 0,
    "prices_inserted": 0,
    "details_updated": 0,
    "groups_loaded": 0,
    "types_loaded": 0,
    "announcements_loaded": 0,
    "current_fund": "",
    "request_count": 0,
    "cooldown_until": None,
    "elapsed_seconds": 0,
    "estimated_remaining": "",
    "last_run_prices": 0,
    "last_run_details": 0,
    "logs": [],
    # Ban detection
    "consecutive_429s": 0,
    "total_429s": 0,
    "total_errors": 0,
    "ban_detected": False,
    "ban_level": 0,          # 0=normal, 1=warning, 2=ban
    "ban_message": "",
    "last_429_time": None,
    "ban_cooldown_until": None,
    "total_consecutive_failures": 0,
    "slowdown_factor": 1.0,  # Jitter multiplier when under pressure
}


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    scrape_state["logs"].append(line)
    if len(scrape_state["logs"]) > 5000:
        scrape_state["logs"] = scrape_state["logs"][-5000:]
    logger.info(msg)


def _api_post(session: requests.Session, endpoint: str, payload: dict,
              request_counter: list) -> dict:
    """Make an API request with jitter, cooldown, and ban detection."""
    request_counter[0] += 1
    scrape_state["request_count"] = request_counter[0]

    # Check if we're in ban cooldown
    if scrape_state["ban_cooldown_until"]:
        until = datetime.fromisoformat(scrape_state["ban_cooldown_until"]) if isinstance(scrape_state["ban_cooldown_until"], str) else scrape_state["ban_cooldown_until"]
        if datetime.now() < until:
            wait_secs = (until - datetime.now()).total_seconds()
            _log(f"  [BAN] Ban cooldown active — waiting {int(wait_secs)}s more...")
            time.sleep(min(wait_secs, 10))  # Sleep in chunks so we can check
            raise Exception(f"BAN_COOLDOWN: {int(wait_secs)}s remaining")
        else:
            scrape_state["ban_cooldown_until"] = None
            scrape_state["ban_detected"] = False
            scrape_state["ban_level"] = 0
            scrape_state["ban_message"] = "Ban cooldown ended, resuming..."
            _log("  [BAN] Cooldown ended — resuming requests")
            session = create_safe_session()

    # Session rotation
    if request_counter[0] % SESSION_REFRESH == 0:
        _log(f"  [ANTI-BAN] Rotating session (#{request_counter[0]})...")
        session = create_safe_session()

    # Scheduled cooldown
    if request_counter[0] % COOLDOWN_EVERY == 0 and request_counter[0] > 0:
        cooldown_end = datetime.now() + timedelta(seconds=COOLDOWN_SECONDS)
        scrape_state["cooldown_until"] = cooldown_end.isoformat()
        _log(f"  [ANTI-BAN] Cooldown: {COOLDOWN_SECONDS}s (request #{request_counter[0]})...")
        time.sleep(COOLDOWN_SECONDS)
        scrape_state["cooldown_until"] = None

    # Apply slowdown multiplier when under pressure
    if scrape_state["slowdown_factor"] > 1.0:
        extra = random.uniform(2, 5) * scrape_state["slowdown_factor"]
        _log(f"  [BAN] Slowdown: +{extra:.1f}s (pressure mode)")
        time.sleep(extra)

    try:
        resp = session.post(f"{TEFAS_BASE}{endpoint}", json=payload, timeout=20)
        resp.raise_for_status()

        # Success — reset consecutive counters
        scrape_state["consecutive_429s"] = 0
        scrape_state["total_consecutive_failures"] = 0
        if scrape_state["slowdown_factor"] > 1.0:
            scrape_state["slowdown_factor"] = max(1.0, scrape_state["slowdown_factor"] - 0.2)
        return resp.json()

    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, 'status_code', None)
        if status == 429:
            scrape_state["consecutive_429s"] += 1
            scrape_state["total_429s"] += 1
            scrape_state["last_429_time"] = datetime.now().isoformat()
            c429 = scrape_state["consecutive_429s"]

            if c429 >= 3:
                # BAN LEVEL 2 — Full ban detected
                ban_mins = min(30, 5 * c429)  # Escalating cooldown
                ban_until = datetime.now() + timedelta(minutes=ban_mins)
                scrape_state["ban_detected"] = True
                scrape_state["ban_level"] = 2
                scrape_state["ban_message"] = f"BANNED! {c429}x 429 — cooling down {ban_mins}min"
                scrape_state["ban_cooldown_until"] = ban_until.isoformat()
                scrape_state["slowdown_factor"] = min(5.0, scrape_state["slowdown_factor"] + 1.0)
                _log(f"  [BAN] 🚨 BAN DETECTED! {c429} consecutive 429s")
                _log(f"  [BAN] 🚨 Cooling down {ban_mins} min until {ban_until.strftime('%H:%M:%S')}")
                _log(f"  [BAN] 🚨 Total 429s this session: {scrape_state['total_429s']}")
            elif c429 >= 1:
                # BAN LEVEL 1 — Warning
                backoff = 30 * c429
                scrape_state["ban_level"] = 1
                scrape_state["ban_message"] = f"WARNING: {c429}x 429 — backing off {backoff}s"
                scrape_state["slowdown_factor"] = min(3.0, scrape_state["slowdown_factor"] + 0.5)
                _log(f"  [BAN] ⚠️ 429 Warning ({c429}x) — backing off {backoff}s")
                _log(f"  [BAN] ⚠️ Slowdown factor: {scrape_state['slowdown_factor']:.1f}")
                time.sleep(backoff)
                session = create_safe_session()

            # Retry once after backoff
            try:
                resp = session.post(f"{TEFAS_BASE}{endpoint}", json=payload, timeout=20)
                resp.raise_for_status()
                scrape_state["consecutive_429s"] = 0  # Reset on success
                return resp.json()
            except Exception:
                raise

        elif status and status >= 500:
            scrape_state["total_errors"] += 1
            scrape_state["total_consecutive_failures"] += 1
            _log(f"  [ANTI-BAN] {status} server error — backing off 15s...")
            time.sleep(15)

            # If too many consecutive failures, treat as potential ban
            if scrape_state["total_consecutive_failures"] >= 5:
                ban_until = datetime.now() + timedelta(minutes=10)
                scrape_state["ban_detected"] = True
                scrape_state["ban_level"] = 2
                scrape_state["ban_message"] = f"BANNED! 5+ consecutive errors — 10min cooldown"
                scrape_state["ban_cooldown_until"] = ban_until.isoformat()
                _log(f"  [BAN] 🚨 5+ consecutive errors — treating as ban")
        raise

    # Jitter after each request
    jitter = random.uniform(JITTER_MIN, JITTER_MAX) * scrape_state["slowdown_factor"]
    time.sleep(jitter)

    return session


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE PHASES
# ══════════════════════════════════════════════════════════════════════════════

def _phase0_reference_data(session: requests.Session, db, req_counter: list):
    """Phase 0: Load reference data — fund groups, sub-types, announcements."""
    _log("=" * 60)
    _log("PHASE 0: Reference Data")
    _log("=" * 60)

    # ── Fund Groups ──
    try:
        data = _api_post(session, ENDPOINTS["fund_groups"], {"dil": "TR"}, req_counter)
        groups = data.get("resultList") or []
        for g in groups:
            gid = g.get("fonGrubu")
            gname = g.get("fongrupaciklama", "")
            if gid and not db.query(TefasFundGroup).filter_by(group_id=gid).first():
                db.add(TefasFundGroup(group_id=gid, group_name=gname))
        db.commit()
        scrape_state["groups_loaded"] = len(groups)
        _log(f"  Fund groups: {len(groups)} loaded")
    except Exception as e:
        _log(f"  ERROR loading fund groups: {e}")
        db.rollback()

    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    time.sleep(jitter)

    # ── Fund Sub-Types ──
    try:
        data = _api_post(session, ENDPOINTS["fund_types"], {"dil": "TR"}, req_counter)
        types = data.get("resultList") or []
        for t in types:
            tid = t.get("sfonTurKod") or t.get("sfonTuru")
            tname = t.get("sfonTurAciklama", "")
            if tid and not db.query(TefasFundSubType).filter_by(type_id=tid).first():
                db.add(TefasFundSubType(type_id=tid, type_name=tname))
        db.commit()
        scrape_state["types_loaded"] = len(types)
        _log(f"  Fund sub-types: {len(types)} loaded")
    except Exception as e:
        _log(f"  ERROR loading fund types: {e}")
        db.rollback()

    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    time.sleep(jitter)

    # ── Announcements ──
    try:
        data = _api_post(session, ENDPOINTS["announcements"], {"dil": "TR"}, req_counter)
        anns = data.get("resultList") or []
        for a in anns:
            seq = a.get("siraNo")
            title = a.get("duyuruBaslik", "")
            detail = a.get("duyuruDetay", "")
            if seq and not db.query(TefasAnnouncement).filter_by(seq_no=seq).first():
                db.add(TefasAnnouncement(seq_no=seq, title=title, detail=detail))
        db.commit()
        scrape_state["announcements_loaded"] = len(anns)
        _log(f"  Announcements: {len(anns)} loaded")
    except Exception as e:
        _log(f"  ERROR loading announcements: {e}")
        db.rollback()

    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    time.sleep(jitter)


def _phase1_fund_list(session: requests.Session, db, req_counter: list) -> list:
    """Phase 1: Fetch ALL fund codes from fonUnvanAra."""
    _log("=" * 60)
    _log("PHASE 1: Fund List (fonUnvanAra — ALL funds)")
    _log("=" * 60)

    data = _api_post(session, ENDPOINTS["fund_list"], {"fonKodu": "", "dil": "TR"}, req_counter)
    all_funds = data.get("resultList") or []
    _log(f"  Discovered {len(all_funds)} funds from TEFAS")

    # Register in DB
    new_count = 0
    for item in all_funds:
        code = item.get("fonKodu", "")
        title = item.get("fonUnvan", "")
        if not code:
            continue
        existing = db.query(TefasFund).filter(TefasFund.code == code).first()
        if existing:
            if title:
                existing.title = title
        else:
            db.add(TefasFund(code=code, title=title))
            new_count += 1
    db.commit()
    scrape_state["total_funds"] = len(all_funds)
    _log(f"  Registered: {new_count} new, {len(all_funds) - new_count} updated")

    return all_funds


def _phase2_fund_details(session: requests.Session, db, req_counter: list):
    """Phase 2: Fetch detailed info for ALL funds (fonBilgiGetir).
    Skips funds whose details were fetched today.
    """
    _log("=" * 60)
    _log("PHASE 2: Fund Details (fonBilgiGetir)")
    _log("=" * 60)

    scrape_state["phase"] = "details"
    today = datetime.utcnow().date()
    def _safe_date(val):
        if val is None: return None
        if isinstance(val, str):
            try: return datetime.strptime(val[:10], '%Y-%m-%d').date()
            except: return None
        try: return val.date()
        except: return None
    funds = db.query(TefasFund).filter(TefasFund.is_active == True).all()
    # Skip funds already fetched today
    funds_to_fetch = [f for f in funds if not _safe_date(f.last_detail_fetch) or _safe_date(f.last_detail_fetch) != today]
    skipped = len(funds) - len(funds_to_fetch)
    if skipped > 0:
        _log(f"  Skipping {skipped} funds (details already fetched today)")
    total = len(funds_to_fetch)
    start_time = time.time()
    updated = 0
    if total == 0:
        _log("  All funds already have today's details — nothing to do")
        return

    for idx, fund in enumerate(funds_to_fetch):
        try:
            scrape_state["current_fund"] = f"{fund.code} ({idx+1}/{total}) [DETAY]"

            data = _api_post(session, ENDPOINTS["fund_info"],
                           {"fonKodu": fund.code, "dil": "TR"}, req_counter)
            result = (data.get("resultList") or [{}])[0] if data.get("resultList") else {}

            if not result:
                continue

            # Update fund details
            fund.title = result.get("fonUnvan") or fund.title
            fund.current_price = _safe_float(result.get("sonFiyat"))
            fund.daily_return_pct = _safe_float(result.get("gunlukGetiri"))
            fund.shares_outstanding = _safe_float(result.get("payAdet"))
            fund.market_cap = _safe_float(result.get("portBuyukluk"))
            fund.category = result.get("fonKategori")
            fund.category_rank = _safe_int(result.get("kategoriDerece"))
            fund.category_fund_count = _safe_int(result.get("kategoriFonSay"))
            fund.investor_count = _safe_int(result.get("yatirimciSayi"))
            fund.market_share_pct = _safe_float(result.get("pazarPayi"))
            fund.last_detail_fetch = datetime.utcnow()
            updated += 1

            db.commit()
            scrape_state["details_updated"] = updated

            if (idx + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - idx - 1) / rate if rate > 0 else 0
                scrape_state["estimated_remaining"] = f"{int(remaining)}s"
                _log(f"  [{idx+1}/{total}] {updated} updated, ETA: {int(remaining)}s")

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, 'status_code', None)
            if status == 429:
                _log(f"  [ANTI-BAN] 429 — 30s backoff...")
                time.sleep(30)
                session = create_safe_session()
            db.rollback()
        except Exception as e:
            err_str = str(e)
            if err_str.startswith("BAN_COOLDOWN"):
                _log(f"  [BAN] Waiting for ban cooldown... {err_str}")
                # Sleep in small chunks and continue
                try:
                    until = datetime.fromisoformat(scrape_state["ban_cooldown_until"]) if scrape_state["ban_cooldown_until"] else None
                    if until and datetime.now() < until:
                        wait = (until - datetime.now()).total_seconds()
                        time.sleep(min(wait, 30))
                    else:
                        time.sleep(5)
                except Exception:
                    time.sleep(5)
            else:
                _log(f"  ERROR {fund.code}: {e}")
                db.rollback()

    _log(f"  Phase 2 complete: {updated}/{total} funds updated")


def _phase3_fund_prices(session: requests.Session, db, req_counter: list,
                         years_back: int = 5):
    """Phase 3: Fetch price history for ALL funds.
    Smart logic: if fund already has prices, only fetch recent (3 months).
    For new funds with no data, fetch full history.
    """
    _log("=" * 60)
    _log(f"PHASE 3: Price History (smart mode)")
    _log("=" * 60)

    scrape_state["phase"] = "prices"
    funds = db.query(TefasFund).filter(TefasFund.is_active == True).all()
    
    # Separate: funds needing full history vs incremental update
    new_funds = []      # No price data -> fetch full history
    update_funds = []   # Has data -> fetch last 3 months only
    for fund in funds:
        price_count = db.query(func.count()).select_from(TefasFundPrice).filter(
            TefasFundPrice.fund_id == fund.id
        ).scalar() or 0
        if price_count == 0:
            new_funds.append(fund)
        elif _safe_date(fund.last_price_fetch) == date.today():
            pass  # Already fetched today, skip
        else:
            update_funds.append(fund)

    _log(f"  New funds (full history): {len(new_funds)}")
    _log(f"  Update funds (3 months): {len(update_funds)}")
    _log(f"  Skipped (fetched today): {len(funds) - len(new_funds) - len(update_funds)}")
    
    total = len(new_funds) + len(update_funds)
    if total == 0:
        _log("  All funds have today's prices — nothing to do")
        return

    start_time = time.time()
    total_saved = 0
    funds_with_data = 0
    
    # Process: new funds first (full history), then updates (3 months)
    all_funds = [(f, years_back * 12) for f in new_funds] + [(f, 3) for f in update_funds]
    
    for idx, (fund, months_back) in enumerate(all_funds):
        try:
            is_new = fund in new_funds
            label = "YENI" if is_new else "GUNCELLE"
            scrape_state["current_fund"] = f"{fund.code} ({idx+1}/{total}) [{label}]"

            data = _api_post(session, ENDPOINTS["fund_prices"],
                           {"fonKodu": fund.code, "dil": "TR", "periyod": months_back},
                           req_counter)
            raw = data.get("resultList") or []
            if not isinstance(raw, list):
                raw = []

            if not raw:
                continue

            # Collect all prices for this fund from API
            new_prices = []
            for item in raw:
                tarih = item.get("tarih", "")
                if not tarih:
                    continue
                try:
                    trade_date = datetime.strptime(tarih[:10], "%Y-%m-%d").date()
                except ValueError:
                    continue
                fiyat = item.get("fiyat")
                if fiyat is None:
                    continue
                try:
                    price = float(str(fiyat).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                new_prices.append((trade_date, price))

            if not new_prices:
                continue

            # Get existing dates for this fund in one query (fast)
            existing_dates = set()
            if not is_new:  # Only check for update funds
                rows = db.query(TefasFundPrice.trade_date).filter(
                    TefasFundPrice.fund_id == fund.id
                ).all()
                existing_dates = {r[0] for r in rows}

            # Insert only new dates (skip existing — historical prices don't change)
            saved = 0
            for trade_date, price in new_prices:
                if trade_date in existing_dates:
                    continue
                db.add(TefasFundPrice(
                    fund_id=fund.id, code=fund.code,
                    trade_date=trade_date, price=price,
                ))
                saved += 1

            db.commit()
            total_saved += saved
            funds_with_data += 1
            scrape_state["prices_inserted"] = total_saved
            scrape_state["funds_with_prices"] = funds_with_data

            if saved > 0:
                fund.price_count = (fund.price_count or 0) + saved
                fund.last_price_fetch = datetime.utcnow()
                db.commit()

            if (idx + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - idx - 1) / rate if rate > 0 else 0
                scrape_state["estimated_remaining"] = f"{int(remaining)}s"
                _log(f"  [{idx+1}/{total}] +{total_saved} prices, "
                     f"{funds_with_data} funds w/data, ETA: {int(remaining)}s")

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, 'status_code', None)
            if status == 429:
                _log(f"  [ANTI-BAN] 429 — 30s backoff...")
                time.sleep(30)
                session = create_safe_session()
            db.rollback()
        except Exception as e:
            err_str = str(e)
            if err_str.startswith("BAN_COOLDOWN"):
                _log(f"  [BAN] Waiting for ban cooldown... {err_str}")
                try:
                    until = datetime.fromisoformat(scrape_state["ban_cooldown_until"]) if scrape_state["ban_cooldown_until"] else None
                    if until and datetime.now() < until:
                        wait = (until - datetime.now()).total_seconds()
                        time.sleep(min(wait, 30))
                    else:
                        time.sleep(5)
                except Exception:
                    time.sleep(5)
            else:
                _log(f"  ERROR {fund.code}: {e}")
                db.rollback()

    _log(f"  Phase 3 complete: {total_saved} prices, {funds_with_data} funds w/data")


def _phase4_fund_allocations(db, max_funds: int = 100):
    """Phase 4: Scrape portfolio allocation data via Selenium.
    Scrapes the 'Varlık Dağılımı' table from each fund's analysis page.
    Skips funds already scraped today.
    ULTRA-CONSERVATIVE timing to avoid bans.
    """
    _log("=" * 60)
    _log("PHASE 4: Fund Allocations (Selenium — ULTRA-CONSERVATIVE)")
    _log(f"  Max funds per run: {max_funds}")
    _log("  Timing: 15-30s jitter, 5min cooldown every 20 pages")
    _log("=" * 60)

    scrape_state["phase"] = "allocation"
    scrape_state["allocations_saved"] = 0

    try:
        from allocation_scraper import scrape_all_allocations
        count = scrape_all_allocations(
            db,
            log_callback=_log,
            state=scrape_state,
            max_funds=max_funds,
        )
        scrape_state["allocations_saved"] = count
        _log(f"  Phase 4 complete: {count} allocation records saved")
    except ImportError as e:
        _log(f"  [ALLOC] Selenium not available, skipping allocation scrape: {e}")
        _log(f"  [ALLOC] Install with: pip install selenium undetected-chromedriver beautifulsoup4 lxml")
    except Exception as e:
        _log(f"  [ALLOC] ERROR in allocation scraper: {e}")
        import traceback
        _log(f"  [ALLOC] {traceback.format_exc()[-500:]}")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None

def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(",", ".")))
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_full_scrape(years_back: int = 5, alloc_max: int = 100):
    """Full scrape with anti-ban measures — fetches ALL TEFAS data."""
    if scrape_state["running"]:
        _log("Scrape already in progress, skipping...")
        return

    scrape_state["running"] = True
    scrape_state["phase"] = "starting"
    scrape_state["funds_scraped"] = 0
    scrape_state["funds_with_prices"] = 0
    scrape_state["prices_inserted"] = 0
    scrape_state["details_updated"] = 0
    scrape_state["request_count"] = 0
    scrape_state["elapsed_seconds"] = 0
    scrape_state["estimated_remaining"] = ""
    scrape_state["consecutive_429s"] = 0
    scrape_state["total_429s"] = 0
    scrape_state["total_errors"] = 0
    scrape_state["ban_detected"] = False
    scrape_state["ban_level"] = 0
    scrape_state["ban_message"] = ""
    scrape_state["last_429_time"] = None
    scrape_state["ban_cooldown_until"] = None
    scrape_state["total_consecutive_failures"] = 0
    scrape_state["slowdown_factor"] = 1.0

    db = SessionLocal()
    run = PipelineRun(
        service_name="tefas_worker", module_name="full_scrape",
        status="RUNNING", started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()

    start_time = time.time()

    try:
        session = create_safe_session()
        req_counter = [0]

        _log("=" * 60)
        _log("TEFAS MAX DATA SCRAPE — ANTI-BAN MODE")
        _log(f"  Jitter: {JITTER_MIN}-{JITTER_MAX}s")
        _log(f"  Cooldown: {COOLDOWN_SECONDS}s every {COOLDOWN_EVERY} req")
        _log(f"  Session refresh: every {SESSION_REFRESH} req")
        _log(f"  Price history: {years_back} years")
        _log("=" * 60)

        # Phase 0: Reference data
        _phase0_reference_data(session, db, req_counter)
        jitter = random.uniform(3, 6)
        time.sleep(jitter)

        # Phase 1: Get ALL fund codes
        all_funds = _phase1_fund_list(session, db, req_counter)
        scrape_state["funds_scraped"] = len(all_funds)
        jitter = random.uniform(3, 6)
        time.sleep(jitter)

        # Phase 2: Fetch details for ALL funds
        _phase2_fund_details(session, db, req_counter)
        jitter = random.uniform(3, 6)
        time.sleep(jitter)

        # Phase 3: Fetch price history for ALL funds
        _phase3_fund_prices(session, db, req_counter, years_back)
        jitter = random.uniform(3, 6)
        time.sleep(jitter)

        # Phase 4: Fund allocation data (portfolio breakdown)
        _phase4_fund_allocations(db, max_funds=alloc_max)

        # Done
        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        scrape_state["last_run"] = datetime.utcnow().isoformat()
        scrape_state["phase"] = "complete"

        run.status = "SUCCESS"
        run.records_processed = scrape_state["total_funds"]
        run.records_inserted = scrape_state["prices_inserted"]
        run.finished_at = datetime.utcnow()
        db.commit()

        _log("=" * 60)
        _log("COMPLETE!")
        _log(f"  Funds: {scrape_state['total_funds']}")
        _log(f"  Details updated: {scrape_state['details_updated']}")
        _log(f"  Prices inserted: {scrape_state['prices_inserted']}")
        _log(f"  Allocations saved: {scrape_state.get('allocations_saved', 0)}")
        _log(f"  Funds with price data: {scrape_state['funds_with_prices']}")
        _log(f"  Total requests: {req_counter[0]}")
        _log(f"  Elapsed: {elapsed}s ({elapsed//60}m {elapsed%60}s)")
        _log("=" * 60)

        # Persist last run results
        scrape_state["last_run_prices"] = scrape_state["prices_inserted"]
        scrape_state["last_run_details"] = scrape_state["details_updated"]
        scrape_state["last_run_allocations"] = scrape_state.get("allocations_saved", 0)

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
        scrape_state["cooldown_until"] = None
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="TEFAS Worker (Max Data)", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schedule.json")
tefas_scheduler = None


def _load_schedule_cfg() -> dict:
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                return json.load(f).get("tefas_worker", {})
        except Exception:
            pass
    return {"enabled": True, "mode": "daily", "hour": 3, "minute": 0, "years_back": 5}


def _scheduled_scrape_wrapper(years_back):
    """Wrapper that logs when the scheduler fires and handles errors."""
    try:
        _log(f"[SCHEDULER] Job fired! Starting scrape (years_back={years_back})...")
        run_full_scrape(years_back=years_back)
    except Exception as e:
        _log(f"[SCHEDULER] ERROR in scheduled job: {e}")
        import traceback
        _log(f"[SCHEDULER] Traceback: {traceback.format_exc()}")


def _setup_scheduler():
    global tefas_scheduler
    if tefas_scheduler:
        try:
            tefas_scheduler.shutdown(wait=False)
        except Exception:
            pass
    cfg = _load_schedule_cfg()
    years_back = cfg.get("years_back", 5)
    tefas_scheduler = BackgroundScheduler(
        timezone="Europe/Istanbul",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}
    )
    # Add error listener
    def on_job_error(event):
        _log(f"[SCHEDULER] Job error: {event.exception}")
    tefas_scheduler.add_listener(on_job_error, 4096)  # EVENT_JOB_ERROR
    if not cfg.get("enabled") or cfg.get("mode") == "manual":
        _log("Scheduler: DISABLED (manual mode)")
        tefas_scheduler.start()
        return
    mode = cfg.get("mode", "daily")
    if mode == "daily":
        h = cfg.get("hour", 3)
        m = cfg.get("minute", 0)
        tefas_scheduler.add_job(
            _scheduled_scrape_wrapper, "cron",
            args=[years_back], hour=h, minute=m, id="daily_scrape",
        )
        tefas_scheduler.start()
        next_run = tefas_scheduler.get_job("daily_scrape").next_run_time
        _log(f"Scheduler: Daily at {h:02d}:{m:02d} Istanbul ({years_back} years) — next: {next_run}")
    elif mode == "interval":
        mins = cfg.get("interval_minutes", 60)
        tefas_scheduler.add_job(
            _scheduled_scrape_wrapper, "interval",
            args=[years_back], minutes=mins, id="interval_scrape",
        )
        tefas_scheduler.start()
        next_run = tefas_scheduler.get_job("interval_scrape").next_run_time
        _log(f"Scheduler: Every {mins} minutes ({years_back} years) — next: {next_run}")
    else:
        tefas_scheduler.start()
        _log(f"Scheduler: mode={mode}")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    _log("TEFAS Worker v3 started (max data mode, anti-ban)")
    _setup_scheduler()


@app.post("/api/schedule/reload")
def reload_schedule():
    _setup_scheduler()
    cfg = _load_schedule_cfg()
    return {"status": "ok", "config": cfg}


@app.get("/health")
def health():
    return {"status": "ok", "service": "tefas_worker", "version": "3.0-max-data"}


@app.get("/api/status")
def status():
    db = SessionLocal()
    try:
        funds = db.query(func.count()).select_from(TefasFund).scalar() or 0
        prices = db.query(func.count()).select_from(TefasFundPrice).scalar() or 0
        groups = db.query(func.count()).select_from(TefasFundGroup).scalar() or 0
        types = db.query(func.count()).select_from(TefasFundSubType).scalar() or 0
        anns = db.query(func.count()).select_from(TefasAnnouncement).scalar() or 0
        runs = db.query(PipelineRun).filter(
            PipelineRun.service_name == "tefas_worker"
        ).order_by(PipelineRun.started_at.desc()).first()
        return {
            "service": "tefas_worker",
            "version": "3.0-max-data",
            "funds": funds,
            "prices": prices,
            "groups": groups,
            "types": types,
            "announcements": anns,
            "scraping": scrape_state["running"],
            "phase": scrape_state["phase"],
            "current_fund": scrape_state["current_fund"],
            "request_count": scrape_state["request_count"],
            "total_funds": scrape_state["total_funds"],
            "details_updated": scrape_state["details_updated"],
            "prices_inserted": scrape_state["prices_inserted"],
            "funds_with_prices": scrape_state["funds_with_prices"],
            "cooldown_until": scrape_state["cooldown_until"],
            "elapsed_seconds": scrape_state["elapsed_seconds"],
            "estimated_remaining": scrape_state["estimated_remaining"],
            "last_run": scrape_state["last_run"] or (runs.finished_at.isoformat() if runs and runs.finished_at else None),
            "last_status": runs.status if runs else None,
            "last_run_prices": scrape_state["last_run_prices"] or (runs.records_inserted or 0),
            "last_run_details": scrape_state["last_run_details"] or (runs.records_processed or 0),
            "ban_detected": scrape_state["ban_detected"],
            "ban_level": scrape_state["ban_level"],
            "ban_message": scrape_state["ban_message"],
            "last_429_time": scrape_state["last_429_time"],
            "ban_cooldown_until": scrape_state["ban_cooldown_until"],
            "total_429s": scrape_state["total_429s"],
            "consecutive_429s": scrape_state["consecutive_429s"],
            "total_errors": scrape_state["total_errors"],
            "slowdown_factor": scrape_state["slowdown_factor"],
        }
    finally:
        db.close()


@app.post("/api/scrape/now")
def trigger_scrape(background_tasks: BackgroundTasks, years: int = 5, alloc_max: int = 100):
    if scrape_state["running"]:
        return {"status": "already_running", "message": "Scrape in progress"}
    background_tasks.add_task(run_full_scrape, years_back=years, alloc_max=alloc_max)
    return {"status": "started", "message": f"Full scrape triggered ({years} years back, alloc_max={alloc_max})"}


@app.post("/api/scrape/prices-only")
def trigger_prices_only(background_tasks: BackgroundTasks, years: int = 5):
    """Only re-fetch prices (skip details)."""
    if scrape_state["running"]:
        return {"status": "already_running", "message": "Scrape in progress"}

    def _prices_only():
        db = SessionLocal()
        try:
            session = create_safe_session()
            req_counter = [0]
            _phase3_fund_prices(session, db, req_counter, years_back=years)
        finally:
            db.close()

    background_tasks.add_task(_prices_only)
    return {"status": "started", "message": f"Prices-only scrape triggered ({years} years)"}


@app.post("/api/scrape/details-only")
def trigger_details_only(background_tasks: BackgroundTasks):
    """Only re-fetch fund details (skip prices)."""
    if scrape_state["running"]:
        return {"status": "already_running", "message": "Scrape in progress"}

    def _details_only():
        db = SessionLocal()
        try:
            session = create_safe_session()
            req_counter = [0]
            _phase2_fund_details(session, db, req_counter)
        finally:
            db.close()

    background_tasks.add_task(_details_only)
    return {"status": "started", "message": "Details-only scrape triggered"}


@app.get("/api/logs")
def get_logs():
    return {"logs": scrape_state["logs"][-500:]}


# ── Test Endpoints (for ban detection testing) ───────────────────────────────

@app.post("/api/test/ban")
def test_set_ban(
    level: int = 2,
    total_429s: int = 5,
    consecutive_429s: int = 3,
    message: str = "TEST BAN — Simulated for dashboard testing",
    slowdown: float = 3.0,
    cooldown_minutes: int = 5,
):
    """Set ban state for testing dashboard indicators."""
    from datetime import timedelta as td
    scrape_state["ban_detected"] = level >= 2
    scrape_state["ban_level"] = level
    scrape_state["total_429s"] = total_429s
    scrape_state["consecutive_429s"] = consecutive_429s
    scrape_state["ban_message"] = message
    scrape_state["slowdown_factor"] = slowdown
    scrape_state["last_429_time"] = datetime.now().isoformat()
    if cooldown_minutes > 0 and level >= 2:
        until = datetime.now() + td(minutes=cooldown_minutes)
        scrape_state["ban_cooldown_until"] = until.isoformat()
    _log(f"  [TEST] Ban state set: level={level}, 429s={total_429s}, slowdown={slowdown}x")
    return {"status": "ok", "ban_level": level, "ban_message": message}


@app.post("/api/test/ban/reset")
def test_reset_ban():
    """Reset ban state."""
    scrape_state["ban_detected"] = False
    scrape_state["ban_level"] = 0
    scrape_state["ban_message"] = ""
    scrape_state["total_429s"] = 0
    scrape_state["consecutive_429s"] = 0
    scrape_state["last_429_time"] = None
    scrape_state["ban_cooldown_until"] = None
    scrape_state["slowdown_factor"] = 1.0
    scrape_state["total_errors"] = 0
    _log("  [TEST] Ban state RESET to normal")
    return {"status": "ok", "message": "Ban state reset"}


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8001)
