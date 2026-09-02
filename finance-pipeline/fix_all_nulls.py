"""
Tüm null verileri doldur:
1. yfinance -> canlı fiyat, F/K, PD/DD, sektör, P/E, market cap
2. KAP API -> current_assets, cash, financial_debt (mümkünse)
3. Hesaplanan -> net_debt, leverage, marjlar, oranlar
"""
import sys, io, psycopg2, time, random, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

SECTOR_MAP = {
    'Technology': 'Teknoloji', 'Industrials': 'Sanayi',
    'Consumer Cyclical': 'Tüketim', 'Financial Services': 'Finans',
    'Healthcare': 'Sağlık', 'Energy': 'Enerji',
    'Basic Materials': 'Hammaddeler', 'Communication Services': 'İletişim',
    'Consumer Defensive': 'Temel Tüketim', 'Real Estate': 'Gayrimenkul',
    'Utilities': 'Altyapı', 'N/A': None, '': None,
}

def fix_all():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    print("=" * 70)
    print("ADIM 1: yfinance ile Fiyat, F/K, PD/DD, Sektör düzelt")
    print("=" * 70)
    
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance yüklü değil!")
        return
    
    # Aktif şirketleri al
    cur.execute("""
        SELECT id, ticker, company_name 
        FROM kap_companies 
        WHERE is_active = true
        AND ticker NOT LIKE '%-%'
        AND LENGTH(ticker) <= 10
        ORDER BY ticker
    """)
    companies = cur.fetchall()
    print(f"  {len(companies)} şirket işlenecek")
    
    fixed_price = 0
    fixed_sector = 0
    fixed_pe = 0
    errors = 0
    
    for i, (cid, ticker, name) in enumerate(companies):
        try:
            symbol = f"{ticker}.IS"
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # --- FİYAT VE PİYASA DEĞERİ ---
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            market_cap = info.get('marketCap')
            
            if current_price and current_price > 0:
                # bist_stock_prices tablosunu güncelle
                cur.execute("""
                    INSERT INTO bist_stock_prices (ticker, price, market_cap, pe_ratio, pb_ratio, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (ticker) DO UPDATE SET
                        price = EXCLUDED.price,
                        market_cap = EXCLUDED.market_cap,
                        pe_ratio = EXCLUDED.pe_ratio,
                        pb_ratio = EXCLUDED.pb_ratio,
                        updated_at = NOW()
                """, (ticker, current_price, market_cap, 
                      info.get('trailingPE'), info.get('priceToBook')))
                fixed_price += 1
                
                # Kap_financials'taki PE ratio'yu güncelle (en son dönem)
                pe = info.get('trailingPE')
                pb = info.get('priceToBook')
                if pe and pe > 0 and pe < 1000:
                    cur.execute("""
                        UPDATE kap_financials 
                        SET pe_ratio = %s, pb_ratio = %s
                        WHERE company_id = %s 
                        AND pe_ratio IS NULL
                        AND year = (SELECT MAX(year) FROM kap_financials WHERE company_id = %s)
                    """, (pe, pb, cid, cid))
                    fixed_pe += 1
            
            # --- SEKTÖR ---
            sector = info.get('sector', None)
            if sector and sector != 'N/A' and sector != '':
                tr_sector = SECTOR_MAP.get(sector, sector)
                cur.execute("""
                    UPDATE kap_companies 
                    SET sector = %s 
                    WHERE id = %s AND (sector IS NULL OR sector = '' OR sector = 'N/A')
                """, (tr_sector, cid))
                if cur.rowcount > 0:
                    fixed_sector += 1
            
            if (i + 1) % 100 == 0:
                conn.commit()
                print(f"  📊 [{i+1}/{len(companies)}] Fiyat:{fixed_price} Sektör:{fixed_sector} PE:{fixed_pe}")
            
            time.sleep(random.uniform(0.3, 0.8))
            
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ❌ {ticker}: {str(e)[:60]}")
    
    conn.commit()
    print(f"\n  ✅ Fiyat: {fixed_price}, Sektör: {fixed_sector}, PE: {fixed_pe}, Hata: {errors}")
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 2: Eksik finansal alanları hesapla
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("ADIM 2: Eksik finansal alanları hesapla")
    print("=" * 70)
    
    # ROE = net_profit / equity
    cur.execute("""
        UPDATE kap_financials SET roe = ROUND((net_profit::numeric / NULLIF(equity,0) * 100), 2)
        WHERE equity > 0 AND net_profit IS NOT NULL AND (roe IS NULL OR roe = 0)
    """)
    print(f"  ✅ ROE: {cur.rowcount} güncellendi")
    
    # ROA = net_profit / total_assets
    cur.execute("""
        UPDATE kap_financials SET roa = ROUND((net_profit::numeric / NULLIF(total_assets,0) * 100), 4)
        WHERE total_assets > 0 AND net_profit IS NOT NULL AND (roa IS NULL OR roa = 0)
    """)
    print(f"  ✅ ROA: {cur.rowcount} güncellendi")
    
    # gross_margin = gross_profit / revenue
    cur.execute("""
        UPDATE kap_financials SET gross_margin = ROUND((gross_profit::numeric / NULLIF(revenue,0) * 100), 2)
        WHERE revenue > 0 AND gross_profit IS NOT NULL AND (gross_margin IS NULL OR gross_margin = 0)
    """)
    print(f"  ✅ Brüt Marj: {cur.rowcount} güncellendi")
    
    # net_margin = net_profit / revenue
    cur.execute("""
        UPDATE kap_financials SET net_margin = ROUND((net_profit::numeric / NULLIF(revenue,0) * 100), 2)
        WHERE revenue > 0 AND net_profit IS NOT NULL AND (net_margin IS NULL OR net_margin = 0)
    """)
    print(f"  ✅ Net Marj: {cur.rowcount} güncellendi")
    
    # ebitda_margin = ebitda / revenue (sadece makul değerler)
    cur.execute("""
        UPDATE kap_financials SET ebitda_margin = ROUND((ebitda::numeric / NULLIF(revenue,0) * 100), 2)
        WHERE revenue > 0 AND ebitda > 0 AND ebitda < revenue * 10
        AND (ebitda_margin IS NULL OR ebitda_margin = 0 OR ebitda_margin > 1000)
    """)
    print(f"  ✅ EBITDA Marjı: {cur.rowcount} güncellendi")
    
    # leverage = total_debts / total_assets
    cur.execute("""
        UPDATE kap_financials SET leverage_ratio = ROUND((total_debts::numeric / NULLIF(total_assets,0)), 4)
        WHERE total_assets > 0 AND total_debts > 0 AND (leverage_ratio IS NULL OR leverage_ratio = 0)
    """)
    print(f"  ✅ Kaldıraç: {cur.rowcount} güncellendi")
    
    # net_debt = total_debts - cash (eğer cash varsa)
    cur.execute("""
        UPDATE kap_financials SET net_debt = total_debts - COALESCE(cash_and_equivalents, 0)
        WHERE total_debts > 0 AND (net_debt IS NULL)
    """)
    print(f"  ✅ Net Borç: {cur.rowcount} güncellendi")
    
    conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 3: Bozuk değerleri temizle
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("ADIM 3: Bozuk değerleri temizle")
    print("=" * 70)
    
    # F/K > 1M veya < 0 olanları temizle
    cur.execute("UPDATE kap_financials SET pe_ratio = NULL WHERE pe_ratio > 1000000 OR pe_ratio < -100")
    print(f"  ✅ Bozuk F/K: {cur.rowcount} temizlendi")
    
    # EBITDA marjı > 10000 olanları temizle
    cur.execute("UPDATE kap_financials SET ebitda_margin = NULL WHERE ebitda_margin > 10000 OR ebitda_margin < -1000")
    print(f"  ✅ Bozuk EBITDA Marjı: {cur.rowcount} temizlendi")
    
    # Kaldıraç > 100 olanları temizle
    cur.execute("UPDATE kap_financials SET leverage_ratio = NULL WHERE leverage_ratio > 100")
    print(f"  ✅ Bozuk Kaldıraç: {cur.rowcount} temizlendi")
    
    conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # SONUÇ RAPORU
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("SONUÇ RAPORU")
    print("=" * 70)
    
    cur.execute("""
        SELECT 
            count(*) as total,
            sum(case when pe_ratio IS NOT NULL AND pe_ratio > 0 AND pe_ratio < 500 then 1 else 0 end) as pe,
            sum(case when pb_ratio IS NOT NULL AND pb_ratio > 0 then 1 else 0 end) as pb,
            sum(case when roe IS NOT NULL then 1 else 0 end) as roe,
            sum(case when roa IS NOT NULL then 1 else 0 end) as roa,
            sum(case when gross_margin IS NOT NULL then 1 else 0 end) as gm,
            sum(case when net_margin IS NOT NULL then 1 else 0 end) as nm,
            sum(case when ebitda_margin IS NOT NULL AND ebitda_margin < 1000 then 1 else 0 end) as em,
            sum(case when leverage_ratio IS NOT NULL AND leverage_ratio < 100 then 1 else 0 end) as lev
        FROM kap_financials
    """)
    r = cur.fetchone()
    t = r[0]
    print(f"  F/K (0-500 arası):  {r[1]}/{t} ({r[1]/t*100:.0f}%)")
    print(f"  PD/DD:               {r[2]}/{t} ({r[2]/t*100:.0f}%)")
    print(f"  ROE:                 {r[3]}/{t} ({r[3]/t*100:.0f}%)")
    print(f"  ROA:                 {r[4]}/{t} ({r[4]/t*100:.0f}%)")
    print(f"  Brüt Marj:           {r[5]}/{t} ({r[5]/t*100:.0f}%)")
    print(f"  Net Marj:            {r[6]}/{t} ({r[6]/t*100:.0f}%)")
    print(f"  EBITDA Marjı:        {r[7]}/{t} ({r[7]/t*100:.0f}%)")
    print(f"  Kaldıraç:            {r[8]}/{t} ({r[8]/t*100:.0f}%)")
    
    cur.execute("SELECT count(*) FROM bist_stock_prices WHERE price > 0")
    print(f"\n  Güncel fiyat olan: {cur.fetchone()[0]} şirket")
    
    cur.execute("SELECT count(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
    print(f"  Sektörü olan: {cur.fetchone()[0]} şirket")
    
    conn.close()
    print("\n✅ TÜM DÜZELTMELER TAMAMLANDI!")

if __name__ == "__main__":
    fix_all()
