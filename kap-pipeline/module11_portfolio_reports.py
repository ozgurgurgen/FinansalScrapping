"""
Module 11 — Portföy Dağılım Raporları (PDR)
=============================================
Yatırım ortaklıklarının ve fonların portföy dağılım raporlarını KAP'tan çeker.

Veri kaynakları:
  - KAP bildirimlerinden "Portföy Dağılımı" kategorisindeki bildirimler
  - Yatırım ortaklığı şirketlerinin aylık portföy raporları
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
    PortfolioReport,
    Disclosure,
    get_session,
)

logger = logging.getLogger(__name__)


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


def _safe_text(val: Any) -> Optional[str]:
    """Safely extract text."""
    if val is None:
        return None
    text = str(val).strip()
    return text if text and text != "-" else None


def _parse_portfolio_report(html_content: bytes, disclosure_id: str) -> List[Dict[str, Any]]:
    """
    Parse a KAP portfolio distribution report (PDR) document.
    These are typically HTML tables showing holdings.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    holdings = []

    # Find the main holdings table
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Check if this looks like a portfolio table
        table_text = table.get_text(strip=True).lower()
        if not any(kw in table_text for kw in ["hisse", "menkul", "tahvil", "bono", "portföy", "değer"]):
            continue

        # Parse header
        header = rows[0]
        header_cells = [th.get_text(strip=True) for th in header.find_all(["th", "td"])]

        col_map = {}
        for i, h in enumerate(header_cells):
            h_lower = h.lower()
            if "menkul" in h_lower or "hisse" in h_lower or "kıymet" in h_lower or "name" in h_lower:
                col_map["security_name"] = i
            elif "adet" in h_lower or "lot" in h_lower or "quantity" in h_lower:
                col_map["quantity"] = i
            elif "değer" in h_lower or "tutar" in h_lower or "value" in h_lower or "tut" in h_lower:
                col_map["value"] = i
            elif "oran" in h_lower or "%" in h_lower or "rate" in h_lower:
                col_map["weight_pct"] = i
            elif "fiyat" in h_lower or "price" in h_lower:
                col_map["price"] = i

        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            security_name = None
            quantity = None
            value = None
            weight_pct = None
            price = None

            if "security_name" in col_map and col_map["security_name"] < len(cells):
                security_name = _safe_text(cells[col_map["security_name"]].get_text(strip=True))

            if "quantity" in col_map and col_map["quantity"] < len(cells):
                quantity = _safe_float(cells[col_map["quantity"]].get_text(strip=True))

            if "value" in col_map and col_map["value"] < len(cells):
                value = _safe_float(cells[col_map["value"]].get_text(strip=True))

            if "weight_pct" in col_map and col_map["weight_pct"] < len(cells):
                weight_pct = _safe_float(cells[col_map["weight_pct"]].get_text(strip=True))

            if "price" in col_map and col_map["price"] < len(cells):
                price = _safe_float(cells[col_map["price"]].get_text(strip=True))

            if security_name:
                holdings.append({
                    "security_name": security_name,
                    "quantity": quantity,
                    "value_tl": value,
                    "weight_percent": weight_pct,
                    "price": price,
                })

    return holdings


def _fetch_portfolio_report_from_disclosure(disclosure) -> List[Dict[str, Any]]:
    """Fetch and parse a portfolio report from a disclosure document."""
    if not disclosure.source_url:
        return []

    client = get_client()
    try:
        response = client.get(disclosure.source_url)
        if response.status_code != 200:
            return []

        return _parse_portfolio_report(response.content, disclosure.disclosure_id)

    except Exception as e:
        logger.error("Error fetching PDR %s: %s", disclosure.disclosure_id, e)
        return []


# ── Module 11 Public Interface ────────────────────────────────────────────────

def run_module11_portfolio_reports(
    days: int = 30,
) -> int:
    """
    Module 11: Fetch portfolio distribution reports from recent disclosures.
    """
    logger.info("═══ Module 11: Portfolio Reports — Starting ═══")

    session = get_session()
    count = 0

    try:
        # Find portfolio-related disclosures
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(days=days)

        disclosures = session.query(Disclosure).filter(
            Disclosure.publish_date >= since,
        ).all()

        # Filter for portfolio-related disclosures
        pdr_keywords = [
            "portföy dağılım", "portföy raporu", "yatırım ortaklığı",
            "fon portföy", "varlık dağılım",
        ]

        pdr_disclosures = []
        for disc in disclosures:
            title_lower = (disc.title or "").lower()
            if any(kw in title_lower for kw in pdr_keywords):
                pdr_disclosures.append(disc)

        logger.info("Found %d portfolio-related disclosures", len(pdr_disclosures))

        for disc in pdr_disclosures:
            try:
                holdings = _fetch_portfolio_report_from_disclosure(disc)
                if not holdings:
                    continue

                for holding in holdings:
                    existing = session.query(PortfolioReport).filter(
                        PortfolioReport.disclosure_id == disc.disclosure_id,
                        PortfolioReport.security_name == holding["security_name"],
                    ).first()

                    if not existing:
                        report = PortfolioReport(
                            disclosure_id=disc.disclosure_id,
                            company_id=disc.company_id,
                            symbol=disc.symbol,
                            report_date=disc.publish_date,
                            security_name=holding["security_name"],
                            quantity=holding.get("quantity"),
                            value_tl=holding.get("value_tl"),
                            weight_percent=holding.get("weight_percent"),
                            price=holding.get("price"),
                        )
                        session.add(report)
                        count += 1

                session.commit()

            except Exception as e:
                logger.error("Error processing PDR %s: %s", disc.disclosure_id, e)
                session.rollback()

    finally:
        session.close()

    logger.info("═══ Module 11: Complete — %d portfolio report entries saved ═══", count)
    return count
