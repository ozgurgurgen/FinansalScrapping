"""
Module 9 — Yönetim Kurulu ve CEO Bilgisi
=========================================
KAP şirket detay sayfalarından yönetim kurulu üyeleri, CEO ve
üst yönetim bilgilerini çeker.

Veri kaynakları:
  - /tr/sirket-bilgileri-genel/{permaLink} → Yönetim Kurulu, CEO
  - KAP bildirimlerinden atama/istifa bilgileri
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
    ManagementMember,
    get_session,
)

logger = logging.getLogger(__name__)


def _safe_text(val: Any) -> Optional[str]:
    """Safely extract text."""
    if val is None:
        return None
    text = str(val).strip()
    return text if text and text != "-" else None


def _parse_management_page(html_content: bytes) -> List[Dict[str, Any]]:
    """
    Parse the KAP company detail page to extract management info.
    Returns list of management member dicts.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    members = []

    # Look for management board table/section
    # KAP typically has a section like "Yönetim Kurulu" or "Board of Directors"
    mgmt_section = None
    for heading in soup.find_all(["h2", "h3", "h4", "div", "span", "caption"]):
        text = heading.get_text(strip=True).lower()
        if "yönetim kurulu" in text or "board" in text or "ceo" in text or "genel müdür" in text:
            mgmt_section = heading
            break

    if mgmt_section is None:
        # Fallback: search for tables with management data
        page_text = soup.get_text().lower()
        if "yönetim kurulu" not in page_text and "ceo" not in page_text and "genel müdür" not in page_text:
            logger.debug("No management section found")
            return members

    # Find the table near the management section
    tables = soup.find_all("table")
    for table in tables:
        # Check if this table is near the management section
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Check header or first rows for management keywords
        table_text = table.get_text(strip=True).lower()
        if not any(kw in table_text for kw in ["yönetim", "board", "başkan", "üye", "member", "ceo", "genel müdür"]):
            continue

        # Parse header
        header = rows[0]
        header_cells = [th.get_text(strip=True) for th in header.find_all(["th", "td"])]

        # Map header columns
        col_map = {}
        for i, h in enumerate(header_cells):
            h_lower = h.lower()
            if "ad" in h_lower or "isim" in h_lower or "name" in h_lower:
                col_map["name"] = i
            elif "görev" in h_lower or "unvan" in h_lower or "title" in h_lower or "position" in h_lower:
                col_map["title"] = i
            elif "tarih" in h_lower or "date" in h_lower:
                col_map["date"] = i

        if not col_map.get("name"):
            # Try to infer from first 2 columns
            if len(header_cells) >= 2:
                col_map["name"] = 0
                col_map["title"] = 1

        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            name = None
            title = None

            if "name" in col_map and col_map["name"] < len(cells):
                name = _safe_text(cells[col_map["name"]].get_text(strip=True))
            if "title" in col_map and col_map["title"] < len(cells):
                title = _safe_text(cells[col_map["title"]].get_text(strip=True))

            if name:
                members.append({
                    "name": name,
                    "title": title or "Yönetim Kurulu Üyesi",
                    "member_type": _classify_member_type(title),
                })

    # Also try to find CEO/General Manager from page text
    page_text = soup.get_text()
    ceo_match = re.search(
        r"(?:CEO|Genel\s*Müdür|Chief\s*Executive)[:\s]*([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)+)",
        page_text
    )
    if ceo_match:
        ceo_name = ceo_match.group(1).strip()
        # Check if already in list
        if not any(m["name"].lower() == ceo_name.lower() for m in members):
            members.append({
                "name": ceo_name,
                "title": "Genel Müdür / CEO",
                "member_type": "ceo",
            })

    return members


def _classify_member_type(title: Optional[str]) -> str:
    """Classify the member type based on their title."""
    if not title:
        return "member"
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["başkan", "chairman", "chair"]):
        return "chairman"
    if any(kw in title_lower for kw in ["başkan vekili", "vice chairman"]):
        return "vice_chairman"
    if any(kw in title_lower for kw in ["genel müdür", "ceo", "chief executive"]):
        return "ceo"
    if any(kw in title_lower for kw in ["bağımsız", "independent"]):
        return "independent"
    if any(kw in title_lower for kw in ["mali işler", "cfo", "finance"]):
        return "cfo"
    return "member"


def _fetch_company_management(company) -> List[Dict[str, Any]]:
    """Fetch management info for a single company."""
    if not company.perma_link:
        return []

    url = f"{KAP_BASE_URL}/tr/sirket-bilgileri-genel/{company.perma_link}"

    client = get_client()
    try:
        response = client.get(url)
        if response.status_code != 200:
            logger.warning("HTTP %d for %s", response.status_code, company.ticker)
            return []

        return _parse_management_page(response.content)

    except Exception as e:
        logger.error("Error fetching management for %s: %s", company.ticker, e)
        return []


# ── Database Operations ───────────────────────────────────────────────────────

def _upsert_management(session, company_id: int, member_data: dict) -> bool:
    """Insert or update a management member."""
    existing = session.query(ManagementMember).filter(
        ManagementMember.company_id == company_id,
        ManagementMember.name == member_data["name"],
    ).first()

    if existing:
        existing.title = member_data.get("title") or existing.title
        existing.member_type = member_data.get("member_type") or existing.member_type
        existing.updated_at = datetime.utcnow()
        session.flush()
        return False
    else:
        member_data["company_id"] = company_id
        mm = ManagementMember(**member_data)
        session.add(mm)
        session.flush()
        return True


# ── Module 9 Public Interface ─────────────────────────────────────────────────

def run_module9_management(
    company_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Module 9: Fetch management board and CEO info for all companies.
    """
    logger.info("═══ Module 9: Management Board — Starting ═══")

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
        logger.info("Processing management info for %d companies", total)

        for idx, company in enumerate(companies):
            try:
                members = _fetch_company_management(company)
                if not members:
                    continue

                for member in members:
                    is_new = _upsert_management(session, company.id, member)
                    if is_new:
                        count += 1

                session.commit()

                if (idx + 1) % 50 == 0:
                    logger.info("  [%d/%d] %d members saved so far", idx + 1, total, count)

            except Exception as e:
                logger.error("Error processing %s: %s", company.ticker, e)
                session.rollback()

    finally:
        session.close()

    logger.info("═══ Module 9: Complete — %d management members saved ═══", count)
    return count
