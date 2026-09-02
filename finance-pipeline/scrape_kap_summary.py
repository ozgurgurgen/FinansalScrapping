"""
KAP Finansal Özet Sayfa Scraper - Hızlı Toplu Çekim
KAP'ın /tr/sirket-finansal-bilgileri/{mkk_id}-{slug} sayfalarından
finansal verileri çekip financials tablosunu günceller.
"""
import sys, io, sqlite3, time, random, re, os, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = str(Path(__file__).parent / 'finance.db')
PROGRESS_FILE = str(Path(__file__).parent / 'kap_summary_progress.json')

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'done': [], 'failed': []}

def save_progress(prog):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(prog, f)

def make_slug(name):
    """Şirket isminden URL slug oluştur"""
    if not name:
        return ''
    slug = name.lower()
    tr_map = {'ı':'i','ö':'o','ü':'u','ş':'s','ç':'c','ğ':'g','İ':'i','I':'i'}
    for k, v in tr_map.items():
        slug = slug.replace(k, v)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug

def parse_value(text, term):
    """Metin içinde terimden sonraki değeri bul"""
    if term not in text:
        return None
    idx = text.index(term)
    line = text[idx:idx+300]
    # Sayıları bul
    nums = re.findall(r'(\d[\d.]*,\d+|\d[\d.]+)', line)
    if nums:
        val_str = nums[0].replace('.', '').replace(',', '.')
        try:
            val = float(val_str)
            return val if val > 0 else None
        except:
            return None
    return None

def scrape_batch(companies, page, db):
    """Bir grup şirketi çek"""
    c = db.cursor()
    updated = 0
    failed = 0
    
    for cid, ticker, mkk_id, name in companies:
        slug = make_slug(name)
        
        urls = [
            f'https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{mkk_id}-{slug}',
            f'https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{mkk_id}',
        ]
        
        for url in urls:
            try:
                page.goto(url, timeout=12000, wait_until='domcontentloaded')
                time.sleep(1.5)
                text = page.inner_text('body')
                
                if 'Dönen Varlıklar' not in text and 'Toplam Varlıklar' not in text:
                    continue
                
                # Parse values (in Milyon TL, multiply by 1,000,000 for actual TL)
                fields = {
                    'current_assets': 'Dönen Varlıklar',
                    'non_current_assets': 'Duran Varlıklar',
                    'total_assets': 'Toplam Varlıklar',
                    'short_term_debt': 'Kısa Vadeli Yükümlülükler',
                    'long_term_debt': 'Uzun Vadeli Yükümlülükler',
                }
                
                updates = {}
                for field, term in fields.items():
                    val = parse_value(text, term)
                    if val:
                        updates[field] = val * 1000000  # Milyon TL → TL
                
                # Equity
                eq_val = parse_value(text, 'Ana Ortaklığa Ait Özkaynaklar')
                if eq_val:
                    updates['equity'] = eq_val * 1000000
                
                # Paid capital
                pc_val = parse_value(text, 'Ödenmiş Sermaye')
                if pc_val:
                    updates['paid_capital'] = pc_val * 1000000
                
                # Revenue
                rev_val = parse_value(text, 'Hasılat')
                if rev_val:
                    updates['revenue'] = rev_val * 1000000
                
                # Net profit
                np_val = parse_value(text, 'Dönem Karı')
                if np_val:
                    updates['net_profit'] = np_val * 1000000
                
                # EBITDA
                ebitda_val = parse_value(text, 'FAVÖK') or parse_value(text, 'EBITDA')
                if ebitda_val:
                    updates['ebitda'] = ebitda_val * 1000000
                
                if updates:
                    # Update latest financials for this company
                    for field, val in updates.items():
                        c.execute(f"""UPDATE financials SET {field} = ?
                            WHERE company_id = ? 
                            AND ({field} IS NULL OR {field} = 0)
                            AND year = (SELECT MAX(year) FROM financials WHERE company_id = ?)""",
                            (val, cid, cid))
                    db.commit()
                    updated += 1
                    return True, ticker, updates
                
                return False, ticker, {}
                
            except Exception as e:
                continue
        
        failed += 1
        return False, ticker, {'error': 'all URLs failed'}
    
    return updated > 0, 'batch', {}

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    progress = load_progress()
    
    # Get companies that need financial data
    c.execute("""
        SELECT DISTINCT c.id, c.ticker, c.mkk_id, c.company_name
        FROM companies c
        JOIN financials f ON f.company_id = c.id
        WHERE c.mkk_id IS NOT NULL AND c.mkk_id != ''
        AND c.ticker IS NOT NULL
        AND (f.current_assets IS NULL OR f.current_assets = 0)
        ORDER BY c.ticker
    """)
    all_companies = c.fetchall()
    
    # Filter done
    done_set = set(progress['done'])
    remaining = [(cid, t, m, n) for cid, t, m, n in all_companies if t not in done_set]
    
    print(f"Toplam: {len(all_companies)}, Kalan: {len(remaining)}, Tamamlanan: {len(progress['done'])}")
    
    if not remaining:
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
    
    batch_size = 100
    batch = remaining[:batch_size]
    
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
            timezone_id='Europe/Istanbul'
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()
        
        for i, (cid, ticker, mkk_id, name) in enumerate(batch):
            slug = make_slug(name)
            
            urls = [
                f'https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{mkk_id}-{slug}',
                f'https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{mkk_id}',
            ]
            
            success = False
            for url in urls:
                try:
                    page.goto(url, timeout=12000, wait_until='domcontentloaded')
                    time.sleep(1.2)
                    text = page.inner_text('body')
                    
                    if 'Dönen Varlıklar' not in text and 'Toplam Varlıklar' not in text:
                        continue
                    
                    # Parse
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
                    }
                    
                    updates = {}
                    for field, (term, multiplier) in fields_map.items():
                        val = parse_value(text, term)
                        if val and val > 0:
                            updates[field] = round(val * multiplier)
                    
                    if updates:
                        # Update latest period only
                        c.execute("""SELECT id, year, period FROM financials 
                            WHERE company_id = ? ORDER BY year DESC, period DESC LIMIT 1""", (cid,))
                        latest = c.fetchone()
                        
                        if latest:
                            for field, val in updates.items():
                                try:
                                    c.execute(f"UPDATE financials SET {field} = ? WHERE id = ? AND ({field} IS NULL OR {field} = 0)",
                                        (val, latest[0]))
                                except:
                                    pass
                            db.commit()
                            updated += 1
                    
                    success = True
                    progress['done'].append(ticker)
                    break
                    
                except Exception as e:
                    continue
            
            if not success:
                errors += 1
                progress['failed'].append(ticker)
            
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(batch)}] ✅{updated} ❌{errors} Son: {ticker}")
                save_progress(progress)
            
            # Anti-ban delay
            time.sleep(random.uniform(1.5, 3.5))
        
        browser.close()
    
    save_progress(progress)
    db.close()
    
    print(f"\n=== SONUÇ ===")
    print(f"Güncellenen: {updated}, Hata: {errors}")
    print(f"Toplam tamamlanan: {len(progress['done'])}")

if __name__ == '__main__':
    main()
