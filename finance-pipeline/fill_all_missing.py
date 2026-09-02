"""
Tüm eksik finansal verileri tek seferde doldurur:
- current_assets, non_current_assets, total_assets
- short_term_debt, long_term_debt
- equity, paid_capital
- revenue, net_profit, ebitda, gross_profit
- cash_and_equivalents (varsa)
- financial_debt (varsa)

KAP finansal özet sayfalarından (doğru URL map ile) çeker.
"""
import sys, io, sqlite3, time, random, re, os, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
URL_MAP_PATH = str(Path(__file__).parent / 'kap_financial_url_map.json')
PROGRESS_PATH = str(Path(__file__).parent / 'fill_all_progress.json')

def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, 'r') as f:
            return json.load(f)
    return {'done': [], 'updated': 0, 'errors': 0}

def save_progress(prog):
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(prog, f)

def parse_value(text, term):
    if term not in text:
        return None
    idx = text.index(term)
    line = text[idx:idx+300]
    nums = re.findall(r'(\d[\d.]*,\d+|\d[\d.]+)', line)
    if nums:
        val_str = nums[0].replace('.', '').replace(',', '.')
        try:
            val = float(val_str)
            return val if val > 0 else None
        except:
            return None
    return None

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    progress = load_progress()
    
    with open(URL_MAP_PATH, 'r', encoding='utf-8') as f:
        url_map = json.load(f)
    
    # Get ALL companies that need ANY financial data
    c.execute("""
        SELECT c.id, c.ticker, c.company_name FROM companies c
        WHERE c.ticker IS NOT NULL
        AND c.ticker IN ({})
    """.format(','.join(['?'] * len(url_map))), list(url_map.keys()))
    
    all_companies = c.fetchall()
    
    # Filter: only those missing critical fields
    targets = []
    for cid, ticker, name in all_companies:
        if ticker in progress['done']:
            continue
        c.execute("""SELECT current_assets, equity, total_assets FROM financials 
            WHERE company_id = ? ORDER BY year DESC LIMIT 1""", (cid,))
        row = c.fetchone()
        if row and (row[0] is None or row[0] == 0):
            targets.append((cid, ticker, url_map[ticker]['fin_url']))
    
    print(f"TOP: {len(url_map)} url_map | {len(all_companies)} companies | {len(targets)} need data | {len(progress['done'])} done", flush=True)
    
    if not targets:
        print("ALL DONE!", flush=True)
        db.close()
        return
    
    from playwright.sync_api import sync_playwright
    
    batch = targets[:300]  # First 300
    updated = 0
    errors = 0
    
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
        
        for i, (cid, ticker, fin_url) in enumerate(batch):
            try:
                resp = page.goto(fin_url, timeout=10000, wait_until='domcontentloaded')
                time.sleep(1.0)
                text = page.inner_text('body')
                
                has_data = 'Dönen Varlıklar' in text or 'Toplam Varlıklar' in text
                
                if not has_data:
                    progress['done'].append(ticker)
                    errors += 1
                    continue
                
                fields_map = {
                    'current_assets': ('Dönen Varlıklar', 1e6),
                    'non_current_assets': ('Duran Varlıklar', 1e6),
                    'total_assets': ('Toplam Varlıklar', 1e6),
                    'short_term_debt': ('Kısa Vadeli Yükümlülükler', 1e6),
                    'long_term_debt': ('Uzun Vadeli Yükümlülükler', 1e6),
                    'equity': ('Ana Ortaklığa Ait Özkaynaklar', 1e6),
                    'paid_capital': ('Ödenmiş Sermaye', 1e6),
                    'revenue': ('Hasılat', 1e6),
                    'net_profit': ('Dönem Karı', 1e6),
                    'ebitda': ('FAVÖK', 1e6),
                    'gross_profit': ('Brüt Kar', 1e6),
                    'cash_and_equivalents': ('Nakit ve Nakit Benzerleri', 1e6),
                    'financial_debt': ('Finansal Borçlar', 1e6),
                }
                
                updates = {}
                for field, (term, mult) in fields_map.items():
                    val = parse_value(text, term)
                    if val and val > 0:
                        updates[field] = round(val * mult)
                
                if updates:
                    c.execute("""SELECT id FROM financials 
                        WHERE company_id = ? ORDER BY year DESC, period DESC LIMIT 1""", (cid,))
                    row = c.fetchone()
                    if row:
                        fid = row[0]
                        for field, val in updates.items():
                            try:
                                c.execute(f"UPDATE financials SET {field} = ? WHERE id = ? AND ({field} IS NULL OR {field} = 0)",
                                    (val, fid))
                            except Exception as e:
                                pass
                        db.commit()
                        updated += 1
                
                progress['done'].append(ticker)
                
            except Exception as e:
                errors += 1
                progress['done'].append(ticker)
            
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(batch)}] OK:{updated} ERR:{errors} | {ticker} | {', '.join(f'{k}={v//1000000}M' for k,v in list(updates.items())[:3]) if updates else 'no data'}", flush=True)
                progress['updated'] = updated
                progress['errors'] = errors
                save_progress(progress)
            
            time.sleep(random.uniform(1.0, 2.5))
        
        browser.close()
    
    progress['updated'] = updated
    progress['errors'] = errors
    save_progress(progress)
    db.close()
    
    print(f"\n=== FINAL === Updated: {updated} | Errors: {errors} | Done: {len(progress['done'])}", flush=True)

if __name__ == '__main__':
    main()
