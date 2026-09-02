"""
Kalani TEXT sutunlarini NUMERIC'e cevir + buyuk deger sorununu coz.
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import psycopg2

PG = {'host':'localhost','port':5432,'database':'finance_platform','user':'admin','password':'admin123'}
conn = psycopg2.connect(**PG)
conn.autocommit = True
c = conn.cursor()

def clean_text(col):
    """Bozuk byte'lari temizle."""
    c.execute(f'SELECT id, "{col}" FROM financials WHERE "{col}" IS NOT NULL')
    rows = c.fetchall()
    fixed = 0
    for rid, val in rows:
        if not val:
            continue
        clean = re.sub(r'[^\x20-\x7E]', '', val)
        if clean != val:
            c.execute(f'UPDATE financials SET "{col}" = %s WHERE id = %s', (clean, rid))
            fixed += 1
    return fixed

# 1. Buyuk finansal sütunlari temizle ve cevir
big_cols = ['revenue', 'gross_profit', 'total_assets', 'short_term_debt', 
            'long_term_debt', 'total_debt', 'equity', 'paid_capital',
            'current_assets', 'non_current_assets', 'net_debt']

print("1. Bosluk/bozuk temizligi...")
for col in big_cols:
    f = clean_text(col)
    if f > 0:
        print(f"  {col}: {f} hucre temizlendi")

# 2. Cevirme - NUMERIC sinirsiz kullan
print("\n2. Tip degisikligi...")
for col in big_cols:
    try:
        c.execute(f'ALTER TABLE financials ALTER COLUMN "{col}" TYPE NUMERIC USING "{col}"::NUMERIC')
        print(f"  {col} -> NUMERIC OK")
    except Exception as e:
        conn.rollback()
        print(f"  {col} HATA: {str(e)[:60]}")

# ebitda_margin icin buyuk precision
try:
    clean_text('ebitda_margin')
    c.execute('ALTER TABLE financials ALTER COLUMN "ebitda_margin" TYPE NUMERIC USING "ebitda_margin"::NUMERIC')
    print("  ebitda_margin -> NUMERIC OK")
except Exception as e:
    conn.rollback()
    print(f"  ebitda_margin HATA: {str(e)[:60]}")

try:
    c.execute('ALTER TABLE kap_financials ALTER COLUMN "ebitda_margin" TYPE NUMERIC USING "ebitda_margin"::NUMERIC')
    print("  kap_financials.ebitda_margin -> NUMERIC OK")
except Exception as e:
    conn.rollback()
    print(f"  kap_financials.ebitda_margin HATA: {str(e)[:60]}")

# 3. Dogrulama
print("\n3. Dogrulama...")
c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='financials' AND data_type IN ('numeric','double precision') ORDER BY column_name")
num_cols = c.fetchall()
print(f"  financials sayisal sutun: {len(num_cols)}")

c.execute("SELECT COUNT(*) FROM financials WHERE revenue > 0")
r = c.fetchone()[0]
print(f"  revenue > 0: {r} satir")

c.execute("SELECT COUNT(*) FROM financials WHERE total_assets > 0")
r = c.fetchone()[0]
print(f"  total_assets > 0: {r} satir")

c.execute("SELECT COUNT(*) FROM financials WHERE equity > 0")
r = c.fetchone()[0]
print(f"  equity > 0: {r} satir")

conn.close()
print("\nTamamlandi!")
