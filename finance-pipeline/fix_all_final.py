"""
TUM EKSIK VERILERI TAMAMLA
1. Disclosure batch API - tum sirketler icin bildirimleri cek
2. yfinance - cashflow detaylari (depreciation, capex, financing)
3. yfinance - balance sheet (kalan bos kayitlar)
4. yfinance - market data (volume, week52, dividend)
5. Revenue fix - bos revenue'lari yfinance'dan cek
"""
import psycopg2
import requests
import time
import random
import sys
import io
import json
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def create_kap_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        ]),
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://kap.org.tr',
        'Origin': 'https://kap.org.tr'
    })
    return s

def parse_kap_date(date_str):
    if not date_str:
        return None
    try:
        if '.' in str(date_str) and len(str(date_str)) > 10:
            dt = datetime.strptime(str(date_str), '%d.%m.%Y %H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif '.' in str(date_str):
            dt = datetime.strptime(str(date_str), '%d.%m.%Y')
            return dt.strftime('%Y-%m-%d')
        return str(date_str)[:19]
    except:
        return str(date_str)[:10]

def fix_disclosures(conn):
    """Disclosure batch API ile tum sirketler icin bildirimleri cek"""
    c = conn.cursor()
    print("\n[1] DISCLOSURE BATCH SCRAPE...")
    
    session = create_kap_session()
    
    # Her yil icin ay ay cek (2020-2026)
    total_saved = 0
    
    # Company ticker -> id mapping
    c.execute("SELECT ticker, id FROM kap_companies")
    ticker_map = {r[0].upper(): r[1] for r in c.fetchall()}
    
    for year in range(2023, 2027):
        for month in range(1, 13):
            try:
                from_date = f'{year}-{month:02d}-01'
                to_date = f'{year}-{month:02d}-28' if month == 2 else f'{year}-{month:02d}-30'
                if month == 12:
                    to_date = f'{year}-12-31'
                
                r = session.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
                    json={'fromDate': from_date, 'toDate': to_date},
                    timeout=15)
                
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        saved = 0
                        for disc in data:
                            stocks = (disc.get('relatedStocks', '') or '').upper()
                            if not stocks:
                                continue
                            title = disc.get('kapTitle', '') or disc.get('summary', '')
                            pub_date = parse_kap_date(disc.get('publishDate', ''))
                            cat = disc.get('disclosureClass', '') or disc.get('disclosureType', '')
                            
                            for ticker in stocks.split(','):
                                ticker = ticker.strip()
                                if ticker in ticker_map:
                                    company_id = ticker_map[ticker]
                                    c.execute("""INSERT INTO kap_disclosures 
                                        (company_id, symbol, title, category, publish_date)
                                        SELECT %s, %s, %s, %s, %s
                                        WHERE NOT EXISTS (
                                            SELECT 1 FROM kap_disclosures 
                                            WHERE company_id=%s AND title=%s
                                        )""",
                                        (company_id, ticker, title, cat, pub_date,
                                         company_id, title))
                                    if c.rowcount > 0:
                                        saved += 1
                        
                        total_saved += saved
                        if saved > 0:
                            print(f"  {year}-{month:02d}: {len(data)} toplam, {saved} yeni")
                        conn.commit()
                
                time.sleep(random.uniform(1.5, 3.0))
                
                # Cooldown her 10 istekte
                if (year - 2023) * 12 + month % 10 == 0:
                    print(f"  [Cooldown] 15sn...")
                    time.sleep(15)
                    
            except Exception as e:
                if 'current transaction' in str(e):
                    conn.rollback()
    
    print(f"  Toplam yeni disclosure: {total_saved}")
    return total_saved

def fix_cashflow_yfinance(conn):
    """yfinance ile cashflow detaylarini doldur"""
    c = conn.cursor()
    print("\n[2] CASHFLOW YFINANCE...")
    
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance yok!")
        return
    
    # Sadece cashflow'u olan ama detaylari bos olan sirketler
    c.execute('''SELECT DISTINCT kc.ticker, kc.id 
        FROM kap_companies kc
        JOIN kap_cashflows kcf ON kcf.company_id = kc.id
        WHERE kcf.depreciation IS NULL AND kcf.operating_cash_flow IS NOT NULL
        LIMIT 200''')
    companies = c.fetchall()
    print(f"  {len(companies)} sirket cashflow detay bekliyor")
    
    fixed = 0
    for idx, (ticker, company_id) in enumerate(companies):
        try:
            t = yf.Ticker(f'{ticker}.IS')
            cf = t.cashflow
            if cf is not None and not cf.empty:
                # En son yil
                latest_col = cf.columns[0]
                latest_year = str(latest_col.year) if hasattr(latest_col, 'year') else str(latest_col)[:4]
                
                dep = cf.loc['Depreciation And Amortization', latest_col] if 'Depreciation And Amortization' in cf.index else None
                capex = cf.loc['Capital Expenditure', latest_col] if 'Capital Expenditure' in cf.index else None
                inv_cf = cf.loc['Total Cash From Investing Activities', latest_col] if 'Total Cash From Investing Activities' in cf.index else None
                fin_cf = cf.loc['Total Cash From Financing Activities', latest_col] if 'Total Cash From Financing Activities' in cf.index else None
                
                if any([dep, capex, inv_cf, fin_cf]):
                    c.execute('''UPDATE kap_cashflows 
                        SET depreciation=%s, capex=%s, investing_cash_flow=%s, financing_cash_flow=%s
                        WHERE company_id=%s AND year=%s AND depreciation IS NULL''',
                        (dep, capex, inv_cf, fin_cf, company_id, latest_year))
                    fixed += 1
                
            conn.commit()
            time.sleep(0.3)
        except Exception:
            pass
        
        if idx % 50 == 0 and idx > 0:
            print(f"  [{idx}/{len(companies)}] {fixed} guncellendi")
    
    print(f"  Cashflow: {fixed}/{len(companies)} guncellendi")

def fix_balance_sheet_remaining(conn):
    """Kalan bos balance sheet verilerini yfinance ile doldur"""
    c = conn.cursor()
    print("\n[3] BALANCE SHEET REMAINING...")
    
    try:
        import yfinance as yf
    except ImportError:
        return
    
    c.execute('''SELECT DISTINCT kc.ticker, kc.id 
        FROM kap_companies kc
        JOIN kap_financials kf ON kf.company_id = kc.id
        WHERE kf.current_assets IS NULL 
        AND kf.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = kc.id)
        LIMIT 300''')
    companies = c.fetchall()
    print(f"  {len(companies)} sirket balance sheet bekliyor")
    
    fixed = 0
    for idx, (ticker, cid) in enumerate(companies):
        try:
            t = yf.Ticker(f'{ticker}.IS')
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                latest = bs.iloc[:, 0]
                ca = latest.get('Current Assets', latest.get('Total Current Assets'))
                if ca and ca > 0:
                    c.execute('UPDATE kap_financials SET current_assets=%s WHERE company_id=%s AND current_assets IS NULL', (int(ca), cid))
                    fixed += 1
                cash = latest.get('Cash And Cash Equivalents', latest.get('Cash'))
                if cash and cash > 0:
                    c.execute('UPDATE kap_financials SET cash_and_equivalents=%s WHERE company_id=%s AND cash_and_equivalents IS NULL', (int(cash), cid))
                td = latest.get('Total Debt', latest.get('Long Term Debt', 0))
                if td and td > 0:
                    c.execute('UPDATE kap_financials SET financial_debt=%s, total_debt=%s WHERE company_id=%s AND financial_debt IS NULL', (int(td), int(td), cid))
            conn.commit()
            time.sleep(0.2)
        except Exception:
            pass
        
        if idx % 50 == 0 and idx > 0:
            print(f"  [{idx}/{len(companies)}] {fixed} guncellendi")
    
    print(f"  Balance sheet: {fixed}/{len(companies)} guncellendi")

def fix_market_data_yfinance(conn):
    """bist_stock_prices eksik alanlarini yfinance ile doldur"""
    c = conn.cursor()
    print("\n[4] MARKET DATA YFINANCE...")
    
    try:
        import yfinance as yf
    except ImportError:
        return
    
    c.execute('''SELECT ticker FROM bist_stock_prices 
        WHERE volume IS NULL OR week52_high IS NULL OR dividend_yield IS NULL
        LIMIT 200''')
    tickers = [r[0] for r in c.fetchall()]
    print(f"  {len(tickers)} sirket market data bekliyor")
    
    fixed = 0
    for idx, ticker in enumerate(tickers):
        try:
            t = yf.Ticker(f'{ticker}.IS')
            info = t.info
            
            updates = []
            params = []
            
            vol = info.get('volume')
            if vol:
                updates.append('volume=%s')
                params.append(vol)
            
            w52h = info.get('fiftyTwoWeekHigh')
            if w52h:
                updates.append('week52_high=%s')
                params.append(w52h)
            
            w52l = info.get('fiftyTwoWeekLow')
            if w52l:
                updates.append('week52_low=%s')
                params.append(w52l)
            
            div = info.get('dividendYield')
            if div:
                updates.append('dividend_yield=%s')
                params.append(div * 100 if div < 1 else div)
            
            prev = info.get('previousClose')
            if prev:
                updates.append('previous_close=%s')
                params.append(prev)
            
            day_high = info.get('dayHigh')
            if day_high:
                updates.append('day_high=%s')
                params.append(day_high)
            
            day_low = info.get('dayLow')
            if day_low:
                updates.append('day_low=%s')
                params.append(day_low)
            
            chg = info.get('regularMarketChangePercent')
            if chg is not None:
                updates.append('day_change_pct=%s')
                params.append(chg)
            
            xu100 = info.get('is_xu100')
            if xu100 is not None:
                updates.append('is_xu100=%s')
                params.append(xu100)
            
            if updates:
                params.append(ticker)
                c.execute(f"UPDATE bist_stock_prices SET {', '.join(updates)} WHERE ticker=%s", params)
                fixed += 1
            
            conn.commit()
            time.sleep(0.3)
        except Exception:
            pass
        
        if idx % 50 == 0 and idx > 0:
            print(f"  [{idx}/{len(tickers)}] {fixed} guncellendi")
    
    print(f"  Market data: {fixed}/{len(tickers)} guncellendi")

def fix_revenue_yfinance(conn):
    """yfinance ile bos revenue kayitlarini doldur"""
    c = conn.cursor()
    print("\n[5] REVENUE FIX YFINANCE...")
    
    try:
        import yfinance as yf
    except ImportError:
        return
    
    c.execute('''SELECT DISTINCT kc.ticker, kc.id, kf.year
        FROM kap_companies kc
        JOIN kap_financials kf ON kf.company_id = kc.id
        WHERE (kf.revenue IS NULL OR kf.revenue = 0)
        AND kf.gross_profit > 0
        LIMIT 100''')
    companies = c.fetchall()
    print(f"  {len(companies)} sirket revenue bekliyor")
    
    fixed = 0
    for idx, (ticker, cid, year) in enumerate(companies):
        try:
            t = yf.Ticker(f'{ticker}.IS')
            inc = t.income_stmt
            if inc is not None and not inc.empty:
                # Find matching year
                for col in inc.columns:
                    if hasattr(col, 'year') and str(col.year) == str(year):
                        rev = inc.loc['Total Revenue', col] if 'Total Revenue' in inc.index else None
                        if rev and rev > 0:
                            c.execute('UPDATE kap_financials SET revenue=%s WHERE company_id=%s AND year=%s AND (revenue IS NULL OR revenue=0)', (int(rev), cid, str(year)))
                            fixed += 1
                        break
            conn.commit()
            time.sleep(0.3)
        except Exception:
            pass
    
    print(f"  Revenue: {fixed}/{len(companies)} guncellendi")

def main():
    conn = psycopg2.connect(DB_URL)
    
    print("=" * 60)
    print("TUM EKSIK VERILERI TAMAMLA")
    print("=" * 60)
    
    # 1. Disclosures
    fix_disclosures(conn)
    
    # 2. Cashflow details
    fix_cashflow_yfinance(conn)
    
    # 3. Balance sheet remaining
    fix_balance_sheet_remaining(conn)
    
    # 4. Market data
    fix_market_data_yfinance(conn)
    
    # 5. Revenue fix
    fix_revenue_yfinance(conn)
    
    # Final stats
    print("\n" + "=" * 60)
    print("FINAL DURUM")
    print("=" * 60)
    
    c = conn.cursor()
    
    # Disclosure stats
    c.execute('SELECT COUNT(*) FROM kap_disclosures')
    disc_total = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT company_id) FROM kap_disclosures WHERE company_id IS NOT NULL')
    disc_companies = c.fetchone()[0]
    print(f"  Disclosures: {disc_total} kayit, {disc_companies} sirket")
    
    # Financial stats
    c.execute('''SELECT 
        COUNT(*) FILTER (WHERE current_assets IS NULL) as ca,
        COUNT(*) FILTER (WHERE cash_and_equivalents IS NULL) as cash,
        COUNT(*) FILTER (WHERE financial_debt IS NULL) as fd,
        COUNT(*) FILTER (WHERE pe_ratio IS NULL OR pe_ratio = 0) as pe,
        COUNT(*) FILTER (WHERE gross_margin IS NULL) as gm,
        COUNT(*) FILTER (WHERE net_margin IS NULL) as nm,
        COUNT(*) FROM kap_financials''')
    ov = c.fetchone()
    total = ov[6]
    print(f"  Financials: CA={total-ov[0]}/{total}, Cash={total-ov[1]}, FDebt={total-ov[2]}, PE={total-ov[3]}, GM={total-ov[4]}, NM={total-ov[5]}")
    
    # Cashflow stats
    c.execute('''SELECT 
        COUNT(*) FILTER (WHERE depreciation IS NOT NULL) as dep,
        COUNT(*) FILTER (WHERE investing_cash_flow IS NOT NULL) as icf,
        COUNT(*) FILTER (WHERE financing_cash_flow IS NOT NULL) as fcf,
        COUNT(*) FROM kap_cashflows''')
    cf = c.fetchone()
    print(f"  Cashflows: depreciation={cf[0]}/{cf[3]}, investing={cf[1]}, financing={cf[2]}")
    
    # THYAO
    c.execute('''SELECT 
        (SELECT COUNT(*) FROM kap_disclosures WHERE company_id=681),
        (SELECT COUNT(*) FROM kap_shareholders WHERE company_id=681),
        (SELECT COUNT(*) FROM kap_management WHERE company_id=681)''')
    thyao = c.fetchone()
    print(f"  THYAO: disc={thyao[0]}, sh={thyao[1]}, mg={thyao[2]}")
    
    conn.close()
    print("\nTAMAMLANDI!")

if __name__ == '__main__':
    main()
