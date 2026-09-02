"""Tum null verileri teshis eden kapsali script."""
import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'
db = psycopg2.connect(DB)
c = db.cursor()

# 1. Disclosures
c.execute("SELECT COUNT(*) FROM kap_disclosures WHERE company_id IS NULL OR company_id = 0")
boş_disc = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM kap_disclosures")
top_disc = c.fetchone()[0]
c.execute("SELECT symbol, COUNT(*) FROM kap_disclosures WHERE symbol IS NOT NULL AND symbol != '' GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 10")
print(f'=== DISCLOSURES === {top_disc} toplam, {boş_disc} bos company_id')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Check disclosure_details
c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='kap_disclosure_details' ORDER BY ordinal_position")
dd_cols = [r[0] for r in c.fetchall()]
print(f'\nDisclosure details columns: {dd_cols}')

if 'ticker' in dd_cols or 'symbol' in dd_cols:
    col = 'ticker' if 'ticker' in dd_cols else 'symbol'
    c.execute(f"SELECT COUNT(*) FROM kap_disclosure_details WHERE {col} IS NULL OR {col} = ''")
    bos_dd = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kap_disclosure_details")
    top_dd = c.fetchone()[0]
    print(f'Disclosure details: {top_dd} toplam, {bos_dd} bos {col}')

# 2. Shareholders
c.execute("SELECT COUNT(*) FROM kap_shareholders WHERE company_id IS NULL OR company_id = 0")
bos_sh = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM kap_shareholders")
top_sh = c.fetchone()[0]
print(f'\n=== SHAREHOLDERS === {top_sh} toplam, {bos_sh} bos company_id')

if top_sh > 0:
    c.execute("SELECT * FROM kap_shareholders LIMIT 2")
    for r in c.fetchall():
        cols = [d[0] for d in c.description]
        print(f'  Sample: company_id={r[cols.index("company_id")]}, name={r[cols.index("holder_name")]}, ratio={r[cols.index("share_ratio_percent")]}')

# 3. Management
c.execute("SELECT COUNT(*) FROM kap_management WHERE company_id IS NULL OR company_id = 0")
bos_mgmt = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM kap_management")
top_mgmt = c.fetchone()[0]
print(f'\n=== MANAGEMENT === {top_mgmt} toplam, {bos_mgmt} bos company_id')

if top_mgmt > 0:
    c.execute("SELECT * FROM kap_management LIMIT 2")
    for r in c.fetchall():
        cols = [d[0] for d in c.description]
        print(f'  Sample: company_id={r[cols.index("company_id")]}, name={r[cols.index("name")]}, title={r[cols.index("title")]}')

# 4. Subsidiaries
c.execute("SELECT COUNT(*) FROM kap_subsidiaries WHERE company_id IS NULL OR company_id = 0")
bos_sub = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM kap_subsidiaries")
top_sub = c.fetchone()[0]
print(f'\n=== SUBSIDIARIES === {top_sub} toplam, {bos_sub} bos company_id')

# 5. Financials null stats
c.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(current_assets) as ca, COUNT(cash_and_equivalents) as cash,
        COUNT(financial_debt) as debt, COUNT(pe_ratio) as pe,
        COUNT(roe) as roe, COUNT(gross_margin) as gm,
        COUNT(ebitda_margin) as em, COUNT(equity) as eq,
        COUNT(leverage_ratio) as lev, COUNT(total_debt) as td,
        COUNT(net_debt) as nd
    FROM kap_financials
""")
s = c.fetchone()
print(f'\n=== FINANCIALS ({s[0]} kayit) ===')
for i, name in enumerate(['current_assets', 'cash', 'financial_debt', 'pe_ratio', 'roe', 'gross_margin', 'ebitda_margin', 'equity', 'leverage', 'total_debt', 'net_debt'], 1):
    pct = int(s[i]*100/s[0]) if s[0]>0 else 0
    print(f'  {name}: {s[i]}/{s[0]} (%{pct})')

# 6. Cashflows null stats
c.execute("""
    SELECT COUNT(*) as total,
        COUNT(depreciation) as dep, COUNT(investing_cash_flow) as icf,
        COUNT(financing_cash_flow) as fcf, COUNT(capex) as cap,
        COUNT(net_change) as nc, COUNT(closing_cash) as cc,
        COUNT(provisions) as prov
    FROM kap_cashflows
""")
s = c.fetchone()
print(f'\n=== CASHFLOWS ({s[0]} kayit) ===')
for i, name in enumerate(['depreciation', 'investing_cf', 'financing_cf', 'capex', 'net_change', 'closing_cash', 'provisions'], 1):
    pct = int(s[i]*100/s[0]) if s[0]>0 else 0
    print(f'  {name}: {s[i]}/{s[0]} (%{pct})')

# 7. Stock prices
c.execute("SELECT COUNT(*) FROM bist_stock_prices")
top_sp = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT ticker) FROM bist_stock_prices")
tickers_sp = c.fetchone()[0]
print(f'\n=== BIST STOCK PRICES === {top_sp} kayit, {tickers_sp} farkli ticker')

# 8. Companies sector
c.execute("SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ''")
sec_ok = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM kap_companies")
top_comp = c.fetchone()[0]
print(f'\n=== COMPANIES === {top_comp} toplam, {sec_ok} sektorlu ({int(sec_ok*100/top_comp) if top_comp else 0}%)')

# 9. Price history
c.execute("SELECT COUNT(*) FROM bist_price_history")
print(f'\n=== PRICE HISTORY === {c.fetchone()[0]} kayit')

# 10. Settlement
c.execute("SELECT COUNT(*) FROM kap_settlement")
print(f'=== SETTLEMENT === {c.fetchone()[0]} kayit')

# 11. Index
c.execute("SELECT COUNT(*) FROM kap_index")
print(f'=== INDEX === {c.fetchone()[0]} kayit')

# 12. Buybacks
c.execute("SELECT COUNT(*) FROM kap_buybacks")
print(f'=== BUYBACKS === {c.fetchone()[0]} kayit')

# 13. IPO
c.execute("SELECT COUNT(*) FROM kap_ipo")
print(f'=== IPO === {c.fetchone()[0]} kayit')

# 14. Corporate actions
c.execute("SELECT COUNT(*) FROM kap_corporate_actions")
print(f'=== CORPORATE ACTIONS === {c.fetchone()[0]} kayit')

# 15. TEFAS
c.execute("SELECT COUNT(*) FROM tefas_funds")
print(f'=== TEFAS FUNDS === {c.fetchone()[0]} kayit')
c.execute("SELECT COUNT(*) FROM tefas_fund_prices")
print(f'=== TEFAS PRICES === {c.fetchone()[0]} kayit')

# 16. Check THYAO specifically
c.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
thyao = c.fetchone()
if thyao:
    tid = thyao[0]
    print(f'\n=== THYAO DETAY (id={tid}) ===')
    for tbl in ['kap_disclosures', 'kap_shareholders', 'kap_management', 'kap_subsidiaries', 'kap_financials', 'kap_cashflows']:
        c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE company_id=%s", (tid,))
        print(f'  {tbl}: {c.fetchone()[0]}')
    c.execute("SELECT COUNT(*) FROM bist_stock_prices WHERE ticker='THYAO'")
    print(f'  bist_stock_prices: {c.fetchone()[0]}')

# 17. Disclosure by category
c.execute("SELECT category, COUNT(*) FROM kap_disclosures GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10")
print(f'\n=== DISCLOSURE KATEGORILERI ===')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

db.close()
print('\n=== TESHIS TAMAMLANDI ===')
