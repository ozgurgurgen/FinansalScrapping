"""
Comprehensive CSV Export — Finance Pipeline
============================================
Exports all data organized by asset (ticker).

MASTER CSV: Her varlık (ticker) bir satır, tüm bilgiler tek satırda.
Ayrılmış CSV'ler: Multi-record veriler (bildirimler, ortaklar, yönetim vb.)
"""
import sqlite3, csv, os, sys, io
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
OUTPUT_DIR = str(Path(__file__).parent / 'csv_export')

os.makedirs(OUTPUT_DIR, exist_ok=True)

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
c = db.cursor()

print("=" * 70)
print("CSV EXPORT — Starting comprehensive export")
print("=" * 70)

# ══════════════════════════════════════════════════════════════════════════════
# 1. MASTER ASSET CSV — Her ticker bir satır
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/8] Creating master asset CSV...")

# Get all tickers from companies
companies = c.execute("""
    SELECT co.id, co.ticker, co.company_name, co.sector, co.market, co.is_active
    FROM kap_companies co
    WHERE co.is_active = 1
    ORDER BY co.ticker
""").fetchall()

master_rows = []
for comp in companies:
    cid = comp[0]
    ticker = comp[1]
    row = {
        'ticker': ticker,
        'company_name': comp[2],
        'sector': comp[3],
        'market': comp[4],
        'is_active': comp[5],
    }

    # Stock price data
    sp = c.execute("SELECT * FROM bist_stock_prices WHERE ticker = ?", (ticker,)).fetchone()
    if sp:
        for key in ['price', 'previous_close', 'day_high', 'day_low', 'volume', 'market_cap',
                     'pe_ratio', 'pb_ratio', 'dividend_yield', 'week52_high', 'week52_low', 'day_change_pct',
                     'is_xu100', 'is_xbank']:
            row[f'stock_{key}'] = sp[key] if sp[key] is not None else ''

    # Latest financials (most recent year+period)
    fin = c.execute("""
        SELECT * FROM kap_financials WHERE company_id = ?
        ORDER BY year DESC, period DESC LIMIT 1
    """, (cid,)).fetchone()
    if fin:
        for key in ['year', 'period', 'revenue', 'gross_profit', 'ebit', 'ebitda', 'net_profit',
                     'total_assets', 'total_debts', 'equity', 'paid_capital',
                     'current_ratio', 'leverage_ratio', 'roe', 'roa',
                     'gross_margin', 'ebitda_margin', 'net_margin',
                     'pe_ratio', 'pb_ratio', 'ev_ebitda', 'ev_revenue',
                     'revenue_yoy', 'net_profit_yoy',
                     'current_assets', 'cash_and_equivalents', 'financial_debt', 'total_debt', 'net_debt']:
            row[f'fin_{key}'] = fin[key] if fin[key] is not None else ''

    # Previous year financials for comparison
    fin_prev = c.execute("""
        SELECT revenue, net_profit, ebitda FROM kap_financials
        WHERE company_id = ? AND year = (SELECT MAX(year) FROM kap_financials WHERE company_id = ?) - 1
        ORDER BY period DESC LIMIT 1
    """, (cid, cid)).fetchone()
    if fin_prev:
        row['fin_prev_revenue'] = fin_prev[0] or ''
        row['fin_prev_net_profit'] = fin_prev[1] or ''
        row['fin_prev_ebitda'] = fin_prev[2] or ''

    # Cash flows (latest)
    cf = c.execute("""
        SELECT operating_cash_flow, investing_cash_flow, financing_cash_flow,
               net_change, closing_cash, capex
        FROM kap_cashflows WHERE company_id = ?
        ORDER BY year DESC, period DESC LIMIT 1
    """, (cid,)).fetchone()
    if cf:
        row['cf_operating'] = cf[0] or ''
        row['cf_investing'] = cf[1] or ''
        row['cf_financing'] = cf[2] or ''
        row['cf_net_change'] = cf[3] or ''
        row['cf_closing_cash'] = cf[4] or ''
        row['cf_capex'] = cf[5] or ''

    # Shareholders (count + top holder)
    sh_count = c.execute("SELECT COUNT(*) FROM kap_shareholders WHERE company_id = ?", (cid,)).fetchone()[0]
    row['shareholders_count'] = sh_count
    top_sh = c.execute("""
        SELECT holder_name, share_ratio_percent FROM kap_shareholders
        WHERE company_id = ? AND share_ratio_percent > 0
        ORDER BY share_ratio_percent DESC LIMIT 1
    """, (cid,)).fetchone()
    if top_sh:
        row['top_shareholder'] = top_sh[0]
        row['top_shareholder_pct'] = top_sh[1]

    # Management (count)
    mg_count = c.execute("SELECT COUNT(*) FROM kap_management WHERE company_id = ?", (cid,)).fetchone()[0]
    row['management_count'] = mg_count

    # Subsidiaries (count + total share)
    sub_count = c.execute("SELECT COUNT(*) FROM kap_subsidiaries WHERE company_id = ?", (cid,)).fetchone()[0]
    sub_pct = c.execute("SELECT SUM(share_percent) FROM kap_subsidiaries WHERE company_id = ? AND share_percent > 0", (cid,)).fetchone()[0]
    row['subsidiaries_count'] = sub_count
    row['subsidiaries_total_pct'] = round(sub_pct, 2) if sub_pct else ''

    # Buybacks
    bb = c.execute("SELECT total_budget_tl, max_shares, total_bought_shares, avg_buyback_price FROM share_buybacks WHERE company_id = ? ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
    if bb:
        row['buyback_budget'] = bb[0] or ''
        row['buyback_max_shares'] = bb[1] or ''
        row['buyback_bought'] = bb[2] or ''
        row['buyback_avg_price'] = bb[3] or ''

    # IPO
    ipo = c.execute("SELECT ipo_date, ipo_price, discount_ratio, distribution_type FROM ipo_data WHERE ticker = ? LIMIT 1", (ticker,)).fetchone()
    if ipo:
        row['ipo_date'] = ipo[0] or ''
        row['ipo_price'] = ipo[1] or ''
        row['ipo_discount'] = ipo[2] or ''
        row['ipo_distribution'] = ipo[3] or ''

    # Index membership
    idx = c.execute("SELECT index_name, weight_pct FROM index_constituents WHERE ticker = ?", (ticker,)).fetchall()
    if idx:
        row['indices'] = ', '.join([f"{r[0]}({r[1]}%)" for r in idx])

    # Settlement
    st = c.execute("SELECT foreign_ratio_pct, free_float_pct FROM settlement_data WHERE ticker = ?", (ticker,)).fetchone()
    if st:
        row['settlement_foreign_pct'] = st[0] or ''
        row['settlement_free_float'] = st[1] or ''

    # VAP data
    vap = c.execute("SELECT foreign_ratio, public_float_pct, market_cap FROM vap_data WHERE ticker = ?", (ticker,)).fetchone()
    if vap:
        row['vap_foreign_ratio'] = vap[0] or ''
        row['vap_public_float'] = vap[1] or ''
        row['vap_market_cap'] = vap[2] or ''

    # Corporate actions (latest)
    ca = c.execute("""
        SELECT action_type, gross_per_share, net_per_share, yield_percent, ex_date, status
        FROM kap_corporate_actions WHERE company_id = ?
        ORDER BY ex_date DESC LIMIT 1
    """, (cid,)).fetchone()
    if ca:
        row['ca_type'] = ca[0] or ''
        row['ca_gross_per_share'] = ca[1] or ''
        row['ca_net_per_share'] = ca[2] or ''
        row['ca_yield_pct'] = ca[3] or ''
        row['ca_ex_date'] = ca[4] or ''
        row['ca_status'] = ca[5] or ''

    # Disclosure stats
    disc_count = c.execute("SELECT COUNT(*) FROM kap_disclosures WHERE company_id = ?", (cid,)).fetchone()[0]
    row['disclosures_count'] = disc_count

    # Price history stats
    ph = c.execute("""
        SELECT MIN(close), MAX(close), AVG(close), MIN(trade_date), MAX(trade_date)
        FROM bist_price_history WHERE ticker = ?
    """, (ticker,)).fetchone()
    if ph and ph[0]:
        row['price_1y_min'] = ph[0]
        row['price_1y_max'] = ph[1]
        row['price_1y_avg'] = round(ph[2], 2) if ph[2] else ''
        row['price_from'] = ph[3]
        row['price_to'] = ph[4]

    master_rows.append(row)

# Write master CSV
all_keys = []
for r in master_rows:
    for k in r.keys():
        if k not in all_keys:
            all_keys.append(k)

master_path = os.path.join(OUTPUT_DIR, 'varliklar_master.csv')
with open(master_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=all_keys)
    writer.writeheader()
    for row in master_rows:
        writer.writerow(row)

print(f"  Master CSV: {len(master_rows)} assets, {len(all_keys)} columns -> {master_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 2. BILDIRIMLER CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/8] Creating disclosures CSV...")
discs = c.execute("""
    SELECT d.symbol, d.title, d.category, d.disclosure_type, d.publish_date, d.source_url, d.is_catalyst
    FROM kap_disclosures d
    ORDER BY d.publish_date DESC
""").fetchall()
disc_path = os.path.join(OUTPUT_DIR, 'bildirimler.csv')
with open(disc_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'title', 'category', 'type', 'publish_date', 'source_url', 'is_catalyst'])
    for d in discs:
        w.writerow([d[0], d[1], d[2], d[3], d[4], d[5], d[6]])
print(f"  {len(discs)} disclosures -> {disc_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 3. ORTAKLAR CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/8] Creating shareholders CSV...")
shs = c.execute("""
    SELECT co.ticker, sh.holder_name, sh.shares_amount, sh.share_ratio_percent,
           sh.voting_power_percent, sh.holder_type, sh.is_qualified, sh.snapshot_date
    FROM kap_shareholders sh
    JOIN kap_companies co ON co.id = sh.company_id
    ORDER BY co.ticker, sh.share_ratio_percent DESC
""").fetchall()
sh_path = os.path.join(OUTPUT_DIR, 'ortaklar.csv')
with open(sh_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'holder_name', 'shares_amount', 'share_pct', 'voting_pct', 'holder_type', 'is_qualified', 'snapshot_date'])
    for s in shs:
        w.writerow(s)
print(f"  {len(shs)} shareholders -> {sh_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 4. YONETIM KURULU CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/8] Creating management CSV...")
mgs = c.execute("""
    SELECT co.ticker, mg.name, mg.title, mg.member_type
    FROM kap_management mg
    JOIN kap_companies co ON co.id = mg.company_id
    ORDER BY co.ticker, mg.member_type
""").fetchall()
mg_path = os.path.join(OUTPUT_DIR, 'yonetim_kurulu.csv')
with open(mg_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'name', 'title', 'member_type'])
    for m in mgs:
        w.writerow(m)
print(f"  {len(mgs)} management members -> {mg_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 5. BAGLI ORTAKLIKLAR CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5/8] Creating subsidiaries CSV...")
subs = c.execute("""
    SELECT co.ticker, s.name, s.share_percent, s.country, s.activity, s.relation_type
    FROM kap_subsidiaries s
    JOIN kap_companies co ON co.id = s.company_id
    ORDER BY co.ticker, s.share_percent DESC
""").fetchall()
sub_path = os.path.join(OUTPUT_DIR, 'bagli_ortakliklar.csv')
with open(sub_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'subsidiary_name', 'share_percent', 'country', 'activity', 'relation_type'])
    for s in subs:
        w.writerow(s)
print(f"  {len(subs)} subsidiaries -> {sub_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 6. FIYAT GECMISI CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6/8] Creating price history CSV...")
phs = c.execute("""
    SELECT ticker, trade_date, open, high, low, close, volume
    FROM bist_price_history
    ORDER BY ticker, trade_date
""").fetchall()
ph_path = os.path.join(OUTPUT_DIR, 'fiyat_gecmisi.csv')
with open(ph_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'trade_date', 'open', 'high', 'low', 'close', 'volume'])
    for p in phs:
        w.writerow(p)
print(f"  {len(phs)} price records -> {ph_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 7. BILDIRIM DETAY CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[7/8] Creating disclosure details CSV...")
dds = c.execute("""
    SELECT ticker, title, detail_type, client_name, contract_amount_tl,
           block_shares, block_price, block_ratio_pct,
           publish_date
    FROM disclosure_details
    WHERE ticker IS NOT NULL
    ORDER BY ticker, publish_date DESC
""").fetchall()
dd_path = os.path.join(OUTPUT_DIR, 'bildirim_detay.csv')
with open(dd_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticker', 'title', 'type', 'client', 'contract_tl', 'block_shares', 'block_price', 'block_pct', 'publish_date'])
    for d in dds:
        w.writerow(d)
print(f"  {len(dds)} details -> {dd_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 8. TEFAS FONLAR CSV
# ══════════════════════════════════════════════════════════════════════════════
print("\n[8/8] Creating TEFAS funds CSV...")
funds = c.execute("""
    SELECT f.code, f.title, f.kind, f.current_price, f.market_cap,
           f.investor_count, f.price_count, f.category, f.fund_group
    FROM tefas_funds f
    ORDER BY f.code
""").fetchall()
fund_path = os.path.join(OUTPUT_DIR, 'tefas_fonlar.csv')
with open(fund_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['code', 'title', 'kind', 'current_price', 'market_cap', 'investor_count', 'price_count', 'category', 'fund_group'])
    for fund in funds:
        w.writerow(fund)
print(f"  {len(funds)} funds -> {fund_path}")

# Fund allocations
allocs = c.execute("""
    SELECT a.code, a.stock, a.treasury_bill, a.government_bond, a.term_deposit,
           a.eurobonds, a.precious_metals, a.repo, a.other
    FROM tefas_fund_allocations a
    ORDER BY a.code
""").fetchall()
alloc_path = os.path.join(OUTPUT_DIR, 'tefas_fon_dagilim.csv')
with open(alloc_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['code', 'stock_pct', 'treasury_bill_pct', 'government_bond_pct', 'term_deposit_pct', 'eurobonds_pct', 'precious_metals_pct', 'repo_pct', 'other_pct'])
    for a in allocs:
        w.writerow(a)
print(f"  {len(allocs)} allocations -> {alloc_path}")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("EXPORT COMPLETE")
print("=" * 70)
files = os.listdir(OUTPUT_DIR)
total_size = sum(os.path.getsize(os.path.join(OUTPUT_DIR, f)) for f in files)
print(f"Output directory: {OUTPUT_DIR}")
print(f"Files: {len(files)}")
print(f"Total size: {total_size / 1024 / 1024:.1f} MB")
for f in sorted(files):
    size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
    print(f"  {f}: {size / 1024:.1f} KB")

db.close()
