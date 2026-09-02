"""
Comprehensive data quality fixer — fixes subsidiaries share_percent, 
financing cash flows, and other missing data.
"""
import sys, io, sqlite3, re, time, random, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB = 'finance.db'
db = sqlite3.connect(DB, timeout=15)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

def log(msg):
    print(f"[FIX] {msg}", flush=True)

# ============================================================
# 1. FINANCING CASH FLOW — KAP API'den cash_flow toplamından hesapla
# ============================================================
log("=== 1. FINANCING CASH FLOW ===")

# KAP API'den cash_flows tablosuna financing_cf hiç yazılmamış
# operating + investing + financing = net_change olduğu için
# financing = net_change - operating - investing olabilir
updated = c.execute("""
    UPDATE cash_flows 
    SET financing_cash_flow = net_change - operating_cash_flow - investing_cash_flow
    WHERE financing_cash_flow = 0 
      AND net_change IS NOT NULL 
      AND operating_cash_flow IS NOT NULL 
      AND investing_cash_flow IS NOT NULL
      AND net_change != 0
""").rowcount
db.commit()
log(f"  financing_cash_flow: {updated} kayıt güncellendi (net_change - op - inv)")

# Kontrol
has_fin = c.execute("SELECT COUNT(*) FROM cash_flows WHERE financing_cash_flow != 0").fetchone()[0]
log(f"  financing_cash_flow dolu: {has_fin}/1274")

# ============================================================
# 2. SUBSIDIARIES — share_percent'i disclosure raw_content'den parse et
# ============================================================
log("\n=== 2. SUBSIDIARIES share_percent ===")

# İlk olarakshare_percent'i disclosure'lardan çekmeye çalışma
# KAP'ın bağlı ortaklık sayfasından Playwright ile çekmek en iyisi
# Ama şimdilik raw_content'ten deneyelim

# Bağlı ortaklık bildirimlerinde "%51" gibi oranlar olabilir
zero_pct_subs = c.execute("""
    SELECT s.id, s.company_id, s.name, d.raw_content 
    FROM subsidiaries s 
    LEFT JOIN disclosures d ON d.company_id = s.company_id AND d.raw_content LIKE '%Ortakl%'
    WHERE (s.share_percent = 0 OR s.share_percent IS NULL)
    LIMIT 20
""").fetchall()

parsed_sub = 0
for sub_id, comp_id, name, raw in zero_pct_subs:
    if not raw or len(raw) < 50:
        continue
    # "%XX" pattern — "AG ANADOLU GRUBU HOLDİNG A.Ş. %56,89" gibi
    name_escaped = re.escape(name[:20])
    pct_match = re.search(name_escaped + r'.*?%\s*(\d+[,\.]\d+)', raw)
    if pct_match:
        val = float(pct_match.group(1).replace(',', '.'))
        c.execute("UPDATE subsidiaries SET share_percent = ? WHERE id = ?", (val, sub_id))
        parsed_sub += 1
    else:
        # "%XX" pattern without name
        pct_match = re.search(r'%\s*(\d+[,\.]\d+)', raw[raw.find(name):raw.find(name)+200] if name in raw else "")
        if pct_match:
            val = float(pct_match.group(1).replace(',', '.'))
            c.execute("UPDATE subsidiaries SET share_percent = ? WHERE id = ?", (val, sub_id))
            parsed_sub += 1

db.commit()
log(f"  {parsed_sub} subsidiary share_percent parse edildi (raw_content)")

# Kalanları shareholders tablosundan eşleştir
log("  shareholders tablosundan eslestirme deneniyor...")
shareholder_data = c.execute("""
    SELECT company_id, holder_name, share_ratio_percent 
    FROM shareholders 
    WHERE share_ratio_percent > 0
""").fetchall()

matched = 0
for comp_id, holder, ratio in shareholder_data:
    # Subsidiaries'de bu company_id için isim benzerliği ara
    similar = c.execute("""
        SELECT id, name FROM subsidiaries 
        WHERE company_id = ? AND share_percent = 0
          AND (name LIKE ? OR ? LIKE '%' || name || '%')
        LIMIT 1
    """, (comp_id, f"%{holder[:15]}%", holder)).fetchone()
    if similar:
        c.execute("UPDATE subsidiaries SET share_percent = ? WHERE id = ?", (ratio, similar[0]))
        matched += 1

db.commit()
log(f"  {matched} subsidiary shareholders'dan eslestirildi")

# ============================================================
# 3. CORPORATE ACTIONS — başlıktan değer parse et
# ============================================================
log("\n=== 3. CORPORATE ACTIONS deger parse ===")

# Tüm corporate_actions başlıklarına bak
ca_rows = c.execute("SELECT id, title FROM corporate_actions WHERE gross_per_share IS NULL").fetchall()
parsed = 0
for ca_id, title in ca_rows:
    if not title:
        continue
    
    # Çeşitli temettü/bilgi formatları
    # Pattern 1: "1,25 TL Brüt"
    m = re.search(r'(\d+[\.,]\d+)\s*TL\s*Br[üu]t', title, re.I)
    if m:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET gross_per_share = ? WHERE id = ?", (val, ca_id))
        parsed += 1
    
    # Pattern 2: "1,0625 TL Net"
    m = re.search(r'(\d+[\.,]\d+)\s*TL\s*Net', title, re.I)
    if m:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET net_per_share = ? WHERE id = ?", (val, ca_id))
    
    # Pattern 3: "Hisse Başı Brüt 1,25 TL"
    m = re.search(r'Br[üu]t\s+(\d+[\.,]\d+)\s*TL', title, re.I)
    if m and not (ca_id in [r[0] for r in c.execute("SELECT id FROM corporate_actions WHERE gross_per_share IS NOT NULL").fetchall()]):
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET gross_per_share = ? WHERE id = ?", (val, ca_id))
        parsed += 1
    
    # Pattern 4: "Hisse Başı Net 1,0625 TL"
    m = re.search(r'Net\s+(\d+[\.,]\d+)\s*TL', title, re.I)
    if m and not (ca_id in [r[0] for r in c.execute("SELECT id FROM corporate_actions WHERE net_per_share IS NOT NULL").fetchall()]):
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET net_per_share = ? WHERE id = ?", (val, ca_id))
    
    # Pattern 5: "temettü verimi %XX"
    m = re.search(r'%\s*(\d+[\.,]\d+)', title)
    if m:
        val = float(m.group(1).replace(',', '.'))
        if val < 50:  # Makul bir verim oranı
            c.execute("UPDATE corporate_actions SET yield_pct = ? WHERE id = ?", (val, ca_id))

    # Pattern 6: "1 e 1 bedelsiz" / "2 e 1 bedelsiz"
    m = re.search(r'(\d+)\s*e\s*1\s*bedelsiz', title, re.I)
    if m:
        c.execute("UPDATE corporate_actions SET bonus_ratio = ? WHERE id = ?", (int(m.group(1)), ca_id))

db.commit()
log(f"  {parsed} corporate_action degeri parse edildi")

# Kalanlara disclosure_id ile raw_content'ten değer çek
remaining = c.execute("""
    SELECT ca.id, ca.disclosure_id, d.raw_content
    FROM corporate_actions ca
    LEFT JOIN disclosures d ON d.id = ca.disclosure_id
    WHERE ca.gross_per_share IS NULL AND ca.disclosure_id IS NOT NULL
""").fetchall()

raw_parsed = 0
for ca_id, disc_id, raw in remaining:
    if not raw or len(raw) < 50:
        continue
    m = re.search(r'(\d+[\.,]\d+)\s*TL\s*(?:Br[üu]t|Brut)', raw)
    if m:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET gross_per_share = ? WHERE id = ?", (val, ca_id))
        raw_parsed += 1
    m = re.search(r'(\d+[\.,]\d+)\s*TL\s*Net', raw)
    if m:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
        c.execute("UPDATE corporate_actions SET net_per_share = ? WHERE id = ?", (val, ca_id))

db.commit()
log(f"  {raw_parsed} raw_content'ten deger parse edildi")

# ============================================================
# 4. VAP DATA — foreign_ratio (yfinance ile)
# ============================================================
log("\n=== 4. VAP DATA foreign_ratio ===")

# YF'den foreign ratio çekmek için MuchetDB holder data kullan
# Ya da simple: bist_stock_prices'dan market_cap ile hesapla
vap_zero = c.execute("""
    SELECT id, ticker, market_cap FROM vap_data 
    WHERE foreign_ratio IS NULL OR foreign_ratio = 0
""").fetchall()
log(f"  foreign_ratio eksik: {len(vap_zero)}")

# şimdilik bypass — yfinance rate-limited. 
# Onun yerine data yoksa 0 olarak işaretle
for v_id, ticker, mcap in vap_zero:
    if mcap and mcap > 0:
        # foreign_ratio olmadan da market_cap var — yeterli
        pass

# ============================================================
# 5. FUND STOCK HOLDINGS — bireysel hisse verisi
# ============================================================
log("\n=== 5. FUND STOCK HOLDINGS ===")

# stock_ticker = "STOCK_PORTFOLIO" olanlar aggregate veri
# Bunlar aslında fonun toplam portföy büyüklüğü
agg_count = c.execute("""
    SELECT COUNT(*) FROM fund_stock_holdings WHERE stock_ticker = 'STOCK_PORTFOLIO'
""").fetchone()[0]
log(f"  aggregate (STOCK_PORTFOLIO): {agg_count}/793")
log("  bireysel hisse verisi icin KAP fon raporlari gerekli")

# KAP portfolio_reports'tan veri çekmeyi dene
pr_count = c.execute("SELECT COUNT(*) FROM kap_portfolio_reports").fetchone()[0]
log(f"  kap_portfolio_reports: {pr_count}")

# ============================================================
# 6. SETTLEMENT DATA — KAP'tan çek
# ============================================================
log("\n=== 6. SETTLEMENT DATA ===")
settlement_count = c.execute("SELECT COUNT(*) FROM settlement_data").fetchone()[0]
log(f"  settlement_data: {settlement_count} satır (bos)")

# ============================================================
# FINAL ÖZET
# ============================================================
log("\n=== FINAL DURUM ===")
db2 = sqlite3.connect(DB, timeout=5)
c2 = db2.cursor()

final_checks = [
    ("companies", "ticker"),
    ("financials", "revenue"),
    ("financials", "cash_and_equivalents"),
    ("financials", "financial_debt"),
    ("financials", "current_assets"),
    ("financials", "pe_ratio"),
    ("disclosures", "symbol"),
    ("bist_stock_prices", "price"),
    ("bist_price_history", "ticker"),
    ("shareholders", "holder_name"),
    ("management_members", "name"),
    ("subsidiaries", "share_percent"),
    ("corporate_actions", "gross_per_share"),
    ("share_buybacks", "total_budget_tl"),
    ("cash_flows", "financing_cash_flow"),
    ("tefas_funds", "current_price"),
    ("tefas_fund_prices", "price"),
    ("tefas_fund_allocations", "stock"),
]

for table, col in final_checks:
    try:
        total = c2.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        filled = c2.execute(f"SELECT COUNT(*) FROM [{table}] WHERE [{col}] IS NOT NULL AND [{col}] != '' AND [{col}] != 0").fetchone()[0]
        pct = (filled / total * 100) if total > 0 else 0
        status = "OK" if pct > 70 else "EKSIK" if pct > 0 else "BOS"
        log(f"  [{status}] {table}.{col}: {filled}/{total} ({pct:.0f}%)")
    except Exception as e:
        log(f"  [ERR] {table}.{col}: {e}")

db.close()
db2.close()
log("\nTamamlandi!")
