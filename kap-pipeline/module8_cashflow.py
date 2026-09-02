"""
Module 8 — Cash Flow Statement (Nakit Akış Tablosu)
====================================================
Extracts operating, investing, and financing cash flows from KAP's
financial information pages. Uses the same HTML parsing approach as Module 2.

Cash flow data is available on the same financial page as balance sheet
and income statement, but in a separate table section.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from client import get_client
from config import CONFIG, KAP_BASE_URL
from database import (
    Company,
    CashFlow,
    get_session,
)

logger = logging.getLogger(__name__)

# ── Cash Flow Key Names (Turkish labels) ─────────────────────────────────────

CASHFLOW_KEYS = {
    # Operating Activities (İşletme Faaliyetleri)
    "net_income": ["Dönem Karı", "Net Kar", "Net Dönem Kârı"],
    "depreciation": ["Amortisman", "İtfa Payları"],
    "provisions": ["Karşılıklar", "Tüketim Rezervleri"],
    "receivables_change": ["Alacaklardaki Değişim", "Ticari Alacaklardaki Değişim"],
    "inventory_change": ["Stoklardaki Değişim", "Stok Değişimi"],
    "payables_change": ["Borçlardaki Değişim", "Ticari Borçlardaki Değişim"],
    "operating_cash_flow": ["İşletme Faaliyetlerinden Nakit Akışı", "İşletme Kaynaklı Nakit"],
    # Investing Activities (Yatırım Faaliyetleri)
    "capex": ["Sabit Varlık Edinimleri", "Tesis ve Makine Alımı", "Yatırım Harcamaları"],
    "investment_sales": ["Yatırım Satışları", "Sabit Varlık Satışları"],
    "acquisitions": ["İşletmelerin Birleşmesi", "Şirket Alımları"],
    "investing_cash_flow": ["Yatırım Faaliyetlerinden Nakit Akışı", "Yatırım Kaynaklı Nakit"],
    # Financing Activities (Finansman Faaliyetleri)
    "borrowings": ["Borçlanmalar", "Yeni Borçlanma"],
    "repayments": ["Borç Ödemeleri", "Kredi Ödemeleri"],
    "equity_issued": ["Sermaye Artırımı", "Yeni Sermaye"],
    "dividends_paid": ["Ödenen Temettü", "Kâr Payı Ödemeleri"],
    "financing_cash_flow": ["Finansman Faaliyetlerinden Nakit Akışı", "Finansman Kaynaklı Nakit"],
    # Summary
    "net_change": ["Nakit ve Nakit Benzerlerindeki Net Değişim"],
    "opening_cash": ["Dönem Başı Nakit"],
    "closing_cash": ["Dönem Sonu Nakit", "Dönem Başı Nakit ve Nakit Benzerleri"],
}


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert value to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().replace("\xa0", "").replace(" ", "")
        if val in ("", "-", "—", "Bilgi Mevcut Değil", "n/a"):
            return None
        val = val.replace(".", "").replace(",", ".")
        try:
            return float(val)
        except ValueError:
            return None
    return None


def _find_value(items: Dict[str, Any], aliases: List[str]) -> Optional[float]:
    """Search for a value using multiple possible key names."""
    for alias in aliases:
        if alias in items:
            return _safe_float(items[alias])
        for k, v in items.items():
            if k.lower().strip() == alias.lower().strip():
                return _safe_float(v)
        for k, v in items.items():
            if alias.lower() in k.lower():
                return _safe_float(v)
    return None


def _extract_period(label: str) -> Optional[int]:
    """Extract period number from label."""
    match = re.search(r"/(\d+)", label)
    if match:
        return int(match.group(1))
    if "yıllık" in label.lower():
        return 12
    return None


def _parse_cashflow_tables(html_content: bytes) -> Dict[str, Dict[str, Any]]:
    """
    Parse cash flow tables from KAP financial page HTML.
    Returns dict keyed by period label.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    period_data: Dict[str, Dict[str, Any]] = {}

    # Find cash flow section — look for "Nakit Akış" or "Cash Flow" heading
    cashflow_section = None
    for heading in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        text = heading.get_text(strip=True).lower()
        if "nakit akış" in text or "cash flow" in text:
            cashflow_section = heading
            break

    if cashflow_section is None:
        # Fallback: try to find tables after "Nakit Akış" text in page
        page_text = soup.get_text()
        if "nakit akış" not in page_text.lower():
            logger.debug("No cash flow section found in page")
            return period_data

    # Find all tables and look for cash flow data
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Check if this table contains cash flow line items
        first_row_text = rows[0].get_text(strip=True).lower() if rows else ""
        has_cashflow = False
        for row in rows[:5]:
            text = row.get_text(strip=True).lower()
            if any(kw in text for kw in ["nakit", "cash", "işletme", "yatırım", "finansman"]):
                has_cashflow = True
                break

        if not has_cashflow:
            continue

        # Parse period columns from header
        header = rows[0]
        header_cells = header.find_all(["th", "td"])
        period_columns = []
        for i, cell in enumerate(header_cells):
            text = cell.get_text(strip=True)
            if re.search(r"\d{4}", text):
                period_columns.append((i, text, _extract_period(text)))

        if not period_columns:
            continue

        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            item_name = cells[0].get_text(strip=True)
            if not item_name:
                continue

            for col_idx, period_label, period_num in period_columns:
                if col_idx >= len(cells):
                    continue

                if period_label not in period_data:
                    period_data[period_label] = {}

                value_text = cells[col_idx].get_text(strip=True)
                value = _safe_float(value_text)
                if value is not None:
                    period_data[period_label][item_name] = value

    return period_data


def _build_cashflow_record(
    period_label: str,
    items: Dict[str, Any],
) -> Optional[dict]:
    """Build a cash flow database record from parsed items."""
    year_match = re.search(r"(\d{4})", period_label)
    if not year_match:
        return None
    year = int(year_match.group(1))

    period = _extract_period(period_label)
    if period is None:
        return None

    return {
        "year": year,
        "period": period,
        "net_income": _find_value(items, CASHFLOW_KEYS["net_income"]),
        "depreciation": _find_value(items, CASHFLOW_KEYS["depreciation"]),
        "provisions": _find_value(items, CASHFLOW_KEYS["provisions"]),
        "receivables_change": _find_value(items, CASHFLOW_KEYS["receivables_change"]),
        "inventory_change": _find_value(items, CASHFLOW_KEYS["inventory_change"]),
        "payables_change": _find_value(items, CASHFLOW_KEYS["payables_change"]),
        "operating_cash_flow": _find_value(items, CASHFLOW_KEYS["operating_cash_flow"]),
        "capex": _find_value(items, CASHFLOW_KEYS["capex"]),
        "investment_sales": _find_value(items, CASHFLOW_KEYS["investment_sales"]),
        "acquisitions": _find_value(items, CASHFLOW_KEYS["acquisitions"]),
        "investing_cash_flow": _find_value(items, CASHFLOW_KEYS["investing_cash_flow"]),
        "borrowings": _find_value(items, CASHFLOW_KEYS["borrowings"]),
        "repayments": _find_value(items, CASHFLOW_KEYS["repayments"]),
        "equity_issued": _find_value(items, CASHFLOW_KEYS["equity_issued"]),
        "dividends_paid": _find_value(items, CASHFLOW_KEYS["dividends_paid"]),
        "financing_cash_flow": _find_value(items, CASHFLOW_KEYS["financing_cash_flow"]),
        "net_change": _find_value(items, CASHFLOW_KEYS["net_change"]),
        "opening_cash": _find_value(items, CASHFLOW_KEYS["opening_cash"]),
        "closing_cash": _find_value(items, CASHFLOW_KEYS["closing_cash"]),
    }


def _fetch_company_cashflow(company) -> List[dict]:
    """Fetch and parse cash flow data for a single company."""
    if not company.perma_link:
        return []

    url = f"{KAP_BASE_URL}/tr/sirket-finansal-bilgileri/{company.perma_link}"

    client = get_client()
    try:
        response = client.get(url)
        if response.status_code != 200:
            logger.warning("HTTP %d for %s", response.status_code, company.ticker)
            return []

        html = response.content
        period_data = _parse_cashflow_tables(html)

        results = []
        for period_label, items in period_data.items():
            record = _build_cashflow_record(period_label, items)
            if record:
                results.append(record)

        return results

    except Exception as e:
        logger.error("Error fetching cashflow for %s: %s", company.ticker, e)
        return []


# ── Database Operations ───────────────────────────────────────────────────────

def _upsert_cashflow(session, company_id: int, data: dict) -> bool:
    """Insert or update a cash flow record."""
    existing = session.query(CashFlow).filter(
        CashFlow.company_id == company_id,
        CashFlow.year == data["year"],
        CashFlow.period == data["period"],
    ).first()

    if existing:
        for key, val in data.items():
            if key not in ("company_id", "year", "period") and val is not None:
                setattr(existing, key, val)
        session.flush()
        return False
    else:
        data["company_id"] = company_id
        cf = CashFlow(**data)
        session.add(cf)
        session.flush()
        return True


# ── Module 8 Public Interface ─────────────────────────────────────────────────

def run_module8_cashflow(
    company_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Module 8: Fetch cash flow statements for all companies.
    """
    logger.info("═══ Module 8: Cash Flow Statement — Starting ═══")

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
        logger.info("Processing cash flow for %d companies", total)

        for idx, company in enumerate(companies):
            try:
                records = _fetch_company_cashflow(company)
                if not records:
                    continue

                for record in records:
                    is_new = _upsert_cashflow(session, company.id, record)
                    if is_new:
                        count += 1

                session.commit()

                if (idx + 1) % 50 == 0:
                    logger.info("  [%d/%d] %d cash flow records saved so far", idx + 1, total, count)

            except Exception as e:
                logger.error("Error processing %s: %s", company.ticker, e)
                session.rollback()

    finally:
        session.close()

    logger.info("═══ Module 8: Complete — %d cash flow records saved ═══", count)
    return count
