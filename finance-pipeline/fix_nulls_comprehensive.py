"""
Kapsamlı Null Veri Düzeltme Scripti
Tüm null alanları tek tek doldurur:
1. Marj hesaplama (mevcut verilerden)
2. PE ratio (bist_stock_prices'dan)
3. Sektör (yfinance ile)
4. current_assets/cash/financial_debt (yfinance ile)
"""
import psycopg2
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def fix_margins(conn):
    """Mevcut revenue/gross_profit/ebitda/net_profit verilerinden marj hesapla"""
    c = conn.cursor()
    
    # gross_margin = gross_profit / revenue (eğer revenue > 0)
    c.execute("""
        UPDATE kap_financials 
        SET gross_margin = ROUND((gross_profit::numeric / NULLIF(revenue, 0) * 100), 2)
        WHERE gross_margin IS NULL 
        AND revenue > 0 
        AND gross_profit IS NOT NULL
        AND gross_profit > 0
    """)
    print(f"  gross_margin: {c.rowcount} güncellendi")
    
    # ebitda_margin = ebitda / revenue
    c.execute("""
        UPDATE kap_financials 
        SET ebitda_margin = ROUND((ebitda::numeric / NULLIF(revenue, 0) * 100), 2)
        WHERE ebitda_margin IS NULL 
        AND revenue > 0 
        AND ebitda IS NOT NULL
        AND ebitda > 0
    """)
    print(f"  ebitda_margin: {c.rowcount} güncellendi")
    
    # net_margin = net_profit / revenue
    c.execute("""
        UPDATE kap_financials 
        SET net_margin = ROUND((net_profit::numeric / NULLIF(revenue, 0) * 100), 2)
        WHERE net_margin IS NULL 
        AND revenue > 0 
        AND net_profit IS NOT NULL
    """)
    print(f"  net_margin: {c.rowcount} güncellendi")
    
    conn.commit()

def fix_pe_from_prices(conn):
    """bist_stock_prices'daki price ile PE ratio hesapla"""
    c = conn.cursor()
    
    # bist_stock_prices'dan mevcut PE/PB ratio'ları kap_financials'a aktar
    c.execute("""
        UPDATE kap_financials f
        SET pe_ratio = ROUND(bsp.pe_ratio::numeric, 2)
        FROM bist_stock_prices bsp
        JOIN kap_companies kc ON kc.ticker = bsp.ticker
        WHERE f.company_id = kc.id
        AND (f.pe_ratio IS NULL OR f.pe_ratio = 0 OR f.pe_ratio > 1000000)
        AND bsp.pe_ratio > 0 AND bsp.pe_ratio < 10000
        AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id)
    """)
    print(f"  PE ratio (from bist_stock_prices): {c.rowcount} güncellendi")
    
    # PB ratio da aynı şekilde
    c.execute("""
        UPDATE kap_financials f
        SET pb_ratio = ROUND(bsp.pb_ratio::numeric, 2)
        FROM bist_stock_prices bsp
        JOIN kap_companies kc ON kc.ticker = bsp.ticker
        WHERE f.company_id = kc.id
        AND (f.pb_ratio IS NULL OR f.pb_ratio = 0)
        AND bsp.pb_ratio > 0 AND bsp.pb_ratio < 1000
        AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id)
    """)
    print(f"  PB ratio (from bist_stock_prices): {c.rowcount} güncellendi")
    
    # EV/EBITDA hesapla: market_cap / ebitda
    c.execute("""
        UPDATE kap_financials f
        SET ev_ebitda = ROUND(bsp.market_cap::numeric / NULLIF(f.ebitda, 0), 2)
        FROM bist_stock_prices bsp
        JOIN kap_companies kc ON kc.ticker = bsp.ticker
        WHERE f.company_id = kc.id
        AND (f.ev_ebitda IS NULL OR f.ev_ebitda = 0)
        AND bsp.market_cap > 0 AND f.ebitda > 0
        AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id)
    """)
    print(f"  EV/EBITDA: {c.rowcount} güncellendi")
    
    # EV/Revenue hesapla: market_cap / revenue
    c.execute("""
        UPDATE kap_financials f
        SET ev_revenue = ROUND(bsp.market_cap::numeric / NULLIF(f.revenue, 0), 2)
        FROM bist_stock_prices bsp
        JOIN kap_companies kc ON kc.ticker = bsp.ticker
        WHERE f.company_id = kc.id
        AND (f.ev_revenue IS NULL OR f.ev_revenue = 0)
        AND bsp.market_cap > 0 AND f.revenue > 0
        AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id)
    """)
    print(f"  EV/Revenue: {c.rowcount} güncellendi")
    
    conn.commit()

def fix_remaining_sectors(conn, batch_size=10):
    """yfinance ile sektör eksiklerini tamamla"""
    c = conn.cursor()
    
    c.execute("""
        SELECT kc.ticker FROM kap_companies kc
        WHERE (kc.sector IS NULL OR kc.sector = '' OR kc.sector = 'Other')
        AND EXISTS (SELECT 1 FROM kap_financials kf WHERE kf.company_id = kc.id)
        LIMIT %s
    """, (batch_size,))
    tickers = [r[0] for r in c.fetchall()]
    
    if not tickers:
        print("  Sektör eksik yok!")
        return
    
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance yok, atlanıyor")
        return
    
    fixed = 0
    for ticker in tickers:
        try:
            t = yf.Ticker(f"{ticker}.IS")
            info = t.info
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            if sector and sector not in ('Other', 'N/A', ''):
                c.execute("UPDATE kap_companies SET sector=%s WHERE ticker=%s", (sector, ticker))
                fixed += 1
                if industry:
                    c.execute("UPDATE kap_companies SET industry=%s WHERE ticker=%s", (industry, ticker))
            conn.commit()
            time.sleep(0.5)
        except Exception as e:
            pass
    
    print(f"  Sektör: {fixed}/{len(tickers)} güncellendi")

def fix_balance_sheet_yfinance(conn, batch_size=20):
    """yfinance balance sheet ile current_assets, cash, debt doldur"""
    c = conn.cursor()
    
    # Sadece null olan şirketleri al
    c.execute("""
        SELECT DISTINCT kc.ticker, kc.id 
        FROM kap_companies kc
        JOIN kap_financials kf ON kf.company_id = kc.id
        WHERE kf.current_assets IS NULL 
        AND kf.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = kc.id)
        LIMIT %s
    """, (batch_size,))
    companies = c.fetchall()
    
    if not companies:
        print("  Balance sheet eksik yok!")
        return
    
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance yok")
        return
    
    fixed = 0
    for ticker, company_id in companies:
        try:
            t = yf.Ticker(f"{ticker}.IS")
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                # En son sütun
                latest = bs.iloc[:, 0]
                
                # Current Assets
                ca = latest.get('Current Assets', latest.get('Total Current Assets'))
                if ca and ca > 0:
                    c.execute("""
                        UPDATE kap_financials SET current_assets = %s 
                        WHERE company_id = %s AND current_assets IS NULL
                    """, (int(ca), company_id))
                    fixed += 1
                
                # Cash
                cash = latest.get('Cash And Cash Equivalents', latest.get('Cash'))
                if cash and cash > 0:
                    c.execute("""
                        UPDATE kap_financials SET cash_and_equivalents = %s 
                        WHERE company_id = %s AND cash_and_equivalents IS NULL
                    """, (int(cash), company_id))
                
                # Total Debt
                td = latest.get('Total Debt', latest.get('Long Term Debt', 0))
                if td and td > 0:
                    c.execute("""
                        UPDATE kap_financials SET financial_debt = %s, total_debt = %s
                        WHERE company_id = %s AND financial_debt IS NULL
                    """, (int(td), int(td), company_id))
                
                # Net Debt
                if cash and td:
                    nd = td - cash
                    c.execute("""
                        UPDATE kap_financials SET net_debt = %s
                        WHERE company_id = %s AND (net_debt IS NULL OR net_debt = 0)
                    """, (int(nd), company_id))
                
                # Total Assets (eğer null ise)
                ta = latest.get('Total Assets')
                if ta and ta > 0:
                    c.execute("""
                        UPDATE kap_financials SET total_assets = %s 
                        WHERE company_id = %s AND total_assets IS NULL
                    """, (int(ta), company_id))
                
                # Equity
                eq = latest.get('Stockholders Equity', latest.get('Total Stockholder Equity', latest.get('Common Stock Equity')))
                if eq and eq > 0:
                    c.execute("""
                        UPDATE kap_financials SET equity = %s 
                        WHERE company_id = %s AND (equity IS NULL OR equity = 0)
                    """, (int(eq), company_id))
                    
            conn.commit()
            time.sleep(0.3)
        except Exception as e:
            pass
    
    print(f"  Balance sheet: {fixed}/{len(companies)} güncellendi")

def fix_cashflow_details(conn):
    """Mevcut cashflow verilerinden eksik alanları hesapla"""
    c = conn.cursor()
    
    # net_change = operating + investing + financing (eğer ikisi doluysa)
    c.execute("""
        UPDATE kap_cashflows 
        SET net_change = COALESCE(operating_cash_flow, 0) + COALESCE(investing_cash_flow, 0)
        WHERE net_change IS NULL 
        AND operating_cash_flow IS NOT NULL 
        AND investing_cash_flow IS NOT NULL
        AND financing_cash_flow IS NULL
    """)
    print(f"  cashflow net_change: {c.rowcount} güncellendi")
    conn.commit()

def fix_old_company_ids(conn):
    """Eski tablolardaki company_id'leri kap_companies ID'leriyle eslestir"""
    c = conn.cursor()
    
    # companies tablosuyla eslesme
    c.execute("""
        UPDATE shareholders s
        SET company_id = k.id
        FROM companies o, kap_companies k
        WHERE s.company_id = o.id AND o.ticker = k.ticker AND s.company_id != k.id
    """)
    print(f"  shareholders ID remap: {c.rowcount}")
    
    c.execute("""
        UPDATE management_members m
        SET company_id = k.id
        FROM companies o, kap_companies k
        WHERE m.company_id = o.id AND o.ticker = k.ticker AND m.company_id != k.id
    """)
    print(f"  management ID remap: {c.rowcount}")
    
    c.execute("""
        UPDATE subsidiaries s
        SET company_id = k.id
        FROM companies o, kap_companies k
        WHERE s.company_id = o.id AND o.ticker = k.ticker AND s.company_id != k.id
    """)
    print(f"  subsidiaries ID remap: {c.rowcount}")
    
    # disclosure_details ticker eslestir (bos olanlari disclosure_index uzerinden)
    c.execute("""
        UPDATE disclosure_details dd
        SET ticker = k.ticker
        FROM kap_disclosures kd, kap_companies k
        WHERE dd.disclosure_index = kd.disclosure_id
        AND kd.company_id = k.id
        AND (dd.ticker IS NULL OR dd.ticker = '')
    """)
    print(f"  disclosure_details ticker fix: {c.rowcount}")
    
    conn.commit()

def recalculate_leverage(conn):
    """Kaldıraç oranını düzelt: leverage = total_debt / equity"""
    c = conn.cursor()
    c.execute("""
        UPDATE kap_financials 
        SET leverage_ratio = ROUND(total_debts::numeric / NULLIF(equity, 0), 4)
        WHERE (leverage_ratio IS NULL OR leverage_ratio = 0)
        AND total_debts > 0 AND equity > 0
    """)
    print(f"  leverage_ratio: {c.rowcount} güncellendi")
    conn.commit()

def main():
    conn = psycopg2.connect(DB_URL)
    
    print("=" * 60)
    print("NULL VERI DUZELTME BASLATILIYOR")
    print("=" * 60)
    
    # 1. Company ID eslestirme (hizli)
    print("\n1. COMPANY ID ESLESTIRME...")
    fix_old_company_ids(conn)
    
    # 2. Marj hesaplama (hizli)
    print("\n2. MARJ HESAPLAMA...")
    fix_margins(conn)
    
    # 3. Kaldiraç duzeltme (hizli)
    print("\n3. KALDIRAC DUZELTME...")
    recalculate_leverage(conn)
    
    # 4. PE/PB/EV ratio (hizli)
    print("\n4. PE/PB/EV RATIO...")
    fix_pe_from_prices(conn)
    
    # 5. Cashflow detaylari (hizli)
    print("\n5. CASHFLOW DETAYLARI...")
    fix_cashflow_details(conn)
    
    # 6. Sektör (yfinance - yavas)
    print("\n6. SEKTOR DUZELTME (yfinance)...")
    for _ in range(10):
        fix_remaining_sectors(conn, batch_size=10)
    
    # 7. Balance sheet (yfinance - yavas)
    print("\n7. BALANCE SHEET (yfinance)...")
    for _ in range(20):
        fix_balance_sheet_yfinance(conn, batch_size=20)
    
    # Final durum
    print("\n" + "=" * 60)
    print("FINAL DURUM")
    print("=" * 60)
    c = conn.cursor()
    c.execute("""
        SELECT 
          COUNT(*) FILTER (WHERE current_assets IS NULL) as ca,
          COUNT(*) FILTER (WHERE cash_and_equivalents IS NULL) as cash,
          COUNT(*) FILTER (WHERE financial_debt IS NULL) as fd,
          COUNT(*) FILTER (WHERE pe_ratio IS NULL OR pe_ratio = 0) as pe,
          COUNT(*) FILTER (WHERE gross_margin IS NULL) as gm,
          COUNT(*) FILTER (WHERE ebitda_margin IS NULL) as em,
          COUNT(*) FILTER (WHERE net_margin IS NULL) as nm,
          COUNT(*)
        FROM kap_financials
    """)
    ov = c.fetchone()
    cols = ['current_assets','cash','f_debt','PE','gross_margin','ebitda_margin','net_margin']
    for i, c2 in enumerate(cols):
        pct = 100 - (100 * ov[i] / ov[7])
        print(f"  {c2}: {ov[7]-ov[i]}/{ov[7]} dolu (%{pct:.0f})")
    
    c.execute("SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
    s1 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kap_companies")
    s2 = c.fetchone()[0]
    print(f"  sector: {s1}/{s2} dolu (%{100*s1//s2})")
    
    conn.close()
    print("\nTAMAMLANDI!")

if __name__ == '__main__':
    main()
