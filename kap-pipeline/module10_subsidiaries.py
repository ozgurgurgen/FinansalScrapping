"""
Module 10 — Bağlı Ortaklıklar ve İştirakler
=============================================
KAP şirket detay sayfalarından bağlı ortaklıklar, iştirakler ve
ilişkili taraflar bilgilerini çeker.

Veri kaynakları:
  - /tr/sirket-bilgileri-genel/{permaLink} → Bağlı Ortaklıklar tablosu
  - KAP bildirimlerinden yeni iştirak bilgileri
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from client import get_client
from config import CONFIG, KAP_BASE_URL
from database import (
    Company,
    Subsidiary,
    get_session,
)

logger = logging.getLogger(__name__)


def _safe_text(val: Any) -> Optional[str]:
    """Safely extract text."""
    if val is None:
        return None
    text = str(val).strip()
    return text if text and text != "-" else None


def _safe_float(val: Any) -> Optional[float]:
    """Safely extract percentage."""
    if val is None:
        return None
    try:
        s = str(val).strip().replace("%", "").replace(",", ".")
        if s in ("", "-"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_subsidiaries_page(html_content: bytes) -> List[Dict[str, Any]]:
    """
    Parse the KAP company detail page to extract subsidiaries info.
    Returns list of subsidiary dicts.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    subsidiaries = []

    # Look for subsidiaries table/section
    sub_section = None
    for heading in soup.find_all(["h2", "h3", "h4", "div", "span", "caption"]):
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in ["bağlı ortaklık", "iştirak", "subsidiary", "ilişkili taraf"]):
            sub_section = heading
            break

    if sub_section is None:
        page_text = soup.get_text().lower()
        if not any(kw in page_text for kw in ["bağlı ortaklık", "iştirak", "subsidiary"]):
            logger.debug("No subsidiaries section found")
            return subsidiaries

    # Find tables with subsidiaries data
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        table_text = table.get_text(strip=True).lower()
        if not any(kw in table_text for kw in ["bağlı ortaklık", "iştirak", "sub", "pay", "orani"]):
            continue

        # Parse header
        header = rows[0]
        header_cells = [th.get_text(strip=True) for th in header.find_all(["th", "td"])]

        col_map = {}
        for i, h in enumerate(header_cells):
            h_lower = h.lower()
            if "ad" in h_lower or "isim" in h_lower or "name" in h_lower or "şirket" in h_lower:
                col_map["name"] = i
            elif "pay" in h_lower or "oran" in h_lower or "rate" in h_lower or "%" in h_lower:
                col_map["share_pct"] = i
            elif "ülke" in h_lower or "country" in h_lower:
                col_map["country"] = i
            elif "faaliyet" in h_lower or "sector" in h_lower or "alan" in h_lower:
                col_map["activity"] = i

        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            name = None
            share_pct = None
            country = None
            activity = None

            if "name" in col_map and col_map["name"] < len(cells):
                name = _safe_text(cells[col_map["name"]].get_text(strip=True))
            elif len(cells) >= 1:
                name = _safe_text(cells[0].get_text(strip=True))

            if "share_pct" in col_map and col_map["share_pct"] < len(cells):
                share_pct = _safe_float(cells[col_map["share_pct"]].get_text(strip=True))

            if "country" in col_map and col_map["country"] < len(cells):
                country = _safe_text(cells[col_map["country"]].get_text(strip=True))

            if "activity" in col_map and col_map["activity"] < len(cells):
                activity = _safe_text(cells[col_map["activity"]].get_text(strip=True))

            if name:
                subsidiaries.append({
                    "name": name,
                    "share_percent": share_pct,
                    "country": country,
                    "activity": activity,
                    "relation_type": _classify_relation(share_pct),
                })

    return subsidiaries


def _classify_relation(share_pct: Optional[float]) -> str:
    """Classify the relation type based on ownership percentage."""
    if share_pct is None:
        return "unknown"
    if share_pct >= 50:
        return "subsidiary"  # Bağlı ortaklık (>50%)
    if share_pct >= 20:
        return "affiliate"  # İştirak (%20-50)
    return "investment"  # Yatırım (<%20)


def _fetch_company_subsidiaries(company) -> List[Dict[str, Any]]:
    """Fetch subsidiaries info for a single company."""
    if not company.perma_link:
        return []

    url = f"{KAP_BASE_URL}/tr/sirket-bilgileri-genel/{company.perma_link}"

    client = get_client()
    try:
        response = client.get(url)
        if response.status_code != 200:
            logger.warning("HTTP %d for %s", response.status_code, company.ticker)
            return []

        return _parse_subsidiaries_page(response.content)

    except Exception as e:
        logger.error("Error fetching subsidiaries for %s: %s", company.ticker, e)
        return []


# ── Database Operations ───────────────────────────────────────────────────────

def _upsert_subsidiary(session, company_id: int, sub_data: dict) -> bool:
    """Insert or update a subsidiary record."""
    existing = session.query(Subsidiary).filter(
        Subsidiary.company_id == company_id,
        Subsidiary.name == sub_data["name"],
    ).first()

    if existing:
        existing.share_percent = sub_data.get("share_percent") or existing.share_percent
        existing.country = sub_data.get("country") or existing.country
        existing.activity = sub_data.get("activity") or existing.activity
        existing.relation_type = sub_data.get("relation_type") or existing.relation_type
        existing.updated_at = datetime.utcnow()
        session.flush()
        return False
    else:
        sub_data["company_id"] = company_id
        sub = Subsidiary(**sub_data)
        session.add(sub)
        session.flush()
        return True


# ── Module 10 Public Interface ────────────────────────────────────────────────

def run_module10_subsidiaries(
    company_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Module 10: Fetch subsidiaries and related parties for all companies.
    """
    logger.info("═══ Module 10: Subsidiaries — Starting ═══")

    session = get_session()
    count = 0

    try:
        query = session.query(Company).filter(Company.is_active == True)
        if company_ids:
            query = query.filter(Company.id.in_(company_ids))
        if limit:
            query = query.limit(limit)

        companies = query.all()
        total = len(companies)
        logger.info("Processing subsidiaries for %d companies", total)

        for idx, company in enumerate(companies):
            try:
                subs = _fetch_company_subsidiaries(company)
                if not subs:
                    continue

                for sub in subs:
                    is_new = _upsert_subsidiary(session, company.id, sub)
                    if is_new:
                        count += 1

                session.commit()

                if (idx + 1) % 50 == 0:
                    logger.info("  [%d/%d] %d subsidiaries saved so far", idx + 1, total, count)

            except Exception as e:
                logger.error("Error processing %s: %s", company.ticker, e)
                session.rollback()

    finally:
        session.close()

    logger.info("═══ Module 10: Complete — %d subsidiaries saved ═══", count)
    return count
