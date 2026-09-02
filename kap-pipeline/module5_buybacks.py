"""
Module 5 - Pay Gerialim Programlari
====================================
Module 3 tarafindan veritabanina yazilan bildirimleri isler.
Gerialim ile ilgili bildirimleri tarar ve regex ile veri cikarir.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from database import (
    Company,
    Disclosure,
    ShareBuyback,
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


# ── Buyback Patterns ────────────────────────────────────────────────────────

_BUYBACK_KEYWORDS = [
    "geri alım", "geri alim", "kendi payını", "kendi payini",
    "pay geri alım", "pay geri alim", "buyback", "kendi payları",
    "kendi paylari", "paylarin geri alimi", "payların geri alımı",
]

_BUDGET_PATTERNS = [
    re.compile(r"toplam\s+(?:tutar|bedel|bütçe)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
    re.compile(r"azami\s+(?:tutar|pay\s+bedeli)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
    re.compile(r"geri\s+alım\s+(?:için\s+)?(?:ayrılacak|tutar)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]

_MAX_SHARES_PATTERNS = [
    re.compile(r"azami\s+(?:pay\s+adedi|adet)\s*[:=]?\s*([\d.,]+)", re.I),
    re.compile(r"toplam\s+(?:pay\s+adedi|adet)\s*[:=]?\s*([\d.,]+)", re.I),
    re.compile(r"geri\s+alınacak\s+(?:azami\s+)?pay\s+adedi\s*[:=]?\s*([\d.,]+)", re.I),
]

_BOUGHT_PATTERNS = [
    re.compile(r"bugüne\s+kadar\s+geri\s+alınan\s+(?:toplam\s+)?pay\s+(?:tutarı|adedi)\s*[:=]?\s*([\d.,]+)", re.I),
    re.compile(r"geri\s+alınan\s+toplam\s+adet\s*[:=]?\s*([\d.,]+)", re.I),
    re.compile(r"toplam\s+geri\s+alınan\s*[:=]?\s*([\d.,]+)", re.I),
]

_AVG_PRICE_PATTERNS = [
    re.compile(r"(?:ortalama|maaliyet|maliyet)\s+(?:fiyat|bedel)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]

_LAST_PRICE_PATTERNS = [
    re.compile(r"(?:son|işlem)\s+fiyatı?\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]

_CAPITAL_RATIO_PATTERNS = [
    re.compile(r"sermaye\s+(?:orani|oranı)?\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
]

_TOTAL_SPENT_PATTERNS = [
    re.compile(r"(?:toplam|harcanan)\s+(?:tutar|bedel)\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
]


def run_module5_buybacks() -> int:
    """
    Module 5 entry point:
    Scan disclosures for buyback keywords, parse structured data.
    """
    logger.info("=" * 60)
    logger.info("Module 5: Pay Gerialim Programlari")
    logger.info("=" * 60)

    session = get_session()
    count = 0

    from sqlalchemy import or_

    # Find buyback-related disclosures
    or_conditions = []
    for kw in _BUYBACK_KEYWORDS:
        or_conditions.append(Disclosure.title.ilike(f"%{kw}%"))
    or_conditions.append(Disclosure.category == "Geri_Alim")

    query = session.query(Disclosure).filter(or_(*or_conditions)).order_by(
        Disclosure.publish_date.desc()
    )
    disclosures = query.all()
    logger.info(f"Bulunan gerialim bildirimleri: {len(disclosures)}")

    for disc in disclosures:
        try:
            # Check if already processed
            existing = (
                session.query(ShareBuyback)
                .filter_by(disclosure_id=disc.disclosure_id)
                .first()
            )
            if existing:
                continue

            if not disc.company_id:
                continue

            text = f"{disc.title} {disc.raw_content or ''}"

            # Verify it's actually a buyback disclosure
            text_lower = text.lower()
            is_buyback = any(kw in text_lower for kw in _BUYBACK_KEYWORDS)
            if not is_buyback:
                continue

            record = {
                "company_id": disc.company_id,
                "disclosure_id": disc.disclosure_id,
                "program_start_date": disc.publish_date.date() if disc.publish_date else None,
                "total_budget_tl": _extract_number(text, _BUDGET_PATTERNS),
                "max_shares": int(_extract_number(text, _MAX_SHARES_PATTERNS) or 0) or None,
                "total_bought_shares": int(_extract_number(text, _BOUGHT_PATTERNS) or 0) or None,
                "avg_buyback_price": _extract_number(text, _AVG_PRICE_PATTERNS),
                "last_transaction_price": _extract_number(text, _LAST_PRICE_PATTERNS),
                "capital_ratio_percent": _extract_number(text, _CAPITAL_RATIO_PATTERNS),
                "total_spent_tl": _extract_number(text, _TOTAL_SPENT_PATTERNS),
            }

            buyback = ShareBuyback(**record)
            session.add(buyback)
            count += 1

            logger.info(f"  + {disc.symbol}: Bütçe={record['total_budget_tl']} TL, Adet={record['max_shares']}")

        except Exception as e:
            logger.error(f"  Error on {disc.disclosure_id}: {e}")
            continue

    session.commit()
    session.close()

    logger.info("=" * 60)
    logger.info(f"Module 5 TAMAMLANDI: {count} gerialim kaydi")
    logger.info("=" * 60)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = run_module5_buybacks()
    print(f"Module 5 done. {n} buyback records.")
