"""
KAP Pipeline Configuration
--------------------------
Central configuration for database, API endpoints, rate limiting,
and module-specific settings.
"""

import os
from dataclasses import dataclass, field
from typing import List


# ─── Database ────────────────────────────────────────────────────────────────
@dataclass
class DatabaseConfig:
    # Set KAP_DB_URL to override (e.g. sqlite:///kap.db for SQLite)
    url_override: str = os.getenv("KAP_DB_URL", "")
    host: str = os.getenv("KAP_DB_HOST", "localhost")
    port: int = int(os.getenv("KAP_DB_PORT", "5432"))
    name: str = os.getenv("KAP_DB_NAME", "kap_pipeline")
    user: str = os.getenv("KAP_DB_USER", "postgres")
    password: str = os.getenv("KAP_DB_PASSWORD", "postgres")
    echo: bool = False  # SQLAlchemy SQL logging

    @property
    def url(self) -> str:
        if self.url_override:
            return self.url_override
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")


# ─── KAP Base URLs ──────────────────────────────────────────────────────────
KAP_BASE_URL = "https://www.kap.org.tr"

# Public AJAX / page endpoints
ENDPOINTS = {
    # Module 1 — Company list (HTML page, parseable)
    "company_list": f"{KAP_BASE_URL}/tr/bist-sirketler",
    # Module 1 — Company detail page (contains mkkMemberId, share structure)
    "company_detail": f"{KAP_BASE_URL}/tr/sirket-bilgileri-genel",
    # Module 2 — Financial statements page per company
    "financials_page": f"{KAP_BASE_URL}/tr/sirket-finansal-bilgileri",
    # Module 3 — Disclosure search (POST with JSON body)
    "disclosure_search": f"{KAP_BASE_URL}/tr/bildirim-sorgu",
    # Real KAP JSON API endpoints
    "api_disclosure_list": f"{KAP_BASE_URL}/tr/api/disclosure/list/main",
    "api_disclosure_by_criteria": f"{KAP_BASE_URL}/tr/api/disclosure/members/byCriteria",
    "api_member_filter": f"{KAP_BASE_URL}/tr/api/member/filter",
    "api_search": f"{KAP_BASE_URL}/tr/api/search/combined",
    "api_disclosure_subjects": f"{KAP_BASE_URL}/tr/api/disclosure/subjects",
    # Module 5 — Buyback notifications
    "buyback_page": f"{KAP_BASE_URL}/tr/pay-geri-alim",
    # Module 6 — IPO / Prospectus
    "ipo_page": f"{KAP_BASE_URL}/tr/halka-ariz",
    # Module 7 — Shareholder info
    "shareholder_page": f"{KAP_BASE_URL}/tr/ortaklik-yapisi",
    # Generic disclosure detail page
    "disclosure_detail": f"{KAP_BASE_URL}/tr/bildirim-detay",
}


# ─── Anti-Bot / HTTP Headers ────────────────────────────────────────────────
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": KAP_BASE_URL,
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "max-age=0",
}

AJAX_HEADERS = {
    "User-Agent": DEFAULT_HEADERS["User-Agent"],
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{KAP_BASE_URL}/tr/bildirim-sorgu",
    "Origin": KAP_BASE_URL,
    "Content-Type": "application/json",
}


# ─── Rate Limiting ──────────────────────────────────────────────────────────
@dataclass
class RateLimitConfig:
    # Delay between financial-statement requests (seconds)
    financials_min_delay: float = 2.0
    financials_max_delay: float = 4.5
    # Delay between disclosure page requests
    disclosures_min_delay: float = 1.5
    disclosures_max_delay: float = 3.0
    # Delay between company detail page requests
    company_detail_min_delay: float = 2.0
    company_detail_max_delay: float = 4.0
    # Cron intervals (minutes)
    live_feed_interval_minutes: int = 5
    financials_cron_hour: int = 2  # Run at 02:00 daily
    seed_cron_hour: int = 3  # Run at 03:00 daily


# ─── Module 3 — Disclosure Types & Category Keywords ───────────────────────
DISCLOSURE_TYPES = [
    "OZEL_DURUM_ACIKLAMASI",
    "FINANSAL_RAPOR",
    "GENEL_KURUL",
    "SERMAYE_ARTIRIMI",
    "TEMETTU",
    "ORTAKLIK_YAPISI",
    "GUNCELLENEN_FINANSAL_TABLO",
    "IHRAC",
]

CATEGORY_KEYWORDS: dict[str, List[str]] = {
    "Buyuklenme": ["büyüme", "satış artışı", "gelir artışı", "rekor"],
    "Yatirim": [
        "yatırım", "fabrika", "tesis", "kapasite",
        "iştirak", "birleşme", "devralma",
    ],
    "Finansman": [
        "finansman", "kredi", "borç", "tahvil", "bono",
        "sureçli menkul", "ipoteğe dayalı",
    ],
    "Ortaklik_Degisimi": [
        "ortaklık yapısı", "pay devri", "hakim hissedar",
        "n Pay satış", "pay alım",
    ],
    "Dava": ["dava", "tazminat", "soruşturma", "idari para cezası"],
    "Temettu": ["temettü", "kar payı", "dividend"],
    "Sermaye": ["sermaye artırımı", "bedelli", "bedelsiz", "rüçhan"],
    "Ihale": ["ihale", "kazanılan ihale", "teklif", "sözleşme"],
    "Yeni_Is": ["yeni iş ilişkisi", "sipariş", "sözleşme bedeli", "proje"],
    "Geri_Alım": ["geri alım", "kendi payını"],
    "IPO": ["halka arz", "izahname", "talep toplama"],
    "Diger": [],  # fallback
}


# ─── Module 2 — Financial Statement Key Names ───────────────────────────────
# These are the Turkish labels used in KAP's hierarchical JSON / HTML tables
# for extracting specific financial line items.
FINANCIAL_KEYS = {
    # Income Statement
    "revenue": ["Hasılat", "Net Satışlar", "Toplam Gelir"],
    "gross_profit": ["Brüt Kâr", "Brüt Kar"],
    "ebit": ["Esas Faaliyet Kârı", "Esas Faaliyet Karı"],
    "ebitda": ["FAVÖK", "FAVOK"],
    "net_profit": ["Net Dönem Kârı", "Net Kar", "Dönem Kârı", "Net dönem kârı"],
    # Balance Sheet
    "current_assets": ["Dönen Varlıklar", "Dönen Varliklar"],
    "non_current_assets": ["Duran Varlıklar", "Duran Varliklar"],
    "total_assets": ["Toplam Varlıklar", "Toplam Aktifler", "Toplam Varliklar"],
    "short_term_debt": [
        "Kısa Vadeli Yükümlülükler",
        "Kısa Vadeli Borçlar",
    ],
    "long_term_debt": [
        "Uzun Vadeli Yükümlülükler",
        "Uzun Vadeli Borçlar",
    ],
    "total_debt": ["Toplam Yükümlülükler", "Toplam Borçlar", "Toplam Borclar"],
    "financial_debt": ["Finansal Borçlar", "Finansal Borclar"],
    "cash_and_equivalents": [
        "Nakit ve Nakit Benzerleri",
        "Nakit Benzerleri",
        "Nakit",
    ],
    "equity": ["Özkaynaklar", "Toplam Özkaynaklar", "Ana Ortaklığa Ait Özkaynaklar"],
    "paid_capital": [
        "Ödenmiş Sermaye",
        "Ödenmiş/Çıkarılmış Sermaye",
        "Çıkarılmış Sermaye",
    ],
}


# ─── Full Config ────────────────────────────────────────────────────────────
@dataclass
class PipelineConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    rate: RateLimitConfig = field(default_factory=RateLimitConfig)
    batch_size: int = 50  # Companies per batch
    max_retries: int = 3
    request_timeout: int = 30  # seconds
    log_level: str = "INFO"


CONFIG = PipelineConfig()
