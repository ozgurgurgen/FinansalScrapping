"""
PE/PB/EV Oranlarını market_cap + financials ile hesapla
"""
import sys, io, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

db = sqlite3.connect('finance.db', timeout=10)
c = db.cursor()

# 1. First fill PE/PB in bist_stock_prices using financials
print("=== PE/PB/EV HESAPLAMA ===")

# Get annual financials (period=12 or latest)
c.execute("""
    SELECT f.company_id, f.ticker, f.net_profit, f.equity, f.ebitda, f.total_debt, f.total_assets, f.paid_capital, f.year, f.period
    FROM financials f
    INNER JOIN (
        SELECT company_id, MAX(year * 100 + period) as max_per
        FROM financials GROUP BY company_id
    ) latest ON f.company_id = latest.company_id AND (f.year * 100 + f.period) = latest.max_per
    WHERE f.net_profit IS NOT NULL OR f.equity IS NOT NULL
""")
fin_data = {}
for row in c.fetchall():
    cid, ticker, np, eq, ebitda, td, ta, pc, yr, per = row
    fin_data[cid] = {
        'ticker': ticker, 'net_profit': np, 'equity': eq, 'ebitda': ebitda,
        'total_debt': td, 'total_assets': ta, 'paid_capital': pc,
        'year': yr, 'period': per
    }

print(f"Finansal veri olan şirket: {len(fin_data)}")

# 2. Update bist_stock_prices with calculated ratios
c.execute("SELECT ticker, price, market_cap FROM bist_stock_prices WHERE price > 0")
prices = c.fetchall()
print(f"Güncellenecek fiyat: {len(prices)}")

updated_pe = 0
updated_pb = 0
updated_ev = 0

for ticker, price, mcap in prices:
    # Find matching financials
    c.execute("SELECT id FROM companies WHERE ticker = ?", (ticker,))
    row = c.fetchone()
    if not row:
        continue
    cid = row[0]
    if cid not in fin_data:
        continue
    
    fd = fin_data[cid]
    
    # PE = market_cap / annual_net_profit
    pe = None
    if fd['net_profit'] and fd['net_profit'] > 0 and mcap and mcap > 0:
        pe = round(mcap / fd['net_profit'], 2)
        if pe > 500 or pe < 0:
            pe = None
    
    # PB = market_cap / equity
    pb = None
    if fd['equity'] and fd['equity'] > 0 and mcap and mcap > 0:
        pb = round(mcap / fd['equity'], 2)
        if pb > 100 or pb < 0:
            pb = None
    
    # EV = market_cap + total_debt - cash (cash=0 for now, so EV ≈ market_cap + debt)
    ev = None
    ev_ebitda = None
    if mcap and mcap > 0:
        debt = fd['total_debt'] or 0
        ev = mcap + debt
        if fd['ebitda'] and fd['ebitda'] > 0:
            ev_ebitda = round(ev / fd['ebitda'], 2)
            if ev_ebitda > 500 or ev_ebitda < 0:
                ev_ebitda = None
    
    # Update
    if pe or pb or ev_ebitda:
        c.execute("""
            UPDATE bist_stock_prices 
            SET pe_ratio = COALESCE(?, pe_ratio),
                pb_ratio = COALESCE(?, pb_ratio)
            WHERE ticker = ?
        """, (pe, pb, ticker))
        if pe: updated_pe += 1
        if pb: updated_pb += 1
    
    # Also update financials with PE/PB
    if pe or pb or ev_ebitda:
        c.execute("""
            UPDATE financials
            SET pe_ratio = COALESCE(?, pe_ratio),
                pb_ratio = COALESCE(?, pb_ratio),
                ev_ebitda = COALESCE(?, ev_ebitda)
            WHERE company_id = ? AND year = ? AND period = ?
        """, (pe, pb, ev_ebitda, cid, fd['year'], fd['period']))
        if ev_ebitda: updated_ev += 1

db.commit()

print(f"\n=== SONUÇ ===")
print(f"PE güncellenen: {updated_pe}")
print(f"PB güncellenen: {updated_pb}")
print(f"EV/EBITDA güncellenen: {updated_ev}")

# Verify
c.execute("SELECT COUNT(*) FROM bist_stock_prices WHERE pe_ratio > 0")
print(f"\nPE dolu: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM bist_stock_prices WHERE pb_ratio > 0")
print(f"PB dolu: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM financials WHERE ev_ebitda > 0")
print(f"EV/EBITDA dolu: {c.fetchone()[0]}")

# Sample
c.execute("SELECT ticker, price, pe_ratio, pb_ratio FROM bist_stock_prices WHERE pe_ratio > 0 AND pb_ratio > 0 LIMIT 5")
print("\nÖrnek:")
for r in c.fetchall():
    print(f"  {r[0]:10s} Fiyat:{r[1]:>8.2f}  F/K:{r[2]:>8.2f}  PD/DD:{r[3]:>6.2f}")

db.close()
