"""
One-time migration: copy KAP data from old kap.db tables
to shared_db tables in finance.db.
"""
import os
import sqlite3
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///finance.db"

from shared_db.models import (
    Base, engine, SessionLocal,
    KapCompany, KapFinancial, KapDisclosure, KapCorporateAction,
)

# Read old kap.db
old_db = sqlite3.connect("kap-pipeline/kap.db")
old_db.row_factory = sqlite3.Row

# New DB
db = SessionLocal()
Base.metadata.create_all(engine)

print("=== Migrating KAP data ===")

# 1. Companies
old_companies = old_db.execute("SELECT * FROM companies").fetchall()
print(f"Old companies: {len(old_companies)}")
migrated = 0
for row in old_companies:
    existing = db.query(KapCompany).filter(KapCompany.ticker == row["ticker"]).first()
    if existing:
        existing.company_name = row["company_name"] or existing.company_name
        existing.sector = row["sector"] or existing.sector
        existing.market = row["market"] or existing.market
    else:
        db.add(KapCompany(
            ticker=row["ticker"],
            mkk_id=row["mkk_id"] or "",
            company_name=row["company_name"],
            sector=row["sector"],
            market=row["market"],
            is_active=bool(row["is_active"]) if row["is_active"] is not None else True,
        ))
        migrated += 1
db.commit()
print(f"  Migrated {migrated} new companies")

# 2. Financials
old_financials = old_db.execute("SELECT * FROM financials").fetchall()
print(f"Old financials: {len(old_financials)}")
migrated = 0
for row in old_financials:
    try:
        existing = db.query(KapFinancial).filter(
            KapFinancial.company_id == row["company_id"],
            KapFinancial.year == row["year"],
            KapFinancial.period == row["period"],
        ).first()
        if existing:
            continue
        db.add(KapFinancial(
            company_id=row["company_id"],
            year=row["year"],
            period=row["period"],
            revenue=row["revenue"],
            gross_profit=row["gross_profit"],
            ebitda=row["ebitda"],
            net_profit=row["net_profit"],
            total_assets=row["total_assets"],
            total_debts=row["total_debts"],
            equity=row["equity"],
            paid_capital=row["paid_capital"],
        ))
        migrated += 1
    except Exception as e:
        pass
db.commit()
print(f"  Migrated {migrated} financials")

# 3. Disclosures
old_disc = old_db.execute("SELECT * FROM disclosures").fetchall()
print(f"Old disclosures: {len(old_disc)}")
migrated = 0
for row in old_disc:
    try:
        disc_id = str(row["disclosure_id"])
        existing = db.query(KapDisclosure).filter(KapDisclosure.disclosure_id == disc_id).first()
        if existing:
            continue
        # Parse publish_date
        pub_date = None
        if row["publish_date"]:
            try:
                pub_date = datetime.strptime(row["publish_date"], "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    pub_date = datetime.strptime(row["publish_date"], "%Y-%m-%dT%H:%M:%S")
                except:
                    pass
        if not pub_date:
            pub_date = datetime.utcnow()

        db.add(KapDisclosure(
            disclosure_id=disc_id,
            company_id=row["company_id"],
            symbol=row["symbol"],
            title=row["title"] or "",
            category=row["category"],
            disclosure_type=row["disclosure_type"],
            publish_date=pub_date,
            source_url=row["source_url"],
            is_catalyst=bool(row["is_catalyst"]) if row["is_catalyst"] is not None else False,
            raw_content=row["raw_content"],
        ))
        migrated += 1
    except Exception as e:
        pass
db.commit()
print(f"  Migrated {migrated} disclosures")

# 4. Corporate Actions
old_ca = old_db.execute("SELECT * FROM corporate_actions").fetchall()
print(f"Old corporate_actions: {len(old_ca)}")
migrated = 0
for row in old_ca:
    try:
        existing = db.query(KapCorporateAction).filter(
            KapCorporateAction.disclosure_id == row.get("disclosure_id")
        ).first() if row.get("disclosure_id") else None
        if existing:
            continue
        db.add(KapCorporateAction(
            company_id=row["company_id"],
            disclosure_id=row["disclosure_id"],
            action_type=row["action_type"],
            gross_per_share=row["gross_per_share"],
            net_per_share=row["net_per_share"],
            yield_percent=row["yield_percent"],
            ratio_percent=row["ratio_percent"],
            ex_date=row["ex_date"],
            payment_date=row["payment_date"],
            status=row["status"],
            description=row["description"],
        ))
        migrated += 1
    except Exception as e:
        pass
db.commit()
print(f"  Migrated {migrated} corporate actions")

# 5. Buybacks
old_bb = old_db.execute("SELECT * FROM share_buybacks").fetchall()
print(f"Old share_buybacks: {len(old_bb)}")
# These go into KapCorporateAction with action_type='BUYBACK'
migrated = 0
for row in old_bb:
    try:
        db.add(KapCorporateAction(
            company_id=row["company_id"],
            action_type="BUYBACK",
            description=f"Total budget: {row.get('total_budget')}, Max shares: {row.get('max_shares')}",
            status="ACTIVE",
        ))
        migrated += 1
    except Exception as e:
        pass
db.commit()
print(f"  Migrated {migrated} buybacks")

# 6. IPO
old_ipo = old_db.execute("SELECT * FROM ipo_data").fetchall()
print(f"Old ipo_data: {len(old_ipo)}")
# These don't have a shared_db table, skip for now

# Final count
print(f"\n=== MIGRATION COMPLETE ===")
print(f"KapCompany:    {db.query(KapCompany).count()}")
print(f"KapFinancial:  {db.query(KapFinancial).count()}")
print(f"KapDisclosure: {db.query(KapDisclosure).count()}")
print(f"KapCorporate:  {db.query(KapCorporateAction).count()}")

old_db.close()
db.close()
