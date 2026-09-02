"""
VAP (vap.org.tr) Yabancı Oranı Çekme
Farklı API'leri ve sayfaları deneyerek veri çekmeye çalışır.
"""
import sys, io, sqlite3, time, random, re, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')

def create_vap_table(db):
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS vap_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            ticker TEXT,
            foreign_ratio REAL,
            local_institutional REAL,
            local_individual REAL,
            public_float_pct REAL,
            market_cap REAL,
            free_float_shares REAL,
            total_shares REAL,
            data_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, data_source)
        )
    """)
    db.commit()

def scrape_via_bigpara():
    """Bigpara'dan halka açıklık ve yabancı oranını çek"""
    import requests
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://bigpara.hurriyet.com.tr/'
    })
    
    db = sqlite3.connect(DB_PATH, timeout=10)
    create_vap_table(db)
    c = db.cursor()
    
    # Get companies
    c.execute("""
        SELECT c.id, c.ticker FROM companies c
        INNER JOIN bist_stock_prices b ON c.ticker = b.ticker
        WHERE c.ticker IS NOT NULL
    """)
    companies = c.fetchall()
    
    print(f"VAP verisi çekilecek şirket: {len(companies)}")
    
    updated = 0
    errors = 0
    
    for cid, ticker in companies:
        try:
            # Bigpara hisse detay sayfası
            url = f"https://bigpara.hurriyet.com.tr/borsa/hisse-fiyatlari/{ticker.lower()}/"
            resp = session.get(url, timeout=10)
            
            if resp.status_code != 200:
                continue
            
            html = resp.text
            
            # Halka açıklık oranını ara
            hao = re.search(r'[Hh]alka\s*[Aa]ç[iİı]l[iİı]k\s*[Oo]ran[iİı].*?(\d+[.,]\d+)\s*%', html)
            foreign = re.search(r'[Yy]abanc[iİı].*?(\d+[.,]\d+)\s*%', html)
            
            hao_val = float(hao.group(1).replace(',', '.')) if hao else None
            foreign_val = float(foreign.group(1).replace(',', '.')) if foreign else None
            
            if hao_val or foreign_val:
                c.execute("""
                    INSERT OR REPLACE INTO vap_data 
                    (company_id, ticker, foreign_ratio, public_float_pct, data_source)
                    VALUES (?, ?, ?, ?, 'bigpara')
                """, (cid, ticker, foreign_val, hao_val))
                updated += 1
            
            time.sleep(random.uniform(1.0, 2.5))
            
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Hata {ticker}: {str(e)[:80]}")
            time.sleep(1)
        
        if updated % 20 == 0 and updated > 0:
            print(f"  [{updated} güncellendi] Son: {ticker}")
    
    db.commit()
    
    c.execute("SELECT COUNT(*) FROM vap_data")
    total = c.fetchone()[0]
    print(f"\n=== VAP SONUCU ===")
    print(f"Toplam kayıt: {total}, Bu tur: {updated}, Hata: {errors}")
    
    db.close()
    return updated

def scrape_via_yfinance():
    """YFinance ile free float ve yabancı oranı çek"""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance yok")
        return 0
    
    db = sqlite3.connect(DB_PATH, timeout=10)
    create_vap_table(db)
    c = db.cursor()
    
    # Get companies without vap_data
    c.execute("""
        SELECT c.id, c.ticker FROM companies c
        INNER JOIN bist_stock_prices b ON c.ticker = b.ticker
        LEFT JOIN vap_data v ON c.ticker = v.ticker
        WHERE v.id IS NULL AND c.ticker IS NOT NULL
        LIMIT 200
    """)
    companies = c.fetchall()
    
    if not companies:
        print("Tüm şirketlerde VAP verisi var")
        db.close()
        return 0
    
    print(f"YFinance ile çekilecek: {len(companies)}")
    
    updated = 0
    for cid, ticker in companies:
        try:
            stock = yf.Ticker(f"{ticker}.IS")
            info = stock.info
            
            shares = info.get('sharesOutstanding')
            float_pct = info.get('floatPercent')
            mcap = info.get('marketCap')
            
            if float_pct or shares:
                c.execute("""
                    INSERT OR REPLACE INTO vap_data 
                    (company_id, ticker, public_float_pct, free_float_shares, market_cap, data_source)
                    VALUES (?, ?, ?, ?, ?, 'yfinance')
                """, (cid, ticker, float_pct, shares, mcap))
                updated += 1
            
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            time.sleep(1)
        
        if updated % 20 == 0 and updated > 0:
            print(f"  [{updated} güncellendi]")
    
    db.commit()
    db.close()
    print(f"YFinance ile {updated} şirket güncellendi")
    return updated

if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'bigpara'
    
    if mode == 'bigpara':
        scrape_via_bigpara()
    elif mode == 'yfinance':
        scrape_via_yfinance()
    elif mode == 'all':
        scrape_via_bigpara()
        scrape_via_yfinance()
