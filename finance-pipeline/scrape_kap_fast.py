"""
KAP Finansal Veri Hızlı Çekici
Doğru URL map'i kullanarak toplu finansal veri çeker.
"""
import sys, io, sqlite3, time, random, re, os, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
URL_MAP_PATH = str(Path(__file__).parent / 'kap_financial_url_map.json')
PROGRESS_PATH = str(Path(__file__).parent / 'kap_fast_progress.json')

def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, 'r') as f:
            return json.load(f)
    return {'done': [], 'updated': 0}

def save_progress(prog):
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(prog, f)

def parse_value(text, term):
    """Metin içinde terimden sonraki ilk sayıyı bul"""
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
    
    # Load URL map
    with open(URL_MAP_PATH, 'r', encoding='utf-8') as f:
        url_map = json.load(f)
    
    # Get companies that need data
    c.execute("""
        SELECT c.id, c.ticker FROM companies c
        JOIN financials f ON f.company_id = c.id
        WHERE c.ticker IS NOT NULL
        AND (f.current_assets IS NULL OR f.current_assets = 0)
    """)
    need_data = {row[1]: row[0] for row in c.fetchall()}
    
    # Filter to those with URL map
    targets = [(ticker, cid, url_map[ticker]['fin_url']) 
               for ticker, cid in need_data.items() 
               if ticker in url_map and ticker not in progress['done']]
    
    print(f"URL map: {len(url_map)} | Need data: {len(need_data)} | Target: {len(targets)} | Done: {len(progress['done'])}", flush=True)
    
    if not targets:
        print("Tamamlanmış!")
        db.close()
        return
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], capture_output=True)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], capture_output=True)
        from playwright.sync_api import sync_playwright
    
    batch_size = min(200, len(targets))
    batch = targets[:batch_size]
    
    updated = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul'
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()
        
        for i, (ticker, cid, fin_url) in enumerate(batch):
            try:
                page.goto(fin_url, timeout=12000, wait_until='domcontentloaded')
                time.sleep(1.2)
                text = page.inner_text('body')
                
                if 'Dönen Varlıklar' not in text and 'Toplam Varlıklar' not in text:
                    progress['done'].append(ticker)
                    errors += 1
                    continue
                
                # Parse financial data
                fields_map = {
                    'current_assets': ('Dönen Varlıklar', 1000000),
                    'non_current_assets': ('Duran Varlıklar', 1000000),
                    'total_assets': ('Toplam Varlıklar', 1000000),
                    'short_term_debt': ('Kısa Vadeli Yükümlülükler', 1000000),
                    'long_term_debt': ('Uzun Vadeli Yükümlülükler', 1000000),
                    'equity': ('Ana Ortaklığa Ait Özkaynaklar', 1000000),
                    'paid_capital': ('Ödenmiş Sermaye', 1000000),
                    'revenue': ('Hasılat', 1000000),
                    'net_profit': ('Dönem Karı', 1000000),
                    'ebitda': ('FAVÖK', 1000000),
                    'gross_profit': ('Brüt Kar', 1000000),
                }
                
                updates = {}
                for field, (term, multiplier) in fields_map.items():
                    val = parse_value(text, term)
                    if val and val > 0:
                        updates[field] = round(val * multiplier)
                
                if updates:
                    # Get latest financials for this company
                    c.execute("""SELECT id FROM financials 
                        WHERE company_id = ? ORDER BY year DESC, period DESC LIMIT 1""", (cid,))
                    row = c.fetchone()
                    
                    if row:
                        fid = row[0]
                        for field, val in updates.items():
                            try:
                                c.execute(f"UPDATE financials SET {field} = ? WHERE id = ? AND ({field} IS NULL OR {field} = 0)",
                                    (val, fid))
                            except:
                                pass
                        db.commit()
                        updated += 1
                
                progress['done'].append(ticker)
                
            except Exception as e:
                errors += 1
                progress['done'].append(ticker)
            
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(batch)}] ✅{updated} ❌{errors} | Son: {ticker}", flush=True)
                save_progress(progress)
            
            time.sleep(random.uniform(1.0, 2.5))
        
        browser.close()
    
    save_progress(progress)
    db.close()
    
    print(f"\n=== HIZLI ÇEKİM SONUCU ===", flush=True)
    print(f"Güncellenen: {updated}, Hata: {errors}", flush=True)
    print(f"Toplam tamamlanan: {len(progress['done'])}", flush=True)

if __name__ == '__main__':
    main()
