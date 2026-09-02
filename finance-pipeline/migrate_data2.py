"""Migration v2: proper company_id mapping"""
import os
import sqlite3
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///finance.db"

from shared_db.models import (
    Base, engine, SessionLocal,
    KapCompany, KapFinancial, KapDisclosure, KapCorporateAction,
)

old_db = sqlite3.connect("kap-pipeline/kap.db")
old_db.row_factory = sqlite3.Row
db = SessionLocal()
Base.metadata.create_all(engine)

# Build company ID mapping: old_id -> new_id
old_to_new = {}
for new_co in db.query(KapCompany).all():
    # Find matching old company by ticker
    old_row = old_db.execute(
        "SELECT id FROM companies WHERE ticker = ?", (new_co.ticker,)
    ).fetchone()
    if old_row:
        old_to_new[old_row["id"]] = new_co.id

print(f"Company ID mapping: {len(old_to_new)} pairs")

# 1. Financials
old_financials = old_db.execute("SELECT * FROM financials").fetchall()
print(f"Migrating {len(old_financials)} financials...")
migrated = 0
for row in old_financials:
    old_cid = row["company_id"]
    new_cid = old_to_new.get(old_cid)
    if not new_cid:
        continue
    existing = db.query(KapFinancial).filter(
        KapFinancial.company_id == new_cid,
        KapFinancial.year == row["year"],
        KapFinancial.period == row["period"],
    ).first()
    if existing:
        continue
    db.add(KapFinancial(
        company_id=new_cid,
        year=row["year"],
        period=row["period"],
        revenue=row["revenue"],
        gross_profit=row["gross_profit"],
        ebit=row["ebit"],
        ebitda=row["ebitda"],
        net_profit=row["net_profit"],
        total_assets=row["total_assets"],
        total_debts=row["total_debt"],
        equity=row["equity"],
        paid_capital=row["paid_capital"],
        current_ratio=row["current_ratio"],
        leverage_ratio=row["leverage_ratio"],
        roe=row["roe"],
        roa=row["roa"],
        gross_margin=row["gross_margin"],
        ebitda_margin=row["ebitda_margin"],
        net_margin=row["net_margin"],
    ))
    migrated += 1
db.commit()
print(f"  +{migrated} financials")

# 2. Corporate Actions
old_ca = old_db.execute("SELECT * FROM corporate_actions").fetchall()
print(f"Migrating {len(old_ca)} corporate actions...")
migrated = 0
for row in old_ca:
    old_cid = row["company_id"]
    new_cid = old_to_new.get(old_cid)
    disc_id = str(row["disclosure_id"]) if row["disclosure_id"] else None
    existing = db.query(KapCorporateAction).filter(
        KapCorporateAction.disclosure_id == disc_id
    ).first() if disc_id else None
    if existing:
        continue
    db.add(KapCorporateAction(
        company_id=new_cid,
        disclosure_id=disc_id,
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
db.commit()
print(f"  +{migrated} corporate actions")

# 3. Share Buybacks -> KapCorporateAction
old_bb = old_db.execute("SELECT * FROM share_buybacks").fetchall()
print(f"Migrating {len(old_bb)} buybacks...")
migrated = 0
for row in old_bb:
    old_cid = row["company_id"]
    new_cid = old_to_new.get(old_cid)
    disc_id = str(row["disclosure_id"]) if row["disclosure_id"] else None
    existing = db.query(KapCorporateAction).filter(
        KapCorporateAction.disclosure_id == disc_id
    ).first() if disc_id else None
    if existing:
        continue
    desc_parts = []
    if row["total_budget_tl"]: desc_parts.append(f"Butce: {row['total_budget_tl']:.0f} TL")
    if row["max_shares"]: desc_parts.append(f"Maks Pay: {row['max_shares']}")
    if row["total_bought_shares"]: desc_parts.append(f"Geri Alinan: {row['total_bought_shares']}")
    if row["capital_ratio_percent"]: desc_parts.append(f"Sermaye: %{row['capital_ratio_percent']:.2f}")
    db.add(KapCorporateAction(
        company_id=new_cid,
        disclosure_id=disc_id,
        action_type="BUYBACK",
        ratio_percent=row["capital_ratio_percent"],
        ex_date=row["program_start_date"],
        status="ACTIVE",
        description=" | ".join(desc_parts) if desc_parts else "Geri alim programi",
    ))
    migrated += 1
db.commit()
print(f"  +{migrated} buybacks")

# Final
print(f"\n=== FINAL COUNTS ===")
print(f"KapCompany:    {db.query(KapCompany).count()}")
print(f"KapFinancial:  {db.query(KapFinancial).count()}")
print(f"KapDisclosure: {db.query(KapDisclosure).count()}")
print(f"KapCorporate:  {db.query(KapCorporateAction).count()}")

old_db.close()
db.close()
