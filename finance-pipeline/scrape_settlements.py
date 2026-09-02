"""
KAP Settlement (Takas) Verisi Çekme
KAP'taki takas bilgilerini Playwright ile çeker.
"""
import sys, io, sqlite3, time, random, json, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')

def get_companies(db):
    c = db.cursor()
    # Get companies with bist prices (most important ones)
    c.execute("""
        SELECT c.id, c.ticker, c.company_name, c.mkk_id
        FROM companies c
        INNER JOIN bist_stock_prices b ON c.ticker = b.ticker
        WHERE c.mkk_id IS NOT NULL AND c.mkk_id != ''
        ORDER BY b.volume DESC
        LIMIT 200
    """)
    return c.fetchall()

def create_settlement_table(db):
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            ticker TEXT,
            date TEXT,
            foreign_ratio REAL,
            local_ratio REAL,
            common_ratio REAL,
            total_shares REAL,
            foreign_shares REAL,
            local_shares REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, date)
        )
    """)
    db.commit()

def scrape_settlements_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright yok, kuruluyor...")
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], capture_output=True)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], capture_output=True)
        from playwright.sync_api import sync_playwright
    
    db = sqlite3.connect(DB_PATH, timeout=10)
    create_settlement_table(db)
    companies = get_companies(db)
    
    print(f"Settlement çekilecek şirket: {len(companies)}")
    
    updated = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR'
        )
        page = context.new_page()
        
        for i, (cid, ticker, name, mkk_id) in enumerate(companies):
            try:
                # KAP takas sayfası - genel bilgi sayfasından
                url = f"https://www.kap.org.tr/tr/sirket-bilgileri/ozet/{mkk_id}-{name.lower().replace(' ', '-').replace('ı','i').replace('ö','o').replace('ü','u').replace('ş','s').replace('ç','c').replace('ğ','g')}"
                
                # Basit URL dene (slug olmadan)
                url = f"https://www.kap.org.tr/tr/sirket-bilgileri/ozet/{mkk_id}"
                
                page.goto(url, timeout=15000, wait_until='domcontentloaded')
                time.sleep(1.5)
                
                # Sayfa içeriğini al
                content = page.content()
                
                # Halka açıklık oranını ara
                # KAP'ta "Halka Açıklık Oranı" tablosunda foreign/local/common ratio var
                text = page.inner_text('body')
                
                foreign_ratio = None
                local_ratio = None
                common_ratio = None
                
                # Parse patterns
                # "Yabancı: %23.45" veya "Yabancı Oranı: 23.45"
                patterns = [
                    (r'[Yy]abanc[iİı]\s*[:\s]*(\d+[.,]\d+)\s*%', 'foreign'),
                    (r'[Y]erli\s*[:\s]*(\d+[.,]\d+)\s*%', 'local'),
                    (r'[Oo]rtak\s*[:\s]*(\d+[.,]\d+)\s*%', 'common'),
                    (r'Halka.*?[Aa]ç[iİı]l[iİı]k.*?(\d+[.,]\d+)\s*%', 'foreign'),
                ]
                
                for pat, typ in patterns:
                    m = re.search(pat, text)
                    if m:
                        val = float(m.group(1).replace(',', '.'))
                        if typ == 'foreign': foreign_ratio = val
                        elif typ == 'local': local_ratio = val
                        elif typ == 'common': common_ratio = val
                
                # Also try to find from structured data
                # KAP often shows: "Niteliği: Borsada İşlem Gören", "Halka Açıklık Oranı(%): 45.67"
                hao_match = re.search(r'[Hh]alka\s*[Aa]ç[iİı]l[iİı]k\s*[Oo]ran[iİı]\s*\(%?\)\s*[:\s]*(\d+[.,]\d+)', text)
                if hao_match and foreign_ratio is None:
                    foreign_ratio = float(hao_match.group(1).replace(',', '.'))
                
                if foreign_ratio or local_ratio:
                    today = time.strftime('%Y-%m-%d')
                    try:
                        c = db.cursor()
                        c.execute("""
                            INSERT OR REPLACE INTO settlements 
                            (company_id, ticker, date, foreign_ratio, local_ratio, common_ratio)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (cid, ticker, today, foreign_ratio, local_ratio, common_ratio))
                        db.commit()
                        updated += 1
                    except Exception as e:
                        print(f"  DB yazma hatası {ticker}: {e}")
                
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(companies)}] {ticker}: foreign={foreign_ratio}, local={local_ratio}")
                
                time.sleep(random.uniform(2.0, 4.0))
                
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Hata {ticker}: {str(e)[:80]}")
                time.sleep(2)
        
        browser.close()
    
    db.close()
    print(f"\n=== SETTLEMENT SONUCU ===")
    print(f"Güncellenen: {updated}, Hata: {errors}")
    return updated

if __name__ == '__main__':
    scrape_settlements_playwright()
