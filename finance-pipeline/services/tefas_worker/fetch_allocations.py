"""
TEFAS Fund Allocation Fetcher
==============================
Fetches portfolio allocation (varlık dağılımı) data for ALL funds
using the dagilimSiraliGetirT JSON API endpoint.

NO SELENIUM NEEDED - uses pure HTTP requests with correct payload format.

Key insights:
- Date format: YYYYMMDD (not YYYY-MM-DD)
- Referer: https://www.tefas.gov.tr/tr/fon-verileri
- Rate limit: ~6 requests/minute (TEFAS throttling)
- Returns all funds of a given type in one request
"""

import os
import sys
import time
import random
import json
import logging
from datetime import datetime, date

# Ensure SQLite mode for local development
import sqlite3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ALLOC] %(message)s")
logger = logging.getLogger(__name__)

# API Configuration
DIST_URL = "https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT"
FUND_TYPES = ["YAT", "EMK", "BYF", "GYF", "GSYF"]

# Field mapping: API short code -> database column
FIELD_MAP = {
    "fonKodu": "code",
    "fonUnvan": "fund_name",
    "tarih": "trade_date",
    "hs": "stock",
    "dt": "government_bond",
    "hb": "treasury_bill",
    "fb": "financing_bill",
    "ost": "private_sector_bond",
    "bb": "bank_bills",
    "vdm": "asset_backed_securities",
    "eut": "eurobonds",
    "kibd": "government_external_debt",
    "osdb": "private_sector_external_debt",
    "kba": "fx_government_internal_debt",
    "dot": "fx_payable_bills",
    "db": "fx_payable_bonds",
    "tpp": "takasbank_money_market",
    "bpp": "bist_money_market",
    "r": "repo",
    "tr": "reverse_repo",
    "vm": "term_deposit",
    "vmtl": "term_deposit_tl",
    "vmd": "term_deposit_fx",
    "vmau": "term_deposit_gold",
    "kh": "participation_account",
    "khtl": "participation_account_tl",
    "khd": "participation_account_fx",
    "khau": "participation_account_gold",
    "kks": "government_lease_certificates",
    "kkstl": "government_lease_certificates_tl",
    "kksd": "government_lease_certificates_fx",
    "kksyd": "government_foreign_lease_certificates",
    "osks": "private_sector_lease_certificates",
    "oksyd": "private_sector_foreign_lease_certificates",
    "km": "precious_metals",
    "kmbyf": "precious_metals_etf",
    "kmkba": "precious_metals_government_debt",
    "kmkks": "precious_metals_lease_certificate",
    "ymk": "foreign_security",
    "yba": "foreign_debt_security",
    "ybkb": "foreign_government_debt",
    "ybosb": "foreign_private_sector_debt",
    "yhs": "foreign_stock",
    "ybyf": "foreign_etf",
    "fkb": "fund_participation_certificate",
    "yyf": "investment_fund",
    "byf": "etf",
    "gykb": "real_estate_fund",
    "gyy": "real_estate_investment",
    "gsykb": "venture_capital_fund",
    "gsyy": "venture_capital_investment",
    "t": "derivatives",
    "vint": "futures_cash_collateral",
    "gas": "real_estate_certificate",
    "d": "other",
}

# DB column names that exist in our table
DB_COLUMNS = [
    "fund_id", "code", "trade_date",
    "stock", "treasury_bill", "government_bond", "term_deposit",
    "term_deposit_tl", "term_deposit_d", "term_deposit_au",
    "repo", "reverse_repo", "eurobonds", "precious_metals",
    "precious_metals_byf", "foreign_currency_bills", "commercial_paper",
    "bank_bills", "derivatives", "participation_account",
    "participation_account_tl", "participation_account_d",
    "participation_account_au", "government_lease_certificates",
    "real_estate_certificate", "other",
]


def create_safe_session():
    """Create requests session with anti-bot measures."""
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    ua = UserAgent()
    session.headers.update({
        "User-Agent": ua.random,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
        "Origin": "https://www.tefas.gov.tr",
        "Content-Type": "application/json",
    })
    return session


def fetch_allocations_for_date(session, trade_date_str):
    """
    Fetch all fund allocations for a given date (YYYYMMDD format).
    Returns list of dicts with allocation data.
    """
    body = {
        "fonTipi": None,  # All types
        "fonKodu": None,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": trade_date_str,
        "bitTarih": trade_date_str,
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": "",
    }

    try:
        resp = session.post(DIST_URL, json=body, timeout=30)
        data = resp.json()

        err_msg = data.get("errorMessage", "")
        if err_msg and "out of bounds" in err_msg.lower():
            return []  # Weekend/holiday - no data

        if err_msg:
            logger.warning(f"API error: {err_msg}")
            return []

        rows = data.get("resultList") or []
        return rows
    except Exception as e:
        logger.error(f"Request error: {e}")
        return []


def save_allocations_to_db(db_path, rows, fund_code_to_id):
    """Save allocation rows to database using raw SQLite (avoids ORM column mismatch)."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get existing columns in the table
    existing_cols = set(r[1] for r in c.execute('PRAGMA table_info(tefas_fund_allocations)').fetchall())
    
    saved = 0
    for row in rows:
        code = row.get("fonKodu", "")
        if not code:
            continue

        fund_id = fund_code_to_id.get(code)
        if not fund_id:
            c.execute("SELECT id FROM tefas_funds WHERE code = ? LIMIT 1", (code,))
            r = c.fetchone()
            if r:
                fund_id = r[0]
                fund_code_to_id[code] = fund_id
            else:
                continue

        # Parse trade date
        tarih = row.get("tarih", "")
        if tarih:
            try:
                trade_date = datetime.strptime(tarih, "%Y-%m-%d").date().isoformat()
            except ValueError:
                trade_date = date.today().isoformat()
        else:
            trade_date = date.today().isoformat()

        # Check if already exists
        c.execute("SELECT id FROM tefas_fund_allocations WHERE fund_id = ? AND trade_date = ? LIMIT 1", (fund_id, trade_date))
        existing = c.fetchone()

        # Map API fields to DB columns (only those that exist in the table)
        alloc_data = {}
        for api_field, db_col in FIELD_MAP.items():
            if db_col in ("code", "fund_name", "trade_date"):
                continue
            if db_col not in existing_cols:
                continue
            val = row.get(api_field)
            if val is not None:
                try:
                    alloc_data[db_col] = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    pass

        if existing:
            # Update existing
            set_clause = ", ".join(f"{k} = ?" for k in alloc_data)
            if set_clause:
                vals = list(alloc_data.values()) + [existing[0]]
                c.execute(f"UPDATE tefas_fund_allocations SET {set_clause} WHERE id = ?", vals)
        else:
            # Insert new
            cols_list = ["fund_id", "code", "trade_date"] + list(alloc_data.keys())
            placeholders = ", ".join(["?"] * len(cols_list))
            vals = [fund_id, code, trade_date] + list(alloc_data.values())
            c.execute(f"INSERT INTO tefas_fund_allocations ({', '.join(cols_list)}) VALUES ({placeholders})", vals)

        saved += 1

    conn.commit()
    conn.close()
    return saved


def run_allocation_fetch():
    """Main function to fetch all fund allocation data."""
    logger.info("=" * 60)
    logger.info("TEFAS ALLOCATION FETCHER — JSON API (No Selenium)")
    logger.info("=" * 60)

    # Get latest trading date
    today = date.today()
    # Try last 5 trading days
    test_dates = []
    d = today
    for _ in range(7):
        if d.weekday() < 5:  # Mon-Fri
            test_dates.append(d.strftime("%Y%m%d"))
        d = d.replace(day=d.day - 1) if d.day > 1 else d

    session = create_safe_session()

    # Warm up session
    logger.info("Warming up session...")
    session.get("https://www.tefas.gov.tr/", timeout=10)
    time.sleep(3)

    # Find a valid trading date using YAT type (most common)
    valid_date = None
    for dt_str in test_dates:
        logger.info(f"Testing date {dt_str}...")
        body = {
            "fonTipi": "YAT",
            "fonKodu": None,
            "aramaMetni": None,
            "fonTurKod": None,
            "fonGrubu": None,
            "sfonTurKod": None,
            "fonTurAciklama": None,
            "kurucuKod": None,
            "basTarih": dt_str,
            "bitTarih": dt_str,
            "basSira": 1,
            "bitSira": 100000,
            "dil": "TR",
            "sFonTurKod": "",
            "fonKod": "",
            "fonGrup": "",
            "fonUnvanTip": "",
        }
        try:
            resp = session.post(DIST_URL, json=body, timeout=30)
            data = resp.json()
            rows = data.get("resultList") or []
            if rows:
                valid_date = dt_str
                logger.info(f"✅ Found data for {dt_str}: {len(rows)} funds")
                break
        except Exception as e:
            logger.info(f"  Error: {e}")
        time.sleep(5)

    if not valid_date:
        logger.error("No valid trading date found in last 7 days")
        return

    # Build fund code -> fund_id mapping using raw SQLite
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "finance.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, code FROM tefas_funds WHERE is_active = 1")
    fund_code_to_id = {row[1]: row[0] for row in c.fetchall()}
    conn.close()
    logger.info(f"Loaded {len(fund_code_to_id)} fund mappings")

    # Fetch for each fund type (to get all funds)
    total_saved = 0
    for fund_type in FUND_TYPES:
        logger.info(f"\nFetching {fund_type} funds...")
        body = {
            "fonTipi": fund_type,
            "fonKodu": None,
            "aramaMetni": None,
            "fonTurKod": None,
            "fonGrubu": None,
            "sfonTurKod": None,
            "fonTurAciklama": None,
            "kurucuKod": None,
            "basTarih": valid_date,
            "bitTarih": valid_date,
            "basSira": 1,
            "bitSira": 100000,
            "dil": "TR",
            "sFonTurKod": "",
            "fonKod": "",
            "fonGrup": "",
            "fonUnvanTip": "",
        }

        try:
            resp = session.post(DIST_URL, json=body, timeout=30)
            data = resp.json()
            rows = data.get("resultList") or []
            if rows:
                saved = save_allocations_to_db(db_path, rows, fund_code_to_id)
                total_saved += saved
                logger.info(f"  {fund_type}: {len(rows)} funds, {saved} saved")
            else:
                logger.info(f"  {fund_type}: No data")
        except Exception as e:
            logger.error(f"  {fund_type} error: {e}")

        # Anti-ban delay
        time.sleep(random.uniform(8, 15))

    logger.info(f"\n{'=' * 60}")
    logger.info(f"TOTAL: {total_saved} allocation records saved")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    run_allocation_fetch()
