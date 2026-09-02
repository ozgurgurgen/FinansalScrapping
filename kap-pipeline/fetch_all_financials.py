"""
Batch Financials Fetcher — Works with the corrected regex-based parser.
Processes all companies in permaLinks file.
"""

import requests, re, json, os, time, sys
from bs4 import BeautifulSoup

os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_session, Company, Financial, upsert_financial

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
})
s.get("https://www.kap.org.tr/tr", timeout=15)

session = get_session()
with open("kap_permaplinks.json") as f:
    perma_map = json.load(f)

def parse_number(text):
    if not text or text.strip() in ("", "-", "n/a"):
        return None
    t = text.strip().replace(".", "").replace(",", ".").replace(" ", "")
    try: return float(t)
    except: return None

BS_FIELDS = [
    (r"nen Varl", "current_assets"), (r"ran Varl", "non_current_assets"),
    (r"plam Varl", "total_assets"), (r"sa Vadeli", "short_term_debt"),
    (r"zun Vadeli", "long_term_debt"), (r"plam Y.k.l", "total_debt"),
    (r"z Kaynak", "equity"), (r"denmi. Sermaye", "paid_capital"),
]
IS_FIELDS = [
    (r"Has.l.t", "revenue"), (r"Br.t K.r", "gross_profit"),
    (r"sas Faaliyet", "ebit"), (r"FAV.K", "ebitda"),
    (r"Net D.nem K", "net_profit"),
]

def match_field(label, patterns):
    for pat, field in patterns:
        if re.search(pat, label, re.IGNORECASE): return field
    return None

def parse_one(comp_id, perma):
    r = s.get(f"https://www.kap.org.tr/tr/sirket-finansal-bilgileri/{perma}", timeout=30)
    if r.status_code != 200: return 0
    soup = BeautifulSoup(r.content, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2: return 0
    periods = re.findall(r"(\d{4})/(\d{2})", tables[0].find("tr").get_text(strip=True))
    if not periods: return 0
    pd_data = {f"{p[0]}/{p[1]}": {} for p in periods}
    for table in tables:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2: continue
            label = cells[0].get_text(strip=True)
            if not label: continue
            vals = [c.get_text(strip=True) for c in cells[1:]]
            field = match_field(label, BS_FIELDS) or match_field(label, IS_FIELDS)
            if field:
                for i, p in enumerate(periods):
                    if i < len(vals):
                        v = parse_number(vals[i])
                        if v is not None: pd_data[f"{p[0]}/{p[1]}"][field] = v
    saved = 0
    for pk, data in pd_data.items():
        if not data or len(data) < 2: continue
        y, p = pk.split("/")
        rev = data.get("revenue")
        gp = data.get("gross_profit")
        ebitda = data.get("ebitda")
        np_val = data.get("net_profit")
        ta = data.get("total_assets")
        eq = data.get("equity")
        ca = data.get("current_assets")
        std = data.get("short_term_debt")
        rec = {
            "year": int(y), "period": int(p),
            "revenue": rev, "gross_profit": gp, "ebitda": ebitda, "net_profit": np_val,
            "total_assets": ta, "equity": eq, "current_assets": ca,
            "short_term_debt": std, "total_debt": data.get("total_debt"),
            "non_current_assets": data.get("non_current_assets"),
            "paid_capital": data.get("paid_capital"),
            "gross_margin": (gp/rev) if gp and rev and rev != 0 else None,
            "ebitda_margin": (ebitda/rev) if ebitda and rev and rev != 0 else None,
            "net_margin": (np_val/rev) if np_val and rev and rev != 0 else None,
            "current_ratio": (ca/std) if ca and std and std > 0 else None,
            "roe": (np_val/eq) if np_val and eq and eq != 0 else None,
            "roa": (np_val/ta) if np_val and ta and ta != 0 else None,
        }
        upsert_financial(session, int(comp_id), rec)
        saved += 1
    session.commit()
    return saved

# Find which companies already have financial data
existing = {c[0] for c in session.query(Financial.company_id).distinct().all()}
to_fetch = [(cid, pdata) for cid, pdata in perma_map.items()
            if int(cid) not in existing and pdata.get("permaLink")]

print(f"Already done: {len(existing)}, Remaining: {len(to_fetch)}")

done = 0
for cid, pdata in to_fetch:
    perma = pdata["permaLink"]
    comp = session.query(Company).filter(Company.id == int(cid)).first()
    if not comp: continue
    try:
        n = parse_one(cid, perma)
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(to_fetch)} processed", flush=True)
        time.sleep(3)
    except:
        session.rollback()

total_fin = session.query(Financial).count()
total_comp = session.query(Financial.company_id).distinct().count()
print(f"\nDONE: {done} more companies. Total: {total_comp} companies, {total_fin} records")
