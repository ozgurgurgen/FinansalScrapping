"""
KAP Worker Service — Local Mode
================================
Runs KAP data pipeline modules directly (not via subprocess).
Modules are imported from the kap-pipeline/ directory.

Endpoints:
  GET  /health               — Health check
  GET  /api/status           — Current status & DB stats
  POST /api/scrape/now       — Run all modules
  POST /api/scrape/{module}  — Run specific module
  GET  /api/logs             — Live scrape logs
  GET  /api/data/companies   — View companies
  GET  /api/data/disclosures — View disclosures
  GET  /api/data/financials  — View financials
"""

import os
import sys
import time
import json
import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Optional

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, text, desc

# Add paths
KAP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "kap-pipeline")
FINANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(KAP_DIR))
sys.path.insert(0, os.path.abspath(FINANCE_DIR))
sys.path.insert(0, WORKER_DIR)

# Set KAP database URL to use the same DB
os.environ.setdefault("KAP_DB_URL", os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/finance_platform"))

from shared_db.models import (
    Base, engine, SessionLocal, PipelineRun,
    KapCompany, KapFinancial, KapDisclosure, KapCorporateAction,
    KapShareholder, KapCashFlow, KapManagement, KapSubsidiary,
    KapPortfolioReport, KapFinancialNote,
    BistStockPrice, DisclosureDetail, IndexConstituent, SettlementData,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [KAP] %(message)s")
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BAN DETECTION — Hook into requests library globally
# ══════════════════════════════════════════════════════════════════════════════

def _kap_requests_hook(response, *args, **kwargs):
    """Track HTTP responses for ban detection in KAP modules."""
    scrape_state["request_count"] += 1
    status = response.status_code
    if status == 429:
        scrape_state["consecutive_429s"] += 1
        scrape_state["total_429s"] += 1
        scrape_state["last_429_time"] = datetime.now().isoformat()
        c429 = scrape_state["consecutive_429s"]
        _log(f"  [BAN] ⚠️ 429 detected! ({c429}x consecutive, {scrape_state['total_429s']} total)")
        if c429 >= 3:
            scrape_state["ban_detected"] = True
            scrape_state["ban_level"] = 2
            scrape_state["ban_message"] = f"BANNED! {c429}x 429 from KAP"
            _log(f"  [BAN] 🚨 KAP BAN DETECTED! Multiple 429s in a row")
        elif c429 >= 1:
            scrape_state["ban_level"] = 1
            scrape_state["ban_message"] = f"WARNING: {c429}x 429"
    elif status >= 500:
        scrape_state["total_errors"] += 1
        scrape_state["total_consecutive_failures"] += 1
    else:
        # Successful request resets consecutive counters
        scrape_state["consecutive_429s"] = 0
        scrape_state["total_consecutive_failures"] = 0
    return response


# Install the hook globally for all requests in this process
try:
    import requests as _requests_lib
    _requests_lib.Session.hooks["response"].append(_kap_requests_hook)
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

scrape_state = {
    "running": False,
    "phase": "",
    "last_run": None,
    "modules_completed": 0,
    "total_records": 0,
    "current_module": "",
    "module_results": {},
    "request_count": 0,
    "elapsed_seconds": 0,
    "last_run_records": 0,
    "last_run_module_results": {},
    "logs": [],
    # Ban detection
    "consecutive_429s": 0,
    "total_429s": 0,
    "total_errors": 0,
    "ban_detected": False,
    "ban_level": 0,
    "ban_message": "",
    "last_429_time": None,
    "total_consecutive_failures": 0,
}


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    scrape_state["logs"].append(line)
    if len(scrape_state["logs"]) > 5000:
        scrape_state["logs"] = scrape_state["logs"][-5000:]
    logger.info(msg)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE RUNNERS — Direct import from kap-pipeline
# ══════════════════════════════════════════════════════════════════════════════

def _run_module1_seed() -> int:
    """Module 1: Scrape KAP company list."""
    _log("  [M1] Importing module1_seeds...")
    try:
        from module1_seeds import run_module1_seed_data
        n = run_module1_seed_data(enrich_details=False)
        _log(f"  [M1] Done: {n} companies")
        return n
    except Exception as e:
        _log(f"  [M1] ERROR: {e}")
        _log(f"  [M1] {traceback.format_exc()[-500:]}")
        return 0


def _run_module2_financials() -> int:
    """Module 2: Fetch financial statements."""
    _log("  [M2] Importing module2_financials...")
    try:
        from module2_financials import run_module2_financials
        n = run_module2_financials()
        _log(f"  [M2] Done: {n} financial records")
        return n
    except Exception as e:
        _log(f"  [M2] ERROR: {e}")
        _log(f"  [M2] {traceback.format_exc()[-500:]}")
        return 0


def _run_module3_disclosures(from_date=None, to_date=None) -> int:
    """Module 3: Fetch disclosures."""
    _log("  [M3] Importing module3_disclosures...")
    try:
        from module3_disclosures import run_module3_disclosures
        if not from_date:
            from_date = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.utcnow().strftime("%Y-%m-%d")
        n = run_module3_disclosures(from_date=from_date, to_date=to_date)
        _log(f"  [M3] Done: {n} disclosures")
        return n
    except Exception as e:
        _log(f"  [M3] ERROR: {e}")
        _log(f"  [M3] {traceback.format_exc()[-500:]}")
        return 0


def _run_module4_corporate() -> int:
    """Module 4: Parse corporate actions from disclosures."""
    _log("  [M4] Importing module4_corporate...")
    try:
        from module4_corporate import run_module4_corporate_actions
        n = run_module4_corporate_actions()
        _log(f"  [M4] Done: {n} corporate actions")
        return n
    except Exception as e:
        _log(f"  [M4] ERROR: {e}")
        _log(f"  [M4] {traceback.format_exc()[-500:]}")
        return 0


def _run_module5_buybacks() -> int:
    """Module 5: Parse buyback notifications."""
    _log("  [M5] Importing module5_buybacks...")
    try:
        from module5_buybacks import run_module5_buybacks
        n = run_module5_buybacks()
        _log(f"  [M5] Done: {n} buyback records")
        return n
    except Exception as e:
        _log(f"  [M5] ERROR: {e}")
        _log(f"  [M5] {traceback.format_exc()[-500:]}")
        return 0


def _run_module6_ipo() -> int:
    """Module 6: Parse IPO data from disclosures."""
    _log("  [M6] Importing module6_ipo...")
    try:
        from module6_ipo import run_module6_ipo
        n = run_module6_ipo()
        _log(f"  [M6] Done: {n} IPO records")
        return n
    except Exception as e:
        _log(f"  [M6] ERROR: {e}")
        _log(f"  [M6] {traceback.format_exc()[-500:]}")
        return 0


def _run_module8_cashflow() -> int:
    """Module 8: Cash flow statements."""
    _log("  [M8] Starting CashFlow scraper...")
    try:
        import requests as _req
        import re as _re
        import json as _json
        from bs4 import BeautifulSoup
        from shared_db.models import KapCompany, KapCashFlow, SessionLocal as S8

        perma_path = os.path.join(KAP_DIR, 'kap_permaplinks.json')
        perma_links = {}
        if os.path.exists(perma_path):
            with open(perma_path, 'r', encoding='utf-8') as f:
                perma_links = _json.load(f)

        db = S8()
        count = 0
        try:
            companies = db.query(KapCompany).filter(KapCompany.is_active == True).all()
            _log(f"  [M8] Processing {len(companies)} companies for cash flow...")
            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'tr-TR,tr;q=0.9',
                'Referer': 'https://kap.org.tr',
                'Accept': 'text/html,application/xhtml+xml',
            })
            CF_KEYS = {
                'operating_cash_flow': ['İşletme Faaliyetlerinden Nakit Akışı', 'İşletme Kaynaklı Nakit'],
                'investing_cash_flow': ['Yatırım Faaliyetlerinden Nakit Akışı', 'Yatırım Kaynaklı Nakit'],
                'financing_cash_flow': ['Finansman Faaliyetlerinden Nakit Akışı', 'Finansman Kaynaklı Nakit'],
                'net_change': ['Nakit ve Nakit Benzerlerindeki Net Değişim'],
                'closing_cash': ['Dönem Sonu Nakit', 'Dönem Başı Nakit ve Nakit Benzerleri'],
                'capex': ['Sabit Varlık Edinimleri', 'Tesis ve Makine Alımı'],
                'borrowings': ['Borçlanmalar', 'Yeni Borçlanma'],
                'repayments': ['Borç Ödemeleri', 'Kredi Ödemeleri'],
                'dividends_paid': ['Ödenen Temettü', 'Kâr Payı Ödemeleri'],
            }
            for idx, company in enumerate(companies):
                try:
                    pl = perma_links.get(str(company.id), {})
                    perma = pl.get('permaLink', '')
                    if not perma:
                        continue
                    url = f"https://kap.org.tr/tr/sirket-bilgileri/ozet/{perma}"
                    resp = session.get(url, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    for table in soup.find_all('table'):
                        rows = table.find_all('tr')
                        if len(rows) < 3:
                            continue
                        has_cf = False
                        for row in rows[:5]:
                            t = row.get_text(strip=True).lower()
                            if any(kw in t for kw in ['nakit', 'işletme', 'yatırım', 'finansman']):
                                has_cf = True
                                break
                        if not has_cf:
                            continue
                        header_cells = rows[0].find_all(['th', 'td'])
                        period_cols = []
                        for i, cell in enumerate(header_cells):
                            text = cell.get_text(strip=True)
                            if _re.search(r'\d{4}', text):
                                pm = _re.search(r'/(\d+)', text)
                                period_cols.append((i, text, int(pm.group(1)) if pm else None))
                        period_data = {}
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) < 2: continue
                            item_name = cells[0].get_text(strip=True)
                            for ci, pl, pn in period_cols:
                                if ci >= len(cells): continue
                                if pl not in period_data: period_data[pl] = {}
                                vt = cells[ci].get_text(strip=True).replace('\xa0','').replace(' ','').replace('.','').replace(',','.')
                                if vt and vt not in ('-','','—'):
                                    try: period_data[pl][item_name] = float(vt)
                                    except: pass
                        for pl, items in period_data.items():
                            ym = _re.search(r'(\d{4})', pl)
                            if not ym: continue
                            year = int(ym.group(1))
                            pm = _re.search(r'/(\d+)', pl)
                            period = int(pm.group(1)) if pm else None
                            if not period: continue
                            def _find(aliases):
                                for a in aliases:
                                    for k, v in items.items():
                                        if a.lower() in k.lower(): return v
                                return None
                            existing = db.query(KapCashFlow).filter_by(company_id=company.id, year=year, period=period).first()
                            data = {k: _find(v) for k, v in CF_KEYS.items()}
                            if existing:
                                for k, v in data.items():
                                    if v is not None: setattr(existing, k, v)
                            else:
                                db.add(KapCashFlow(company_id=company.id, year=year, period=period, **data))
                                count += 1
                        db.commit()
                        break
                    __import__('time').sleep(1.5)
                    if (idx+1) % 50 == 0:
                        _log(f"  [M8] [{idx+1}/{len(companies)}] {count} cashflow records so far")
                except Exception as e:
                    db.rollback()
                    continue
        finally:
            db.close()
        _log(f"  [M8] Done: {count} cash flow records")
        return count
    except Exception as e:
        _log(f"  [M8] ERROR: {e}")
        _log(f"  [M8] {traceback.format_exc()[-500:]}")
        return 0


def _run_module9_management() -> int:
    """Module 9: Management board and CEO info."""
    _log("  [M9] Starting Management scraper...")
    try:
        import requests as _req
        import re as _re
        import json as _json
        from bs4 import BeautifulSoup
        from shared_db.models import KapCompany, KapManagement, SessionLocal as S9

        perma_path = os.path.join(KAP_DIR, 'kap_permaplinks.json')
        perma_links = {}
        if os.path.exists(perma_path):
            with open(perma_path, 'r', encoding='utf-8') as f:
                perma_links = _json.load(f)

        db = S9()
        count = 0
        try:
            companies = db.query(KapCompany).filter(KapCompany.is_active == True).all()
            _log(f"  [M9] Processing {len(companies)} companies for management...")
            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'tr-TR,tr;q=0.9',
                'Referer': 'https://kap.org.tr',
                'Accept': 'text/html,application/xhtml+xml',
            })
            for idx, company in enumerate(companies):
                try:
                    pl = perma_links.get(str(company.id), {})
                    perma = pl.get('permaLink', '')
                    if not perma:
                        continue
                    url = f"https://kap.org.tr/tr/sirket-bilgileri/ozet/{perma}"
                    resp = session.get(url, timeout=15)
                    if resp.status_code != 200: continue
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    found = False
                    for table in soup.find_all('table'):
                        tt = table.get_text(strip=True).lower()
                        if not any(kw in tt for kw in ['yönetim', 'board', 'başkan', 'ceo', 'genel müdür']):
                            continue
                        rows = table.find_all('tr')
                        if len(rows) < 2: continue
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) < 2: continue
                            name = cells[0].get_text(strip=True)
                            title = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            if not name: continue
                            mt = 'member'
                            tl = title.lower()
                            if any(k in tl for k in ['başkan', 'chairman']): mt = 'chairman'
                            elif any(k in tl for k in ['ceo', 'genel müdür']): mt = 'ceo'
                            elif any(k in tl for k in ['bağımsız', 'independent']): mt = 'independent'
                            elif any(k in tl for k in ['cfo', 'mali işler']): mt = 'cfo'
                            existing = db.query(KapManagement).filter_by(company_id=company.id, name=name).first()
                            if existing:
                                existing.title = title or existing.title
                                existing.member_type = mt
                            else:
                                db.add(KapManagement(company_id=company.id, name=name, title=title, member_type=mt))
                                count += 1
                            found = True
                        if found: break
                    db.commit()
                    __import__('time').sleep(1.5)
                    if (idx+1) % 50 == 0:
                        _log(f"  [M9] [{idx+1}/{len(companies)}] {count} members so far")
                except Exception as e:
                    db.rollback()
                    continue
        finally:
            db.close()
        _log(f"  [M9] Done: {count} management records")
        return count
    except Exception as e:
        _log(f"  [M9] ERROR: {e}")
        _log(f"  [M9] {traceback.format_exc()[-500:]}")
        return 0


def _run_module10_subsidiaries() -> int:
    """Module 10: Subsidiaries and affiliates."""
    _log("  [M10] Starting Subsidiaries scraper...")
    try:
        import requests as _req
        import re as _re
        import json as _json
        from bs4 import BeautifulSoup
        from shared_db.models import KapCompany, KapSubsidiary, SessionLocal as S10

        perma_path = os.path.join(KAP_DIR, 'kap_permaplinks.json')
        perma_links = {}
        if os.path.exists(perma_path):
            with open(perma_path, 'r', encoding='utf-8') as f:
                perma_links = _json.load(f)

        db = S10()
        count = 0
        try:
            companies = db.query(KapCompany).filter(KapCompany.is_active == True).all()
            _log(f"  [M10] Processing {len(companies)} companies for subsidiaries...")
            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'tr-TR,tr;q=0.9',
                'Referer': 'https://kap.org.tr',
                'Accept': 'text/html,application/xhtml+xml',
            })
            for idx, company in enumerate(companies):
                try:
                    pl = perma_links.get(str(company.id), {})
                    perma = pl.get('permaLink', '')
                    if not perma:
                        continue
                    url = f"https://kap.org.tr/tr/sirket-bilgileri/ozet/{perma}"
                    resp = session.get(url, timeout=15)
                    if resp.status_code != 200: continue
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    found = False
                    for table in soup.find_all('table'):
                        tt = table.get_text(strip=True).lower()
                        if not any(kw in tt for kw in ['bağlı ortaklık', 'iştirak', 'sub', 'pay']):
                            continue
                        rows = table.find_all('tr')
                        if len(rows) < 2: continue
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) < 1: continue
                            name = cells[0].get_text(strip=True)
                            if not name: continue
                            sp = None
                            if len(cells) > 1:
                                sp_text = cells[1].get_text(strip=True).replace('%','').replace(',','.').replace(' ','')
                                try: sp = float(sp_text)
                                except: pass
                            rt = 'unknown'
                            if sp is not None:
                                if sp >= 50: rt = 'subsidiary'
                                elif sp >= 20: rt = 'affiliate'
                                else: rt = 'investment'
                            existing = db.query(KapSubsidiary).filter_by(company_id=company.id, name=name).first()
                            if existing:
                                existing.share_percent = sp or existing.share_percent
                                existing.relation_type = rt
                            else:
                                db.add(KapSubsidiary(company_id=company.id, name=name, share_percent=sp, relation_type=rt))
                                count += 1
                            found = True
                        if found: break
                    db.commit()
                    __import__('time').sleep(1.5)
                    if (idx+1) % 50 == 0:
                        _log(f"  [M10] [{idx+1}/{len(companies)}] {count} subsidiaries so far")
                except Exception as e:
                    db.rollback()
                    continue
        finally:
            db.close()
        _log(f"  [M10] Done: {count} subsidiary records")
        return count
    except Exception as e:
        _log(f"  [M10] ERROR: {e}")
        _log(f"  [M10] {traceback.format_exc()[-500:]}")
        return 0


def _run_module11_portfolio() -> int:
    """Module 11: Portfolio distribution reports."""
    _log("  [M11] Starting Portfolio Reports scraper...")
    try:
        from shared_db.models import KapDisclosure, KapPortfolioReport, SessionLocal as S11
        from datetime import timedelta

        db = S11()
        count = 0
        try:
            since = datetime.utcnow() - timedelta(days=90)
            disclosures = db.query(KapDisclosure).filter(
                KapDisclosure.publish_date >= since
            ).all()
            pdr_kw = ['portföy dağılım', 'portföy raporu', 'yatırım ortaklığı', 'fon portföy', 'varlık dağılım']
            pdr_discs = [d for d in disclosures if any(kw in (d.title or '').lower() for kw in pdr_kw)]
            _log(f"  [M11] Found {len(pdr_discs)} portfolio-related disclosures")
            import requests as _req
            from bs4 import BeautifulSoup
            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://kap.org.tr',
            })
            for disc in pdr_discs:
                try:
                    if not disc.source_url: continue
                    resp = session.get(disc.source_url, timeout=15)
                    if resp.status_code != 200: continue
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    for table in soup.find_all('table'):
                        rows = table.find_all('tr')
                        if len(rows) < 3: continue
                        tt = table.get_text(strip=True).lower()
                        if not any(kw in tt for kw in ['hisse', 'menkul', 'tahvil', 'değer']): continue
                        for row in rows[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) < 2: continue
                            sec_name = cells[0].get_text(strip=True)
                            if not sec_name: continue
                            existing = db.query(KapPortfolioReport).filter_by(
                                disclosure_id=disc.disclosure_id, security_name=sec_name).first()
                            if not existing:
                                def _pf(t):
                                    t = t.strip().replace('%','').replace(',','.').replace(' ','').replace('\xa0','')
                                    try: return float(t)
                                    except: return None
                                db.add(KapPortfolioReport(
                                    disclosure_id=disc.disclosure_id,
                                    company_id=disc.company_id, symbol=disc.symbol,
                                    report_date=disc.publish_date, security_name=sec_name,
                                ))
                                count += 1
                        break
                    db.commit()
                except Exception as e:
                    db.rollback()
                    continue
        finally:
            db.close()
        _log(f"  [M11] Done: {count} portfolio report entries")
        return count
    except Exception as e:
        _log(f"  [M11] ERROR: {e}")
        _log(f"  [M11] {traceback.format_exc()[-500:]}")
        return 0


def _run_module12_notes() -> int:
    """Module 12: Financial notes."""
    _log("  [M12] Starting Financial Notes scraper...")
    try:
        from shared_db.models import KapDisclosure, KapFinancialNote, SessionLocal as S12
        from datetime import timedelta
        from bs4 import BeautifulSoup
        import requests as _req

        db = S12()
        count = 0
        try:
            since = datetime.utcnow() - timedelta(days=90)
            disclosures = db.query(KapDisclosure).filter(
                KapDisclosure.publish_date >= since,
                KapDisclosure.disclosure_type == 'FINANSAL_RAPOR'
            ).order_by(KapDisclosure.publish_date.desc()).limit(200).all()
            _log(f"  [M12] Found {len(disclosures)} financial report disclosures")
            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://kap.org.tr',
            })
            for disc in disclosures:
                try:
                    existing = db.query(KapFinancialNote).filter_by(disclosure_id=disc.disclosure_id).first()
                    if existing: continue
                    if not disc.source_url: continue
                    resp = session.get(disc.source_url, timeout=15)
                    if resp.status_code != 200: continue
                    content = ''
                    if 'text/html' in resp.headers.get('content-type', ''):
                        soup = BeautifulSoup(resp.content, 'html.parser')
                        for s in soup(['script', 'style']): s.decompose()
                        content = soup.get_text('\n', strip=True)[:10000]
                    else:
                        content = resp.text[:10000] if resp.text else ''
                    if not content: continue
                    note_type = 'general'
                    tl = (disc.title or '').lower()
                    if 'dipnot' in tl or 'açıklama' in tl: note_type = 'financial_note'
                    elif 'risk' in tl: note_type = 'risk_report'
                    db.add(KapFinancialNote(
                        disclosure_id=disc.disclosure_id,
                        company_id=disc.company_id, symbol=disc.symbol,
                        title=disc.title, note_type=note_type,
                        content_text=content, source_url=disc.source_url,
                        publish_date=disc.publish_date,
                    ))
                    count += 1
                    db.commit()
                    if count % 25 == 0:
                        _log(f"  [M12] {count} notes saved so far")
                except Exception as e:
                    db.rollback()
                    continue
        finally:
            db.close()
        _log(f"  [M12] Done: {count} financial notes")
        return count
    except Exception as e:
        _log(f"  [M12] ERROR: {e}")
        _log(f"  [M12] {traceback.format_exc()[-500:]}")
        return 0


def _run_module7_ownership() -> int:
    """Module 7: Ownership from KAP disclosure API."""
    _log("  [M7] Starting Ownership (enhanced)...")
    try:
        import requests as _req
        from enhanced_modules import run_module7_ownership
        session = _req.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://kap.org.tr'})
        from shared_db.models import SessionLocal as S7
        db = S7()
        try:
            n = run_module7_ownership(session, db)
            _log(f"  [M7] Done: {n} shareholders")
            return n
        finally:
            db.close()
    except Exception as e:
        _log(f"  [M7] ERROR: {e}")
        _log(f"  [M7] {traceback.format_exc()[-500:]}")
        return 0


def _run_module13_prices() -> int:
    """Module 13: BIST Stock Prices via Yahoo Finance."""
    _log("  [M13] Starting BIST price fetcher (Yahoo Finance)...")
    try:
        import requests as _req
        from shared_db.models import KapCompany, BistStockPrice, SessionLocal as S13
        from datetime import date as _date

        db = S13()
        count = 0
        try:
            companies = db.query(KapCompany).filter(KapCompany.is_active == True).all()
            _log(f"  [M13] Fetching prices for {len(companies)} companies...")
            session = _req.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

            today = _date.today()
            for idx, company in enumerate(companies):
                ticker = company.ticker
                try:
                    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.IS?interval=1d&range=5d'
                    r = session.get(url, timeout=5)
                    if r.status_code != 200:
                        continue
                    d = r.json()
                    result = d.get('chart', {}).get('result', [])
                    if not result:
                        continue
                    meta = result[0].get('meta', {})
                    price = meta.get('regularMarketPrice')
                    if price is None:
                        continue
                    prev = meta.get('chartPreviousClose', meta.get('previousClose'))
                    vol = meta.get('regularMarketVolume')
                    chg = ((price - prev) / prev * 100) if prev and price else None
                    indicators = result[0].get('indicators', {}).get('quote', [{}])[0]
                    day_high = max(indicators.get('high', [None])) if indicators.get('high') else None
                    day_low = min(indicators.get('low', [None])) if indicators.get('low') else None
                    week_high = meta.get('fiftyTwoWeekHigh')
                    week_low = meta.get('fiftyTwoWeekLow')

                    existing = db.query(BistStockPrice).filter_by(ticker=ticker).first()
                    data = {
                        'company_name': company.company_name,
                        'price': price,
                        'previous_close': prev,
                        'day_high': day_high,
                        'day_low': day_low,
                        'volume': vol,
                        'day_change_pct': chg,
                        'week52_high': week_high,
                        'week52_low': week_low,
                    }
                    if existing:
                        for k, v in data.items():
                            if v is not None:
                                setattr(existing, k, v)
                    else:
                        db.add(BistStockPrice(ticker=ticker, **data))
                    count += 1
                    db.commit()
                except Exception:
                    db.rollback()
                    continue
                __import__('time').sleep(0.3)
                if (idx + 1) % 100 == 0:
                    _log(f"  [M13] [{idx+1}/{len(companies)}] {count} prices fetched")
        finally:
            db.close()
        _log(f"  [M13] Done: {count} stock prices")
        return count
    except Exception as e:
        _log(f"  [M13] ERROR: {e}")
        _log(f"  [M13] {traceback.format_exc()[-500:]}")
        return 0


def _run_module14_disclosure_details() -> int:
    """Module 14: Parse structured data from disclosures (tenders, block sales, etc.)."""
    _log("  [M14] Starting Disclosure Detail Parser (enhanced)...")
    try:
        import requests as _req
        from enhanced_modules import run_module14_disclosure_details
        session = _req.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://kap.org.tr'})
        from shared_db.models import SessionLocal as S14
        db = S14()
        try:
            n = run_module14_disclosure_details(session, db)
            _log(f"  [M14] Done: {n} disclosure details")
            return n
        finally:
            db.close()
    except Exception as e:
        _log(f"  [M14] ERROR: {e}")
        _log(f"  [M14] {traceback.format_exc()[-500:]}")
        return 0


def _run_module15_index_settlement() -> int:
    """Module 15: Index constituents + settlement data."""
    _log("  [M15] Starting Index & Settlement (enhanced)...")
    try:
        import requests as _req
        from enhanced_modules import run_module15_index_settlement
        session = _req.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://kap.org.tr'})
        from shared_db.models import SessionLocal as S15
        db = S15()
        try:
            n = run_module15_index_settlement(session, db)
            _log(f"  [M15] Done: {n} index/settlement records")
            return n
        finally:
            db.close()
    except Exception as e:
        _log(f"  [M15] ERROR: {e}")
        _log(f"  [M15] {traceback.format_exc()[-500:]}")
        return 0


def _run_module16_selenium() -> int:
    """Module 16: Selenium anti-detection KAP scraper."""
    _log("  [M16] Starting Selenium KAP scraper...")
    try:
        from selenium_kap import run_selenium_scrape
        n = run_selenium_scrape(max_companies=50)
        _log(f"  [M16] Done: {n} records from Selenium")
        return n
    except Exception as e:
        _log(f"  [M16] ERROR: {e}")
        _log(f"  [M16] {traceback.format_exc()[-500:]}")
        return 0


MODULE_RUNNERS = {
    "seed": _run_module1_seed,
    "financials": _run_module2_financials,
    "disclosures": _run_module3_disclosures,
    "corporate": _run_module4_corporate,
    "buybacks": _run_module5_buybacks,
    "ipo": _run_module6_ipo,
    "ownership": _run_module7_ownership,
    "cashflow": _run_module8_cashflow,
    "management": _run_module9_management,
    "subsidiaries": _run_module10_subsidiaries,
    "portfolio": _run_module11_portfolio,
    "notes": _run_module12_notes,
    "prices": _run_module13_prices,
    "disclosure_details": _run_module14_disclosure_details,
    "index_settlement": _run_module15_index_settlement,
    "selenium": _run_module16_selenium,
}

MODULE_NAMES = {
    "seed": "Sirket Listesi (Module 1)",
    "financials": "Mali Tablolar (Module 2)",
    "disclosures": "Bildirim Akisi (Module 3)",
    "corporate": "Kurumsal Islemler (Module 4)",
    "buybacks": "Geri Alim Programlari (Module 5)",
    "ipo": "Halka Arz Verileri (Module 6)",
    "ownership": "Ortaklik Yapisi (Module 7)",
    "cashflow": "Nakit Akis Tablosu (Module 8)",
    "management": "Yonetim Kurulu/CEO (Module 9)",
    "subsidiaries": "Bagli Ortakliklar (Module 10)",
    "portfolio": "Portfoy Raporlari (Module 11)",
    "notes": "Finansal Dipnotlar (Module 12)",
    "prices": "BIST Fiyatlar (Module 13)",
    "disclosure_details": "Bildirim Detay (Module 14)",
    "index_settlement": "Endeks & Takas (Module 15)",
    "selenium": "Selenium KAP (Module 16)",
}


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def run_all_modules():
    """Run all KAP modules sequentially."""
    if scrape_state["running"]:
        _log("KAP scrape already in progress")
        return

    scrape_state["running"] = True
    scrape_state["modules_completed"] = 0
    scrape_state["total_records"] = 0
    scrape_state["module_results"] = {}
    scrape_state["elapsed_seconds"] = 0
    scrape_state["phase"] = "starting"
    scrape_state["consecutive_429s"] = 0
    scrape_state["total_429s"] = 0
    scrape_state["total_errors"] = 0
    scrape_state["ban_detected"] = False
    scrape_state["ban_level"] = 0
    scrape_state["ban_message"] = ""
    scrape_state["last_429_time"] = None
    scrape_state["total_consecutive_failures"] = 0

    db = SessionLocal()
    run = PipelineRun(
        service_name="kap_worker", module_name="full_pipeline",
        status="RUNNING", started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()

    start_time = time.time()

    try:
        _log("=" * 60)
        _log("KAP FULL PIPELINE START")
        _log("=" * 60)

        # Run modules in order (all 15)
        modules = ["seed", "disclosures", "corporate", "buybacks", "ipo",
                    "ownership", "cashflow", "management", "subsidiaries", "portfolio", "notes",
                    "prices", "disclosure_details", "index_settlement"]
        for mod in modules:
            scrape_state["current_module"] = mod
            scrape_state["phase"] = mod
            _log(f"--- Running: {MODULE_NAMES.get(mod, mod)} ---")

            try:
                count = MODULE_RUNNERS[mod]()
                scrape_state["modules_completed"] += 1
                scrape_state["total_records"] += count
                scrape_state["module_results"][mod] = count
            except Exception as e:
                _log(f"  Module {mod} FAILED: {e}")
                scrape_state["module_results"][mod] = f"ERROR: {e}"

            time.sleep(2)  # Brief pause between modules

        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        scrape_state["last_run"] = datetime.utcnow().isoformat()
        scrape_state["phase"] = "complete"

        run.status = "SUCCESS"
        run.records_processed = scrape_state["modules_completed"]
        run.records_inserted = scrape_state["total_records"]
        run.finished_at = datetime.utcnow()
        db.commit()

        _log("=" * 60)
        _log("KAP PIPELINE COMPLETE!")
        for mod, count in scrape_state["module_results"].items():
            _log(f"  {MODULE_NAMES.get(mod, mod)}: {count}")
        _log(f"  Total: {scrape_state['total_records']} records")
        _log(f"  Elapsed: {elapsed}s ({elapsed//60}m {elapsed%60}s)")
        _log("=" * 60)

        # Persist last run results with ACTUAL table counts
        actual = dict(scrape_state["module_results"])
        try:
            from sqlalchemy import text as sa_text
            actual["corporate"] = db.execute(sa_text("SELECT COUNT(*) FROM corporate_actions")).scalar() or 0
            actual["buybacks"] = db.execute(sa_text("SELECT COUNT(*) FROM share_buybacks")).scalar() or 0
            actual["ipo"] = db.execute(sa_text("SELECT COUNT(*) FROM ipo_data")).scalar() or 0
        except Exception:
            pass
        scrape_state["last_run_records"] = scrape_state["total_records"]
        scrape_state["last_run_module_results"] = actual

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
        scrape_state["current_module"] = ""
        db.close()


def run_single_module(module_name: str):
    """Run a single KAP module."""
    if scrape_state["running"]:
        _log("KAP scrape already in progress")
        return

    if module_name not in MODULE_RUNNERS:
        _log(f"Unknown module: {module_name}")
        return

    scrape_state["running"] = True
    scrape_state["phase"] = module_name
    scrape_state["current_module"] = module_name
    scrape_state["elapsed_seconds"] = 0

    start_time = time.time()

    try:
        _log(f"--- Running single module: {MODULE_NAMES.get(module_name, module_name)} ---")
        count = MODULE_RUNNERS[module_name]()
        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        scrape_state["module_results"][module_name] = count
        scrape_state["last_run"] = datetime.utcnow().isoformat()
        scrape_state["phase"] = "complete"
        _log(f"  Module {module_name} complete: {count} records ({elapsed}s)")
    except Exception as e:
        elapsed = int(time.time() - start_time)
        scrape_state["elapsed_seconds"] = elapsed
        scrape_state["module_results"][module_name] = f"ERROR: {e}"
        _log(f"  Module {module_name} FAILED: {e}")
    finally:
        scrape_state["running"] = False
        scrape_state["phase"] = ""
        scrape_state["current_module"] = ""


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="KAP Worker", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schedule.json")
kap_scheduler = None


def _load_schedule_cfg() -> dict:
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                return json.load(f).get("kap_worker", {})
        except Exception:
            pass
    return {"enabled": True, "mode": "daily", "hour": 2, "minute": 0}


def _setup_scheduler():
    global kap_scheduler
    if kap_scheduler:
        try:
            kap_scheduler.shutdown(wait=False)
        except Exception:
            pass
    cfg = _load_schedule_cfg()
    kap_scheduler = BackgroundScheduler(
        timezone="Europe/Istanbul",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}
    )
    def on_job_error(event):
        _log(f"[SCHEDULER] Job error: {event.exception}")
    kap_scheduler.add_listener(on_job_error, 4096)
    if not cfg.get("enabled") or cfg.get("mode") == "manual":
        _log("Scheduler: DISABLED (manual mode)")
        kap_scheduler.start()
        return
    mode = cfg.get("mode", "daily")
    if mode == "daily":
        h = cfg.get("hour", 2)
        m = cfg.get("minute", 0)
        def _daily_job():
            try:
                _log("[SCHEDULER] Job fired! Starting KAP scrape...")
                threading.Thread(target=run_all_modules, daemon=True).start()
            except Exception as e:
                _log(f"[SCHEDULER] ERROR: {e}")
        kap_scheduler.add_job(_daily_job, "cron", hour=h, minute=m, id="daily_kap")
        kap_scheduler.start()
        next_run = kap_scheduler.get_job("daily_kap").next_run_time
        _log(f"Scheduler: Daily at {h:02d}:{m:02d} Istanbul — next: {next_run}")
    elif mode == "interval":
        mins = cfg.get("interval_minutes", 60)
        def _interval_job():
            try:
                _log("[SCHEDULER] Job fired! Starting KAP scrape...")
                threading.Thread(target=run_all_modules, daemon=True).start()
            except Exception as e:
                _log(f"[SCHEDULER] ERROR: {e}")
        kap_scheduler.add_job(_interval_job, "interval", minutes=mins, id="interval_kap")
        kap_scheduler.start()
        next_run = kap_scheduler.get_job("interval_kap").next_run_time
        _log(f"Scheduler: Every {mins} minutes — next: {next_run}")
    else:
        kap_scheduler.start()
        _log(f"Scheduler: mode={mode}")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    _log("KAP Worker v2 started (local mode)")
    _setup_scheduler()


@app.post("/api/schedule/reload")
def reload_schedule():
    _setup_scheduler()
    cfg = _load_schedule_cfg()
    return {"status": "ok", "config": cfg}


@app.get("/health")
def health():
    return {"status": "ok", "service": "kap_worker", "version": "2.0-local"}


@app.get("/api/status")
def status():
    db = SessionLocal()
    try:
        companies = db.query(func.count()).select_from(KapCompany).scalar() or 0
        financials = db.query(func.count()).select_from(KapFinancial).scalar() or 0
        disclosures = db.query(func.count()).select_from(KapDisclosure).scalar() or 0
        corporate = db.query(func.count()).select_from(KapCorporateAction).scalar() or 0
        shareholders = db.query(func.count()).select_from(KapShareholder).scalar() or 0
        cashflows = db.query(func.count()).select_from(KapCashFlow).scalar() or 0
        management = db.query(func.count()).select_from(KapManagement).scalar() or 0
        subsidiaries = db.query(func.count()).select_from(KapSubsidiary).scalar() or 0
        portfolio = db.query(func.count()).select_from(KapPortfolioReport).scalar() or 0
        notes = db.query(func.count()).select_from(KapFinancialNote).scalar() or 0
        stock_prices = db.query(func.count()).select_from(BistStockPrice).scalar() or 0
        disc_details = db.query(func.count()).select_from(DisclosureDetail).scalar() or 0
        index_members = db.query(func.count()).select_from(IndexConstituent).scalar() or 0
        settlements = db.query(func.count()).select_from(SettlementData).scalar() or 0
        runs = db.query(PipelineRun).filter(
            PipelineRun.service_name == "kap_worker"
        ).order_by(PipelineRun.started_at.desc()).first()

        # Category breakdown
        cats = db.query(
            KapDisclosure.category, func.count()
        ).group_by(KapDisclosure.category).all()

        # Get counts from old tables (modules 4/5/6 write there)
        try:
            from sqlalchemy import text as sa_text
            old_corporate = db.execute(sa_text("SELECT COUNT(*) FROM corporate_actions")).scalar() or 0
            old_buybacks = db.execute(sa_text("SELECT COUNT(*) FROM share_buybacks")).scalar() or 0
            old_ipo = db.execute(sa_text("SELECT COUNT(*) FROM ipo_data")).scalar() or 0
        except Exception:
            old_corporate = corporate
            old_buybacks = 0
            old_ipo = 0

        return {
            "service": "kap_worker",
            "version": "2.0-local",
            "companies": companies,
            "financials": financials,
            "disclosures": disclosures,
            "corporate_actions": old_corporate,
            "share_buybacks": old_buybacks,
            "ipo_data": old_ipo,
            "shareholders": shareholders,
            "cashflows": cashflows,
            "management": management,
            "subsidiaries": subsidiaries,
            "portfolio_reports": portfolio,
            "financial_notes": notes,
            "stock_prices": stock_prices,
            "disclosure_details": disc_details,
            "index_members": index_members,
            "settlements": settlements,
            "disclosure_categories": {c: n for c, n in cats},
            "running": scrape_state["running"],
            "phase": scrape_state["phase"],
            "current_module": scrape_state["current_module"],
            "modules_completed": scrape_state["modules_completed"],
            "module_results": scrape_state["module_results"],
            "total_records": scrape_state["total_records"],
            "elapsed_seconds": scrape_state["elapsed_seconds"],
            "last_run": scrape_state["last_run"] or (str(runs.finished_at) if runs and runs.finished_at else None),
            "last_status": runs.status if runs else None,
            "last_run_records": scrape_state["last_run_records"] or (runs.records_inserted or 0),
            "last_run_module_results": scrape_state["last_run_module_results"] or {},
            "ban_detected": scrape_state["ban_detected"],
            "ban_level": scrape_state["ban_level"],
            "ban_message": scrape_state["ban_message"],
            "last_429_time": scrape_state["last_429_time"],
            "total_429s": scrape_state["total_429s"],
            "consecutive_429s": scrape_state["consecutive_429s"],
            "total_errors": scrape_state["total_errors"],
            "total_consecutive_failures": scrape_state["total_consecutive_failures"],
        }
    finally:
        db.close()


# ── Manual Triggers ──────────────────────────────────────────────────────────

@app.post("/api/scrape/now")
def trigger_all(background_tasks: BackgroundTasks):
    if scrape_state["running"]:
        return {"status": "already_running", "message": "KAP pipeline in progress"}
    background_tasks.add_task(run_all_modules)
    return {"status": "started", "message": "KAP full pipeline triggered"}


@app.post("/api/scrape/{module}")
def trigger_module(module: str, background_tasks: BackgroundTasks):
    if module not in MODULE_RUNNERS:
        return {"status": "error", "message": f"Unknown module: {module}. Valid: {list(MODULE_RUNNERS.keys())}"}
    if scrape_state["running"]:
        return {"status": "already_running", "message": "KAP pipeline in progress"}
    background_tasks.add_task(run_single_module, module)
    return {"status": "started", "module": module, "name": MODULE_NAMES.get(module, module)}


@app.get("/api/logs")
def get_logs():
    return {"logs": scrape_state["logs"][-500:]}


# ── Data Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/data/companies")
def get_companies(limit: int = Query(100, le=5000), offset: int = 0):
    db = SessionLocal()
    try:
        total = db.query(func.count()).select_from(KapCompany).scalar() or 0
        items = db.query(KapCompany).order_by(KapCompany.ticker).offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": [{
                "ticker": c.ticker,
                "company_name": c.company_name,
                "sector": c.sector,
                "market": c.market,
                "is_active": c.is_active,
            } for c in items]
        }
    finally:
        db.close()


@app.get("/api/data/disclosures")
def get_disclosures(
    limit: int = Query(100, le=5000),
    offset: int = 0,
    category: Optional[str] = None,
    symbol: Optional[str] = None,
    days: int = Query(30, le=365),
):
    db = SessionLocal()
    try:
        q = db.query(KapDisclosure)
        if category:
            q = q.filter(KapDisclosure.category == category)
        if symbol:
            q = q.filter(KapDisclosure.symbol == symbol)
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(KapDisclosure.publish_date >= since)

        total = q.count()
        items = q.order_by(desc(KapDisclosure.publish_date)).offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": [{
                "disclosure_id": d.disclosure_id,
                "symbol": d.symbol,
                "title": d.title,
                "category": d.category,
                "publish_date": d.publish_date.isoformat() if d.publish_date else None,
                "source_url": d.source_url,
                "is_catalyst": d.is_catalyst,
            } for d in items]
        }
    finally:
        db.close()


@app.get("/api/data/financials")
def get_financials(
    limit: int = Query(100, le=5000),
    offset: int = 0,
    company_id: Optional[int] = None,
):
    db = SessionLocal()
    try:
        q = db.query(KapFinancial)
        if company_id:
            q = q.filter(KapFinancial.company_id == company_id)
        total = q.count()
        items = q.order_by(desc(KapFinancial.year), desc(KapFinancial.period)).offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": [{
                "company_id": f.company_id,
                "year": f.year,
                "period": f.period,
                "revenue": float(f.revenue) if f.revenue else None,
                "net_profit": float(f.net_profit) if f.net_profit else None,
                "total_assets": float(f.total_assets) if f.total_assets else None,
                "equity": float(f.equity) if f.equity else None,
            } for f in items]
        }
    finally:
        db.close()


@app.get("/api/data/corporate-actions")
def get_corporate_actions(limit: int = Query(100, le=5000), offset: int = 0):
    db = SessionLocal()
    try:
        total = db.query(func.count()).select_from(KapCorporateAction).scalar() or 0
        items = db.query(KapCorporateAction).order_by(desc(KapCorporateAction.id)).offset(offset).limit(limit).all()
        return {
            "total": total,
            "data": [{
                "company_id": ca.company_id,
                "action_type": ca.action_type,
                "gross_per_share": float(ca.gross_per_share) if ca.gross_per_share else None,
                "net_per_share": float(ca.net_per_share) if ca.net_per_share else None,
                "yield_percent": ca.yield_percent,
                "ratio_percent": ca.ratio_percent,
                "ex_date": ca.ex_date.isoformat() if ca.ex_date else None,
                "status": ca.status,
                "description": ca.description,
            } for ca in items]
        }
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=8002)
