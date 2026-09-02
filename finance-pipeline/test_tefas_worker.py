"""Quick test: fetch fund list + details for 10 funds + prices for 3 funds"""
import os, sys, time
os.environ["DATABASE_URL"] = "sqlite:///finance.db"

sys.path.insert(0, ".")
from shared_db.models import Base, engine, SessionLocal, TefasFund, TefasFundPrice, TefasFundGroup, TefasFundSubType, TefasAnnouncement

from services.tefas_worker.main import (
    create_safe_session, _phase0_reference_data, _phase1_fund_list,
    _phase2_fund_details, _phase3_fund_prices, _log, scrape_state
)

# Create tables
Base.metadata.create_all(engine)
db = SessionLocal()
session = create_safe_session()
req_counter = [0]

print("Phase 0: Reference data...")
_phase0_reference_data(session, db, req_counter)

# Check what we loaded
groups = db.query(TefasFundGroup).all()
types = db.query(TefasFundSubType).all()
anns = db.query(TefasAnnouncement).all()
print(f"  Groups: {len(groups)} | Types: {len(types)} | Announcements: {len(anns)}")
for g in groups:
    print(f"    {g.group_id}: {g.group_name}")
for t in types:
    print(f"    {t.type_id}: {t.type_name}")

print("\nPhase 1: Fund list (all funds)...")
all_funds = _phase1_fund_list(session, db, req_counter)
total = db.query(TefasFund).count()
print(f"  Total funds in DB: {total}")

# Test: fetch details for 10 funds
print("\nPhase 2: Fund details (10 funds)...")
# Only do 10 funds
test_funds = db.query(TefasFund).limit(10).all()
scrape_state["current_fund"] = ""
for f in test_funds:
    data = session.post(
        f"https://www.tefas.gov.tr/api/funds/fonBilgiGetir",
        json={"fonKodu": f.code, "dil": "TR"}, timeout=20
    ).json()
    result = (data.get("resultList") or [{}])[0]
    print(f"  {f.code}: price={result.get('sonFiyat')}, return={result.get('gunlukGetiri')}, "
          f"category={result.get('fonKategori')}, rank={result.get('kategoriDerece')}/{result.get('kategoriFonSay')}, "
          f"investors={result.get('yatirimciSayi')}, mcap={result.get('portBuyukluk')}, share={result.get('pazarPayi')}%")
    time.sleep(3)

# Test: fetch prices for 3 funds
print("\nPhase 3: Price history (3 funds)...")
for f in test_funds[:3]:
    data = session.post(
        f"https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir",
        json={"fonKodu": f.code, "dil": "TR", "periyod": 60}, timeout=20
    ).json()
    prices = data.get("resultList") or []
    print(f"  {f.code}: {len(prices)} prices (last 60 months)")
    if prices:
        print(f"    First: {prices[0].get('tarih')[:10]} @ {prices[0].get('fiyat')}")
        print(f"    Last:  {prices[-1].get('tarih')[:10]} @ {prices[-1].get('fiyat')}")
    time.sleep(3)

# Summary
funds_count = db.query(TefasFund).count()
prices_count = db.query(TefasFundPrice).count()
print(f"\n=== SUMMARY ===")
print(f"Funds: {funds_count}")
print(f"Prices: {prices_count}")
print(f"Groups: {db.query(TefasFundGroup).count()}")
print(f"Types: {db.query(TefasFundSubType).count()}")
print(f"Announcements: {db.query(TefasAnnouncement).count()}")
print(f"Requests: {req_counter[0]}")

db.close()
