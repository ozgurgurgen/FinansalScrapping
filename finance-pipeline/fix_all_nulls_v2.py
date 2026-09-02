"""
KAPSAMLI NULL DOLDURMA SCRIPTI
Tum null verileri yfinance + mevcut DB verileri ile doldurur.
Anti-ban: 0.5sn gecikme ile yavas cekim.
"""
import sys, io, time, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import psycopg2

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'

try:
    import yfinance as yf
except ImportError:
    print("yfinance yuklenemedi, pip install yfinance")
    sys.exit(1)

def get_db():
    return psycopg2.connect(DB)

def fill_missing_sectors(db):
    """Sektor bilgisi olmayan sirketleri yfinance ile doldur."""
    c = db.cursor()
    c.execute("SELECT id, ticker FROM kap_companies WHERE sector IS NULL OR sector = ''")
    companies = c.fetchall()
    print(f'\n=== SEKTOR DOLDURMA === {len(companies)} sirket eksik')
    
    filled = 0
    failed = 0
    for i, (cid, ticker) in enumerate(companies):
        try:
            # Yahoo Finance ticker format: THYAO.IS
            yf_ticker = f"{ticker}.IS"
            t = yf.Ticker(yf_ticker)
            info = t.info
            sector = info.get('sector', '') or info.get('industry', '') or ''
            if sector:
                c.execute("UPDATE kap_companies SET sector=%s WHERE id=%s", (sector, cid))
                filled += 1
                if filled % 20 == 0:
                    db.commit()
                    print(f'  {i+1}/{len(companies)}: {filled} dolduruldu, {failed} basarisiz - son: {ticker}={sector}')
            else:
                failed += 1
        except Exception as e:
            failed += 1
        time.sleep(random.uniform(0.3, 0.8))
        
        if i > 0 and i % 100 == 0:
            db.commit()
    
    db.commit()
    print(f'  SEKTOR: {filled} dolduruldu, {failed} basarisiz')
    return filled

def fill_missing_financials(db):
    """current_assets, cash, financial_debt, total_debt alanlarini yfinance ile doldur."""
    c = db.cursor()
    # Sadece bos olanlari guncelle
    c.execute("""
        SELECT f.id, c.ticker, f.year, f.period
        FROM kap_financials f
        JOIN kap_companies c ON f.company_id = c.id
        WHERE (f.current_assets IS NULL OR f.cash_and_equivalents IS NULL 
               OR f.financial_debt IS NULL OR f.total_debt IS NULL)
        ORDER BY c.ticker, f.year DESC
    """)
    rows = c.fetchall()
    print(f'\n=== FINANSAL DETAY DOLDURMA === {len(rows)} kayit eksik')
    
    filled = 0
    failed = 0
    last_ticker = None
    
    for i, (fid, ticker, year, period) in enumerate(rows):
        # Her yeni ticker icin yeni istek
        if ticker != last_ticker:
            try:
                yf_ticker = f"{ticker}.IS"
                t = yf.Ticker(yf_ticker)
                # Try annual balance sheet first
                bs = t.balance_sheet
                if bs is not None and not bs.empty:
                    # Get the right period column
                    period_col = None
                    for col in bs.columns:
                        col_year = col.year if hasattr(col, 'year') else int(str(col)[:4])
                        if col_year == int(year):
                            period_col = col
                            break
                    if period_col is None and len(bs.columns) > 0:
                        period_col = bs.columns[0]  # Most recent
                    
                    if period_col:
                        vals = {}
                        bs_index = [str(x).lower() for x in bs.index]
                        
                        # current_assets
                        for idx, idx_name in enumerate(bs_index):
                            if 'current' in idx_name and 'asset' in idx_name:
                                vals['current_assets'] = bs.iloc[idx][period_col]
                                break
                        
                        # cash
                        for idx, idx_name in enumerate(bs_index):
                            if 'cash' in idx_name or 'nakit' in idx_name:
                                vals['cash'] = bs.iloc[idx][period_col]
                                break
                        
                        # total_debt / financial_debt
                        for idx, idx_name in enumerate(bs_index):
                            if 'total debt' in idx_name or 'toplam borc' in idx_name:
                                val = bs.iloc[idx][period_col]
                                vals['total_debt'] = val
                                vals['financial_debt'] = val
                                break
                            elif 'long term debt' in idx_name or 'short term debt' in idx_name:
                                if 'financial_debt' not in vals:
                                    vals['financial_debt'] = 0
                                vals['financial_debt'] += bs.iloc[idx][period_col]
                        
                        # net_debt = total_debt - cash
                        if 'cash' in vals and 'total_debt' in vals:
                            vals['net_debt'] = (vals.get('total_debt') or 0) - (vals.get('cash') or 0)
                        
                        if vals:
                            sets = []
                            params = []
                            for k, v in vals.items():
                                if v is not None and v != 0:
                                    sets.append(f"{k}=%s")
                                    params.append(float(v))
                            
                            if sets:
                                params.append(fid)
                                c.execute(f"UPDATE kap_financials SET {', '.join(sets)} WHERE id=%s", params)
                                filled += 1
                
                last_ticker = ticker
            except Exception as e:
                failed += 1
                last_ticker = ticker
            
            time.sleep(random.uniform(0.5, 1.2))
        
        if i > 0 and i % 50 == 0:
            db.commit()
            print(f'  {i+1}/{len(rows)}: {filled} guncellendi, {failed} basarisiz')
    
    db.commit()
    print(f'  FINANSAL: {filled} guncellendi, {failed} basarisiz')
    return filled

def fix_pe_pb_from_prices(db):
    """bist_stock_prices'daki PE/PB'yi kap_financials'a aktar."""
    c = db.cursor()
    c.execute("""
        UPDATE kap_financials f
        SET pe_ratio = p.pe_ratio, pb_ratio = p.pb_ratio
        FROM kap_companies comp
        JOIN bist_stock_prices p ON p.ticker = comp.ticker
        WHERE f.company_id = comp.id 
          AND (f.pe_ratio IS NULL OR f.pe_ratio = 0)
          AND p.pe_ratio > 0
          AND f.period = '12'
          AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = comp.id AND period = '12')
    """)
    updated = c.rowcount
    db.commit()
    print(f'\n=== PE/PB DUZELTME === {updated} kayit guncellendi')
    return updated

def fix_thyao_company_link(db):
    """THYAO icin disclosures, shareholders, management, subsidiaries eslestirmesi."""
    c = db.cursor()
    
    # THYAO id
    c.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    row = c.fetchone()
    if not row:
        print('THYAO bulunamadi!')
        return 0
    thyao_id = row[0]
    
    # Disclosures: symbol icinde THYAO gecenleri bagla
    c.execute("UPDATE kap_disclosures SET company_id=%s WHERE symbol LIKE '%%THYAO%%' AND company_id != %s", (thyao_id, thyao_id))
    disc_fixed = c.rowcount
    
    # Disclosure_details varsa symbol uzerinden bagla
    try:
        c.execute("UPDATE kap_disclosure_details SET company_id=%s WHERE (ticker='THYAO' OR symbol='THYAO') AND company_id != %s", (thyao_id, thyao_id))
        dd_fixed = c.rowcount
    except:
        dd_fixed = 0
    
    db.commit()
    print(f'\n=== THYAO ESLESTIRME === disclosures: {disc_fixed}, details: {dd_fixed}')
    
    # Diger sirketler icin de aynisini yap
    c.execute("""
        UPDATE kap_disclosures d
        SET company_id = c.id
        FROM kap_companies c
        WHERE d.symbol LIKE '%' || c.ticker || '%'
          AND d.company_id != c.id
          AND c.ticker IN ('GARAN', 'ASELS', 'BIMAS', 'AKBNK', 'EREGL', 'SAHOL', 'TUPRS', 'KCHOL', 'SISE', 'FROTO')
    """)
    gen_fixed = c.rowcount
    db.commit()
    print(f'  Genel sirket eslestirme: {gen_fixed} disclosure guncellendi')
    
    return disc_fixed + dd_fixed + gen_fixed

def fix_cashflow_details(db):
    """Nakit akis detaylarini (depreciation, financing_cf) mevcut veriden tureterek doldur."""
    c = db.cursor()
    
    # operating_cf varsa ama digerleri yoksa, hesapla
    c.execute("""
        UPDATE kap_cashflows
        SET net_change = operating_cash_flow + COALESCE(investing_cash_flow, 0) + COALESCE(financing_cash_flow, 0)
        WHERE net_change IS NULL 
          AND operating_cash_flow IS NOT NULL
    """)
    nc_fixed = c.rowcount
    
    db.commit()
    print(f'\n=== NAKIT AKIS DETAY === net_change hesaplandi: {nc_fixed}')
    return nc_fixed

def fill_missing_sectors_kap(db):
    """KAP'tan sektor bilgisini cekmek icin disclosure basliklarindan sektor cikar."""
    c = db.cursor()
    
    # Disclosure'lardan sektor cikarmaya calis - kategori ile
    c.execute("""
        SELECT DISTINCT c.id, c.ticker, d.category
        FROM kap_companies c
        JOIN kap_disclosures d ON d.company_id = c.id
        WHERE (c.sector IS NULL OR c.sector = '')
          AND d.category IS NOT NULL AND d.category != ''
    """)
    rows = c.fetchall()
    
    # Kategori -> sektor eslesme
    cat_sector = {
        'Finans': 'Financials', 'Banka': 'Financials', 'Sigorta': 'Financials',
        'Sanayi': 'Industrials', 'Holding': 'Financials',
        'Teknoloji': 'Technology', 'Bilisim': 'Technology',
        'Gida': 'Consumer Defensive', 'Perakende': 'Consumer Defensive',
        'Enerji': 'Energy', 'Elektrik': 'Utilities',
        'Gayrimenkul': 'Real Estate', 'GYO': 'Real Estate',
        'Ulasim': 'Industrials', 'Turizm': 'Consumer Cyclical',
        'Kimya': 'Basic Materials', 'Maden': 'Basic Materials',
        'Otomotiv': 'Consumer Cyclical', 'Tekstil': 'Consumer Cyclical',
        'Iletisim': 'Communication Services', 'Medya': 'Communication Services',
        'Saglik': 'Healthcare', 'Egitim': 'Consumer Defensive',
    }
    
    updated = 0
    for cid, ticker, cat in rows:
        if cat:
            for key, sector in cat_sector.items():
                if key.lower() in cat.lower():
                    c.execute("UPDATE kap_companies SET sector=%s WHERE id=%s AND (sector IS NULL OR sector='')", (sector, cid))
                    updated += 1
                    break
    
    db.commit()
    print(f'\n=== DISCLOSURE SEKTOR TAHMIN === {updated} sirket guncellendi')
    return updated


# ========== ANA CALISMA ==========
if __name__ == '__main__':
    db = get_db()
    
    print('='*60)
    print('KAPSAMLI NULL DOLDURMA BASLADI')
    print('='*60)
    
    # 1. THYAO eslestirme
    fix_thyao_company_link(db)
    
    # 2. Disclosure'dan sektor tahmini
    fill_missing_sectors_kap(db)
    
    # 3. PE/PB duzeltme
    fix_pe_pb_from_prices(db)
    
    # 4. Nakit akis net_change
    fix_cashflow_details(db)
    
    # 5. yfinance ile sektor doldurma (en yavas, sona birak)
    try:
        fill_missing_sectors(db)
    except Exception as e:
        print(f'Sektor doldurma hatasi: {e}')
    
    # 6. yfinance ile finansal detay doldurma
    try:
        fill_missing_financials(db)
    except Exception as e:
        print(f'Finansal detay hatasi: {e}')
    
    # Final stats
    c = db.cursor()
    c.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(current_assets) as ca, COUNT(cash_and_equivalents) as cash,
            COUNT(financial_debt) as debt, COUNT(pe_ratio) as pe,
            COUNT(roe) as roe, COUNT(equity) as eq
        FROM kap_financials
    """)
    s = c.fetchone()
    print(f'\n{"="*60}')
    print(f'SONUC - FINANSAL DOLULUK ({s[0]} kayit)')
    print(f'{"="*60}')
    for i, name in enumerate(['current_assets', 'cash', 'financial_debt', 'pe_ratio', 'roe', 'equity'], 1):
        pct = int(s[i]*100/s[0]) if s[0]>0 else 0
        print(f'  {name}: {s[i]}/{s[0]} (%{pct})')
    
    c.execute("SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
    sec = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kap_companies")
    top = c.fetchone()[0]
    print(f'\n  Sektorsuz sirket: {top - sec}/{top} (%{int((top-sec)*100/top) if top else 0})')
    
    # THYAO check
    c.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    r = c.fetchone()
    if r:
        for tbl in ['kap_disclosures', 'kap_shareholders', 'kap_management', 'kap_subsidiaries']:
            c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE company_id=%s", (r[0],))
            print(f'  THYAO {tbl}: {c.fetchone()[0]}')
    
    db.close()
    print('\nTAMAMLANDI!')
