"""
Module 3 - Canli Bildirim Akisi (Genis Kapsamli)
=================================================
KAP byCriteria API + pykap kullanarak tum bildirim turlerini ceker.

Desteklenen turler:
  - FR: Finansal Raporlar (bilanco, gelir tablosu)
  - ODA: Ozel Durum Aciklamasi (temettu, sermaye artisi, geri alim, ihale, dava, vb.)
  - MR: Mali Tablolar (duzenlenmemis)
  - YAP: Yapilandirma
  - KV: Konsolide Veriler

Ornek bildirim kategorileri (title bazli):
  - Temettu, Sermaye_Artirimi, Bedelli, Bedelsiz, Geri_Alom,
  - Yeni_Is, Ihale, Siparis, Dava, Finansman, Yatirim, vb.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from client import get_client
from config import CONFIG, KAP_BASE_URL
from database import (
    Company,
    Disclosure,
    get_session,
    upsert_disclosure,
)

logger = logging.getLogger(__name__)

# KAP Disclosure Subject IDs (from pykap source)
SUBJECT_IDS = {
    "financial_report": "4028328c594bfdca01594c0af9aa0057",
    "operating_review": "4028328d594c04f201594c5155dd0076",
}

# Disclosure class values for byCriteria API
DISCLOSURE_CLASSES = ["FR", "ODA", "MR", "YAP", "KV"]


def _categorize(title: str) -> tuple:
    """Categorize disclosure title. Returns (category, is_catalyst)."""
    t = title.lower()

    # -- Catalysts (high impact) --
    if any(kw in t for kw in ["temettü", "kar payi", "kar payı", "dividend", "kâr dağıt", "kâr payı dağıtım"]):
        return "Temettu", True
    if any(kw in t for kw in ["sermaye artırımı", "bedelli", "bedelsiz", "hak kullanımı", "rüçhan"]):
        return "Sermaye", True
    if any(kw in t for kw in ["geri alım", "geri alim", "kendi payını", "kendi payini", "buyback"]):
        return "Geri_Alim", True
    if any(kw in t for kw in ["halka arz", "izahname", "talep toplama", "ihrac"]):
        return "IPO", True
    if any(kw in t for kw in ["yeni iş", "yeni iş ilişkisi", "sipariş", "sözleşme", "ihale", "işgemeç"]):
        return "Yeni_Is", True
    if any(kw in t for kw in ["satış", "gelir", "büyüme", "artış", "rekor"]):
        return "Buyuklenme", True
    if any(kw in t for kw in ["yatırım", "fabrika", "tesis", "kapasite"]):
        return "Yatirim", True
    if any(kw in t for kw in ["finansman", "kredi", "tahvil", "bono", "borç"]):
        return "Finansman", True
    if any(kw in t for kw in ["dava", "tazminat", "ceza", "vergi"]):
        return "Dava", True
    if any(kw in t for kw in ["ortaklık", "pay satışı", "pay alımı", "nitelikli", "devir"]):
        return "Ortaklik", True

    # -- Non-catalyst --
    if any(kw in t for kw in ["faaliyet raporu", "activity report"]):
        return "Faaliyet_Raporu", False
    if any(kw in t for kw in ["kurumsal yonetim", "kurumsal yönetim", "corporate governance"]):
        return "Kurumsal_Yonetim", False
    if any(kw in t for kw in ["sürdürülebilirlik", "sürdürulebilirlik", "sustainability"]):
        return "Surdurulebilirlik", False
    if any(kw in t for kw in ["değerleme", "degerleme", "valuation", "rapor"]):
        return "Degerleme", False

    return "Diger", False


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from KAP format (multiple formats)."""
    if not date_str:
        return None
    for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _fetch_by_criteria(
    session_obj: requests.Session,
    from_date: str,
    to_date: str,
    disclosure_class: str = "FR",
    subject_ids: Optional[List[str]] = None,
) -> list:
    """
    Fetch disclosures using KAP byCriteria API.
    This is the same API that pykap's get_historical_disclosure_list uses.
    """
    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "disclosureClass": disclosure_class,
        "subjectList": subject_ids or [],
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "bdkMemberOidList": [],
        "fromSrc": False,
        "disclosureIndexList": [],
    }

    url = f"{KAP_BASE_URL}/tr/api/disclosure/members/byCriteria"

    try:
        resp = session_obj.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("resultList", []) if isinstance(data, dict) else []
    except Exception as e:
        logger.error(f"byCriteria API error ({disclosure_class}): {e}")
        return []


def _fetch_company_disclosures(
    session_obj: requests.Session,
    company_id: str,
    disclosure_type: str = "FAR",
) -> list:
    """
    Fetch per-company disclosures using company-detail API.
    Used for FAR, KDP, KYUR, SUR, DEG types.
    """
    url = f"{KAP_BASE_URL}/tr/api/company-detail/disclosures/{disclosure_type}/{company_id}"
    try:
        resp = session_obj.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return [item.get("disclosureBasic", item) for item in data] if isinstance(data, list) else []
    except Exception as e:
        logger.debug(f"Company detail API error ({disclosure_type}/{company_id}): {e}")
        return []


def run_module3_disclosures(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    max_companies: int = 0,
    disclosure_types: Optional[List[str]] = None,
) -> int:
    """
    Module 3 entry point:
    1. Use byCriteria API to get broad disclosure feed (FR + ODA classes)
    2. Also fetch per-company disclosures (FAR, KDP, etc.) for top companies
    3. Categorize and save to database

    Args:
        from_date: Start date (YYYY-MM-DD) - default 90 days ago
        to_date: End date (YYYY-MM-DD) - default today
        max_companies: Max companies for per-company fetch (0 = skip)
        disclosure_types: Per-company types to fetch (default: all)
    """
    logger.info("=" * 60)
    logger.info("Module 3: Genis Kapsamli Bildirim Akisi")
    logger.info("=" * 60)

    if not from_date:
        from_date = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

    if not disclosure_types:
        disclosure_types = ["FAR", "KDP", "KYUR", "SUR", "DEG"]

    session = get_session()
    http = get_client().session

    total_saved = 0
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: byCriteria API — Broad disclosure feed
    # ═══════════════════════════════════════════════════════════════════════
    logger.info("--- Phase 1: byCriteria API (broad feed) ---")

    # Build company OID lookup
    company_lookup = {}  # mkk_id -> Company
    for c in session.query(Company).filter(Company.is_active == True).all():
        company_lookup[c.mkk_id] = c
        company_lookup[c.ticker] = c

    for disc_class in DISCLOSURE_CLASSES:
        logger.info(f"  Fetching class={disc_class} ...")
        time.sleep(3)  # Rate limit between API calls

        raw_data = _fetch_by_criteria(http, from_date, to_date, disc_class)
        logger.info(f"  {disc_class}: {len(raw_data)} raw records")

        for item in raw_data:
            try:
                # Extract disclosure info - API returns flat or nested
                basic = item.get("disclosureBasic") or item
                if not basic:
                    continue

                disc_id = str(basic.get("disclosureIndex", ""))
                if not disc_id or disc_id == "0":
                    continue

                title = basic.get("summary") or basic.get("subject") or basic.get("kapTitle") or ""
                symbol = basic.get("stockCodes") or basic.get("stockCode") or ""
                pub_date_str = basic.get("publishDate", "")
                pub_date = _parse_date(pub_date_str)
                if not pub_date:
                    continue

                # Filter by date range
                if pub_date < from_dt or pub_date > to_dt:
                    continue

                # Match company
                company_id = None
                if symbol and symbol in company_lookup:
                    company_id = company_lookup[symbol].id

                # Categorize
                category, is_catalyst = _categorize(title)

                # Build raw content from available fields
                raw_parts = []
                for key in ["summary", "subject", "marketType", "disclosureType", "year", "period"]:
                    val = basic.get(key)
                    if val:
                        raw_parts.append(f"{key}: {val}")
                raw_content = " | ".join(raw_parts) if raw_parts else ""

                record = {
                    "disclosure_id": disc_id,
                    "company_id": company_id,
                    "symbol": symbol,
                    "title": title,
                    "category": category,
                    "disclosure_type": basic.get("disclosureType", disc_class),
                    "publish_date": pub_date,
                    "source_url": f"{KAP_BASE_URL}/tr/{disc_id}",
                    "is_catalyst": is_catalyst,
                    "raw_content": raw_content,
                }

                upsert_disclosure(session, record)
                total_saved += 1

            except Exception as e:
                logger.debug(f"  Error parsing record: {e}")
                continue

        session.commit()

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: Per-company disclosures (FAR, KDP, etc.)
    # ═══════════════════════════════════════════════════════════════════════
    if max_companies > 0:
        logger.info(f"--- Phase 2: Per-company disclosures (top {max_companies}) ---")

        companies = (
            session.query(Company)
            .filter(Company.is_active == True, Company.mkk_id.isnot(None))
            .order_by(Company.ticker)
            .limit(max_companies)
            .all()
        )

        for idx, company in enumerate(companies):
            company_saved = 0

            for disc_type in disclosure_types:
                try:
                    time.sleep(2)  # Rate limit
                    discs = _fetch_company_disclosures(http, company.mkk_id, disc_type)

                    for disc_data in discs:
                        disc_id = str(disc_data.get("disclosureIndex", ""))
                        if not disc_id or disc_id == "0":
                            continue

                        title = disc_data.get("title", "")
                        pub_date = _parse_date(disc_data.get("publishDate", ""))
                        if not pub_date:
                            continue

                        if pub_date < from_dt or pub_date > to_dt:
                            continue

                        category, is_catalyst = _categorize(title)

                        record = {
                            "disclosure_id": disc_id,
                            "company_id": company.id,
                            "symbol": company.ticker,
                            "title": title,
                            "category": category,
                            "disclosure_type": disc_data.get("disclosureType", disc_type),
                            "publish_date": pub_date,
                            "source_url": f"{KAP_BASE_URL}/tr/{disc_id}",
                            "is_catalyst": is_catalyst,
                            "raw_content": disc_data.get("summary", ""),
                        }

                        upsert_disclosure(session, record)
                        company_saved += 1

                except Exception as e:
                    logger.debug(f"  {company.ticker}/{disc_type}: {e}")
                    continue

            if company_saved > 0:
                total_saved += company_saved
                logger.info(f"  [{idx+1}/{len(companies)}] {company.ticker}: +{company_saved} bildirim")

            session.commit()

    session.close()
    logger.info("=" * 60)
    logger.info(f"Module 3 TAMAMLANDI: {total_saved} bildirim kaydedildi")
    logger.info("=" * 60)
    return total_saved


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n = run_module3_disclosures(max_companies=limit)
    print(f"Module 3 done. {n} disclosures saved.")
