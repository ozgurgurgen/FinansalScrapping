"""
KAP Selenium Scraper — Anti-Detection Mode
===========================================
Uses undetected-chromedriver to bypass bot detection.
Extracts: ownership, management, subsidiaries, governance, committees, free float
"""

import os
import sys
import time
import json
import re
import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _random_delay(min_s=2.0, max_s=5.0):
    """Human-like random delay."""
    time.sleep(random.uniform(min_s, max_s))


def _create_driver():
    """Create undetected Chrome driver with stealth settings."""
    import undetected_chromedriver as uc
    
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--lang=tr-TR')
    
    # Random user agent
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    options.add_argument(f'--user-agent={random.choice(agents)}')
    
    driver = uc.Chrome(options=options, version_main=151)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    
    return driver


def _parse_ownership(html):
    """Parse ownership structure from KAP company page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    shareholders = []
    
    for table in soup.find_all('table'):
        txt = table.get_text().lower()
        if not any(kw in txt for kw in ['ortak', 'pay tutarı', 'pay oranı', 'oy oranı', 'sermaye payı']):
            continue
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        
        # Parse header
        header = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
        name_col = shares_col = ratio_col = vote_col = None
        for i, h in enumerate(header):
            if any(kw in h for kw in ['ortak', 'adı', 'unvan']): name_col = i
            elif any(kw in h for kw in ['pay tutar', 'tutar', 'adet']): shares_col = i
            elif any(kw in h for kw in ['pay oranı', 'oran']): ratio_col = i
            elif any(kw in h for kw in ['oy oranı', 'oy']): vote_col = i
        
        name_col = name_col or 0
        shares_col = shares_col or min(1, len(header)-1)
        ratio_col = ratio_col or min(2, len(header)-1)
        
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            cell_texts = [c.get_text(strip=True) for c in cells]
            if not cell_texts or len(cell_texts) <= name_col:
                continue
            name = cell_texts[name_col].strip()
            if not name or name.lower() in ['toplam', 'total', '']:
                continue
            
            def _pn(t):
                if not t: return None
                t = t.strip().replace('\xa0','').replace(' ','').replace('.','').replace(',','.')
                try: return float(t)
                except: return None
            
            shares = _pn(cell_texts[shares_col] if shares_col < len(cell_texts) else '')
            ratio = _pn((cell_texts[ratio_col] if ratio_col < len(cell_texts) else '').replace('%',''))
            
            shareholders.append({
                'holder_name': name[:500],
                'shares_amount': shares,
                'share_ratio_percent': ratio,
                'is_qualified': (ratio or 0) > 5.0,
                'holder_type': 'CORPORATE' if any(k in name.upper() for k in ['A.Ş.','AŞ','HOLDİNG','FON','BANK']) else 'REAL_PERSON',
            })
        break
    
    return shareholders


def _parse_management(html):
    """Parse management board from KAP company page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    members = []
    
    for table in soup.find_all('table'):
        tt = table.get_text(strip=True).lower()
        if not any(kw in tt for kw in ['yönetim', 'board', 'başkan', 'ceo', 'genel müdür', 'bağımsız']):
            continue
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            name = cells[0].get_text(strip=True)
            title = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            if not name:
                continue
            
            mt = 'member'
            tl = title.lower()
            if any(k in tl for k in ['başkan', 'chairman']): mt = 'chairman'
            elif any(k in tl for k in ['ceo', 'genel müdür']): mt = 'ceo'
            elif any(k in tl for k in ['bağımsız', 'independent']): mt = 'independent'
            elif any(k in tl for k in ['cfo', 'mali işler']): mt = 'cfo'
            
            members.append({
                'name': name[:300],
                'title': title[:200],
                'member_type': mt,
            })
        break
    
    return members


def _parse_subsidiaries(html):
    """Parse subsidiaries from KAP company page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    subsidiaries = []
    
    for table in soup.find_all('table'):
        tt = table.get_text(strip=True).lower()
        if not any(kw in tt for kw in ['bağlı ortaklık', 'iştirak', 'sub', 'pay']):
            continue
        rows = table.find_all('tr')
        if len(rows) < 2:
            continue
        
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 1:
                continue
            name = cells[0].get_text(strip=True)
            if not name:
                continue
            sp = None
            if len(cells) > 1:
                sp_text = cells[1].get_text(strip=True).replace('%','').replace(',','.').replace(' ','')
                try: sp = float(sp_text)
                except: pass
            
            subsidiaries.append({
                'name': name[:500],
                'share_percent': sp,
                'relation_type': 'subsidiary' if (sp or 0) >= 50 else 'affiliate' if (sp or 0) >= 20 else 'investment',
            })
        break
    
    return subsidiaries


def _parse_governance(html):
    """Parse governance info (committees, audit, free float) from KAP company page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    info = {}
    page_text = soup.get_text()
    
    # Free float
    ff_match = re.search(r'serbest\s+dolaşım.*?(\d+[\.,]?\d*)\s*%', page_text, re.I)
    if ff_match:
        info['free_float_pct'] = float(ff_match.group(1).replace(',', '.'))
    
    # Audit firm
    for heading in soup.find_all(['h2','h3','h4','div','span']):
        text = heading.get_text(strip=True).lower()
        if 'denetim' in text or 'bağımsız denetim' in text:
            next_el = heading.find_next(['table','div','p'])
            if next_el:
                audit_text = next_el.get_text(strip=True)[:200]
                if audit_text and audit_text != '-':
                    info['audit_firm'] = audit_text
    
    # Committees
    committee_keywords = ['denetim komitesi', 'fiyat komitesi', 'risk komitesi', 'üt komitesi', 'sürdürülebilirlik komitesi']
    for kw in committee_keywords:
        if kw in page_text.lower():
            info.setdefault('committees', []).append(kw.title())
    
    # Governance score (TYYP)
    tyy_match = re.search(r'(?:tyyp|kurumsal\s+yönetim)\s*(?:puanı|notu|derecesi)[:\s]*([A-Z\d\+]+)', page_text, re.I)
    if tyy_match:
        info['governance_score'] = tyy_match.group(1)
    
    return info


def _parse_cashflow(html):
    """Parse cash flow data from KAP financial page."""
    from bs4 import BeautifulSoup
    import re as _re
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    CF_KEYS = {
        'operating_cash_flow': ['işletme faaliyetlerinden nakit akışı', 'işletme kaynaklı nakit'],
        'investing_cash_flow': ['yatırım faaliyetlerinden nakit akışı', 'yatırım kaynaklı nakit'],
        'financing_cash_flow': ['finansman faaliyetlerinden nakit akışı', 'finansman kaynaklı nakit'],
        'net_change': ['nakit ve nakit benzerlerindeki net değişim'],
        'closing_cash': ['dönem sonu nakit', 'dönem başı nakit ve nakit benzerleri'],
        'capex': ['sabit varlık edinimleri', 'tesis ve makine alımı'],
        'borrowings': ['borçlanmalar', 'yeni borçlanma'],
        'repayments': ['borç ödemeleri', 'kredi ödemeleri'],
        'dividends_paid': ['ödenen temettü', 'kâr payı ödemeleri'],
        'depreciation': ['amortisman', 'itfa payları'],
    }
    
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) < 3:
            continue
        has_cf = False
        for row in rows[:5]:
            t = row.get_text(strip=True).lower()
            if any(kw in t for kw in ['nakit', 'işletme', 'yatırım', 'finansman', 'cash flow']):
                has_cf = True
                break
        if not has_cf:
            continue
        
        # Parse header for periods
        header_cells = rows[0].find_all(['th', 'td'])
        period_cols = []
        for i, cell in enumerate(header_cells):
            text = cell.get_text(strip=True)
            if _re.search(r'\d{4}', text):
                pm = _re.search(r'/(\d+)', text)
                period_cols.append((i, text, int(pm.group(1)) if pm else None))
        
        if not period_cols:
            continue
        
        period_data = {}
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            item_name = cells[0].get_text(strip=True).lower()
            for ci, pl, pn in period_cols:
                if ci >= len(cells):
                    continue
                if pl not in period_data:
                    period_data[pl] = {}
                vt = cells[ci].get_text(strip=True).replace('\xa0','').replace(' ','').replace('.','').replace(',','.')
                if vt and vt not in ('-','','—'):
                    try:
                        period_data[pl][item_name] = float(vt)
                    except:
                        pass
        
        for pl, items in period_data.items():
            ym = _re.search(r'(\d{4})', pl)
            if not ym:
                continue
            year = int(ym.group(1))
            pm = _re.search(r'/(\d+)', pl)
            period = int(pm.group(1)) if pm else None
            if not period:
                continue
            
            def _find(aliases):
                for a in aliases:
                    for k, v in items.items():
                        if a.lower() in k:
                            return v
                return None
            
            results.append({
                'year': year, 'period': period,
                'operating_cash_flow': _find(CF_KEYS['operating_cash_flow']),
                'investing_cash_flow': _find(CF_KEYS['investing_cash_flow']),
                'financing_cash_flow': _find(CF_KEYS['financing_cash_flow']),
                'net_change': _find(CF_KEYS['net_change']),
                'closing_cash': _find(CF_KEYS['closing_cash']),
                'capex': _find(CF_KEYS['capex']),
                'borrowings': _find(CF_KEYS['borrowings']),
                'repayments': _find(CF_KEYS['repayments']),
                'dividends_paid': _find(CF_KEYS['dividends_paid']),
                'depreciation': _find(CF_KEYS['depreciation']),
            })
        break  # Only first matching table
    
    return results


def scrape_kap_company(driver, perma_link, ticker):
    """Scrape a single KAP company page with Selenium."""
    url = f'https://kap.org.tr/tr/sirket-bilgileri/ozet/{perma_link}'
    try:
        driver.get(url)
        _random_delay(2.0, 4.0)
        
        html = driver.page_source
        if len(html) < 5000:
            return None
        
        result = {
            'ticker': ticker,
            'shareholders': _parse_ownership(html),
            'management': _parse_management(html),
            'subsidiaries': _parse_subsidiaries(html),
            'governance': _parse_governance(html),
        }
        return result
    except Exception as e:
        logger.error(f"  Selenium error for {ticker}: {e}")
        return None


def run_selenium_scrape(max_companies=50):
    """Main entry: scrape KAP company + financial + settlement pages."""
    logger.info("=" * 60)
    logger.info("SELENIUM KAP SCRAPER — Anti-Detection Mode")
    logger.info("=" * 60)
    
    try:
        driver = _create_driver()
        logger.info("Chrome driver created")
    except Exception as e:
        logger.error(f"Failed to create driver: {e}")
        return 0
    
    # ═══ PHASE 1: Settlement page (ortaliklar) ═══
    try:
        from shared_db.models import SettlementData, SessionLocal as SSettle
        from datetime import date as _date
        db_s = SSettle()
        try:
            logger.info("[SELENIUM] Scraping settlement page...")
            driver.get('https://kap.org.tr/tr/ortaliklar')
            _random_delay(4.0, 7.0)
            html = driver.page_source
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            settle_count = 0
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if len(rows) < 3:
                    continue
                header = rows[0].get_text(strip=True).lower()
                if not any(kw in header for kw in ['yabanc', 'takas', 'oran', 'serbest']):
                    continue
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    ticker = cells[0].get_text(strip=True)
                    if not ticker or len(ticker) > 10:
                        continue
                    # Try to extract foreign ratio
                    for ci in range(1, min(5, len(cells))):
                        txt = cells[ci].get_text(strip=True).replace('%','').replace(',','.').replace(' ','')
                        try:
                            val = float(txt)
                            if 0 < val < 100:
                                existing = db_s.query(SettlementData).filter_by(
                                    ticker=ticker.upper(), trade_date=_date.today()).first()
                                if not existing:
                                    db_s.add(SettlementData(
                                        ticker=ticker.upper(), trade_date=_date.today(),
                                        foreign_ratio_pct=val))
                                    settle_count += 1
                                break
                        except:
                            pass
                if settle_count > 0:
                    break
            db_s.commit()
            logger.info(f"[SELENIUM] Settlement: {settle_count} records")
        finally:
            db_s.close()
    except Exception as e:
        logger.error(f"[SELENIUM] Settlement error: {e}")
    
    _random_delay(3.0, 5.0)
    
    try:
        from shared_db.models import (
            KapCompany, KapShareholder, KapManagement, KapSubsidiary,
            BistStockPrice, SessionLocal
        )
        import json as _json
        
        # Load permaLinks
        perma_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'kap-pipeline', 'kap_permaplinks.json')
        perma_links = {}
        if os.path.exists(perma_path):
            with open(perma_path, 'r', encoding='utf-8') as f:
                perma_links = _json.load(f)
        
        db = SessionLocal()
        count = 0
        
        try:
            companies = db.query(KapCompany).filter(KapCompany.is_active == True).limit(max_companies).all()
            logger.info(f"Scraping {len(companies)} companies with Selenium...")
            
            for idx, company in enumerate(companies):
                pl = perma_links.get(str(company.id), {})
                perma = pl.get('permaLink', '')
                if not perma:
                    continue
                
                result = scrape_kap_company(driver, perma, company.ticker)
                if not result:
                    continue
                
                # Also scrape financial page for cash flow data
                try:
                    fin_url = f'https://kap.org.tr/tr/sirket-finansal-bilgileri/{perma}'
                    driver.get(fin_url)
                    _random_delay(2.0, 4.0)
                    fin_html = driver.page_source
                    if len(fin_html) > 5000:
                        cf_data = _parse_cashflow(fin_html)
                        if cf_data:
                            from shared_db.models import KapCashFlow
                            for cf in cf_data:
                                existing = db.query(KapCashFlow).filter_by(
                                    company_id=company.id, year=cf['year'], period=cf['period']).first()
                                if not existing:
                                    # Remove None values
                                    cf_fields = {k: v for k, v in cf.items() if v is not None and k not in ('year','period')}
                                    if cf_fields:
                                        db.add(KapCashFlow(
                                            company_id=company.id,
                                            year=cf['year'], period=cf['period'],
                                            **cf_fields))
                                        count += 1
                except Exception as e:
                    logger.debug(f"  Cash flow error for {company.ticker}: {e}")
                
                # Save shareholders
                for sh in result.get('shareholders', []):
                    existing = db.query(KapShareholder).filter_by(
                        company_id=company.id, holder_name=sh['holder_name']).first()
                    if existing:
                        if sh.get('share_ratio_percent'):
                            existing.share_ratio_percent = sh['share_ratio_percent']
                            existing.is_qualified = sh['is_qualified']
                    else:
                        db.add(KapShareholder(
                            company_id=company.id,
                            holder_name=sh['holder_name'][:500],
                            shares_amount=sh.get('shares_amount'),
                            share_ratio_percent=sh.get('share_ratio_percent'),
                            is_qualified=sh.get('is_qualified', False),
                            holder_type=sh.get('holder_type', 'UNKNOWN'),
                        ))
                    count += 1
                
                # Save management
                for mg in result.get('management', []):
                    existing = db.query(KapManagement).filter_by(
                        company_id=company.id, name=mg['name']).first()
                    if not existing:
                        db.add(KapManagement(
                            company_id=company.id,
                            name=mg['name'][:300],
                            title=mg.get('title', '')[:200],
                            member_type=mg.get('member_type', 'member'),
                        ))
                        count += 1
                
                # Save subsidiaries
                for sub in result.get('subsidiaries', []):
                    existing = db.query(KapSubsidiary).filter_by(
                        company_id=company.id, name=sub['name']).first()
                    if not existing:
                        db.add(KapSubsidiary(
                            company_id=company.id,
                            name=sub['name'][:500],
                            share_percent=sub.get('share_percent'),
                            relation_type=sub.get('relation_type', 'unknown'),
                        ))
                        count += 1
                
                # Save free float to BistStockPrice
                gov = result.get('governance', {})
                if gov.get('free_float_pct'):
                    stock = db.query(BistStockPrice).filter_by(ticker=company.ticker).first()
                    if stock:
                        stock.market_cap = gov['free_float_pct']  # Temporary field usage
                
                db.commit()
                
                if (idx + 1) % 10 == 0:
                    logger.info(f"  [{idx+1}/{len(companies)}] {count} records so far")
                
                # Anti-ban delay: 3-7 seconds between companies
                _random_delay(3.0, 7.0)
        
        finally:
            db.close()
            driver.quit()
        
        logger.info("=" * 60)
        logger.info(f"SELENIUM SCRAPE COMPLETE: {count} records")
        logger.info("=" * 60)
        return count
        
    except Exception as e:
        logger.error(f"Selenium scrape error: {e}")
        try: driver.quit()
        except: pass
        return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    n = run_selenium_scrape(max_companies=30)
    print(f'Done. {n} records.')
