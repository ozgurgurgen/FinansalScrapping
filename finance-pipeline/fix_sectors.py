"""
Sektör verisini yfinance ile tamamla.
73/1014 olan sektör atamasını 500+ şirkete çıkar.
"""
import sys, io, psycopg2, time, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

# Sektör mapping - yfinance sector -> Türkçe sektör
SECTOR_MAP = {
    'Technology': 'Teknoloji',
    'Industrials': 'Sanayi',
    'Consumer Cyclical': 'Tüketim',
    'Financial Services': 'Finans',
    'Healthcare': 'Sağlık',
    'Energy': 'Enerji',
    'Basic Materials': 'Hammaddeler',
    'Communication Services': 'İletişim',
    'Consumer Defensive': 'Temel Tüketim',
    'Real Estate': 'Gayrimenkul',
    'Utilities': 'Altyapı',
    'N/A': None,
    '': None,
}

def fix_sectors():
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance yüklü değil: pip install yfinance")
        return
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Sektörü olmayan şirketleri bul
    cur.execute("""
        SELECT id, ticker, company_name 
        FROM kap_companies 
        WHERE (sector IS NULL OR sector = '' OR sector = 'N/A')
        AND ticker NOT LIKE '%-%'
        AND LENGTH(ticker) <= 10
        ORDER BY ticker
        LIMIT 600
    """)
    companies = cur.fetchall()
    print(f"Sektörü olmayan {len(companies)} şirket bulundu")
    
    fixed = 0
    errors = 0
    
    for i, (cid, ticker, name) in enumerate(companies):
        try:
            # Yahoo Finance'da BIST hisseleri .IS uzantısı ile aranır
            symbol = f"{ticker}.IS"
            stock = yf.Ticker(symbol)
            info = stock.info
            
            sector = info.get('sector', None)
            industry = info.get('industry', None)
            
            if sector and sector != 'N/A':
                tr_sector = SECTOR_MAP.get(sector, sector)
                cur.execute("""
                    UPDATE kap_companies 
                    SET sector = %s 
                    WHERE id = %s AND (sector IS NULL OR sector = '' OR sector = 'N/A')
                """, (tr_sector, cid))
                fixed += 1
                print(f"  ✅ [{i+1}/{len(companies)}] {ticker}: {tr_sector} ({industry or ''})")
            else:
                errors += 1
            
            # Rate limit
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            errors += 1
            if i < 5:
                print(f"  ❌ {ticker}: {str(e)[:50]}")
        
        # Her 50 şirkette commit
        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  📊 İlerleme: {i+1}/{len(companies)} — {fixed} düzeltildi")
    
    conn.commit()
    
    # Sonuç
    cur.execute("SELECT count(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != '' AND sector != 'N/A'")
    total_with_sector = cur.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"SONUÇ: {fixed} şirketin sektörü güncellendi")
    print(f"Toplam sektörü olan: {total_with_sector}/1,014")
    print(f"Hata: {errors}")
    print(f"{'='*60}")
    
    conn.close()

if __name__ == "__main__":
    fix_sectors()
