"""
Module 4 - Kurumsal Islemler & Sermaye Hareketleri
===================================================
Module 3 tarafindan veritabanina yazilan bildirimleri isler.
Yeni API cagrisi yapmaz, mevcut Disclosure tablosundan calisir.

Temettu verileri: brüt/net hisse basina, verim, ex-date, odeme tarihi
Sermaye artirimlari: bedelli/bedelsiz orani, ruchan tarihleri
"""

import logging
import re
from datetime import datetime
from typing import Any, List, Optional

from database import (
    Company,
    CorporateAction,
    Disclosure,
    get_session,
)

logger = logging.getLogger(__name__)


# ── Turkish Number Parser ────────────────────────────────────────────────────

def _parse_tr_number(text: str) -> Optional[float]:
    """Parse Turkish-formatted number: '1.234,56' -> 1234.56"""
    if not text:
        return None
    text = text.strip().replace("\xa0", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_tr_date(text: str) -> Optional[str]:
    """Parse Turkish date, return YYYY-MM-DD string."""
    if not text:
        return None
    text = text.strip()
    for fmt in ["%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── Title-Based Classification ──────────────────────────────────────────────

def _is_dividend(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in [
        "temettü", "kâr payı", "kar payi", "dividend",
        "kâr dağıt", "kar dagit", "nakit temettü",
        "bedelsiz", "kâr payı dağıtım",
    ])


def _is_capital_increase(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in [
        "sermaye artırımı", "sermaye artirimi", "bedelli",
        "rüçhan", "ruçhan", "hak kullanımı", "hak kullanimi",
    ])


def _detect_status(title: str) -> str:
    t = title.lower()
    for kw in ["onaylandı", "kesinleşti", "kabul edildi", "uygulandı", "tescili"]:
        if kw in t:
            return "APPROVED"
    for kw in ["teklif", "öneri", "karar", "gündem", "başvuru"]:
        if kw in t:
            return "PROPOSAL"
    return "PROPOSAL"


# ── Pattern-Based Data Extraction ───────────────────────────────────────────

# Dividend patterns (brüt/net temettü, verim, tarihler)
_DIV_PATTERNS = {
    "gross_per_share": [
        re.compile(r"brüt\s*(?:temettü|kâr\s*payı)?\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
        re.compile(r"hisse\s*başına\s*(?:brüt)?\s*([\d.,]+)\s*TL", re.I),
        re.compile(r"her\s*bir\s*pay\s*(?:için|başına)\s*(?:brüt)?\s*([\d.,]+)\s*TL", re.I),
        re.compile(r"pay\s*başına\s*([\d.,]+)\s*TL", re.I),
    ],
    "net_per_share": [
        re.compile(r"net\s*(?:temettü|kâr\s*payı)?\s*[:=]?\s*([\d.,]+)\s*TL", re.I),
        re.compile(r"vergi\s*sonrası\s*(?:temettü)?\s*([\d.,]+)\s*TL", re.I),
    ],
    "yield_percent": [
        re.compile(r"temettü\s*verimi\s*[:=]?\s*([\d.,]+)\s*%", re.I),
        re.compile(r"kâr\s*payı\s*verimi\s*[:=]?\s*([\d.,]+)\s*%", re.I),
    ],
    "ex_date": [
        re.compile(r"hak\s*kullanım\s*(?:başlamasına)?\s*esas\s*tarih\s*[:=]?\s*([\d./]+)", re.I),
        re.compile(r"ex[- ]?date\s*[:=]?\s*([\d./]+)", re.I),
        re.compile(r"başlangıç\s*tarihi\s*[:=]?\s*([\d./]+)", re.I),
    ],
    "payment_date": [
        re.compile(r"(?:ödeme|nakit\s*ödeme)\s+tarihi\s*[:=]?\s*([\d./]+)", re.I),
        re.compile(r"ödeme\s+bAŞLADI", re.I),
    ],
}

# Capital increase patterns
_CAP_PATTERNS = {
    "bedelli_ratio": [
        re.compile(r"bedelli\s*(?:sermaye\s*artırımı)?\s*(?:oranı)?\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
    ],
    "bedelsiz_ratio": [
        re.compile(r"bedelsiz\s*(?:sermaye\s*artırımı)?\s*(?:oranı)?\s*[:=]?\s*%?\s*([\d.,]+)\s*%", re.I),
    ],
    "ruhcan_start": [
        re.compile(r"rüçhan\s*hakkı\s*(?:kullanım\s*)?(?:başlangıç|başlama)\s*(?:tarihi)?\s*[:=]?\s*([\d./]+)", re.I),
    ],
    "ruhcan_end": [
        re.compile(r"rüçhan\s*hakkı\s*(?:kullanım\s*)?(?:bitiş|son)\s*(?:tarihi)?\s*[:=]?\s*([\d./]+)", re.I),
    ],
}


def _extract(text: str, patterns: list) -> Optional[str]:
    """Try each regex pattern, return first matched group(1)."""
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip()
    return None


def _extract_number(text: str, patterns: list) -> Optional[float]:
    raw = _extract(text, patterns)
    return _parse_tr_number(raw) if raw else None


def _extract_date(text: str, patterns: list) -> Optional[str]:
    raw = _extract(text, patterns)
    return _parse_tr_date(raw) if raw else None


# ── Module 4 Main Function ──────────────────────────────────────────────────

def run_module4_corporate_actions() -> int:
    """
    Module 4 entry point:
    Scan disclosures for dividend and capital increase keywords,
    parse each disclosure's raw_content for structured data.
    """
    logger.info("=" * 60)
    logger.info("Module 4: Kurumsal Islemler")
    logger.info("=" * 60)

    session = get_session()
    count = 0

    # Find relevant disclosures
    from sqlalchemy import or_

    query = session.query(Disclosure).filter(
        or_(
            Disclosure.category.in_(["Temettu", "Sermaye"]),
            Disclosure.title.ilike("%temettü%"),
            Disclosure.title.ilike("%kâr payı%"),
            Disclosure.title.ilike("%kar payi%"),
            Disclosure.title.ilike("%bedelli%"),
            Disclosure.title.ilike("%bedelsiz%"),
            Disclosure.title.ilike("%sermaye artırımı%"),
            Disclosure.title.ilike("%hak kullanımı%"),
            Disclosure.title.ilike("%rüçhan%"),
        )
    ).order_by(Disclosure.publish_date.desc())

    disclosures = query.all()
    logger.info(f"Bulunan ilgili bildirim sayisi: {len(disclosures)}")

    for disc in disclosures:
        try:
            # Check if already processed
            existing = (
                session.query(CorporateAction)
                .filter_by(disclosure_id=disc.disclosure_id)
                .first()
            )
            if existing:
                continue

            # Combine title + raw_content for extraction
            text = f"{disc.title} {disc.raw_content or ''}"

            if not disc.company_id:
                continue

            if _is_dividend(disc.title):
                action = _build_dividend(disc, text)
            elif _is_capital_increase(disc.title):
                action = _build_capital(disc, text)
            else:
                continue

            ca = CorporateAction(**action)
            session.add(ca)
            count += 1
            logger.info(f"  + {disc.symbol}: {action['action_type']} ({action['status']})")

        except Exception as e:
            logger.error(f"  Error on {disc.disclosure_id}: {e}")
            continue

    session.commit()
    session.close()

    logger.info("=" * 60)
    logger.info(f"Module 4 TAMAMLANDI: {count} kurumsal islem")
    logger.info("=" * 60)
    return count


def _build_dividend(disc: Disclosure, text: str) -> dict:
    return {
        "company_id": disc.company_id,
        "disclosure_id": disc.disclosure_id,
        "action_type": "DIVIDEND",
        "gross_per_share": _extract_number(text, _DIV_PATTERNS["gross_per_share"]),
        "net_per_share": _extract_number(text, _DIV_PATTERNS["net_per_share"]),
        "yield_percent": _extract_number(text, _DIV_PATTERNS["yield_percent"]),
        "ratio_percent": None,
        "ex_date": _extract_date(text, _DIV_PATTERNS["ex_date"]),
        "payment_date": _extract_date(text, _DIV_PATTERNS["payment_date"]),
        "board_meeting_date": None,
        "general_assembly_date": None,
        "status": _detect_status(disc.title),
        "description": disc.title[:500],
    }


def _build_capital(disc: Disclosure, text: str) -> dict:
    bedelli = _extract_number(text, _CAP_PATTERNS["bedelli_ratio"])
    bedelsiz = _extract_number(text, _CAP_PATTERNS["bedelsiz_ratio"])
    return {
        "company_id": disc.company_id,
        "disclosure_id": disc.disclosure_id,
        "action_type": "RIGHTS_ISSUE" if bedelli else "BONUS_ISSUE",
        "gross_per_share": None,
        "net_per_share": None,
        "yield_percent": None,
        "ratio_percent": bedelli or bedelsiz,
        "ex_date": _extract_date(text, _CAP_PATTERNS["ruhcan_start"]),
        "payment_date": _extract_date(text, _CAP_PATTERNS["ruhcan_end"]),
        "board_meeting_date": None,
        "general_assembly_date": None,
        "status": _detect_status(disc.title),
        "description": disc.title[:500],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = run_module4_corporate_actions()
    print(f"Module 4 done. {n} corporate actions parsed.")
