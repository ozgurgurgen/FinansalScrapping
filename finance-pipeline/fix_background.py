"""
ARKA PLAN: yfinance ile finansal detay + KAP bildirim cekme
300 saniye timeout ile calistirilir.
"""
import sys, io, time, random, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psycopg2

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'

try:
    import yfinance as yf
except:
    print('yfinance yok!')
    sys.exit(1)

db = psycopg2.connect(DB)
c = db.cursor()

# === PART A: yfinance ile sektor + finansal detay ===
c.execute("SELECT id, ticker FROM kap_companies WHERE sector IS NULL OR sector = ''")
companies = c.fetchall()
print(f'[A] SEKTOR: {len(companies)} sirket isleniyor...')

sec_filled = 0
for i, (cid, ticker) in enumerate(companies):
    try:
        info = yf.Ticker(f"{ticker}.IS").info
        sector = info.get('sector') or info.get('industry') or ''
        if sector and sector != 'N/A' and len(sector) > 2:
            c.execute("UPDATE kap_companies SET sector=%s WHERE id=%s", (sector, cid))
            sec_filled += 1
    except:
        pass
    time.sleep(random.uniform(0.3, 0.7))
    if (i+1) % 30 == 0:
        db.commit()
        print(f'  sektor: {i+1}/{len(companies)} ({sec_filled} doldu)')

db.commit()
print(f'[A] SEKTOR TAMAM: {sec_filled}/{len(companies)}')

# === PART B: yfinance balance sheet ===
c.execute("""
    SELECT DISTINCT c.ticker
    FROM kap_financials f JOIN kap_companies c ON f.company_id=c.id
    WHERE f.current_assets IS NULL AND f.period='12' AND f.year >= 2023
""")
tickers = [r[0] for r in c.fetchall()]
print(f'\n[B] FINANSAL DETAY: {len(tickers)} ticker...')

fin_filled = 0
for i, ticker in enumerate(tickers):
    try:
        t = yf.Ticker(f"{ticker}.IS")
        bs = t.balance_sheet
        if bs is not None and not bs.empty:
            col = bs.columns[0]
            data = {}
            for idx in bs.index:
                idx_s = str(idx).lower()
                val = bs.loc[idx, col]
                if val is None or str(val) in ('nan', 'None', ''):
                    continue
                try:
                    v = float(val)
                except:
                    continue
                    
                if 'current asset' in idx_s:
                    data['current_assets'] = v
                elif 'cash' in idx_s and 'equivalent' in idx_s:
                    data['cash'] = v
                elif 'total debt' in idx_s:
                    data['total_debt'] = v
                elif 'long term debt' in idx_s:
                    data['lt_debt'] = v
                elif 'short term debt' in idx_s:
                    data['st_debt'] = v
            
            # total_debt hesapla
            if 'total_debt' not in data:
                lt = data.get('lt_debt', 0) or 0
                st = data.get('st_debt', 0) or 0
                if lt > 0 or st > 0:
                    data['total_debt'] = lt + st
            
            if data.get('current_assets') or data.get('cash') or data.get('total_debt'):
                net_debt = None
                if data.get('total_debt') and data.get('cash'):
                    net_debt = data['total_debt'] - data['cash']
                
                c.execute("""
                    UPDATE kap_financials SET 
                        current_assets = COALESCE(%s, current_assets),
                        cash_and_equivalents = COALESCE(%s, cash_and_equivalents),
                        total_debt = COALESCE(%s, total_debt),
                        financial_debt = COALESCE(%s, financial_debt),
                        net_debt = COALESCE(%s, net_debt)
                    WHERE company_id = (SELECT id FROM kap_companies WHERE ticker=%s LIMIT 1)
                      AND period = '12' AND year >= 2023
                """, (
                    data.get('current_assets'), data.get('cash'),
                    data.get('total_debt'), data.get('total_debt'),
                    net_debt, ticker
                ))
                fin_filled += 1
    except:
        pass
    time.sleep(random.uniform(0.5, 1.0))
    if (i+1) % 20 == 0:
        db.commit()
        print(f'  finansal: {i+1}/{len(tickers)} ({fin_filled} guncellendi)')

db.commit()
print(f'[B] FINANSAL TAMAM: {fin_filled}/{len(tickers)}')

# === PART C: KAP API bildirim cek ===
c.execute("""
    SELECT c.id, c.ticker FROM kap_companies c
    LEFT JOIN kap_disclosures d ON d.company_id = c.id
    WHERE d.id IS NULL
    ORDER BY c.ticker
    LIMIT 50
""")
no_disc = c.fetchall()
print(f'\n[C] KAP BILDIRIM: {len(no_disc)} sirket...')

H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
     'Accept': 'application/json', 'Accept-Language': 'tr-TR,tr;q=0.9', 'Referer': 'https://www.kap.org.tr'}

kap_added = 0
for cid, ticker in no_disc:
    try:
        url = f"https://www.kap.org.tr/tr/api/disclosure?companyCode={ticker}&from=2024-01-01&to=2026-12-31&page=1&pageSize=20"
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                for item in data:
                    did = str(item.get('disclosureIndex', ''))
                    title = item.get('subject', '') or item.get('title', '')
                    cat = item.get('category', '') or item.get('disclosureType', '')
                    dt = item.get('disclosureClass', '') or ''
                    pub = item.get('publishDate', '') or item.get('date', '')
                    c.execute("""INSERT INTO kap_disclosures (company_id, disclosure_id, symbol, title, category,
                                disclosure_type, publish_date, source_url, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                                ON CONFLICT DO NOTHING""", (cid, did, ticker, title, cat, dt, pub,
                                f"https://www.kap.org.tr/tr/Bildirim/{did}"))
                    kap_added += 1
    except:
        pass
    time.sleep(random.uniform(2.0, 4.0))
    if kap_added > 0 and kap_added % 10 == 0:
        db.commit()
        print(f'  bildirim: {ticker} -> +{kap_added}')

db.commit()
print(f'[C] KAP BILDIRIM TAMAM: {kap_added}')

# === FINAL ===
c.execute("""SELECT COUNT(*) as t, COUNT(current_assets) as ca, COUNT(cash_and_equivalents) as cash,
    COUNT(financial_debt) as debt, COUNT(pe_ratio) as pe FROM kap_financials""")
s = c.fetchone()
print(f'\n=== FINAL: ca={s[1]}/{s[0]} cash={s[2]}/{s[0]} debt={s[3]}/{s[0]} pe={s[4]}/{s[0]}')

c.execute("SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
print(f'Sektor: {c.fetchone()[0]}')
c.execute("SELECT COUNT(*) FROM kap_disclosures")
print(f'Disclosures: {c.fetchone()[0]}')

db.close()
print('\nTAMAMLANDI!')
