"""
Düzelt: TEXT sütunlarını geri al + büyük finansal veriler için precision artır.
"""
import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PG = {'host':'localhost','port':5432,'database':'finance_platform','user':'admin','password':'admin123'}
conn = psycopg2.connect(**PG)
c = conn.cursor()

# 1. TEXT olarak kalması gereken sütunlar (metin içerikli)
TEXT_COLS = [
    ('assets', 'asset_code'), ('assets', 'asset_type'),
    ('companies', 'mkk_id'), ('companies', 'index_group'),
    ('kap_companies', 'mkk_id'),
    ('index_constituents', 'index_name'),
    ('tefas_funds', 'fund_group'), ('tefas_funds', 'fund_sub_type'),
    ('tefas_funds', 'last_price_fetch'),
    ('fund_stock_holdings', 'fund_code'),
    ('fund_stock_holdings', 'fund_name'),
    ('fund_stock_holdings', 'stock_ticker'),
    ('test_companies', 'mkk_id'),
    ('kap_subsidiaries', 'country'), ('subsidiaries', 'country'),
    ('portfolio_reports', 'report_date'),
    ('fund_stock_holdings', 'stock_name'),  # hisse adı, sayı değil
]

print("=== TEXT'e geri alınıyor ===")
for tbl, col in TEXT_COLS:
    try:
        c.execute(f'ALTER TABLE "{tbl}" ALTER COLUMN "{col}" TYPE TEXT')
        conn.commit()
        print(f"  {tbl}.{col} -> TEXT OK")
    except Exception as e:
        conn.rollback()
        print(f"  {tbl}.{col} HATA: {str(e)[:60]}")

# 2. Büyük finansal veriler için NUMERIC precision artır
print("\n=== Büyük finansal sütunlar genişletiliyor ===")
BIG_COLS = [
    ('financials', 'revenue'), ('financials', 'gross_profit'),
    ('financials', 'ebit'), ('financials', 'net_profit'),
    ('financials', 'current_assets'), ('financials', 'non_current_assets'),
    ('financials', 'total_assets'), ('financials', 'short_term_debt'),
    ('financials', 'long_term_debt'), ('financials', 'total_debt'),
    ('financials', 'equity'), ('financials', 'paid_capital'),
    ('financials', 'net_debt'),
    ('kap_financials', 'revenue'), ('kap_financials', 'gross_profit'),
    ('kap_financials', 'ebit'), ('kap_financials', 'net_profit'),
    ('kap_financials', 'total_assets'), ('kap_financials', 'total_debts'),
    ('kap_financials', 'equity'), ('kap_financials', 'paid_capital'),
    ('kap_financials', 'current_assets'), ('kap_financials', 'total_debt'),
    ('kap_financials', 'net_debt'),
]

for tbl, col in BIG_COLS:
    try:
        c.execute(f'ALTER TABLE "{tbl}" ALTER COLUMN "{col}" TYPE NUMERIC(20,4)')
        conn.commit()
        print(f"  {tbl}.{col} -> NUMERIC(20,4) OK")
    except Exception as e:
        conn.rollback()
        print(f"  {tbl}.{col} HATA: {str(e)[:60]}")

# 3. ebitda_margin için更大 precision
MARGIN_COLS = [
    ('financials', 'ebitda_margin'), ('kap_financials', 'ebitda_margin'),
]
for tbl, col in MARGIN_COLS:
    try:
        c.execute(f'ALTER TABLE "{tbl}" ALTER COLUMN "{col}" TYPE NUMERIC(14,6)')
        conn.commit()
        print(f"  {tbl}.{col} -> NUMERIC(14,6) OK")
    except Exception as e:
        conn.rollback()
        print(f"  {tbl}.{col} HATA: {str(e)[:60]}")

conn.close()
print("\nTamamlandı!")
