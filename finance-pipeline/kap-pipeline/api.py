"""
KAP Pipeline REST API — FastAPI
================================
KAP Pipeline verilerini disariya REST API olarak sunar.

Calistirmak icin:
    cd kap-pipeline
    python api.py
    # veya
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Swagger Docs:
    http://localhost:8000/docs
    http://localhost:8000/redoc
"""

import os, sys
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")
sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_db, get_session, Company, Financial, Disclosure,
    OrderBacklog, CorporateAction, ShareBuyback, IpoData,
    Shareholder, PipelineRun,
)

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="KAP Pipeline API",
    description="Kamuyu Aydinlatma Platformu verilerini sunan REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ── Helpers ──────────────────────────────────────────────────────────────────
def sf(val):
    if val is None: return None
    if isinstance(val, Decimal): return float(val)
    try: return float(val)
    except: return None

def serialize_date(val):
    if val is None: return None
    if isinstance(val, datetime): return val.isoformat()
    if isinstance(val, date): return val.isoformat()
    return str(val)


# ── Pydantic Models ──────────────────────────────────────────────────────────
class CompanyOut(BaseModel):
    id: int
    ticker: str
    mkk_id: str
    company_name: Optional[str] = None
    city: Optional[str] = None
    sector: Optional[str] = None
    market: Optional[str] = None
    is_active: bool
    class Config: from_attributes = True

class FinancialOut(BaseModel):
    id: int
    company_id: int
    year: int
    period: int
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    net_profit: Optional[float] = None
    gross_margin: Optional[float] = None
    ebitda_margin: Optional[float] = None
    net_margin: Optional[float] = None
    total_assets: Optional[float] = None
    total_debt: Optional[float] = None
    equity: Optional[float] = None
    current_ratio: Optional[float] = None
    leverage_ratio: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    net_debt: Optional[float] = None
    revenue_yoy_growth: Optional[float] = None
    pe_ratio: Optional[float] = None
    class Config: from_attributes = True

class DisclosureOut(BaseModel):
    id: int
    disclosure_id: str
    symbol: Optional[str] = None
    title: str
    category: Optional[str] = None
    disclosure_type: Optional[str] = None
    publish_date: Optional[str] = None
    source_url: Optional[str] = None
    is_catalyst: bool
    class Config: from_attributes = True

class OrderBacklogOut(BaseModel):
    id: int
    disclosure_id: int
    client_name: Optional[str] = None
    contract_description: Optional[str] = None
    amount_tl: Optional[float] = None
    amount_usd: Optional[float] = None
    amount_eur: Optional[float] = None
    ciro_effect_percent: Optional[float] = None
    class Config: from_attributes = True

class CorporateActionOut(BaseModel):
    id: int
    company_id: int
    action_type: str
    gross_per_share: Optional[float] = None
    net_per_share: Optional[float] = None
    yield_percent: Optional[float] = None
    ratio_percent: Optional[float] = None
    ex_date: Optional[str] = None
    payment_date: Optional[str] = None
    status: Optional[str] = None
    class Config: from_attributes = True

class ShareBuybackOut(BaseModel):
    id: int
    company_id: int
    total_budget_tl: Optional[float] = None
    max_shares: Optional[int] = None
    total_bought_shares: Optional[int] = None
    capital_ratio_percent: Optional[float] = None
    avg_buyback_price: Optional[float] = None
    class Config: from_attributes = True

class IpoDataOut(BaseModel):
    id: int
    company_name: str
    ticker: Optional[str] = None
    ipo_price: Optional[float] = None
    discount_ratio: Optional[float] = None
    distribution_type: Optional[str] = None
    consortium_leader: Optional[str] = None
    use_of_funds_investment_pct: Optional[float] = None
    use_of_funds_rd_pct: Optional[float] = None
    use_of_funds_working_capital_pct: Optional[float] = None
    use_of_funds_debt_pct: Optional[float] = None
    class Config: from_attributes = True

class ShareholderOut(BaseModel):
    id: int
    company_id: int
    holder_name: str
    shares_amount: Optional[float] = None
    share_ratio_percent: Optional[float] = None
    voting_power_percent: Optional[float] = None
    holder_type: Optional[str] = None
    is_qualified: bool
    class Config: from_attributes = True

class PipelineRunOut(BaseModel):
    id: int
    module_name: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str
    records_processed: int
    error_message: Optional[str] = None
    class Config: from_attributes = True


def to_dict(obj, extra=None):
    """Convert SQLAlchemy model to dict with proper serialization."""
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, (datetime, date)):
            val = val.isoformat()
        d[col.name] = val
    if extra:
        d.update(extra)
    return d


# ══════════════════════════════════════════════════════════════════════════════
# ROOT & STATUS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/", tags=["Status"])
def root():
    return {"message": "KAP Pipeline API", "docs": "/docs", "version": "1.0.0"}

@app.get("/api/status", tags=["Status"])
def api_status():
    s = get_session()
    return {
        "status": "ok",
        "database": "connected",
        "tables": {
            "companies": s.query(Company).count(),
            "financials": s.query(Financial).count(),
            "disclosures": s.query(Disclosure).count(),
            "order_backlogs": s.query(OrderBacklog).count(),
            "corporate_actions": s.query(CorporateAction).count(),
            "share_buybacks": s.query(ShareBuyback).count(),
            "ipo_data": s.query(IpoData).count(),
            "shareholders": s.query(Shareholder).count(),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1: COMPANIES
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/companies", response_model=List[CompanyOut], tags=["Module 1 - Companies"])
def get_companies(
    search: Optional[str] = Query(None, description="Ticker veya isimde ara"),
    sector: Optional[str] = Query(None, description="Sektore gore filtrele"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Tum BIST sirketlerini listeler."""
    s = get_session()
    q = s.query(Company)
    if search:
        q = q.filter(Company.ticker.ilike(f"%{search}%") | Company.company_name.ilike(f"%{search}%"))
    if sector:
        q = q.filter(Company.sector.ilike(f"%{sector}%"))
    return [to_dict(c) for c in q.order_by(Company.ticker).offset(offset).limit(limit).all()]

@app.get("/api/companies/{ticker}", tags=["Module 1 - Companies"])
def get_company(ticker: str):
    """Tek bir sirketin bilgilerini dondurur."""
    s = get_session()
    c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not c:
        raise HTTPException(404, f"Company {ticker} not found")
    return to_dict(c)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2: FINANCIALS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/financials/latest/{ticker}", tags=["Module 2 - Financials"])
def get_latest_financial(ticker: str):
    s = get_session()
    c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not c:
        raise HTTPException(404, f"Company {ticker} not found")
    f = s.query(Financial).filter(Financial.company_id == c.id).order_by(
        Financial.year.desc(), Financial.period.desc()
    ).first()
    if not f:
        raise HTTPException(404, f"No financial data for {ticker}")
    return to_dict(f, {"ticker": ticker})

@app.get("/api/financials/compare", tags=["Module 2 - Financials"])
def compare_financials(
    tickers: str = Query(..., description="Virgullu ayirilmis ticker listesi, or: THYAO,ASELS,GARAN"),
    year: int = Query(2025, description="Yil"),
    period: int = Query(12, description="Donem"),
):
    """
    Birden fazla sirketi karsilastirir.
    Ornek: /api/financials/compare?tickers=THYAO,ASELS,TUPRS&year=2025&period=12
    """
    s = get_session()
    result = []
    for ticker in tickers.split(","):
        ticker = ticker.strip().upper()
        c = s.query(Company).filter(Company.ticker == ticker).first()
        if not c: continue
        f = s.query(Financial).filter(
            Financial.company_id == c.id, Financial.year == year, Financial.period == period
        ).first()
        if f:
            d = to_dict(f)
            d["ticker"] = ticker
            result.append(d)
    return result

@app.get("/api/financials/{ticker}", response_model=List[FinancialOut], tags=["Module 2 - Financials"])
def get_financials(
    ticker: str,
    year: Optional[int] = Query(None, description="Yil filtresi"),
    period: Optional[int] = Query(None, description="Donem filtresi (3,6,9,12)"),
    limit: int = Query(20, ge=1, le=100),
):
    """Bir sirketin mali tablolarini dondurur."""
    s = get_session()
    c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not c:
        raise HTTPException(404, f"Company {ticker} not found")
    q = s.query(Financial).filter(Financial.company_id == c.id)
    if year: q = q.filter(Financial.year == year)
    if period: q = q.filter(Financial.period == period)
    return [to_dict(f) for f in q.order_by(Financial.year.desc(), Financial.period.desc()).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3: DISCLOSURES
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/disclosures", response_model=List[DisclosureOut], tags=["Module 3 - Disclosures"])
def get_disclosures(
    ticker: Optional[str] = Query(None, description="Sirket ticker filtresi"),
    category: Optional[str] = Query(None, description="Kategori filtresi"),
    catalyst_only: bool = Query(False, description="Sadece katalizorler"),
    days: int = Query(30, ge=1, le=365, description="Son kac gun"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    KAP bildirimlerini listeler.

    Kategoriler: Buyuklenme, Yatirim, Finansman, Ortaklik_Degisimi, Dava,
                 Temettu, Sermaye, Ihale, Yeni_Is, Geri_Alim, IPO, Diger
    """
    s = get_session()
    cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=days)
    q = s.query(Disclosure).filter(Disclosure.publish_date >= cutoff)
    if ticker: q = q.filter(Disclosure.symbol == ticker.upper())
    if category: q = q.filter(Disclosure.category == category)
    if catalyst_only: q = q.filter(Disclosure.is_catalyst == True)
    return [to_dict(d) for d in q.order_by(Disclosure.publish_date.desc()).limit(limit).all()]

@app.get("/api/disclosures/{disclosure_id}", tags=["Module 3 - Disclosures"])
def get_disclosure(disclosure_id: str):
    """Tek bir bildirimin detayini dondurur."""
    s = get_session()
    d = s.query(Disclosure).filter(Disclosure.disclosure_id == disclosure_id).first()
    if not d:
        raise HTTPException(404, f"Disclosure {disclosure_id} not found")
    return to_dict(d)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3b: ORDER BACKLOGS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/orders", response_model=List[OrderBacklogOut], tags=["Module 3b - Orders"])
def get_orders(limit: int = Query(50, ge=1, le=200)):
    """Yeni is iliskileri ve siparis havuzunu listeler."""
    s = get_session()
    return [to_dict(o) for o in s.query(OrderBacklog).order_by(
        OrderBacklog.created_at.desc()
    ).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4: CORPORATE ACTIONS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/corporate-actions", response_model=List[CorporateActionOut], tags=["Module 4 - Corporate Actions"])
def get_corporate_actions(
    ticker: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None, description="DIVIDEND, RIGHTS_ISSUE, BONUS_ISSUE"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Kurumsal islemleri listeler.

    Action tipleri: DIVIDEND, RIGHTS_ISSUE (Bedelli), BONUS_ISSUE (Bedelsiz)
    """
    s = get_session()
    q = s.query(CorporateAction)
    if ticker:
        c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
        if c: q = q.filter(CorporateAction.company_id == c.id)
    if action_type:
        q = q.filter(CorporateAction.action_type == action_type)
    return [to_dict(a) for a in q.order_by(CorporateAction.created_at.desc()).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5: SHARE BUYBACKS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/buybacks", response_model=List[ShareBuybackOut], tags=["Module 5 - Buybacks"])
def get_buybacks(
    ticker: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Pay geri alim programlarini listeler."""
    s = get_session()
    q = s.query(ShareBuyback)
    if ticker:
        c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
        if c: q = q.filter(ShareBuyback.company_id == c.id)
    return [to_dict(b) for b in q.order_by(ShareBuyback.created_at.desc()).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 6: IPO
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/ipo", response_model=List[IpoDataOut], tags=["Module 6 - IPO"])
def get_ipo(limit: int = Query(50, ge=1, le=100)):
    """Halka arz verilerini listeler."""
    s = get_session()
    return [to_dict(i) for i in s.query(IpoData).order_by(
        IpoData.created_at.desc()
    ).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 7: SHAREHOLDERS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/shareholders/{ticker}", response_model=List[ShareholderOut], tags=["Module 7 - Shareholders"])
def get_shareholders(ticker: str):
    """Bir sirketin ortaklik yapisini dondurur."""
    s = get_session()
    c = s.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not c:
        raise HTTPException(404, f"Company {ticker} not found")
    return [to_dict(sh) for sh in s.query(Shareholder).filter(
        Shareholder.company_id == c.id
    ).order_by(Shareholder.share_ratio_percent.desc()).all()]

@app.get("/api/shareholders/qualified/list", tags=["Module 7 - Shareholders"])
def get_qualified_shareholders(
    min_ratio: float = Query(5.0, description="Min pay orani (%)"),
    limit: int = Query(50),
):
    """Tum nitelikli pay sahiplerini (%X+ sahipler) listeler."""
    s = get_session()
    results = []
    shs = s.query(Shareholder).filter(Shareholder.share_ratio_percent >= min_ratio).all()
    for sh in shs:
        c = s.query(Company).filter(Company.id == sh.company_id).first()
        d = to_dict(sh)
        d["ticker"] = c.ticker if c else None
        results.append(d)
    return sorted(results, key=lambda x: x.get("share_ratio_percent") or 0, reverse=True)[:limit]


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE STATUS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/pipeline/runs", tags=["Pipeline"])
def get_pipeline_runs(limit: int = Query(20)):
    """Pipeline calistirma gecmisini dondurur."""
    s = get_session()
    return [to_dict(r) for r in s.query(PipelineRun).order_by(
        PipelineRun.started_at.desc()
    ).limit(limit).all()]


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/dashboard/summary", tags=["Dashboard"])
def dashboard_summary():
    """
    Dashboard icin ozet veriler.
    Tüm modullerin durumunu tek cevapta dondurur.
    """
    s = get_session()
    return {
        "companies": {
            "total": s.query(Company).count(),
            "active": s.query(Company).filter(Company.is_active == True).count(),
        },
        "financials": {
            "total_records": s.query(Financial).count(),
            "companies_with_data": s.query(Financial.company_id).distinct().count(),
            "latest_year": (s.query(Financial.year).order_by(Financial.year.desc()).first() or (None,))[0],
        },
        "disclosures": {
            "total": s.query(Disclosure).count(),
            "catalysts": s.query(Disclosure).filter(Disclosure.is_catalyst == True).count(),
            "categories": dict(
                s.query(Disclosure.category, __import__("sqlalchemy").func.count(Disclosure.id))
                .filter(Disclosure.category.isnot(None))
                .group_by(Disclosure.category).all()
            ),
        },
        "corporate_actions": s.query(CorporateAction).count(),
        "buybacks": s.query(ShareBuyback).count(),
        "ipo": s.query(IpoData).count(),
        "shareholders": s.query(Shareholder).count(),
    }


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("Starting KAP Pipeline API on http://localhost:8000")
    print("Swagger Docs: http://localhost:8000/docs")
    print("ReDoc:        http://localhost:8000/redoc")
    uvicorn.run(app, host="0.0.0.0", port=8000)
