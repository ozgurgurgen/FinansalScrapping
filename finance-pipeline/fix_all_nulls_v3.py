"""
TUM NULL VERILERI KAPSAMLI DOLDURMA v3
Adim 1: DB'den turetilebilecekler (hizli)
Adim 2: yfinance (yavas ama guvenli)
Adim 3: KAP API bildirim cekme
"""
import sys, io, time, random, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psycopg2

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def get_db():
    return psycopg2.connect(DB)

# ============= ADIM 1: DB TURETME (HIZLI) =============

def step1_pe_pb_from_prices(db):
    """bist_stock_prices PE/PB'sini son donem finansallara aktar."""
    c = db.cursor()
    c.execute("""
        WITH latest AS (
            SELECT DISTINCT ON (f.company_id) f.id, f.company_id, f.year
            FROM kap_financials f
            WHERE f.period = '12'
            ORDER BY f.company_id, f.year DESC
        )
        UPDATE kap_financials f
        SET pe_ratio = p.pe_ratio,
            pb_ratio = p.pb_ratio
        FROM latest l
        JOIN kap_companies comp ON comp.id = l.company_id
        JOIN bist_stock_prices p ON p.ticker = comp.ticker
        WHERE f.id = l.id
          AND (f.pe_ratio IS NULL OR f.pe_ratio = 0)
          AND p.pe_ratio > 0
    """)
    db.commit()
    print(f'  PE/PB: {c.rowcount} guncellendi')
    return c.rowcount

def step1_net_change(db):
    """Cashflow net_change hesapla."""
    c = db.cursor()
    c.execute("""
        UPDATE kap_cashflows
        SET net_change = COALESCE(operating_cash_flow, 0) 
                       + COALESCE(investing_cash_flow, 0) 
                       + COALESCE(financing_cash_flow, 0)
        WHERE net_change IS NULL 
          AND operating_cash_flow IS NOT NULL
    """)
    db.commit()
    print(f'  net_change: {c.rowcount} hesaplandi')
    return c.rowcount

def step1_leverage(db):
    """leverage_ratio = total_debts / equity hesapla eger yoksa."""
    c = db.cursor()
    c.execute("""
        UPDATE kap_financials
        SET leverage_ratio = total_debts / NULLIF(equity, 0)
        WHERE leverage_ratio IS NULL 
          AND total_debts IS NOT NULL AND total_debts > 0
          AND equity IS NOT NULL AND equity > 0
    """)
    db.commit()
    print(f'  leverage: {c.rowcount} hesaplandi')
    return c.rowcount

def step1_margin_fixes(db):
    """Eksik marjlari turet."""
    c = db.cursor()
    # gross_margin = gross_profit / revenue
    c.execute("""
        UPDATE kap_financials SET gross_margin = ROUND((gross_profit / NULLIF(revenue, 0) * 100)::numeric, 2)
        WHERE gross_margin IS NULL AND gross_profit > 0 AND revenue > 0
    """)
    gm = c.rowcount
    
    # net_margin = net_profit / revenue
    c.execute("""
        UPDATE kap_financials SET net_margin = ROUND((net_profit / NULLIF(revenue, 0) * 100)::numeric, 2)
        WHERE net_margin IS NULL AND net_profit > 0 AND revenue > 0
    """)
    nm = c.rowcount
    
    # ebitda_margin = ebitda / revenue
    c.execute("""
        UPDATE kap_financials SET ebitda_margin = ROUND((ebitda / NULLIF(revenue, 0) * 100)::numeric, 2)
        WHERE ebitda_margin IS NULL AND ebitda > 0 AND revenue > 0
    """)
    em = c.rowcount
    
    # roe = net_profit / equity
    c.execute("""
        UPDATE kap_financials SET roe = ROUND((net_profit / NULLIF(equity, 0) * 100)::numeric, 2)
        WHERE (roe IS NULL OR roe = 0) AND net_profit > 0 AND equity > 0
    """)
    roe = c.rowcount
    
    # roa = net_profit / total_assets
    c.execute("""
        UPDATE kap_financials SET roa = ROUND((net_profit / NULLIF(total_assets, 0) * 100)::numeric, 2)
        WHERE (roa IS NULL OR roa = 0) AND net_profit > 0 AND total_assets > 0
    """)
    roa = c.rowcount
    
    db.commit()
    print(f'  Marjlar: brut={gm}, net={nm}, ebitda={em}, roe={roe}, roa={roa}')
    return gm + nm + em + roe + roa

# ============= ADIM 2: YFINANCE (YAVAS) =============

def step2_sectors_yfinance(db):
    """Sektor bilgisi olmayan sirketleri yfinance ile doldur."""
    c = db.cursor()
    c.execute("SELECT id, ticker FROM kap_companies WHERE sector IS NULL OR sector = ''")
    companies = c.fetchall()
    print(f'\n  yfinance sektor: {len(companies)} sirket isleniyor...')
    
    filled = 0
    for i, (cid, ticker) in enumerate(companies):
        try:
            t = __import__('yfinance').Ticker(f"{ticker}.IS")
            info = t.info
            sector = info.get('sector') or info.get('industry') or ''
            if sector and sector != 'N/A':
                c.execute("UPDATE kap_companies SET sector=%s WHERE id=%s", (sector, cid))
                filled += 1
        except:
            pass
        time.sleep(random.uniform(0.4, 0.9))
        
        if (i+1) % 25 == 0:
            db.commit()
            print(f'    {i+1}/{len(companies)}: {filled} dolduruldu')
    
    db.commit()
    print(f'  SEKTOR: {filled} dolduruldu')
    return filled

def step2_financials_yfinance(db):
    """current_assets, cash, financial_debt, total_debt cek."""
    c = db.cursor()
    c.execute("""
        SELECT DISTINCT c.ticker
        FROM kap_financials f
        JOIN kap_companies c ON f.company_id = c.id
        WHERE f.current_assets IS NULL AND f.period = '12'
        LIMIT 500
    """)
    tickers = [r[0] for r in c.fetchall()]
    print(f'\n  yfinance finansal: {len(tickers)} ticker isleniyor...')
    
    filled = 0
    for i, ticker in enumerate(tickers):
        try:
            t = __import__('yfinance').Ticker(f"{ticker}.IS")
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                # En guncel donemi al
                col = bs.columns[0]
                data = {}
                for idx in bs.index:
                    idx_str = str(idx).lower()
                    val = bs.loc[idx, col]
                    if val is None or str(val) == 'nan':
                        continue
                    
                    if 'current asset' in idx_str:
                        data['current_assets'] = float(val)
                    elif idx_str == 'cash and cash equivalents' or idx_str == 'cash cash equivalents and short term investments':
                        data['cash_and_equivalents'] = float(val)
                    elif 'total debt' in idx_str:
                        data['total_debt'] = float(val)
                        data['financial_debt'] = float(val)
                    elif 'long term debt' in idx_str:
                        data['total_debt'] = data.get('total_debt', 0) + float(val)
                    elif 'short term debt' in idx_str:
                        data['total_debt'] = data.get('total_debt', 0) + float(val)
                
                if data:
                    # net_debt
                    if 'total_debt' in data and 'cash_and_equivalents' in data:
                        data['net_debt'] = data['total_debt'] - data['cash_and_equivalents']
                    
                    # Son donem finansali guncelle
                    c.execute("""
                        UPDATE kap_financials f
                        SET current_assets = COALESCE(%s, current_assets),
                            cash_and_equivalents = COALESCE(%s, cash_and_equivalents),
                            total_debt = COALESCE(%s, total_debt),
                            financial_debt = COALESCE(%s, financial_debt),
                            net_debt = COALESCE(%s, net_debt)
                        FROM kap_companies comp
                        WHERE f.company_id = comp.id 
                          AND comp.ticker = %s 
                          AND f.period = '12'
                          AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id AND period = '12')
                    """, (
                        data.get('current_assets'),
                        data.get('cash_and_equivalents'),
                        data.get('total_debt'),
                        data.get('financial_debt'),
                        data.get('net_debt'),
                        ticker
                    ))
                    if c.rowcount > 0:
                        filled += 1
        except:
            pass
        time.sleep(random.uniform(0.5, 1.0))
        
        if (i+1) % 25 == 0:
            db.commit()
            print(f'    {i+1}/{len(tickers)}: {filled} guncellendi')
    
    db.commit()
    print(f'  FINANSAL: {filled} guncellendi')
    return filled

# ============= ADIM 3: KAP API BILDIRIM =============

def step3_kap_disclosures(db):
    """KAP'tan buyuk sirketlerin bildirimlerini cek."""
    c = db.cursor()
    
    # Bildirimi olmayan buyuk sirketleri bul
    c.execute("""
        SELECT c.id, c.ticker, c.company_name
        FROM kap_companies c
        LEFT JOIN kap_disclosures d ON d.company_id = c.id
        WHERE d.id IS NULL AND c.ticker IN (
            'THYAO', 'GARAN', 'ASELS', 'BIMAS', 'AKBNK', 'EREGL', 'SAHOL', 
            'TUPRS', 'KCHOL', 'SISE', 'FROTO', 'HEKTS', 'KOZAL', 'AEFES',
            'TCELL', 'TTKOM', 'VAKBN', 'YKBNK', 'HALKB', 'TRYHL', 'PETKM',
            'TOASO', 'TAVHL', 'TOASO', 'VESTL', 'KONTR', 'ODAS', 'ENKAI',
            'KRDMD', 'ISCTR', 'QNBFIN', 'TKFEN', 'ARCLK', 'SASA', 'KZBGY',
            'BRYAT', 'EKGYO', 'ISMEN', 'ICBCT', 'AKFGY', 'ISGYO', 'ODAS',
            'NTHOL', 'ANHYT', 'ODAS', 'SMRTG', 'KERVT', 'DEVA', 'MPARK'
        )
        LIMIT 50
    """)
    companies = c.fetchall()
    print(f'\n  KAP bildirim: {len(companies)} sirket icin cekiliyor...')
    
    session_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://www.kap.org.tr',
    }
    
    added = 0
    for cid, ticker, name in companies:
        try:
            # KAP bildirim API
            url = f"https://www.kap.org.tr/tr/api/disclosure?companyCode={ticker}&from=2024-01-01&to=2026-12-31&page=1&pageSize=50"
            req = urllib.request.Request(url, headers=session_headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
                if isinstance(data, list):
                    for item in data:
                        disc_id = item.get('disclosureIndex') or item.get('id', '')
                        title = item.get('subject') or item.get('title', '')
                        cat = item.get('category') or item.get('disclosureType', '')
                        pub_date = item.get('publishDate') or item.get('date', '')
                        disc_type = item.get('disclosureClass') or ''
                        
                        # Insert
                        c.execute("""
                            INSERT INTO kap_disclosures (company_id, disclosure_id, symbol, title, category, 
                                                       disclosure_type, publish_date, source_url, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT DO NOTHING
                        """, (cid, str(disc_id), ticker, title, cat, disc_type, pub_date, 
                              f"https://www.kap.org.tr/tr/Bildirim/{disc_id}"))
                        added += 1
        except Exception as e:
            pass
        
        time.sleep(random.uniform(2.0, 4.0))
        
        if added % 10 == 0 and added > 0:
            db.commit()
            print(f'    {ticker}: {added} bildirim eklendi')
    
    db.commit()
    print(f'  KAP BILDIRIM: {added} bildirim eklendi')
    return added


# ============= ANA CALISMA =============

if __name__ == '__main__':
    db = get_db()
    
    print('='*60)
    print('ADIM 1: DB TURETME (HIZLI)')
    print('='*60)
    step1_pe_pb_from_prices(db)
    step1_net_change(db)
    step1_leverage(db)
    step1_margin_fixes(db)
    
    print('\n' + '='*60)
    print('ADIM 2: YFINANCE (YAVAS)')
    print('='*60)
    try:
        step2_sectors_yfinance(db)
    except Exception as e:
        print(f'  Sektor hatasi: {e}')
    
    try:
        step2_financials_yfinance(db)
    except Exception as e:
        print(f'  Finansal hatasi: {e}')
    
    print('\n' + '='*60)
    print('ADIM 3: KAP API BILDIRIM')
    print('='*60)
    try:
        step3_kap_disclosures(db)
    except Exception as e:
        print(f'  KAP bildirim hatasi: {e}')
    
    # ========== FINAL STAT ==========
    c = db.cursor()
    print('\n' + '='*60)
    print('SONUCLAR')
    print('='*60)
    
    c.execute("""
        SELECT COUNT(*) as total,
            COUNT(current_assets) as ca, COUNT(cash_and_equivalents) as cash,
            COUNT(financial_debt) as debt, COUNT(pe_ratio) as pe,
            COUNT(roe) as roe, COUNT(equity) as eq,
            COUNT(leverage_ratio) as lev
        FROM kap_financials
    """)
    s = c.fetchone()
    print(f'\nFINANSAL ({s[0]} kayit):')
    for i, n in enumerate(['current_assets', 'cash', 'financial_debt', 'pe_ratio', 'roe', 'equity', 'leverage'], 1):
        pct = int(s[i]*100/s[0]) if s[0]>0 else 0
        print(f'  {n}: {s[i]}/{s[0]} (%{pct})')
    
    c.execute("SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
    sec = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kap_companies")
    top = c.fetchone()[0]
    print(f'\nSEKTOR: {sec}/{top} (%{int(sec*100/top) if top else 0})')
    
    c.execute("SELECT COUNT(*) FROM kap_disclosures")
    print(f'DISCL: {c.fetchone()[0]}')
    
    # THYAO check
    c.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    r = c.fetchone()
    if r:
        print(f'\nTHYAO (id={r[0]}):')
        for tbl in ['kap_disclosures', 'kap_shareholders', 'kap_management', 'kap_subsidiaries', 'kap_financials']:
            c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE company_id=%s", (r[0],))
            print(f'  {tbl}: {c.fetchone()[0]}')
    
    db.close()
    print('\nTAMAMLANDI!')
