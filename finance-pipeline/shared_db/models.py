"""
Shared Database Models — PostgreSQL (SQLAlchemy ORM)
====================================================
All services share the same database and these models.
"""

import os
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Float,
    ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, relationship, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@localhost:5432/finance_platform",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# KAP MODELS
# ══════════════════════════════════════════════════════════════════════════════

class KapCompany(Base):
    __tablename__ = "kap_companies"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = Column(String(20), unique=True, nullable=False, index=True)
    mkk_id: Mapped[str] = Column(String(100), nullable=False)
    company_name: Mapped[Optional[str]] = Column(String(500))
    sector: Mapped[Optional[str]] = Column(String(200))
    market: Mapped[Optional[str]] = Column(String(100))
    is_active: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KapFinancial(Base):
    __tablename__ = "kap_financials"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "period", name="uq_kap_fin"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("kap_companies.id"), nullable=False)
    year: Mapped[int] = Column(Integer, nullable=False)
    period: Mapped[int] = Column(Integer, nullable=False)
    revenue: Mapped[Optional[float]] = Column(Numeric(20, 2))
    gross_profit: Mapped[Optional[float]] = Column(Numeric(20, 2))
    ebit: Mapped[Optional[float]] = Column(Numeric(20, 2))
    ebitda: Mapped[Optional[float]] = Column(Numeric(20, 2))
    net_profit: Mapped[Optional[float]] = Column(Numeric(20, 2))
    total_assets: Mapped[Optional[float]] = Column(Numeric(20, 2))
    total_debts: Mapped[Optional[float]] = Column(Numeric(20, 2))
    equity: Mapped[Optional[float]] = Column(Numeric(20, 2))
    paid_capital: Mapped[Optional[float]] = Column(Numeric(20, 2))
    current_ratio: Mapped[Optional[float]] = Column(Float)
    leverage_ratio: Mapped[Optional[float]] = Column(Float)
    roe: Mapped[Optional[float]] = Column(Float)
    roa: Mapped[Optional[float]] = Column(Float)
    gross_margin: Mapped[Optional[float]] = Column(Float)
    ebitda_margin: Mapped[Optional[float]] = Column(Float)
    net_margin: Mapped[Optional[float]] = Column(Float)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class KapDisclosure(Base):
    __tablename__ = "kap_disclosures"
    __table_args__ = (
        UniqueConstraint("disclosure_id", name="uq_kap_disclosure"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_id: Mapped[str] = Column(String(50), nullable=False, unique=True)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("kap_companies.id"))
    symbol: Mapped[Optional[str]] = Column(String(20))
    title: Mapped[str] = Column(Text, nullable=False)
    category: Mapped[Optional[str]] = Column(String(50))
    disclosure_type: Mapped[Optional[str]] = Column(String(100))
    publish_date: Mapped[datetime] = Column(DateTime, nullable=False, index=True)
    source_url: Mapped[Optional[str]] = Column(Text)
    is_catalyst: Mapped[bool] = Column(Boolean, default=False)
    raw_content: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class KapCorporateAction(Base):
    __tablename__ = "kap_corporate_actions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("kap_companies.id"))
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    action_type: Mapped[str] = Column(String(30), nullable=False)
    gross_per_share: Mapped[Optional[float]] = Column(Numeric(20, 4))
    net_per_share: Mapped[Optional[float]] = Column(Numeric(20, 4))
    yield_percent: Mapped[Optional[float]] = Column(Float)
    ratio_percent: Mapped[Optional[float]] = Column(Float)
    ex_date: Mapped[Optional[date]] = Column(Date)
    payment_date: Mapped[Optional[date]] = Column(Date)
    status: Mapped[Optional[str]] = Column(String(20))
    description: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# TEFAS MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TefasFund(Base):
    __tablename__ = "tefas_funds"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = Column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = Column(String(500))
    kind: Mapped[Optional[str]] = Column(String(10))  # YAT, EMK, BYF
    # Extra fields from fonBilgiGetir
    current_price: Mapped[Optional[float]] = Column(Numeric(20, 8))
    daily_return_pct: Mapped[Optional[float]] = Column(Float)
    shares_outstanding: Mapped[Optional[float]] = Column(Numeric(20, 2))
    market_cap: Mapped[Optional[float]] = Column(Numeric(20, 2))
    category: Mapped[Optional[str]] = Column(String(100))
    category_rank: Mapped[Optional[int]] = Column(Integer)
    category_fund_count: Mapped[Optional[int]] = Column(Integer)
    investor_count: Mapped[Optional[int]] = Column(BigInteger)
    market_share_pct: Mapped[Optional[float]] = Column(Float)
    # Fund group/type info from fonGrupGetir/fonTurGetir
    fund_group: Mapped[Optional[str]] = Column(String(100))
    fund_sub_type: Mapped[Optional[str]] = Column(String(100))
    # Tracking
    last_detail_fetch: Mapped[Optional[datetime]] = Column(DateTime)
    last_price_fetch: Mapped[Optional[datetime]] = Column(DateTime)
    price_count: Mapped[int] = Column(Integer, default=0)
    is_active: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TefasFundPrice(Base):
    __tablename__ = "tefas_fund_prices"
    __table_args__ = (
        UniqueConstraint("fund_id", "trade_date", name="uq_tefas_price"),
        Index("ix_tefas_date", "trade_date"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = Column(Integer, ForeignKey("tefas_funds.id"), nullable=False)
    code: Mapped[str] = Column(String(20), nullable=False, index=True)
    trade_date: Mapped[date] = Column(Date, nullable=False)
    price: Mapped[Optional[float]] = Column(Numeric(20, 8))
    shares_outstanding: Mapped[Optional[float]] = Column(Numeric(20, 2))
    investors_count: Mapped[Optional[int]] = Column(BigInteger)
    market_cap: Mapped[Optional[float]] = Column(Numeric(20, 2))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class TefasFundAllocation(Base):
    __tablename__ = "tefas_fund_allocations"
    __table_args__ = (
        UniqueConstraint("fund_id", "trade_date", name="uq_tefas_alloc"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = Column(Integer, ForeignKey("tefas_funds.id"), nullable=False)
    code: Mapped[str] = Column(String(20), nullable=False, index=True)
    trade_date: Mapped[date] = Column(Date, nullable=False)

    # ── Equity ──
    stock: Mapped[Optional[float]] = Column(Float)                                          # Hisse senedi
    exchange_traded_fund: Mapped[Optional[float]] = Column(Float)                           # Borsa yatırım fonu (BYF)
    foreign_equity: Mapped[Optional[float]] = Column(Float)                                 # Yabancı hisse senedi
    foreign_exchange_traded_funds: Mapped[Optional[float]] = Column(Float)                   # Yabancı BYF
    venture_capital_investment_fund: Mapped[Optional[float]] = Column(Float)                 # GSYF katılımı
    real_estate_investment_fund: Mapped[Optional[float]] = Column(Float)                     # GYF katılımı

    # ── Government Debt ──
    treasury_bill: Mapped[Optional[float]] = Column(Float)                                  # Hazine bonosu
    government_bond: Mapped[Optional[float]] = Column(Float)                                # Devlet tahvili
    government_bonds_and_bills_fx: Mapped[Optional[float]] = Column(Float)                  # Döviz cinsi devlet tahvili/bonosu
    public_domestic_debt_instruments: Mapped[Optional[float]] = Column(Float)               # Kamu iç borçlanma (döviz)
    government_lease_certificates: Mapped[Optional[float]] = Column(Float)                  # Kamu kira sertifikası
    government_lease_certificates_tl: Mapped[Optional[float]] = Column(Float)               # Kamu kira sertifikası (TL)
    government_lease_certificates_d: Mapped[Optional[float]] = Column(Float)                # Kamu kira sertifikası (döviz)
    government_lease_certificates_foreign: Mapped[Optional[float]] = Column(Float)          # Yabancı kamu kira sertifikası

    # ── Private Sector Debt ──
    commercial_paper: Mapped[Optional[float]] = Column(Float)                               # Ticari kağıt
    bank_bills: Mapped[Optional[float]] = Column(Float)                                     # Banka bonosu
    private_sector_lease_certificates: Mapped[Optional[float]] = Column(Float)              # Özel sektör kira sertifikası
    private_sector_bond: Mapped[Optional[float]] = Column(Float)                            # Özel sektör tahvili
    private_sector_international_lease: Mapped[Optional[float]] = Column(Float)             # Uluslararası özel sektör kira sertifikası
    private_sector_foreign_debt: Mapped[Optional[float]] = Column(Float)                    # Özel sektör yabancı borçlanma
    eurobonds: Mapped[Optional[float]] = Column(Float)                                      # Eurobond
    asset_backed_securities: Mapped[Optional[float]] = Column(Float)                        # Varlık dayalı menkul kıymet
    foreign_debt_instruments: Mapped[Optional[float]] = Column(Float)                       # Yabancı borçlanma aracı
    foreign_domestic_debt: Mapped[Optional[float]] = Column(Float)                          # Yabancı iç borçlanma
    foreign_private_sector_debt: Mapped[Optional[float]] = Column(Float)                    # Yabancı özel sektör borçlanma
    foreign_securities: Mapped[Optional[float]] = Column(Float)                             # Yabancı menkul kıymet
    foreign_investment_fund: Mapped[Optional[float]] = Column(Float)                        # Yabancı yatırım fonu katılma payı

    # ── Deposits & Participation ──
    term_deposit: Mapped[Optional[float]] = Column(Float)                                   # Vadeli mevduat (toplam)
    term_deposit_tl: Mapped[Optional[float]] = Column(Float)                                # Vadeli mevduat (TL)
    term_deposit_d: Mapped[Optional[float]] = Column(Float)                                 # Vadeli mevduat (döviz)
    term_deposit_au: Mapped[Optional[float]] = Column(Float)                                # Vadeli mevduat (altın)
    participation_account: Mapped[Optional[float]] = Column(Float)                          # Katılım hesabı (toplam)
    participation_account_tl: Mapped[Optional[float]] = Column(Float)                       # Katılım hesabı (TL)
    participation_account_d: Mapped[Optional[float]] = Column(Float)                        # Katılım hesabı (döviz)
    participation_account_au: Mapped[Optional[float]] = Column(Float)                       # Katılım hesabı (altın)
    futures_cash_collateral: Mapped[Optional[float]] = Column(Float)                        # Vadeli işlem teminatı

    # ── Precious Metals ──
    precious_metals: Mapped[Optional[float]] = Column(Float)                                # Kıymetli madenler (toplam)
    precious_metals_byf: Mapped[Optional[float]] = Column(Float)                            # Kıymetli maden BYF
    precious_metals_kba: Mapped[Optional[float]] = Column(Float)                            # Kıymetli maden kamu borçlanma aracı
    precious_metals_kks: Mapped[Optional[float]] = Column(Float)                            # Kıymetli maden kamu kira sertifikası

    # ── Repo / Reverse ──
    repo: Mapped[Optional[float]] = Column(Float)                                           # Repo
    reverse_repo: Mapped[Optional[float]] = Column(Float)                                   # Ters repo
    tmm: Mapped[Optional[float]] = Column(Float)                                            # TMM (Türev Menkul Kıymet)

    # ── Other ──
    fx_payable_bills: Mapped[Optional[float]] = Column(Float)                               # Döviz tahvil
    foreign_currency_bills: Mapped[Optional[float]] = Column(Float)                         # Yabancı para tahvil
    fund_participation_certificate: Mapped[Optional[float]] = Column(Float)                 # Fon katılma sertifikası
    real_estate_certificate: Mapped[Optional[float]] = Column(Float)                        # Gayrimenkul sertifikası
    derivatives: Mapped[Optional[float]] = Column(Float)                                    # Türev araçlar
    other: Mapped[Optional[float]] = Column(Float)                                          # Diğer

    # ── Metadata ──
    scraped_at: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# TEFAS REFERENCE DATA
# ══════════════════════════════════════════════════════════════════════════════

class TefasFundGroup(Base):
    """Fund groups from fonGrupGetir"""
    __tablename__ = "tefas_fund_groups"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = Column(Integer, unique=True, nullable=False)
    group_name: Mapped[str] = Column(String(100), nullable=False)


class TefasFundSubType(Base):
    """Fund sub-types from fonTurGetir"""
    __tablename__ = "tefas_fund_subtypes"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = Column(Integer, unique=True, nullable=False)
    type_name: Mapped[str] = Column(String(100), nullable=False)


class TefasAnnouncement(Base):
    """TEFAS announcements from fonTefasDuyuruGetir"""
    __tablename__ = "tefas_announcements"
    __table_args__ = (
        UniqueConstraint("seq_no", name="uq_tefas_duyuru"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    seq_no: Mapped[int] = Column(Integer, unique=True, nullable=False)
    title: Mapped[str] = Column(Text, nullable=False)
    detail: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# KAP MODULE 7-12 MODELS
# ══════════════════════════════════════════════════════════════════════════════

class KapShareholder(Base):
    """Module 7: Ortaklık Yapısı — Pay sahipleri, %5+ ortaklar"""
    __tablename__ = "kap_shareholders"
    __table_args__ = (
        UniqueConstraint("company_id", "holder_name", name="uq_kap_shareholder"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("kap_companies.id"), nullable=False)
    holder_name: Mapped[str] = Column(String(500), nullable=False)
    shares_amount: Mapped[Optional[float]] = Column(Numeric(20, 2))
    share_ratio_percent: Mapped[Optional[float]] = Column(Float)
    voting_power_percent: Mapped[Optional[float]] = Column(Float)
    holder_type: Mapped[Optional[str]] = Column(String(30))  # CORPORATE, REAL_PERSON
    is_qualified: Mapped[bool] = Column(Boolean, default=False)
    snapshot_date: Mapped[Optional[date]] = Column(Date)
    disclosure_id: Mapped[Optional[str]] = Column(String(50))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KapCashFlow(Base):
    """Module 8: Nakit Akış Tablosu"""
    __tablename__ = "kap_cashflows"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "period", name="uq_kap_cashflow"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("kap_companies.id"), nullable=False)
    year: Mapped[int] = Column(Integer, nullable=False)
    period: Mapped[int] = Column(Integer, nullable=False)
    net_income: Mapped[Optional[float]] = Column(Numeric(20, 2))
    depreciation: Mapped[Optional[float]] = Column(Numeric(20, 2))
    provisions: Mapped[Optional[float]] = Column(Numeric(20, 2))
    receivables_change: Mapped[Optional[float]] = Column(Numeric(20, 2))
    inventory_change: Mapped[Optional[float]] = Column(Numeric(20, 2))
    payables_change: Mapped[Optional[float]] = Column(Numeric(20, 2))
    operating_cash_flow: Mapped[Optional[float]] = Column(Numeric(20, 2))
    capex: Mapped[Optional[float]] = Column(Numeric(20, 2))
    investment_sales: Mapped[Optional[float]] = Column(Numeric(20, 2))
    acquisitions: Mapped[Optional[float]] = Column(Numeric(20, 2))
    investing_cash_flow: Mapped[Optional[float]] = Column(Numeric(20, 2))
    borrowings: Mapped[Optional[float]] = Column(Numeric(20, 2))
    repayments: Mapped[Optional[float]] = Column(Numeric(20, 2))
    equity_issued: Mapped[Optional[float]] = Column(Numeric(20, 2))
    dividends_paid: Mapped[Optional[float]] = Column(Numeric(20, 2))
    financing_cash_flow: Mapped[Optional[float]] = Column(Numeric(20, 2))
    net_change: Mapped[Optional[float]] = Column(Numeric(20, 2))
    opening_cash: Mapped[Optional[float]] = Column(Numeric(20, 2))
    closing_cash: Mapped[Optional[float]] = Column(Numeric(20, 2))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class KapManagement(Base):
    """Module 9: Yönetim Kurulu ve CEO"""
    __tablename__ = "kap_management"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_kap_management"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("kap_companies.id"), nullable=False)
    name: Mapped[str] = Column(String(300), nullable=False)
    title: Mapped[Optional[str]] = Column(String(200))
    member_type: Mapped[Optional[str]] = Column(String(30))  # chairman, ceo, cfo, independent, member
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KapSubsidiary(Base):
    """Module 10: Bağlı Ortaklıklar ve İştirakler"""
    __tablename__ = "kap_subsidiaries"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_kap_subsidiary"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = Column(Integer, ForeignKey("kap_companies.id"), nullable=False)
    name: Mapped[str] = Column(String(500), nullable=False)
    share_percent: Mapped[Optional[float]] = Column(Float)
    country: Mapped[Optional[str]] = Column(String(100))
    activity: Mapped[Optional[str]] = Column(String(200))
    relation_type: Mapped[Optional[str]] = Column(String(30))  # subsidiary, affiliate, investment
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KapPortfolioReport(Base):
    """Module 11: Portföy Dağılım Raporları"""
    __tablename__ = "kap_portfolio_reports"
    __table_args__ = (
        UniqueConstraint("disclosure_id", "security_name", name="uq_kap_portfolio"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_id: Mapped[str] = Column(String(50), nullable=False)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("kap_companies.id"))
    symbol: Mapped[Optional[str]] = Column(String(20))
    report_date: Mapped[Optional[datetime]] = Column(DateTime)
    security_name: Mapped[str] = Column(String(500), nullable=False)
    quantity: Mapped[Optional[float]] = Column(Numeric(20, 2))
    value_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    weight_percent: Mapped[Optional[float]] = Column(Float)
    price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class KapFinancialNote(Base):
    """Module 12: Finansal Dipnotlar"""
    __tablename__ = "kap_financial_notes"
    __table_args__ = (
        UniqueConstraint("disclosure_id", name="uq_kap_note"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_id: Mapped[str] = Column(String(50), nullable=False, unique=True)
    company_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("kap_companies.id"))
    symbol: Mapped[Optional[str]] = Column(String(20))
    title: Mapped[Optional[str]] = Column(Text)
    note_type: Mapped[Optional[str]] = Column(String(50))  # financial_note, risk_report, off_balance_sheet
    content_text: Mapped[Optional[str]] = Column(Text)
    source_url: Mapped[Optional[str]] = Column(Text)
    publish_date: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 13: BIST STOCK PRICES
# ══════════════════════════════════════════════════════════════════════════════

class BistStockPrice(Base):
    """Current + recent BIST stock prices from Yahoo Finance."""
    __tablename__ = "bist_stock_prices"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_bist_price"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = Column(String(20), nullable=False, unique=True, index=True)
    company_name: Mapped[Optional[str]] = Column(String(500))
    price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    previous_close: Mapped[Optional[float]] = Column(Numeric(20, 4))
    day_high: Mapped[Optional[float]] = Column(Numeric(20, 4))
    day_low: Mapped[Optional[float]] = Column(Numeric(20, 4))
    volume: Mapped[Optional[int]] = Column(BigInteger)
    market_cap: Mapped[Optional[float]] = Column(Numeric(20, 2))
    pe_ratio: Mapped[Optional[float]] = Column(Float)
    pb_ratio: Mapped[Optional[float]] = Column(Float)
    dividend_yield: Mapped[Optional[float]] = Column(Float)
    week52_high: Mapped[Optional[float]] = Column(Numeric(20, 4))
    week52_low: Mapped[Optional[float]] = Column(Numeric(20, 4))
    day_change_pct: Mapped[Optional[float]] = Column(Float)
    is_xu100: Mapped[bool] = Column(Boolean, default=False)
    is_xbank: Mapped[bool] = Column(Boolean, default=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 14: ENHANCED DISCLOSURE DETAILS
# ══════════════════════════════════════════════════════════════════════════════

class DisclosureDetail(Base):
    """Structured data parsed from specific disclosure types."""
    __tablename__ = "disclosure_details"
    __table_args__ = (
        UniqueConstraint("disclosure_index", name="uq_disc_detail"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    disclosure_index: Mapped[str] = Column(String(50), nullable=False, unique=True)
    ticker: Mapped[Optional[str]] = Column(String(20))
    title: Mapped[Optional[str]] = Column(Text)
    detail_type: Mapped[Optional[str]] = Column(String(50))  # tender, block_sale, new_business, qualified_investor
    # Tender/Business
    client_name: Mapped[Optional[str]] = Column(String(500))
    contract_amount_tl: Mapped[Optional[float]] = Column(Numeric(20, 2))
    contract_amount_usd: Mapped[Optional[float]] = Column(Numeric(20, 2))
    contract_amount_eur: Mapped[Optional[float]] = Column(Numeric(20, 2))
    revenue_impact_pct: Mapped[Optional[float]] = Column(Float)
    delivery_date: Mapped[Optional[str]] = Column(String(100))
    # Block sale
    seller_name: Mapped[Optional[str]] = Column(String(500))
    buyer_name: Mapped[Optional[str]] = Column(String(500))
    block_shares: Mapped[Optional[int]] = Column(BigInteger)
    block_price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    block_ratio_pct: Mapped[Optional[float]] = Column(Float)
    # Qualified investor
    qi_investor: Mapped[Optional[str]] = Column(String(500))
    qi_shares: Mapped[Optional[int]] = Column(BigInteger)
    qi_price: Mapped[Optional[float]] = Column(Numeric(20, 4))
    publish_date: Mapped[Optional[datetime]] = Column(DateTime)
    source_url: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 15: INDEX & SETTLEMENT DATA
# ══════════════════════════════════════════════════════════════════════════════

class IndexConstituent(Base):
    """BIST index membership (XU100, XBANK, XULAS etc.)"""
    __tablename__ = "index_constituents"
    __table_args__ = (
        UniqueConstraint("index_name", "ticker", name="uq_index_member"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    index_name: Mapped[str] = Column(String(30), nullable=False)  # XU100, XBANK, XULAS
    ticker: Mapped[str] = Column(String(20), nullable=False)
    weight_pct: Mapped[Optional[float]] = Column(Float)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SettlementData(Base):
    """Daily settlement (takas) data — foreign/base/common ratios."""
    __tablename__ = "settlement_data"
    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_settlement"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = Column(String(20), nullable=False, index=True)
    trade_date: Mapped[date] = Column(Date, nullable=False)
    foreign_ratio_pct: Mapped[Optional[float]] = Column(Float)
    base_ratio_pct: Mapped[Optional[float]] = Column(Float)
    common_ratio_pct: Mapped[Optional[float]] = Column(Float)
    foreign_shares: Mapped[Optional[int]] = Column(BigInteger)
    total_shares: Mapped[Optional[int]] = Column(BigInteger)
    free_float_pct: Mapped[Optional[float]] = Column(Float)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUN LOG (shared)
# ══════════════════════════════════════════════════════════════════════════════

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = Column(String(50), nullable=False, index=True)
    module_name: Mapped[str] = Column(String(50), nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False, default="RUNNING")
    records_processed: Mapped[int] = Column(Integer, default=0)
    records_inserted: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[Optional[str]] = Column(Text)
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = Column(DateTime)


# ══════════════════════════════════════════════════════════════════════════════
# MARKET DATA — Macro Economic & Market Indicators
# ══════════════════════════════════════════════════════════════════════════════

class MarketIndicator(Base):
    """Macro economic indicators: TCMB rate, CPI, Fed rate, etc."""
    __tablename__ = "market_indicators"
    __table_args__ = (
        UniqueConstraint("name", name="uq_market_indicator"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = Column(String(50), nullable=False, unique=True, index=True)
    value: Mapped[Optional[float]] = Column(Float)
    category: Mapped[Optional[str]] = Column(String(30))   # macro, rate, commodity, crypto
    source: Mapped[Optional[str]] = Column(String(100))     # tcmb.gov.tr, tuik.gov.tr, etc.
    description: Mapped[Optional[str]] = Column(String(500))
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class MarketRate(Base):
    """Exchange rates: USD/TRY, USD/JPY, EUR/TRY, GBP/TRY."""
    __tablename__ = "market_rates"
    __table_args__ = (
        UniqueConstraint("pair", name="uq_market_rate"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = Column(String(20), nullable=False, unique=True, index=True)
    rate: Mapped[Optional[float]] = Column(Float)
    source: Mapped[Optional[str]] = Column(String(100))
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class CommodityPrice(Base):
    """Commodity prices: Gold, Silver, Copper, ETFs."""
    __tablename__ = "commodity_prices"
    __table_args__ = (
        UniqueConstraint("name", name="uq_commodity"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = Column(String(50), nullable=False, unique=True, index=True)
    price: Mapped[Optional[float]] = Column(Float)
    unit: Mapped[Optional[str]] = Column(String(20))      # USD/oz, USD/lb, USD
    source: Mapped[Optional[str]] = Column(String(100))
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class CryptoPrice(Base):
    """Cryptocurrency prices: BTC, ETH, etc."""
    __tablename__ = "crypto_prices"
    __table_args__ = (
        UniqueConstraint("pair", name="uq_crypto"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = Column(String(20), nullable=False, unique=True, index=True)
    price: Mapped[Optional[float]] = Column(Float)
    source: Mapped[Optional[str]] = Column(String(100))
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
