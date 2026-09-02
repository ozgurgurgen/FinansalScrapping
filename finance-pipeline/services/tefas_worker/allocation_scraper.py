"""
TEFAS Fund Allocation Scraper
=============================
Scrapes portfolio allocation (varlık dağılımı) data from tefas.gov.tr's
Fon Analiz pages using Selenium with stealth mode to bypass Imperva bot protection.

The TEFAS JSON API does not expose allocation breakdown data — it was removed
when the old fundturkey.com.tr API was retired. The only source is the
"Varlık Dağılımı" table on each fund's analysis page.

Anti-bot measures:
  1. undetected-chromedriver (bypasses Imperva fingerprinting)
  2. Random delays between fund page loads (8-15s)
  3. Cooldown every 50 funds (3 min)
  4. Session rotation (restart browser) every 200 funds
"""

import os
import re
import time
import random
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("tefas_allocation")

# ── Turkish field name → English model field mapping ──────────────────────────
# These are the Turkish labels used in the TEFAS "Varlık Dağılımı" table.
# We map them to our TefasFundAllocation model columns.

FIELD_MAP: Dict[str, str] = {
    "Hisse Senedi":                          "stock",
    "Hisse Senedi (YURTDIŞI)":               "foreign_equity",
    "Borçlanma Araçları (Hazine Bonosu)":    "treasury_bill",
    "Borçlanma Araçları (Devlet Tahvili)":   "government_bond",
    "Tahvil":                                "government_bond",
    "Devlet Tahvili":                        "government_bond",
    "Hazine Bonosu":                         "treasury_bill",
    "Bono":                                  "treasury_bill",
    "Kamu Kira Sertifikası":                 "government_lease_certificates",
    "Kira Sertifikası":                      "government_lease_certificates",
    "Özel Sektör Kira Sertifikası":         "private_sector_lease_certificates",
    "Özel Sektör Tahvili":                   "private_sector_bond",
    "Özel Sektör Bonosu":                    "commercial_paper",
    "Ticari Kağıt":                          "commercial_paper",
    "Banka Bonosu":                          "bank_bills",
    "Eurobond":                              "eurobonds",
    "Döviz Tahvili":                         "fx_payable_bills",
    "Yabancı Tahvil":                        "foreign_currency_bills",
    "Vadeli Mevduat":                        "term_deposit",
    "Vadeli Mevduat (TL)":                   "term_deposit_tl",
    "Vadeli Mevduat (Döviz)":                "term_deposit_d",
    "Vadeli Mevduat (Altın)":                "term_deposit_au",
    "Altın Mevduatı":                        "term_deposit_au",
    "Katılım Hesabı":                        "participation_account",
    "Katılım Hesabı (TL)":                   "participation_account_tl",
    "Katılım Hesabı (Döviz)":                "participation_account_d",
    "Katılım Hesabı (Altın)":                "participation_account_au",
    "Altın Katılım Hesabı":                  "participation_account_au",
    "Repo":                                  "repo",
    "Ters Repo":                             "reverse_repo",
    "TMM":                                   "tmm",
    "Kıymetli Madenler":                     "precious_metals",
    "Kıymetli Madenler (BYF)":               "precious_metals_byf",
    "Altın BYF":                             "precious_metals_byf",
    "Gümüş BYF":                             "precious_metals_byf",
    "BYF":                                   "exchange_traded_fund",
    "Borsa Yatırım Fonu":                    "exchange_traded_fund",
    "Türev Araçlar":                         "derivatives",
    "Gayrimenkul Sertifikası":               "real_estate_certificate",
    "Fon Katılma Sertifikası":               "fund_participation_certificate",
    "GSYF":                                  "venture_capital_investment_fund",
    "Girişim Sermayesi Yatırım Fonu":       "venture_capital_investment_fund",
    "GYF":                                   "real_estate_investment_fund",
    "Gayrimenkul Yatırım Fonu":              "real_estate_investment_fund",
    "Varlık Dayalı Menkul Kıymet":          "asset_backed_securities",
    "Yabancı Menkul Kıymet":                "foreign_securities",
    "Yabancı Borçlanma Aracı":              "foreign_debt_instruments",
    "Yabancı Yatırım Fonu":                 "foreign_investment_fund",
    "Yabancı BYF":                           "foreign_exchange_traded_funds",
    "Diğer":                                 "other",
}


def _safe_float(val) -> Optional[float]:
    """Parse a Turkish-formatted percentage string to float."""
    if val is None:
        return None
    try:
        s = str(val).strip().replace("%", "").replace(",", ".")
        if s == "" or s == "-":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


# ── Selenium Browser Setup ────────────────────────────────────────────────────

def _create_driver(headless: bool = True):
    """Create a stealth Chrome driver using undetected-chromedriver."""
    try:
        import undetected_chromedriver as uc
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=tr-TR")
        driver = uc.Chrome(options=options, version_main=None)
        return driver
    except ImportError:
        logger.warning("undetected-chromedriver not installed, falling back to selenium")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--lang=tr-TR")
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(options=opts)
        return driver
    except Exception as e:
        logger.error("Failed to create Chrome driver: %s", e)
        raise


# ── Page Parser ───────────────────────────────────────────────────────────────

def _parse_allocation_table(html: str) -> Tuple[Optional[date], Dict[str, float]]:
    """
    Parse the 'Varlık Dağılımı' table from a TEFAS Fund Analiz page.
    Returns (date, {field_name: percentage_value}).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    allocation = {}
    trade_date = None

    # Try to find the allocation date — usually in a header or caption
    # Common patterns: "Dağılım Tarihi: 2024-01-15" or date in table header
    date_patterns = [
        r"Dağılım\s+Tarihi[:\s]*(\d{4}-\d{2}-\d{2})",
        r"Dağılım\s+Tarihi[:\s]*(\d{2}/\d{2}/\d{4})",
        r"Tarih[:\s]*(\d{4}-\d{2}-\d{2})",
        r"Tarih[:\s]*(\d{2}/\d{2}/\d{4})",
    ]
    text = soup.get_text()
    for pattern in date_patterns:
        m = re.search(pattern, text)
        if m:
            raw = m.group(1)
            try:
                if "-" in raw:
                    trade_date = datetime.strptime(raw, "%Y-%m-%d").date()
                else:
                    trade_date = datetime.strptime(raw, "%d/%m/%Y").date()
            except ValueError:
                pass
            break

    # If no explicit date found, try to find it in meta or title
    if trade_date is None:
        # Look for a date pattern near "Varlık Dağılımı" text
        m = re.search(r"Varlık\s+Dağılımı.*?(\d{2}/\d{2}/\d{4})", text, re.DOTALL)
        if m:
            try:
                trade_date = datetime.strptime(m.group(1), "%d/%m/%Y").date()
            except ValueError:
                pass

    # Find the allocation table — look for "Varlık Dağılımı" heading
    tables = soup.find_all("table")
    alloc_table = None

    for table in tables:
        # Check if this table or its parent has "Varlık Dağılımı" text
        prev = table.find_previous(["h2", "h3", "h4", "div", "span", "caption", "th"])
        if prev and "Dağılım" in prev.get_text():
            alloc_table = table
            break
        # Also check table headers
        headers = table.find_all("th")
        for h in headers:
            ht = h.get_text().strip()
            if "Dağılım" in ht or "Varlık" in ht:
                alloc_table = table
                break
        if alloc_table:
            break

    # If no specific table found, try finding by column content
    if alloc_table is None:
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    cell_text = cell.get_text().strip()
                    # Match any known Turkish field name
                    for tr_name in FIELD_MAP:
                        if tr_name.lower() in cell_text.lower():
                            alloc_table = table
                            break
                    if alloc_table:
                        break
                if alloc_table:
                    break
            if alloc_table:
                break

    if alloc_table is None:
        logger.debug("No allocation table found on page")
        return trade_date, allocation

    # Parse table rows
    rows = alloc_table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        # Try to find Turkish label and value
        # Pattern: [label, value] or [label, value%]
        for i in range(len(cells) - 1):
            label_text = cells[i].get_text().strip()
            value_text = cells[i + 1].get_text().strip()

            # Match against known field names (fuzzy)
            for tr_name, field_name in FIELD_MAP.items():
                if tr_name.lower() in label_text.lower() or label_text.lower() in tr_name.lower():
                    val = _safe_float(value_text)
                    if val is not None:
                        allocation[field_name] = val
                    break

    return trade_date, allocation


# ── Main Scraper Function ─────────────────────────────────────────────────────

def scrape_fund_allocation(
    fund_code: str,
    driver=None,
    timeout: int = 30,
) -> Optional[Dict]:
    """
    Scrape portfolio allocation for a single fund from tefas.gov.tr.
    
    Returns dict with 'trade_date' and allocation fields, or None on failure.
    """
    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?fon={fund_code}"
    close_driver = False

    try:
        if driver is None:
            driver = _create_driver(headless=True)
            close_driver = True

        driver.get(url)

        # Wait for page to load (Imperva challenge + content)
        time.sleep(random.uniform(5, 8))

        # Check for Imperva challenge
        page_source = driver.page_source
        if "challenge" in page_source.lower() and len(page_source) < 2000:
            logger.warning("  [%s] Imperva challenge detected, waiting...", fund_code)
            time.sleep(10)
            page_source = driver.page_source

        # Parse allocation
        trade_date, allocation = _parse_allocation_table(page_source)

        if not allocation:
            logger.debug("  [%s] No allocation data found", fund_code)
            return None

        return {
            "fund_code": fund_code,
            "trade_date": trade_date or date.today(),
            "allocations": allocation,
        }

    except Exception as e:
        logger.error("  [%s] Error scraping allocation: %s", fund_code, e)
        return None
    finally:
        if close_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


# ── Batch Scraper ─────────────────────────────────────────────────────────────

# Allocation timing config — ULTRA-CONSERVATIVE (ban prevention)
JITTER_MIN = 15.0    # Min 15s between page loads (was 8s)
JITTER_MAX = 30.0    # Max 30s between page loads (was 15s)
COOLDOWN_EVERY = 20   # Cooldown every 20 pages (was 50)
COOLDOWN_SECONDS = 300  # 5 min cooldown (was 3 min)
SESSION_REFRESH = 50   # New browser every 50 pages (was 200)
MAX_FUNDS_PER_RUN = 100  # Safety limit per run (0 = unlimited)


def scrape_all_allocations(
    db,
    fund_codes: Optional[List[str]] = None,
    log_callback=None,
    state: Optional[Dict] = None,
    max_funds: int = 0,
) -> int:
    """
    Scrape allocation data for all (or selected) funds.
    
    Args:
        db: SQLAlchemy session
        fund_codes: List of fund codes to scrape. If None, scrape all active funds.
        log_callback: Function to call with log messages
        state: Dict to update with progress info
        
    Returns:
        Number of funds with allocation data saved.
    """
    from shared_db.models import TefasFund, TefasFundAllocation

    def _log(msg):
        if log_callback:
            log_callback(msg)
        logger.info(msg)

    if state is None:
        state = {}

    # Get fund list
    if fund_codes:
        funds = db.query(TefasFund).filter(
            TefasFund.code.in_(fund_codes),
            TefasFund.is_active == True,
        ).all()
    else:
        funds = db.query(TefasFund).filter(TefasFund.is_active == True).all()

    _log(f"  [ALLOC] {len(funds)} funds found for allocation data")

    # Apply safety limit
    limit = max_funds or MAX_FUNDS_PER_RUN
    if limit > 0 and len(funds) > limit:
        _log(f"  [ALLOC] Safety limit: processing {limit} funds per run (out of {len(funds)})")
        funds = funds[:limit]

    driver = None
    saved_count = 0
    error_count = 0
    skipped_count = 0

    try:
        driver = _create_driver(headless=True)
        req_count = 0

        for idx, fund in enumerate(funds):
            try:
                state["current_fund"] = f"{fund.code} ({idx+1}/{len(funds)}) [ALLOC]"
                state["phase"] = "allocation"

                # Check if already scraped today
                today_alloc = db.query(TefasFundAllocation).filter(
                    TefasFundAllocation.fund_id == fund.id,
                    TefasFundAllocation.trade_date == date.today(),
                ).first()
                if today_alloc:
                    skipped_count += 1
                    continue

                result = scrape_fund_allocation(fund.code, driver=driver)
                req_count += 1

                if result is None:
                    error_count += 1
                    continue

                alloc_data = result.get("allocations", {})
                trade_date = result.get("trade_date", date.today())

                # Upsert allocation record
                existing = db.query(TefasFundAllocation).filter(
                    TefasFundAllocation.fund_id == fund.id,
                    TefasFundAllocation.trade_date == trade_date,
                ).first()

                if existing:
                    # Update
                    for field_name, value in alloc_data.items():
                        if hasattr(existing, field_name):
                            setattr(existing, field_name, value)
                    existing.scraped_at = datetime.utcnow()
                else:
                    # Insert new
                    alloc_record = TefasFundAllocation(
                        fund_id=fund.id,
                        code=fund.code,
                        trade_date=trade_date,
                        scraped_at=datetime.utcnow(),
                    )
                    for field_name, value in alloc_data.items():
                        if hasattr(alloc_record, field_name):
                            setattr(alloc_record, field_name, value)
                    db.add(alloc_record)

                db.commit()
                saved_count += 1

                if (idx + 1) % 25 == 0:
                    _log(f"  [ALLOC] [{idx+1}/{len(funds)}] saved={saved_count} errors={error_count} skipped={skipped_count}")

                # Session cooldown
                if req_count % COOLDOWN_EVERY == 0 and req_count > 0:
                    _log(f"  [ALLOC] Cooldown {COOLDOWN_SECONDS}s (request #{req_count})...")
                    time.sleep(COOLDOWN_SECONDS)

                # Session rotation
                if req_count % SESSION_REFRESH == 0 and req_count > 0:
                    _log(f"  [ALLOC] Rotating browser session...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = _create_driver(headless=True)

                # Jitter between requests
                jitter = random.uniform(JITTER_MIN, JITTER_MAX)
                time.sleep(jitter)

            except Exception as e:
                error_count += 1
                db.rollback()
                _log(f"  [ALLOC] ERROR {fund.code}: {e}")

                # If too many errors, recreate driver
                if error_count > 10 and error_count % 10 == 0:
                    _log(f"  [ALLOC] Too many errors, recreating browser...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = _create_driver(headless=True)

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    _log(f"  [ALLOC] Complete: {saved_count} saved, {error_count} errors, {skipped_count} skipped")
    return saved_count


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape TEFAS fund allocation data")
    parser.add_argument("command", choices=["fund", "all"], help="fund=one fund, all=all funds")
    parser.add_argument("--code", help="Fund code (for 'fund' command)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless (default)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [ALLOC] %(message)s",
    )

    if args.command == "fund":
        if not args.code:
            print("Error: --code is required for 'fund' command")
            exit(1)
        result = scrape_fund_allocation(args.code)
        if result:
            print(f"\n=== {result['fund_code']} — {result['trade_date']} ===")
            for k, v in sorted(result["allocations"].items()):
                print(f"  {k}: {v:.2f}%")
        else:
            print("No allocation data found")
    else:
        from shared_db.models import Base, engine, SessionLocal
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            count = scrape_all_allocations(db, log_callback=print)
            print(f"\nTotal saved: {count}")
        finally:
            db.close()
