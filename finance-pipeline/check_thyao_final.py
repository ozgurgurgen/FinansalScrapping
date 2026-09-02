import psycopg2, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
conn = psycopg2.connect('postgresql://admin:admin123@localhost:5432/finance_platform')
c = conn.cursor()

print('=== THYAO FINAL DURUM ===')
c.execute('SELECT company_name, sector FROM kap_companies WHERE id=681')
r = c.fetchone()
print(f'Sirket: {r[0]}, Sector: {r[1]}')

c.execute('''SELECT year, period, pe_ratio, pb_ratio, current_assets, cash_and_equivalents, 
  financial_debt, gross_margin, net_margin, ebitda_margin, ev_ebitda, revenue, net_profit
FROM kap_financials WHERE company_id=681 ORDER BY year DESC, period DESC''')
print('\nFinansal Veriler:')
for row in c.fetchall():
    print(f'  {row[0]}-{row[1]}: PE={row[2]}, PB={row[3]}, Rev={row[11]}, NP={row[12]}')
    print(f'    CA={row[4]}, Cash={row[5]}, FDebt={row[6]}')
    print(f'    GM={row[7]}, NM={row[8]}, EM={row[9]}, EV/EBITDA={row[10]}')

c.execute('SELECT COUNT(*) FROM kap_disclosures WHERE company_id=681')
print(f'\nBildirimler: {c.fetchone()[0]}')
c.execute('SELECT title, publish_date FROM kap_disclosures WHERE company_id=681 ORDER BY publish_date DESC LIMIT 5')
for row in c.fetchall():
    print(f'  {row[1]}: {str(row[0])[:60]}')

for tbl, label in [('kap_shareholders','Ortaklar'), ('kap_management','Yonetim'), ('kap_subsidiaries','Bagli Ortakliklar')]:
    c.execute('SELECT COUNT(*) FROM ' + tbl + ' WHERE company_id=681')
    print(f'{label}: {c.fetchone()[0]}')

c.execute('''SELECT year, period, operating_cash_flow, investing_cash_flow, financing_cash_flow
FROM kap_cashflows WHERE company_id=681 ORDER BY year DESC, period DESC''')
print('\nNakit Akis:')
for row in c.fetchall():
    print(f'  {row[0]}-{row[1]}: OpCF={row[2]}, InvCF={row[3]}, FinCF={row[4]}')

c.execute('SELECT price, market_cap, pb_ratio, volume, week52_high, week52_low, dividend_yield FROM bist_stock_prices WHERE ticker=%s', ('THYAO',))
bsp = c.fetchone()
if bsp:
    print(f'\nPiyasa: Fiyat={bsp[0]}, Piyasa Degeri={bsp[1]}, PB={bsp[2]}, Hacim={bsp[3]}, 52H={bsp[4]}, 52L={bsp[5]}, Div={bsp[6]}')

print('\n=== GENEL ===')
c.execute('SELECT COUNT(*) FROM kap_disclosures')
print(f'Toplam Bildirim: {c.fetchone()[0]}')
c.execute('SELECT COUNT(DISTINCT company_id) FROM kap_disclosures WHERE company_id IS NOT NULL')
print(f'Bildirim olan sirket: {c.fetchone()[0]}')

c.execute('''SELECT 
    COUNT(*) FILTER (WHERE current_assets IS NULL) as ca,
    COUNT(*) FILTER (WHERE cash_and_equivalents IS NULL) as cash,
    COUNT(*) FILTER (WHERE pe_ratio IS NULL OR pe_ratio = 0) as pe,
    COUNT(*) FROM kap_financials''')
ov = c.fetchone()
print(f'CA: {ov[3]-ov[0]}/{ov[3]} ({100*(ov[3]-ov[0])//ov[3]}%)')
print(f'Cash: {ov[3]-ov[1]}/{ov[3]} ({100*(ov[3]-ov[1])//ov[3]}%)')
print(f'PE: {ov[3]-ov[2]}/{ov[3]} ({100*(ov[3]-ov[2])//ov[3]}%)')

conn.close()
