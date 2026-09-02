"""
Module 6 - Halka Arz (IPO) & Izahname Analizi
==============================================
Module 3 tarafindan veritabanina yazilan bildirimleri isler.
IPO ile ilgili bildirimleri tarar ve regex ile veri cikarir.
"""

import logging
import re
from typing import Optional

from database import (
    Disclosure,
    IpoData,
    get_session,
)

logger = logging.getLogger(__name__)


def _parse_tr_number(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.strip().replace("\xa0", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract(text: str, patterns: list) -> Optional[str]:
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip()
    return None


def _extract_number(text: str, patterns: list) -> Optional[float]:
    raw = _extract(text, patterns)
    return _parse_tr_number(raw) if raw else None


# ── IPO Patterns ────────────────────────────────────────────────────────────

_IPO_KEYWORDS = [
    "halka arz", "izahname", "talep toplama", "ihrac",
    "hammad arz", "tahvil ihracı", "bono ihracı",
]

_IPO_PRICE_PATTERNS = [
    re.compile(r"(?:halka\s+arz\s+)?fiyatı?\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
    re.compile(r"ihrac\s+fiyatı?\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]

_DISCOUNT_PATTERNS = [
    re.compile(r"(?:iskonto|indirim)\s+(?:oranı)?\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]

_DIST_TYPE_PATTERNS = [
    re.compile(r"(?:dağıtım|tahsisat)\s+(?:yöntemi|şekli)\s*[:=]?\s*(.+?)(?:\.|,|\n|$)", re.I),
]

_CONSORTIUM_PATTERNS = [
    re.compile(r"(?:konsorsiyum\s+lideri|lider\s+kurum)\s*[:=]?\s*(.+?)(?:\.|,|\n|$)", re.I),
]

_TOTAL_SHARES_PATTERNS = [
    re.compile(r"(?:halka\s+arz\s+)?(?:toplam\s+)?(?:pay\s+adedi|adet)\s*[:=]?\s*([\d.,]+)", re.I),
]

_OFFERING_AMOUNT_PATTERNS = [
    re.compile(r"(?:halka\s+arz\s+)?(?:tutar|bedel)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]

# Fund usage patterns
_FUND_INV_PATTERNS = [
    re.compile(r"(?:yeni\s+yatırım|kapasite\s+artışı|yatırım)\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]
_FUND_RD_PATTERNS = [
    re.compile(r"(?:ar-?ge|teknoloji|AR-GE)\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]
_FUND_WC_PATTERNS = [
    re.compile(r"(?:işletme\s+sermayesi|çalışma\s+sermayesi)\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]
_FUND_DEBT_PATTERNS = [
    re.compile(r"(?:borç\s+kapama|borç\s+ödeme|finansal\s+borç)\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]


def _extract_company_name(title: str) -> Optional[str]:
    """Try to extract company name from disclosure title."""
    patterns = [
        re.compile(r"^(.+?)\s*[-–—]\s*(?:halka|izahname|talep)", re.I),
        re.compile(r"^(.+?)\s+halka\s+arz", re.I),
        re.compile(r"^(.+?)\s+izahname", re.I),
    ]
    for p in patterns:
        m = p.match(title)
        if m:
            name = m.group(1).strip()
            if len(name) > 3:
                return name
    return None


def run_module6_ipo() -> int:
    """
    Module 6 entry point:
    Scan disclosures for IPO keywords, parse structured data.
    """
    logger.info("=" * 60)
    logger.info("Module 6: Halka Arz (IPO)")
    logger.info("=" * 60)

    session = get_session()
    count = 0

    from sqlalchemy import or_

    or_conditions = []
    for kw in _IPO_KEYWORDS:
        or_conditions.append(Disclosure.title.ilike(f"%{kw}%"))
    or_conditions.append(Disclosure.category == "IPO")

    query = session.query(Disclosure).filter(or_(*or_conditions)).order_by(
        Disclosure.publish_date.desc()
    )
    disclosures = query.all()
    logger.info(f"Bulunan IPO bildirimleri: {len(disclosures)}")

    for disc in disclosures:
        try:
            existing = (
                session.query(IpoData)
                .filter_by(disclosure_id=disc.disclosure_id)
                .first()
            )
            if existing:
                continue

            text = f"{disc.title} {disc.raw_content or ''}"
            text_lower = text.lower()

            # Verify it's actually IPO related
            is_ipo = any(kw in text_lower for kw in _IPO_KEYWORDS)
            if not is_ipo:
                continue

            company_name = _extract_company_name(disc.title) or disc.symbol or "Unknown"

            record = {
                "company_name": company_name,
                "ticker": disc.symbol,
                "disclosure_id": disc.disclosure_id,
                "ipo_date": disc.publish_date.date() if disc.publish_date else None,
                "ipo_price": _extract_number(text, _IPO_PRICE_PATTERNS),
                "discount_ratio": _extract_number(text, _DISCOUNT_PATTERNS),
                "distribution_type": _extract(text, _DIST_TYPE_PATTERNS),
                "consortium_leader": _extract(text, _CONSORTIUM_PATTERNS),
                "total_offered_shares": int(_extract_number(text, _TOTAL_SHARES_PATTERNS) or 0) or None,
                "offering_amount_tl": _extract_number(text, _OFFERING_AMOUNT_PATTERNS),
                "use_of_funds_investment_pct": _extract_number(text, _FUND_INV_PATTERNS),
                "use_of_funds_rd_pct": _extract_number(text, _FUND_RD_PATTERNS),
                "use_of_funds_working_capital_pct": _extract_number(text, _FUND_WC_PATTERNS),
                "use_of_funds_debt_pct": _extract_number(text, _FUND_DEBT_PATTERNS),
            }

            ipo = IpoData(**record)
            session.add(ipo)
            count += 1

            logger.info(f"  + {company_name}: Fiyat={record['ipo_price']} TL")

        except Exception as e:
            logger.error(f"  Error on {disc.disclosure_id}: {e}")
            continue

    session.commit()
    session.close()

    logger.info("=" * 60)
    logger.info(f"Module 6 TAMAMLANDI: {count} IPO kaydi")
    logger.info("=" * 60)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = run_module6_ipo()
    print(f"Module 6 done. {n} IPO records.")
