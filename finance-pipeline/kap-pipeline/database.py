"""
Database Layer — SQLAlchemy Models & Session Management
-------------------------------------------------------
Supports both PostgreSQL (full upsert) and SQLite (fallback) backends.
Uses upsert patterns to prevent duplicate records.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, relationship, sessionmaker

from config import CONFIG


# ─── Base ────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─── Module 1: Companies ────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = Column(String(20), unique=True, nullable=False, index=True)
    mkk_id: Mapped[str] = Column(String(100), nullable=False)
    company_name: Mapped[Optional[str]] = Column(String(500))
    city: Mapped[Optional[str]] = Column(String(100))
    sector: Mapped[Optional[str]] = Column(String(200))
    market: Mapped[Optional[str]] = Column(String(100))
    index_group: Mapped[Optional[str]] = Column(String(200))
    is_active: Mapped[bool] = Column(Boolean, default=True)
    paid_capital_static: Mapped[Optional[float]] = Column(Numeric(20, 2))
    website: Mapped[Optional[str]] = Column(String(500))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    financials = relationship("Financial", back_populates="company")
    disclosures = relationship("Disclosure", back_populates="company")
    corporate_actions = relationship("CorporateAction", back_populates="company")
    buybacks = relationship("ShareBuyback", back_populates="company")
    shareholders = relationship("Shareholder", back_populates="company")

    def __repr__(self):
        return f"<Company {self.ticker} mkk_id={self.mkk_id}>"


# ─── Module 2: Quarterly Financials ─────────────────────────────────────────
class Financial(Base):
    __tablename__ = "financials"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "period", name="uq_financial_company_period"),
        Index("ix_financial_company_year", "company_id", "year"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("companies.id"), nullable=False)
    year: Mapped[int] = Column(Integer, nullable=False)
    period: Mapped[int] = Column(Integer, nullable=False)

    # Income Statement
    revenue: Mapped[Optional[float]] = Column(Numeric(20, 2))
    gross_profit: Mapped[Optional[float]] = Column(Numeric(20, 2))
    ebit: Mapped[Optional[float]] = Column(Numeric(20, 2))
    ebitda: Mapped[Optional[float]] = Column(Numeric(20, 2))
    net_profit: Mapped[Optional[float]] = Column(Numeric(20, 2))

    # Margins
    gross_margin: Mapped[Optional[float]] = Column(Float)
    ebitda_margin: Mapped[Optional[float]] = Column(Float)
    net_margin: Mapped[Optional[float]] = Column(Float)

    # Balance Sheet
    current_assets: Mapped[Optional[float]] = Column(Numeric(20, 2))
    non_current_assets: Mapped[Optional[float]] = Column(Numeric(20, 2))
    total_assets: Mapped[Optional[float]] = Column(Numeric(20, 2))
    short_term_debt: Mapped[Optional[float]] = Column(Numeric(20, 2))
    long_term_debt: Mapped[Optional[float]] = Column(Numeric(20, 2))
    total_debt: Mapped[Optional[float]] = Column(Numeric(20, 2))
    financial_debt: Mapped[Optional[float]] = Column(Numeric(20, 2))
    cash_and_equivalents: Mapped[Optional[float]] = Column(Numeric(20, 2))
    equity: Mapped[Optional[float]] = Column(Numeric(20, 2))
    paid_capital: Mapped[Optional[float]] = Column(Numeric(20, 2))

    # Derived Ratios
    net_debt: Mapped[Optional[float]] = Column(Numeric(20, 2))
    current_ratio: Mapped[Optional[float]] = Column(Float)
    leverage_ratio: Mapped[Optional[float]] = Column(Float)
    roe: Mapped[Optional[float]] = Column(Float)
    roa: Mapped[Optional[float]] = Column(Float)

    # Growth Rates
    revenue_yoy_growth: Mapped[Optional[float]] = Column(Float)
    revenue_qoq_growth: Mapped[Optional[float]] = Column(Float)
    net_profit_yoy_growth: Mapped[Optional[float]] = Column(Float)

    # Market Ratios
    pe_ratio: Mapped[Optional[float]] = Column(Float)
    pb_ratio: Mapped[Optional[float]] = Column(Float)
    ev_ebitda: Mapped[Optional[float]] = Column(Float)
    ev_revenue: Mapped[Optional[float]] = Column(Float)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="financials")


# ─── Module 3: Disclosures ──────────────────────────────────────────────────
class Disclosure(Base):
    __tablename__ = "disclosures"
    __table_args__ = (
        UniqueConstraint("disclosure_id", name="uq_disclosure_id"),
        Index("ix_disclosure_publish_date", "publish_date"),
        Index("ix_disclosure_company_date", "company_id", "publish_date"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_id: Mapped[str] = Column(String(50), nullable=False, unique=True)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("companies.id"))
    symbol: Mapped[Optional[str]] = Column(String(20))
    title: Mapped[str] = Column(Text, nullable=False)
    category: Mapped[Optional[str]] = Column(String(50))
    disclosure_type: Mapped[Optional[str]] = Column(String(100))
    publish_date: Mapped[datetime] = Column(DateTime, nullable=False)
    source_url: Mapped[Optional[str]] = Column(Text)
    is_catalyst: Mapped[bool] = Column(Boolean, default=False)
    raw_content: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="disclosures")
    order_backlog = relationship("OrderBacklog", uselist=False, back_populates="disclosure")


# ─── Module 3b: Order Backlogs ──────────────────────────────────────────────
class OrderBacklog(Base):
    __tablename__ = "order_backlogs"
    __table_args__ = (
        UniqueConstraint("disclosure_id", name="uq_order_backlog_disclosure"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_id: Mapped[int] = Column(
        Integer, ForeignKey("disclosures.id"), nullable=False
    )
    client_name: Mapped[Optional[str]] = Column(String(500))
    contract_description: Mapped[Optional[str]] = Column(Text)
    amount_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    amount_usd: Mapped[Optional[float]] = Column(Numeric(20, 2))
    amount_eur: Mapped[Optional[float]] = Column(Numeric(20, 2))
    currency: Mapped[Optional[str]] = Column(String(10))
    ciro_effect_percent: Mapped[Optional[float]] = Column(Float)
    delivery_schedule: Mapped[Optional[str]] = Column(String(255))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    disclosure = relationship("Disclosure", back_populates="order_backlog")


# ─── Module 4: Corporate Actions ────────────────────────────────────────────
class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (
        Index("ix_ca_company_type", "company_id", "action_type"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("companies.id"))
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    action_type: Mapped[str] = Column(String(30), nullable=False)
    gross_per_share: Mapped[Optional[float]] = Column(Numeric(20, 4))
    net_per_share: Mapped[Optional[float]] = Column(Numeric(20, 4))
    yield_percent: Mapped[Optional[float]] = Column(Float)
    ratio_percent: Mapped[Optional[float]] = Column(Float)
    ex_date: Mapped[Optional[datetime]] = Column(Date)
    payment_date: Mapped[Optional[datetime]] = Column(Date)
    board_meeting_date: Mapped[Optional[datetime]] = Column(Date)
    general_assembly_date: Mapped[Optional[datetime]] = Column(Date)
    status: Mapped[Optional[str]] = Column(String(20))
    description: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="corporate_actions")


# ─── Module 5: Share Buybacks ───────────────────────────────────────────────
class ShareBuyback(Base):
    __tablename__ = "share_buybacks"
    __table_args__ = (Index("ix_buyback_company", "company_id"),)

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("companies.id"), nullable=False)
    program_start_date: Mapped[Optional[datetime]] = Column(Date)
    total_budget_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    max_shares: Mapped[Optional[int]] = Column(BigInteger)
    total_bought_shares: Mapped[Optional[int]] = Column(BigInteger)
    capital_ratio_percent: Mapped[Optional[float]] = Column(Float)
    avg_buyback_price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    last_transaction_price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    total_spent_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    company = relationship("Company", back_populates="buybacks")


# ─── Module 6: IPO Data ─────────────────────────────────────────────────────
class IpoData(Base):
    __tablename__ = "ipo_data"
    __table_args__ = (Index("ix_ipo_company", "company_name"),)

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = Column(String(500), nullable=False)
    ticker: Mapped[Optional[str]] = Column(String(20))
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    ipo_date: Mapped[Optional[datetime]] = Column(Date)
    ipo_price: Mapped[Optional[float]] = Column(Numeric(20, 2))
    discount_ratio: Mapped[Optional[float]] = Column(Float)
    distribution_type: Mapped[Optional[str]] = Column(String(50))
    consortium_leader: Mapped[Optional[str]] = Column(String(500))
    use_of_funds_investment_pct: Mapped[Optional[float]] = Column(Float)
    use_of_funds_rd_pct: Mapped[Optional[float]] = Column(Float)
    use_of_funds_working_capital_pct: Mapped[Optional[float]] = Column(Float)
    use_of_funds_debt_pct: Mapped[Optional[float]] = Column(Float)
    total_offered_shares: Mapped[Optional[int]] = Column(BigInteger)
    offering_amount_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ─── Module 7: Ownership / Shareholders ──────────────────────────────────────
class Shareholder(Base):
    __tablename__ = "shareholders"
    __table_args__ = (
        Index("ix_sh_company", "company_id"),
        Index("ix_sh_name", "holder_name"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("companies.id"), nullable=False)
    holder_name: Mapped[str] = Column(String(500), nullable=False)
    shares_amount: Mapped[Optional[float]] = Column(Numeric(20, 2))
    share_ratio_percent: Mapped[Optional[float]] = Column(Float)
    voting_power_percent: Mapped[Optional[float]] = Column(Float)
    holder_type: Mapped[Optional[str]] = Column(String(50))
    is_qualified: Mapped[bool] = Column(Boolean, default=False)
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    snapshot_date: Mapped[Optional[datetime]] = Column(Date)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    company = relationship("Company", back_populates="shareholders")


# ─── Pipeline Run Log ───────────────────────────────────────────────────────
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    module_name: Mapped[str] = Column(String(50), nullable=False)
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = Column(DateTime)
    status: Mapped[str] = Column(String(20), default="RUNNING")
    records_processed: Mapped[int] = Column(Integer, default=0)
    records_inserted: Mapped[int] = Column(Integer, default=0)
    records_updated: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[Optional[str]] = Column(Text)


# ═══════════════════════════════════════════════════════════════════════════════
# Database Engine, Session Factory & Upsert Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_engine = None
_SessionFactory = None
_is_sqlite = False


def init_db(config=None):
    """Initialize the database engine and create all tables."""
    global _engine, _SessionFactory, _is_sqlite
    if config is None:
        config = CONFIG.db

    _is_sqlite = config.is_sqlite
    connect_args = {}
    if _is_sqlite:
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        config.url,
        echo=config.echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _SessionFactory = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)
    return _engine


def get_session():
    """Get a new database session."""
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


# ── SQLite-friendly upsert helpers ───────────────────────────────────────────

def upsert_company(session, data):
    """Insert or update a company record (UPSERT)."""
    ticker = data["ticker"]
    existing = session.query(Company).filter(Company.ticker == ticker).first()

    if existing:
        for key, val in data.items():
            if key != "ticker" and val is not None:
                setattr(existing, key, val)
        session.flush()
        return existing
    else:
        company = Company(**data)
        session.add(company)
        session.flush()
        return company


def upsert_financial(session, company_id, data):
    """Insert or update a financial record (UPSERT by company_id+year+period)."""
    year = data["year"]
    period = data["period"]

    existing = (
        session.query(Financial)
        .filter_by(company_id=company_id, year=year, period=period)
        .first()
    )

    if existing:
        for key, val in data.items():
            if key not in ("company_id", "year", "period") and val is not None:
                setattr(existing, key, val)
        session.flush()
        return existing
    else:
        data["company_id"] = company_id
        fin = Financial(**data)
        session.add(fin)
        session.flush()
        return fin


def upsert_disclosure(session, data):
    """Insert a disclosure record (skip if disclosure_id already exists)."""
    disc_id = data["disclosure_id"]
    existing = session.query(Disclosure).filter(Disclosure.disclosure_id == disc_id).first()

    if existing:
        return existing

    disc = Disclosure(**data)
    session.add(disc)
    session.flush()
    return disc
