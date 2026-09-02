#!/usr/bin/env python3
"""Veri kalitesi denetimi"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sqlite3
import requests

db = sqlite3.connect('finance.db')
c = db.cursor()

print('=' * 60)
print('VERI KALITESI DENETIMI')
print('=' * 60)

# 1. Companies
print('\n1. COMPANIES')
r = c.execute('SELECT COUNT(*) FROM companies WHERE company_name IS NULL OR company_name = ""').fetchone()[0]
print(f'  Bos isim: {r}')
r = c.execute('SELECT COUNT(*) FROM companies WHERE company_name IN ("ISTANBUL","ANKARA","IZMIR","BURSA","ANTALYA","ADANA","KONYA")').fetchone()[0]
print(f'  Sehir ismi olan: {r}')
r = c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NULL OR sector = ""').fetchone()[0]
print(f'  Sektoru bos: {r}')
r = c.execute('SELECT COUNT(*) FROM companies WHERE market IS NULL OR market = ""').fetchone()[0]
print(f'  Piyasasi bos: {r}')

# 2. Financials
print('\n2. FINANCIALS')
r = c.execute('SELECT COUNT(*) FROM financials WHERE revenue IS NULL OR revenue = 0').fetchone()[0]
print(f'  Hasilati bos/sifir: {r}')
r = c.execute('SELECT COUNT(*) FROM financials WHERE net_profit IS NULL').fetchone()[0]
print(f'  Net kar bos: {r}')
r = c.execute('SELECT COUNT(*) FROM financials WHERE total_assets IS NULL OR total_assets = 0').fetchone()[0]
print(f'  Toplam aktif bos: {r}')
r = c.execute('SELECT COUNT(*) FROM financials WHERE equity IS NULL OR equity = 0').fetchone()[0]
print(f'  Ozkaynak bos: {r}')
r = c.execute('SELECT COUNT(*) FROM financials WHERE ebitda IS NULL OR ebitda = 0').fetchone()[0]
print(f'  EBITDA bos: {r}')
r = c.execute('SELECT COUNT(*) FROM financials WHERE gross_profit IS NULL OR gross_profit = 0').fetchone()[0]
print(f'  Brut kar bos: {r}')

# 3. BIST Prices
print('\n3. BIST FIYAT')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE pe_ratio IS NULL OR pe_ratio = 0').fetchone()[0]
total = c.execute('SELECT COUNT(*) FROM bist_stock_prices').fetchone()[0]
print(f'  PE bos: {r}/{total}')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE pb_ratio IS NULL OR pb_ratio = 0').fetchone()[0]
print(f'  PB bos: {r}/{total}')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE price <= 0').fetchone()[0]
print(f'  Fiyat <= 0: {r}')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE market_cap IS NULL OR market_cap = 0').fetchone()[0]
print(f'  Market cap bos: {r}')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE dividend_yield IS NULL OR dividend_yield = 0').fetchone()[0]
print(f'  Temettu verimi bos: {r}')
r = c.execute('SELECT COUNT(*) FROM bist_stock_prices WHERE volume IS NULL OR volume = 0').fetchone()[0]
print(f'  Hacim bos: {r}')

# 4. Disclosures
print('\n4. BILDIRIMLER')
cols = [row[1] for row in c.execute('PRAGMA table_info(disclosures)').fetchall()]
print(f'  Sutunlar: {cols}')
for col in ['symbol', 'ticker', 'stock_code', 'company_id']:
    if col in cols:
        r = c.execute(f'SELECT COUNT(*) FROM disclosures WHERE {col} IS NULL OR {col} = ""').fetchone()[0]
        print(f'  {col} bos: {r}')
if 'category' in cols:
    r = c.execute('SELECT COUNT(*) FROM disclosures WHERE category IS NULL OR category = ""').fetchone()[0]
    print(f'  Kategori bos: {r}')

# 5. TEFAS
print('\n5. TEFAS')
r = c.execute('SELECT COUNT(*) FROM tefas_funds WHERE fund_group IS NULL OR fund_group = ""').fetchone()[0]
print(f'  Fon grubu bos: {r}')
r = c.execute('SELECT COUNT(*) FROM tefas_fund_prices WHERE price <= 0').fetchone()[0]
print(f'  Fiyat <= 0: {r}')
r = c.execute('SELECT COUNT(*) FROM tefas_fund_prices WHERE market_cap IS NULL OR market_cap <= 0').fetchone()[0]
print(f'  Market cap bos/negatif: {r}')
try:
    r = c.execute('SELECT COUNT(*) FROM tefas_fund_prices WHERE number_of_investors IS NULL OR number_of_investors = 0').fetchone()[0]
    print(f'  Yatirimci sayisi bos: {r}')
except:
    print('  Yatirimci sutunu yok')

# 6. Price History
print('\n6. FIYAT GECMISI')
try:
    r = c.execute('SELECT COUNT(DISTINCT ticker) FROM bist_price_history').fetchone()[0]
    r2 = c.execute('SELECT COUNT(*) FROM bist_price_history').fetchone()[0]
    print(f'  Ticker: {r}, Toplam: {r2}')
except Exception as e:
    print(f'  Hata: {e}')

# 7. Anomaliler
print('\n7. ANOMALILER')
r = c.execute('SELECT ticker, price FROM bist_stock_prices WHERE price > 10000 ORDER BY price DESC LIMIT 10').fetchall()
print(f'  Yuksek fiyatli (>10000 TL): {len(r)} tane')
for t, p in r:
    print(f'    {t}: {p} TL')

r = c.execute('SELECT ticker, pe_ratio FROM bist_stock_prices WHERE pe_ratio > 500 OR pe_ratio < 0').fetchall()
print(f'  Anormal PE (>500 veya negatif): {len(r)} tane')
for t, p in r[:5]:
    print(f'    {t}: PE={p}')

r = c.execute('SELECT ticker, pb_ratio FROM bist_stock_prices WHERE pb_ratio > 50 OR pb_ratio < 0').fetchall()
print(f'  Anormal PB (>50 veya negatif): {len(r)} tane')

# 8. Sehir isimleri
print('\n8. SEHIR ISMI OLAN SIRKETLER')
r = c.execute('SELECT ticker, company_name FROM companies WHERE company_name IN ("ISTANBUL","ANKARA","IZMIR","BURSA","ANTALYA","ADANA","KONYA")').fetchall()
for t, n in r:
    print(f'  {t}: {n}')

# 9. Eksik sektor
print('\n9. SEKTORSUZ SIRKETLER (ilk 15)')
r = c.execute('SELECT ticker, company_name FROM companies WHERE sector IS NULL OR sector = "" LIMIT 15').fetchall()
for t, n in r:
    print(f'  {t}: {n}')

# 10. Eksik PE
print('\n10. PE OLMAYAN SIRKETLER (en yuksek fiyatli)')
r = c.execute('''SELECT b.ticker, c.company_name, b.price 
    FROM bist_stock_prices b 
    LEFT JOIN companies c ON b.ticker = c.ticker 
    WHERE b.pe_ratio IS NULL OR b.pe_ratio = 0 
    ORDER BY b.price DESC LIMIT 10''').fetchall()
for t, n, p in r:
    print(f'  {t} ({n}): {p} TL')

# 11. Sifir degerler
print('\n11. SIFIR/NULL DEGERLER')
for table, col in [('financials', 'gross_profit'), ('financials', 'ebitda'), 
                     ('financials', 'net_debt'), ('financials', 'leverage_ratio'),
                     ('cash_flows', 'operating_cf'), ('cash_flows', 'investing_cf'),
                     ('cash_flows', 'financing_cf')]:
    try:
        r = c.execute(f'SELECT COUNT(*) FROM [{table}] WHERE [{col}] IS NULL OR [{col}] = 0').fetchone()[0]
        total = c.execute(f'SELECT COUNT(*) FROM [{table}]').fetchone()[0]
        if r > 0:
            print(f'  {table}.{col}: {r}/{total} bos')
    except:
        pass

# 12. Buffett API test
print('\n12. BUFFETT API TEST')
try:
    r = requests.get('http://localhost:3000/api/buffett/THYAO', timeout=15)
    d = r.json()
    print(f'  THYAO Skor: {d.get("buffett_score")}/100 - {d.get("rating")}')
    print(f'  Fiyat: {d.get("price")} TL')
    dcf = d.get('dcf', {})
    print(f'  Ic Deger: {dcf.get("intrinsic_per_share")} TL')
    print(f'  Guvenli Marj: {d.get("safety_margin")}%')
    oe = d.get('owner_earnings', {})
    print(f'  Owner Earnings: {oe.get("value")}')
except Exception as e:
    print(f'  HATA: {e}')

# 13. Teknik analiz test
print('\n13. TEKNIK ANALIZ TEST')
try:
    r = requests.get('http://localhost:3000/api/technical-extended/THYAO?period=3mo', timeout=15)
    d = r.json()
    ind = d.get('indicators', {})
    sig = d.get('signal_summary', {})
    print(f'  RSI: {ind.get("rsi", {}).get("value")}')
    print(f'  MACD: {ind.get("macd", {}).get("histogram")}')
    print(f'  ADX: {ind.get("adx", {}).get("value")}')
    print(f'  Stoch K: {ind.get("stochastic", {}).get("k")}')
    print(f'  CCI: {ind.get("cci", {}).get("value")}')
    print(f'  Williams: {ind.get("williams_r", {}).get("value")}')
    print(f'  Aroon Up: {ind.get("aroon", {}).get("up")}')
    print(f'  Sinyal: {sig.get("overall")} (AL:{sig.get("buy_count")} SAT:{sig.get("sell_count")})')
except Exception as e:
    print(f'  HATA: {e}')

# 14. Makro veri test
print('\n14. MAKRO VERI TEST')
try:
    r = requests.get('http://localhost:3000/api/macro/inflation', timeout=10)
    d = r.json()
    data = d.get('data', [])
    print(f'  Enflasyon kayit: {len(data)}')
    if data:
        print(f'  Son TUYE: {data[0]}')
except Exception as e:
    print(f'  HATA: {e}')

# 15. Takvim test
print('\n15. TAKVIM TEST')
try:
    r = requests.get('http://localhost:3000/api/macro/calendar?country=tr', timeout=15)
    d = r.json()
    events = d.get('events', [])
    print(f'  Olay sayisi: {len(events)}')
    if events:
        print(f'  Son olay: {events[0].get("event", "?")} - {events[0].get("impact", "?")}')
except Exception as e:
    print(f'  HATA: {e}')

db.close()
print('\n' + '=' * 60)
print('DENETIM TAMAMLANDI')
print('=' * 60)
