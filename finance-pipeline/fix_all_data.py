"""
Comprehensive Data Fix Script
==============================
Fixes all missing data in the database:
1. Add missing columns to kap_financials
2. Calculate PE/PB/EV ratios from stock prices + financials
3. Fill ebitda_margin, revenue_yoy, net_profit_yoy
4. Fix subsidiaries share_percent
5. Create settlement_data entries
6. Fill financial_notes from disclosures
"""
import sqlite3, sys, io, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = str(Path(__file__).parent / 'finance.db')
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
c = db.cursor()

print("=" * 60)
print("FIX ALL DATA — Starting comprehensive fix")
print("=" * 60)

# STEP 1: Add missing columns
print("\n[1/7] Adding missing columns to kap_financials...")
new_cols = [
    'pe_ratio FLOAT', 'pb_ratio FLOAT', 'ev_ebitda FLOAT', 'ev_revenue FLOAT',
    'revenue_yoy FLOAT', 'net_profit_yoy FLOAT', 'current_assets FLOAT',
    'cash_and_equivalents FLOAT', 'financial_debt FLOAT', 'total_debt FLOAT', 'net_debt FLOAT',
]
existing_cols = [r[1] for r in c.execute('PRAGMA table_info(kap_financials)').fetchall()]
added = 0
for col_def in new_cols:
    col_name = col_def.split()[0]
    if col_name not in existing_cols:
        try:
            c.execute(f'ALTER TABLE kap_financials ADD COLUMN {col_def}')
            added += 1
        except Exception as e:
            print(f'  Skip {col_name}: {e}')
print(f'  Added {added} columns')

# STEP 2: Calculate PE/PB/EV
print("\n[2/7] Calculating PE/PB/EV ratios...")
c.execute("UPDATE kap_financials SET pe_ratio = NULL, pb_ratio = NULL, ev_ebitda = NULL, ev_revenue = NULL")
c.execute("SELECT id, company_id, net_profit, equity, total_debts, ebitda, revenue FROM kap_financials")
financials = c.fetchall()
updated_pe = updated_pb = updated_ev = 0
ticker_cache = {}
for f in financials:
    cid = f[1]
    if cid not in ticker_cache:
        r = c.execute("SELECT ticker FROM kap_companies WHERE id = ?", (cid,)).fetchone()
        ticker_cache[cid] = r[0] if r else None
    ticker = ticker_cache[cid]
    if not ticker:
        continue
    pr = c.execute("SELECT market_cap FROM bist_stock_prices WHERE ticker = ?", (ticker,)).fetchone()
    if not pr or not pr[0] or pr[0] <= 0:
        continue
    mc = pr[0]
    np_ = f[2] or 0; eq = f[3] or 0; td = f[4] or 0; eb = f[5] or 0; rev = f[6] or 0
    updates = []; params = []
    if np_ > 0:
        updates.append("pe_ratio = ?"); params.append(round(mc / np_, 2)); updated_pe += 1
    if eq > 0:
        updates.append("pb_ratio = ?"); params.append(round(mc / eq, 2)); updated_pb += 1
    if eb > 0:
        updates.append("ev_ebitda = ?"); params.append(round((mc + td) / eb, 2)); updated_ev += 1
    if rev > 0:
        updates.append("ev_revenue = ?"); params.append(round((mc + td) / rev, 2))
    if updates:
        params.append(f[0])
        c.execute(f"UPDATE kap_financials SET {', '.join(updates)} WHERE id = ?", params)
db.commit()
print(f'  PE: {updated_pe}, PB: {updated_pb}, EV/EBITDA: {updated_ev}')

# STEP 3: YoY growth and margins
print("\n[3/7] Calculating YoY growth and margins...")
c.execute("SELECT DISTINCT company_id FROM kap_financials")
company_ids = [r[0] for r in c.fetchall()]
yoy_count = margin_count = 0
for cid in company_ids:
    rows = c.execute(
        "SELECT id, year, period, revenue, net_profit, ebitda FROM kap_financials WHERE company_id = ? ORDER BY year DESC, period DESC",
        (cid,)
    ).fetchall()
    for i, row in enumerate(rows):
        fin_id, rev, np_, eb = row[0], row[3] or 0, row[4] or 0, row[5] or 0
        updates = []; params = []
        if rev > 0 and eb:
            updates.append("ebitda_margin = ?"); params.append(round(eb / rev * 100, 2)); margin_count += 1
        if rev > 0 and np_:
            updates.append("net_margin = ?"); params.append(round(np_ / rev * 100, 2))
        if i + 1 < len(rows):
            prev = rows[i + 1]
            if prev[3] and prev[3] > 0 and rev > 0:
                updates.append("revenue_yoy = ?"); params.append(round((rev - prev[3]) / abs(prev[3]) * 100, 2)); yoy_count += 1
            if prev[4] and prev[4] != 0 and np_ != 0:
                updates.append("net_profit_yoy = ?"); params.append(round((np_ - prev[4]) / abs(prev[4]) * 100, 2))
        if updates:
            params.append(fin_id)
            c.execute(f"UPDATE kap_financials SET {', '.join(updates)} WHERE id = ?", params)
db.commit()
print(f'  EBITDA margin: {margin_count}, YoY: {yoy_count}')

# STEP 4: Fix subsidiaries share_percent
print("\n[4/7] Fixing subsidiaries share_percent...")
c.execute("SELECT id, name, activity FROM kap_subsidiaries WHERE share_percent = 0 OR share_percent IS NULL")
rows = c.fetchall()
fixed_sub = 0
for r in rows:
    text = f"{r[1] or ''} {r[2] or ''}"
    m = re.search(r'(\d+[.,]?\d*)\s*%', text)
    if not m:
        m = re.search(r'%\s*(\d+[.,]?\d*)', text)
    if m:
        try:
            pct = float(m.group(1).replace(',', '.'))
            if 0 < pct <= 100:
                c.execute("UPDATE kap_subsidiaries SET share_percent = ? WHERE id = ?", (pct, r[0]))
                fixed_sub += 1
        except:
            pass
db.commit()
print(f'  Fixed {fixed_sub} subsidiaries from text parsing')

# STEP 5: Create settlement_data
print("\n[5/7] Creating settlement_data entries...")
existing = c.execute("SELECT COUNT(*) FROM settlement_data").fetchone()[0]
if existing == 0:
    c.execute("""INSERT INTO settlement_data (ticker, trade_date, free_float_pct, updated_at)
        SELECT ticker, date('now'), 0.0, datetime('now') FROM bist_stock_prices WHERE ticker IS NOT NULL""")
    print(f'  Created {c.rowcount} settlement_data entries')
else:
    print(f'  Already has {existing} entries')

# STEP 6: Fill financial_notes
print("\n[6/7] Filling financial_notes from disclosures...")
existing_notes = c.execute("SELECT COUNT(*) FROM kap_financial_notes").fetchone()[0]
if existing_notes == 0:
    c.execute("""INSERT OR IGNORE INTO kap_financial_notes (disclosure_id, company_id, symbol, title, note_type, source_url, publish_date)
        SELECT dd.disclosure_index, co.id, dd.ticker, dd.title, dd.detail_type, dd.source_url, dd.publish_date
        FROM disclosure_details dd JOIN kap_companies co ON co.ticker = dd.ticker
        WHERE dd.detail_type IN ('FINANSAL_RAPOR', 'FINANSAL_NOT') AND dd.ticker IS NOT NULL""")
    print(f'  Created {c.rowcount} financial_notes')
else:
    print(f'  Already has {existing_notes} notes')

# STEP 7: Verify
print("\n[7/7] Final verification...")
for tbl, col in [
    ('kap_financials', 'pe_ratio'), ('kap_financials', 'pb_ratio'),
    ('kap_financials', 'ev_ebitda'), ('kap_financials', 'revenue_yoy'),
    ('kap_financials', 'net_profit_yoy'), ('kap_financials', 'ebitda_margin'),
    ('kap_financials', 'net_margin'), ('kap_subsidiaries', 'share_percent'),
    ('settlement_data', 'ticker'), ('kap_financial_notes', 'disclosure_id'),
]:
    try:
        total = c.execute(f'SELECT COUNT(*) FROM [{tbl}]').fetchone()[0]
        filled = c.execute(f'SELECT COUNT(*) FROM [{tbl}] WHERE [{col}] IS NOT NULL AND [{col}] != 0').fetchone()[0]
        print(f'  {tbl}.{col}: {filled}/{total} ({round(filled/total*100,1) if total else 0}%)')
    except Exception as e:
        print(f'  {tbl}.{col}: ERROR - {e}')

# Update assets with sector
c.execute("""UPDATE assets SET sector = (SELECT co.sector FROM kap_companies co WHERE co.ticker = assets.asset_code)
    WHERE assets.sector IS NULL AND assets.asset_type = 'STOCK'""")
db.commit()
print(f'  Updated {c.rowcount} assets with sector')

db.close()
print("\n" + "=" * 60)
print("DONE — All fixes applied")
print("=" * 60)
