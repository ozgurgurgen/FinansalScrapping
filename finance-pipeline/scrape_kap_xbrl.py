"""
KAP XBRL Detail Scraper
Disclosure sayfalarindan XBRL tag'leri ile cash, financial_debt vb. detay veri ceker.
Resume-able + exponential backoff ile.
"""
import sys, io, sqlite3, time, random, re, os, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
PROGRESS_FILE = str(Path(__file__).parent / 'xbrl_progress.json')

TARGET_TAGS = {
    'ifrs-full_CashAndCashEquivalents': 'cash_and_equivalents',
    'ifrs-full_LongtermBorrowings': 'longterm_borrowings',
    'ifrs-full_CurrentAssets': 'current_assets',
    'ifrs-full_NoncurrentAssets': 'non_current_assets',
    'ifrs-full_Assets': 'total_assets',
    'ifrs-full_CurrentLiabilities': 'current_liabilities',
    'ifrs-full_NoncurrentLiabilities': 'non_current_liabilities',
    'ifrs-full_Liabilities': 'total_liabilities',
    'ifrs-full_Equity': 'equity',
    'ifrs-full_Revenue': 'revenue',
    'ifrs-full_ProfitLoss': 'net_profit',
    'ifrs-full_GrossProfit': 'gross_profit',
    'ifrs-full_AdjustmentsForDepreciationAndAmortisationExpense': 'depreciation',
    'ifrs-full_ProceedsFromBorrowingsClassifiedAsFinancingActivities': 'borrowings_proceeds',
    'ifrs-full_RepaymentsOfBorrowingsClassifiedAsFinancingActivities': 'borrowings_repayments',
    'ifrs-full_DividendsPaid': 'dividends_paid',
}

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'done': [], 'updated': 0, 'errors': 0}

def save_progress(prog):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(prog, f)

def parse_number(text):
    if not text or text.strip() in ['-', '', 'n/a']:
        return None
    val_str = text.strip().replace('.', '').replace(',', '.')
    try:
        val = float(val_str)
        return val if val > 0 else None
    except:
        return None

def scrape_xbrl_page(page, disclosure_id):
    """Tek bir disclosure sayfasindan XBRL verilerini cek"""
    url = f'https://www.kap.org.tr/tr/Bildirim/{disclosure_id}'
    try:
        page.goto(url, timeout=15000, wait_until='domcontentloaded')
        time.sleep(2)
        html = page.content()
        
        results = {}
        for tag, field in TARGET_TAGS.items():
            positions = [m.start() for m in re.finditer(re.escape(tag), html)]
            for pos in positions:
                search_html = html[pos:pos+4000]
                monetary_vals = re.findall(r'class="[^"]*monetary[^"]*"[^>]*>([\d.,]+)<', search_html)
                if monetary_vals:
                    for val_str in reversed(monetary_vals):
                        val = parse_number(val_str)
                        if val and val > 100:
                            results[field] = val
                            break
                    break
        
        # Calculate financial_debt = longterm_borrowings (close enough for now)
        if 'longterm_borrowings' in results:
            results['financial_debt'] = results['longterm_borrowings']
        
        return results
    except Exception as e:
        return {'error': str(e)}

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    progress = load_progress()
    
    # Get financial report disclosures that we haven't scraped yet
    c.execute("""
        SELECT d.disclosure_id, comp.ticker, comp.id as company_id, comp.company_name
        FROM disclosures d
        JOIN companies comp ON d.company_id = comp.id
        WHERE (d.title LIKE '%Finansal Rapor%' OR d.category = 'FINANSAL_RAPOR')
        AND d.disclosure_id IS NOT NULL
        AND comp.ticker IS NOT NULL
        AND d.disclosure_id NOT IN ({})
        ORDER BY d.publish_date DESC
        LIMIT 300
    """.format(','.join(['?'] * len(progress['done']))) if progress['done'] else """
        SELECT d.disclosure_id, comp.ticker, comp.id as company_id, comp.company_name
        FROM disclosures d
        JOIN companies comp ON d.company_id = comp.id
        WHERE (d.title LIKE '%Finansal Rapor%' OR d.category = 'FINANSAL_RAPOR')
        AND d.disclosure_id IS NOT NULL
        AND comp.ticker IS NOT NULL
        ORDER BY d.publish_date DESC
        LIMIT 300
    """, progress['done'] if progress['done'] else [])
    
    targets = c.fetchall()
    print(f"Hedef: {len(targets)} | Onceki: {len(progress['done'])} | Guncellenen: {progress['updated']}", flush=True)
    
    if not targets:
        print("Tamamlandi!", flush=True)
        db.close()
        return
    
    from playwright.sync_api import sync_playwright
    
    updated = 0
    errors = 0
    backoff = 2.0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR', timezone_id='Europe/Istanbul'
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()
        
        for i, (disc_id, ticker, cid, name) in enumerate(targets):
            try:
                result = scrape_xbrl_page(page, disc_id)
                
                if 'error' in result:
                    errors += 1
                    backoff = min(backoff * 1.5, 30.0)
                    if '429' in result['error'] or '403' in result['error']:
                        print(f"  RATE LIMIT! Backoff: {backoff:.1f}s", flush=True)
                        time.sleep(backoff)
                        continue
                else:
                    backoff = 2.0
                    # Update DB
                    updated_fields = []
                    for field, val in result.items():
                        if field in ['cash_and_equivalents', 'financial_debt', 'current_assets', 
                                    'non_current_assets', 'total_assets', 'equity',
                                    'short_term_debt', 'long_term_debt',
                                    'depreciation', 'dividends_paid']:
                            try:
                                c.execute(f"""UPDATE financials SET {field} = ?
                                    WHERE company_id = ? AND ({field} IS NULL OR {field} = 0)
                                    AND year = (SELECT MAX(year) FROM financials WHERE company_id = ?)""",
                                    (val, cid, cid))
                                updated_fields.append(field)
                            except:
                                pass
                    
                    if updated_fields:
                        db.commit()
                        updated += 1
                    
                    progress['done'].append(disc_id)
                
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(targets)}] OK:{updated} ERR:{errors} | {ticker} | {updated_fields[:3] if updated_fields else 'skip'}", flush=True)
                    progress['updated'] = progress.get('updated', 0) + updated
                    progress['errors'] = progress.get('errors', 0) + errors
                    save_progress(progress)
                
                time.sleep(random.uniform(2.0, 5.0))
                
            except Exception as e:
                errors += 1
                progress['done'].append(disc_id)
                time.sleep(random.uniform(3.0, 7.0))
        
        browser.close()
    
    progress['updated'] = progress.get('updated', 0) + updated
    progress['errors'] = progress.get('errors', 0) + errors
    save_progress(progress)
    db.close()
    
    print(f"\n=== XBRL SONUCU === Updated: {updated} | Errors: {errors} | Done: {len(progress['done'])}", flush=True)

if __name__ == '__main__':
    main()
