"""
HIZLI yfinance: current_assets, cash, total_debt doldurur.
Sadece bos olanlari isler. Batch tarzinda calisir.
"""
import sys, io, time, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psycopg2
import yfinance as yf

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'
db = psycopg2.connect(DB)
c = db.cursor()

# Sadece current_assets bos olan son donemleri al
c.execute("""
    SELECT f.id, f.company_id, f.year, c.ticker
    FROM kap_financials f
    JOIN kap_companies c ON f.company_id = c.id
    WHERE f.current_assets IS NULL 
      AND f.period = '12'
      AND f.year = (SELECT MAX(year) FROM kap_financials WHERE company_id = f.company_id AND period = '12')
    ORDER BY c.ticker
""")
rows = c.fetchall()
print(f'{len(rows)} kayit islenecek...')

filled = 0
failed = 0
last_ticker = None

for i, (fid, cid, year, ticker) in enumerate(rows):
    if ticker != last_ticker:
        try:
            t = yf.Ticker(f"{ticker}.IS")
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                col = bs.columns[0]
                vals = {}
                for idx in bs.index:
                    s = str(idx).lower()
                    v = bs.loc[idx, col]
                    if v is None or str(v) == 'nan':
                        continue
                    try:
                        v = float(v)
                    except:
                        continue
                    if s == 'current assets':
                        vals['ca'] = v
                    elif s == 'cash and cash equivalents':
                        vals['cash'] = v
                    elif s == 'total debt':
                        vals['debt'] = v
                
                if vals:
                    net = None
                    if 'debt' in vals and 'cash' in vals:
                        net = vals['debt'] - vals['cash']
                    c.execute("""
                        UPDATE kap_financials SET 
                            current_assets = %s, cash_and_equivalents = %s,
                            total_debt = %s, financial_debt = %s, net_debt = %s
                        WHERE id = %s
                    """, (vals.get('ca'), vals.get('cash'), vals.get('debt'), vals.get('debt'), net, fid))
                    filled += 1
        except:
            failed += 1
        last_ticker = ticker
        time.sleep(random.uniform(0.4, 0.8))
    
    if (i+1) % 25 == 0:
        db.commit()
        print(f'  {i+1}/{len(rows)}: {filled} guncellendi, {failed} basarisiz')

db.commit()
print(f'\nTAMAM: {filled}/{len(rows)} guncellendi, {failed} basarisiz')

# Sonuc
c.execute("""SELECT COUNT(*) as t, COUNT(current_assets) as ca, COUNT(cash_and_equivalents) as cash,
    COUNT(financial_debt) as debt FROM kap_financials""")
s = c.fetchone()
print(f'FINANSAL: ca={s[1]}/{s[0]} cash={s[2]}/{s[0]} debt={s[3]}/{s[0]}')

db.close()
