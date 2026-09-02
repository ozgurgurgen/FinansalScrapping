"""
KAP Finansal Tablo Detail Scraper v2
- disclosureIndex URL pattern kullanir
- Fuzzy match ile Türkçe muhasebe satırlarını eşleştirir
- Resume-able: zaten çekilen şirketleri atlar
- Anti-ban: exponential backoff + jitter
"""
import sys, io, sqlite3, time, random, re, json, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
LOG_FILE = str(Path(__file__).parent / 'kap_fin_log.json')

def load_progress():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return {'scraped': [], 'failed': [], 'last_index': 0}

def save_progress(progress):
    with open(LOG_FILE, 'w') as f:
        json.dump(progress, f)

def fuzzy_match(text, candidates, threshold=60):
    """Basit fuzzy match — rapidfuzz yoksa substring matching kullan"""
    text_lower = text.lower().strip()
    for candidate in candidates:
        cand_lower = candidate.lower()
        # Direct substring
        if cand_lower in text_lower or text_lower in cand_lower:
            return candidate
        # Word overlap
        text_words = set(text_lower.split())
        cand_words = set(cand_lower.split())
        if len(text_words & cand_words) / max(len(cand_words), 1) > 0.5:
            return candidate
    return None

# Turkish accounting term mappings
BALANCE_SHEET_MAP = {
    # Cash & equivalents
    'cash': ['nakit ve nakit benzerleri', 'nakit', 'kasa', 'banka mevduatı', 'nakit benzerleri'],
    # Current assets
    'current_assets': ['dönen varlıklar', 'toplam dönen varlıklar', 'kısa vadeli varlıklar'],
    # Fixed assets  
    'fixed_assets': ['durulan varlıklar', 'duran varlıklar', 'toplam duran varlıklar'],
    # Financial debt
    'financial_debt': ['finansal borçlar', 'finansal borçlanmalar', 'uzun vadeli finansal borçlar',
                       'kısa vadeli borçlanmalar', 'kira sözleşmelerinden doğan borçlar'],
    # Short-term debt
    'short_term_debt': ['kısa vadeli yükümlülükler', 'kısa vadeli borçlar'],
    # Long-term debt
    'long_term_debt': ['uzun vadeli yükümlülükler', 'uzun vadeli borçlar'],
    # Equity
    'equity': ['özkaynaklar', 'ana ortaklığa ait özkaynaklar', 'toplam özkaynaklar'],
    # Total assets
    'total_assets': ['toplam varlıklar', 'toplam aktifler'],
    # Total liabilities
    'total_liabilities': ['toplam yükümlülükler', 'toplam borclar'],
}

INCOME_MAP = {
    'revenue': ['hasılat', 'net satışlar', 'satış gelirleri', 'brüt satışlar'],
    'cost_of_goods': ['satışların maliyeti', 'sattığı malların maliyeti', 'brüt kar/zarar'],
    'gross_profit': ['brüt kar', 'brüt kar/zarar', 'faaliyet karı öncesi kar'],
    'operating_expenses': ['faaliyet giderleri', 'satış ve dağıtım giderleri', 'genel yönetim giderleri'],
    'ebit': ['esas faaliyet karı', 'faaliyet karı', 'işletme karı'],
    'ebitda': ['faiz, vergi, amortisman öncesi kar', 'favök', 'ebitda'],
    'net_profit': ['dönem karı', 'net kar', 'ana ortaklığa ait net kar', 'dönem net karı'],
}

CASHFLOW_MAP = {
    'operating_cf': ['işletme faaliyetlerinden nakit akışları', 'işletme activities', 'operasyonel nakit'],
    'investing_cf': ['yatırım faaliyetlerinden nakit akışları', 'yatırım activities'],
    'financing_cf': ['finansman faaliyetlerinden nakit akışları', 'finansman activities', 'finans activities'],
    'depreciation': ['amortisman', 'yıpranma giderleri', 'amortisman ve tükenme'],
    'capex': ['maddi duran varlık yatırımları', 'iyileştirme ve yenileme giderleri', 'varlık alımları'],
}

def parse_number(text):
    """Turkish number format parse"""
    if not text or text.strip() in ['-', '—', '', 'n/a', 'N/A', 'TBD']:
        return None
    text = text.strip()
    # Handle parentheses as negative
    negative = '(' in text and ')' in text
    text = text.replace('(', '').replace(')', '')
    # Turkish format: 1.234.567,89 → 1234567.89
    text = text.replace('.', '').replace(',', '.')
    text = re.sub(r'[^\d.\-]', '', text)
    try:
        val = float(text)
        return -val if negative else val
    except:
        return None

def parse_table_rows(html_content, table_map):
    """HTML tablo satırlarından veri çıkar"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    results = {}
    
    # Find all table rows
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                
                # Try fuzzy match
                for field, keywords in table_map.items():
                    if field not in results:
                        matched = fuzzy_match(label, keywords)
                        if matched:
                            parsed = parse_number(value)
                            if parsed is not None:
                                results[field] = parsed
    
    # Also try text-based parsing (KAP sometimes renders as divs, not tables)
    text = soup.get_text()
    for field, keywords in table_map.items():
        if field not in results:
            for keyword in keywords:
                # Pattern: "keyword ... value TL" or "keyword: value"
                pattern = re.escape(keyword) + r'[:\s]*([-\d.,]+)'
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    parsed = parse_number(m.group(1))
                    if parsed is not None:
                        results[field] = parsed
                        break
    
    return results

def scrape_financial_page(page, disclosure_index):
    """KAP bildirim sayfasından finansal tabloyu çek"""
    url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
    
    try:
        page.goto(url, timeout=20000, wait_until='networkidle')
        time.sleep(2)
        
        # Wait for content to load
        try:
            page.wait_for_selector('table, .content, .detail-content', timeout=10000)
        except:
            pass
        
        html = page.content()
        
        # Parse balance sheet
        bs_data = parse_table_rows(html, BALANCE_SHEET_MAP)
        
        # Parse income statement
        is_data = parse_table_rows(html, INCOME_MAP)
        
        # Parse cash flow
        cf_data = parse_table_rows(html, CASHFLOW_MAP)
        
        # Merge all
        all_data = {}
        all_data.update(bs_data)
        all_data.update(is_data)
        all_data.update(cf_data)
        
        return all_data
        
    except Exception as e:
        return {'error': str(e)}

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    progress = load_progress()
    
    # Get financial disclosure IDs that we haven't scraped yet
    # Focus on companies that have financials but missing key fields
    c.execute("""
        SELECT DISTINCT comp.ticker, comp.id as company_id, comp.mkk_id, comp.company_name,
               d.disclosure_id, d.source_url, d.id as db_id
        FROM disclosures d
        JOIN companies comp ON d.company_id = comp.id
        JOIN financials f ON f.company_id = comp.id
        WHERE (d.disclosure_type LIKE '%FR%' 
           OR d.title LIKE '%Finansal Tablolar%'
           OR d.title LIKE '%Mali Tablolar%'
           OR d.title LIKE '%Bilanço%'
           OR d.category = 'FINANSAL_RAPOR')
        AND (f.cash_and_equivalents IS NULL OR f.cash_and_equivalents = 0)
        AND comp.ticker IS NOT NULL
        ORDER BY comp.ticker
        LIMIT 300
    """)
    targets = c.fetchall()
    
    print(f"Hedef: {len(targets)} bildirim")
    print(f"Önceki: {len(progress['scraped'])} çekildi, {len(progress['failed'])} başarısız")
    
    # Filter already scraped
    scraped_set = set(progress['scraped'])
    targets = [t for t in targets 
               if f"{t[0]}_{t[5]}" not in scraped_set]
    
    print(f"Kalan: {len(targets)}")
    
    if not targets:
        print("Tümü tamamlanmış!")
        db.close()
        return
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright kuruluyor...")
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], capture_output=True)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], capture_output=True)
        from playwright.sync_api import sync_playwright
    
    updated = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Stealth: remove webdriver property
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        page = context.new_page()
        
        for i, (ticker, cid, mkk_id, name, disc_id, source_url, db_id) in enumerate(targets):
            key = f"{ticker}_{disc_id}"
            
            try:
                # Use source_url directly if available
                data = scrape_financial_page(page, disc_id)
                
                if 'error' in data:
                    errors += 1
                    progress['failed'].append({'key': key, 'error': data['error'][:100]})
                else:
                    # Update financials table
                    updated_fields = []
                    
                    if 'cash' in data:
                        c.execute("""UPDATE financials SET cash_and_equivalents = ? 
                            WHERE company_id = ? AND cash_and_equivalents IS NULL""",
                            (data['cash'], cid))
                        updated_fields.append('cash')
                    
                    if 'current_assets' in data:
                        c.execute("""UPDATE financials SET current_assets = ? 
                            WHERE company_id = ? AND current_assets IS NULL""",
                            (data['current_assets'], cid))
                        updated_fields.append('current_assets')
                    
                    if 'financial_debt' in data:
                        c.execute("""UPDATE financials SET financial_debt = ? 
                            WHERE company_id = ? AND financial_debt IS NULL""",
                            (data['financial_debt'], cid))
                        updated_fields.append('financial_debt')
                    
                    if 'short_term_debt' in data:
                        c.execute("""UPDATE financials SET short_term_debt = ? 
                            WHERE company_id = ? AND short_term_debt IS NULL OR short_term_debt = 0""",
                            (data['short_term_debt'], cid))
                        updated_fields.append('short_term_debt')
                    
                    if 'long_term_debt' in data:
                        c.execute("""UPDATE financials SET long_term_debt = ? 
                            WHERE company_id = ? AND long_term_debt IS NULL OR long_term_debt = 0""",
                            (data['long_term_debt'], cid))
                        updated_fields.append('long_term_debt')
                    
                    if 'equity' in data:
                        c.execute("""UPDATE financials SET equity = ? 
                            WHERE company_id = ? AND (equity IS NULL OR equity = 0)""",
                            (data['equity'], cid))
                        updated_fields.append('equity')
                    
                    if 'depreciation' in data:
                        c.execute("""UPDATE cash_flows SET depreciation = ? 
                            WHERE company_id = ? AND (depreciation IS NULL OR depreciation = 0)""",
                            (data['depreciation'], cid))
                        updated_fields.append('depreciation')
                    
                    if 'capex' in data:
                        c.execute("""UPDATE cash_flows SET capex = ? 
                            WHERE company_id = ? AND (capex IS NULL OR capex = 0)""",
                            (data['capex'], cid))
                        updated_fields.append('capex')
                    
                    if 'financing_cf' in data:
                        c.execute("""UPDATE cash_flows SET financing_cf = ? 
                            WHERE company_id = ? AND (financing_cf IS NULL OR financing_cf = 0)""",
                            (data['financing_cf'], cid))
                        updated_fields.append('financing_cf')
                    
                    if updated_fields:
                        db.commit()
                        updated += 1
                    
                    progress['scraped'].append(key)
                
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(targets)}] {ticker}: {updated} güncellendi, {errors} hata")
                    save_progress(progress)
                
                # Exponential backoff with jitter
                delay = random.uniform(2.0, 5.0)
                if errors > 0 and errors % 10 == 0:
                    delay = random.uniform(10.0, 20.0)  # Extra cool-down
                time.sleep(delay)
                
            except Exception as e:
                errors += 1
                progress['failed'].append({'key': key, 'error': str(e)[:100]})
                time.sleep(random.uniform(5.0, 10.0))
        
        browser.close()
    
    save_progress(progress)
    db.close()
    
    print(f"\n=== SONUÇ ===")
    print(f"Güncellenen: {updated}, Hata: {errors}")
    print(f"Toplam çekilen: {len(progress['scraped'])}")

if __name__ == '__main__':
    main()
