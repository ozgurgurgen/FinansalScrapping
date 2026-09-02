"""
Batch Data Fetcher — Adim Adim Veri Cekme
==========================================
Buyuk veri setlerini batch'ler halinde ceker ve veritabanina kaydeder.
Her batch sonrasi commit yaparak veri kaybini onler.
"""

import os, sys, json, re, time, logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup

os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_session, Company, Financial, Disclosure, upsert_financial, upsert_disclosure
from config import ENDPOINTS, KAP_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
})


def parse_number(text):
    """Parse Turkish number format to float."""
    if not text or text.strip() in ("", "-", "n/a", "Bilgi Mevcut Degil"):
        return None
    text = text.strip().replace("\xa0", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except:
        return None


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 1: Fetch permaLinks for all companies
# ═════════════════════════════════════════════════════════════════════════════

def stage1_fetch_permaLinks(batch_size=50):
    """Fetch permaLinks using member/filter API."""
    logger.info("STAGE 1: Fetching permaLinks...")
    
    # Load existing permaLinks
    perma_file = "kap_permaplinks.json"
    existing = {}
    if os.path.exists(perma_file):
        with open(perma_file) as f:
            existing = json.load(f)
        logger.info(f"Loaded {len(existing)} existing permaLinks")
    
    session = get_session()
    companies = session.query(Company).all()
    session.close()
    
    # Filter companies that don't have permaLinks yet
    to_fetch = [c for c in companies if str(c.id) not in existing]
    logger.info(f"Need to fetch {len(to_fetch)} permaLinks")
    
    if not to_fetch:
        logger.info("All permaLinks already fetched!")
        return existing
    
    # Init session
    try:
        SESSION.get("https://www.kap.org.tr/tr", timeout=15)
    except:
        pass
    
    fetched = 0
    for i, comp in enumerate(to_fetch):
        try:
            r = SESSION.get(
                f"https://www.kap.org.tr/tr/api/member/filter/{comp.ticker}",
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    existing[str(comp.id)] = {
                        "permaLink": data[0].get("permaLink", ""),
                        "oid": data[0].get("mkkMemberOid", ""),
                        "title": data[0].get("title", ""),
                    }
                    fetched += 1
            
            time.sleep(0.3)
            
            if (i + 1) % batch_size == 0:
                # Save checkpoint
                with open(perma_file, "w") as f:
                    json.dump(existing, f)
                logger.info(f"  Checkpoint: {i+1}/{len(to_fetch)} fetched ({fetched} new)")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"  Error fetching {comp.ticker}: {e}")
            time.sleep(3)
    
    # Final save
    with open(perma_file, "w") as f:
        json.dump(existing, f)
    logger.info(f"STAGE 1 DONE: {len(existing)} total permaLinks")
    return existing


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 2: Fetch financial data for companies
# ═════════════════════════════════════════════════════════════════════════════

def stage2_fetch_financials(perma_map, batch_size=20):
    """Fetch and parse financial data from KAP financial pages."""
    logger.info("STAGE 2: Fetching financial data...")
    
    session = get_session()
    companies = session.query(Company).all()
    
    # Filter companies that have permaLinks but no financial data
    from sqlalchemy import func
    companies_with_fin = (
        session.query(Financial.company_id)
        .distinct()
        .all()
    )
    companies_with_fin_ids = {c[0] for c in companies_with_fin}
    
    to_fetch = [
        c for c in companies
        if str(c.id) in perma_map and c.id not in companies_with_fin_ids
    ]
    logger.info(f"Need to fetch financials for {len(to_fetch)} companies")
    
    count = 0
    for i, comp in enumerate(to_fetch[:batch_size]):
        perma = perma_map[str(comp.id)]["permaLink"]
        if not perma:
            continue
        
        url = f"https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{perma}"
        
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            tables = soup.find_all("table")
            
            if len(tables) < 2:
                continue
            
            # Parse periods from header
            header = tables[0].find("tr")
            if not header:
                continue
            header_text = header.get_text(strip=True)
            periods = re.findall(r"(\d{4})/(\d{2})", header_text)
            
            if not periods:
                continue
            
            # Build period data dict
            period_data = {}
            for p_year, p_period in periods:
                period_data[f"{p_year}/{p_period}"] = {}
            
            # Parse balance sheet (Table 0)
            _parse_table(tables[0], period_data, {
                "Toplam Varliklar": "total_assets",
                "Toplam Aktifler": "total_assets",
                "Donen Varliklar": "current_assets",
                "Duran Varliklar": "non_current_assets",
                "Kisa Vadeli Borclar": "short_term_debt",
                "Uzun Vadeli Borclar": "long_term_debt",
                "Nakit ve Nakit Benzerleri": "cash_and_equivalents",
                "Oz Kaynaklar": "equity",
                "Odenmis Sermaye": "paid_capital",
                "Finansal Borclar": "financial_debt",
                "Toplam Kaynaklar": "total_debt",
            })
            
            # Parse income statement (Table 1)
            _parse_table(tables[1], period_data, {
                "Hasilat": "revenue",
                "Net Satislar": "revenue",
                "Brut Kar": "gross_profit",
                "FAVOK": "ebitda",
                "Esas Faaliyet Kar": "ebit",
                "Net Donem Kar": "net_profit",
                "Net Kar": "net_profit",
                "Diger Gelirler": "other_income",
            })
            
            # Save to database
            saved = 0
            for period_key, data in period_data.items():
                if not data or len(data) < 2:
                    continue
                year, period = period_key.split("/")
                
                rev = data.get("revenue")
                gp = data.get("gross_profit")
                ebitda = data.get("ebitda")
                np_val = data.get("net_profit")
                ta = data.get("total_assets")
                eq = data.get("equity")
                ca = data.get("current_assets")
                std = data.get("short_term_debt")
                fin_debt = data.get("financial_debt")
                cash = data.get("cash_and_equivalents")
                
                record = {
                    "year": int(year),
                    "period": int(period),
                    "revenue": rev,
                    "gross_profit": gp,
                    "ebitda": ebitda,
                    "net_profit": np_val,
                    "total_assets": ta,
                    "equity": eq,
                    "current_assets": ca,
                    "short_term_debt": std,
                    "financial_debt": fin_debt,
                    "cash_and_equivalents": cash,
                    "gross_margin": (gp / rev) if gp and rev and rev > 0 else None,
                    "ebitda_margin": (ebitda / rev) if ebitda and rev and rev > 0 else None,
                    "net_margin": (np_val / rev) if np_val and rev and rev > 0 else None,
                    "current_ratio": (ca / std) if ca and std and std > 0 else None,
                    "leverage_ratio": ((data.get("total_debt") or 0) / ta) if ta and ta > 0 else None,
                    "roe": (np_val / eq) if np_val and eq and eq > 0 else None,
                    "roa": (np_val / ta) if np_val and ta and ta > 0 else None,
                    "net_debt": ((fin_debt or 0) - (cash or 0)) if fin_debt is not None else None,
                }
                
                upsert_financial(session, comp.id, record)
                saved += 1
            
            session.commit()
            count += 1
            logger.info(f"  [{count}] {comp.ticker}: {saved} periods")
            
            time.sleep(3)  # Rate limit
            
        except Exception as e:
            logger.error(f"  {comp.ticker}: Error - {e}")
            session.rollback()
    
    session.close()
    logger.info(f"STAGE 2 DONE: {count} companies processed")
    return count


def _parse_table(table, period_data, field_map):
    """Parse a financial HTML table."""
    rows = table.find_all("tr")
    for row in rows[2:]:  # Skip header and currency row
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        if not label:
            continue
        values = [c.get_text(strip=True) for c in cells[1:]]
        
        for turkish_label, field in field_map.items():
            if turkish_label.lower() in label.lower():
                for idx, period in enumerate(periods_from_header(table)):
                    if idx < len(values):
                        val = parse_number(values[idx])
                        period_key = f"{period[0]}/{period[1]}"
                        if period_key in period_data and val is not None:
                            period_data[period_key][field] = val


def periods_from_header(table):
    """Extract period tuples from table header."""
    header = table.find("tr")
    if not header:
        return []
    return re.findall(r"(\d{4})/(\d{2})", header.get_text(strip=True))


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 3: Fetch disclosures (when API is available)
# ═════════════════════════════════════════════════════════════════════════════

def stage3_fetch_disclosures(from_date="01.08.2026", to_date="28.08.2026"):
    """Fetch disclosures using KAP API (when not rate-limited)."""
    logger.info("STAGE 3: Fetching disclosures...")
    
    session = get_session()
    
    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "disclosureClass": None,
        "memberType": "IGS",
        "mkkMemberOid": None,
        "subject": None,
        "withInactive": False,
        "term": None,
        "year": None,
        "indexList": [],
        "stockCode": None,
        "disclosureIndexList": [],
    }
    
    try:
        r = SESSION.post(
            "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria",
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            logger.error(f"Disclosure API returned {r.status_code}")
            return 0
        
        data = r.json()
        if not isinstance(data, list):
            logger.error(f"Unexpected response type: {type(data)}")
            return 0
        
        count = 0
        for item in data:
            basic = item.get("disclosureBasic", item)
            disc_id = str(basic.get("disclosureIndex", ""))
            if not disc_id or disc_id == "0":
                continue
            
            symbol = basic.get("stockCode", "")
            company_id = None
            if symbol:
                comp = session.query(Company).filter(Company.ticker == symbol).first()
                if comp:
                    company_id = comp.id
            
            title = basic.get("title", "")
            category = _categorize(title)
            is_catalyst = category not in ("Diger", "Finansman")
            
            date_str = basic.get("publishDate", "")
            try:
                pub_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            except:
                pub_date = datetime.utcnow()
            
            disc_data = {
                "disclosure_id": disc_id,
                "company_id": company_id,
                "symbol": symbol,
                "title": title,
                "category": category,
                "disclosure_type": basic.get("disclosureType"),
                "publish_date": pub_date,
                "source_url": f"{KAP_BASE_URL}/tr/{disc_id}",
                "is_catalyst": is_catalyst,
                "raw_content": basic.get("summary", ""),
            }
            
            upsert_disclosure(session, disc_data)
            count += 1
        
        session.commit()
        session.close()
        logger.info(f"STAGE 3 DONE: {count} disclosures saved")
        return count
        
    except Exception as e:
        logger.error(f"Disclosure fetch failed: {e}")
        session.close()
        return 0


def _categorize(title):
    """Categorize disclosure title."""
    t = title.lower()
    if any(kw in t for kw in ["temettu", "kar payi"]):
        return "Temettu"
    if any(kw in t for kw in ["buyume", "satis artis", "rekor"]):
        return "Buyuklenme"
    if any(kw in t for kw in ["yatirim", "fabrika", "tesis"]):
        return "Yatirim"
    if any(kw in t for kw in ["yeni is", "sozlesme", "siparis", "ihale"]):
        return "Yeni_Is"
    if any(kw in t for kw in ["sermaye", "bedelli", "bedelsiz"]):
        return "Sermaye"
    if any(kw in t for kw in ["dava", "tazminat"]):
        return "Dava"
    if any(kw in t for kw in ["finansman", "kredi", "tahvil"]):
        return "Finansman"
    if any(kw in t for kw in ["halka ariz", "izahname"]):
        return "IPO"
    if any(kw in t for kw in ["geri alim"]):
        return "Geri_Alim"
    if any(kw in t for kw in ["ortaklik", "pay devri"]):
        return "Ortaklik_Degisimi"
    return "Diger"


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["1", "2", "3", "all"], default="all", nargs="?")
    parser.add_argument("--batch", type=int, default=20)
    args = parser.parse_args()
    
    init_db()
    
    if args.stage in ("1", "all"):
        perma_map = stage1_fetch_permaLinks(batch_size=args.batch)
    else:
        # Load existing
        with open("kap_permaplinks.json") as f:
            perma_map = json.load(f)
    
    if args.stage in ("2", "all"):
        stage2_fetch_financials(perma_map, batch_size=args.batch)
    
    if args.stage in ("3", "all"):
        stage3_fetch_disclosures()
    
    logger.info("ALL STAGES COMPLETE")
