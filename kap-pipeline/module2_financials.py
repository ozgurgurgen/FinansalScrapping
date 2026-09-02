"""
Module 2 — Quarterly Financials & Ratio Calculations
-----------------------------------------------------
Fetches balance sheet and income statement data for each company
from KAP's financial information pages.

Extracts key line items, calculates derived ratios (margins,
leverage, current ratio, ROE/ROA), and computes YoY/QoQ growth rates.

The hierarchical JSON/HTML returned by KAP is parsed to extract
the required financial line items using the key-name mapping in config.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from client import get_client
from config import CONFIG, FINANCIAL_KEYS, KAP_BASE_URL
from database import (
    Company,
    Financial,
    get_session,
    upsert_financial,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(val: Any) -> Optional[float]:
    """Safely convert a value to float, handling Turkish number format."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().replace("\xa0", "").replace(" ", "")
        if val in ("", "-", "—", "Bilgi Mevcut Değil", "n/a"):
            return None
        # Turkish format: 1.234.567,89
        val = val.replace(".", "").replace(",", ".")
        try:
            return float(val)
        except ValueError:
            return None
    return None


def _calculate_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safe division for ratio calculation."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _calculate_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Calculate growth rate percentage."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


# ── Financial Data Extraction ────────────────────────────────────────────────

def _find_financial_value(
    data_map: Dict[str, Any],
    key_aliases: List[str],
) -> Optional[float]:
    """Search for a financial value using multiple possible key names."""
    for alias in key_aliases:
        # Direct match
        if alias in data_map:
            return _safe_float(data_map[alias])
        # Case-insensitive match
        for k, v in data_map.items():
            if k.lower().strip() == alias.lower().strip():
                return _safe_float(v)
        # Partial match
        for k, v in data_map.items():
            if alias.lower() in k.lower():
                return _safe_float(v)
    return None


def _extract_period_from_label(label: str) -> Optional[int]:
    """
    Extract the period number from a KAP period label.
    Examples: '2024/3 Çeyrek' → 3, '2024 Yıllık' → 12
    """
    # Match patterns like "2024/3" or "2024 Yıllık" or "2024 3. Çeyrek"
    match = re.search(r"/(\d+)", label)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*(?:Çeyrek|çeyrek|Q)", label)
    if match:
        return int(match.group(1))

    if "yıllık" in label.lower() or "annual" in label.lower():
        return 12

    return None


# ── KAP Financial Page Parser ────────────────────────────────────────────────

def _parse_financial_page_html(html_content: bytes) -> Dict[str, Dict[str, Any]]:
    """
    Parse the KAP financial information page HTML to extract financial data.

    KAP renders financial data in HTML tables with specific class patterns.
    The tables contain rows for each financial line item and columns for
    each period (year/quarter).

    Returns a dict keyed by period label, e.g.:
      {"2024/3 Çeyrek": {"Hasılat": 1234567, "Brüt Kâr": 234567, ...}, ...}
    """
    soup = BeautifulSoup(html_content, "html.parser")
    period_data: Dict[str, Dict[str, Any]] = {}

    # ── Find all financial tables ──────────────────────────────────────────
    # KAP uses tables with class patterns like "table", "data-table",
    # or specific IDs for different financial statement sections
    tables = soup.select(
        "table.table, table.data-table, "
        ".financial-statement-table, "
        "[class*='finansal'] table, "
        "[class*='bilanco'] table, "
        "[class*='gelir'] table"
    )

    if not tables:
        # Fallback: try all tables on the page
        tables = soup.find_all("table")
        logger.debug("Fallback: found %d total tables on page", len(tables))

    for table in tables:
        _parse_financial_table(table, period_data)

    # ── Try to parse from JavaScript embedded data ─────────────────────────
    if not period_data:
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            # Look for JSON data in script tags
            json_patterns = [
                r'(?:var|let|const)\s+(\w+)\s*=\s*(\{.*?\});',
                r'JSON\.parse\s*\(\s*["\'](.+?)["\']',
                r'data\s*:\s*(\[.*?\])',
            ]
            for pattern in json_patterns:
                matches = re.finditer(pattern, text, re.DOTALL)
                for match in matches:
                    try:
                        import json
                        raw = match.group(match.lastindex)
                        if "\\x" in raw or "\\u" in raw:
                            raw = raw.encode().decode("unicode_escape")
                        data = json.loads(raw)
                        _parse_json_financial_data(data, period_data)
                    except (json.JSONDecodeError, TypeError, IndexError):
                        continue

    logger.info(
        "Parsed %d periods from financial page", len(period_data)
    )
    return period_data


def _parse_financial_table(table, period_data: Dict[str, Dict[str, Any]]) -> None:
    """Parse a single financial statement HTML table."""
    rows = table.find_all("tr")
    if len(rows) < 2:
        return

    # First row typically contains period headers
    header_row = rows[0]
    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

    # Parse period labels from headers
    period_columns: List[Tuple[int, str, Optional[int]]] = []
    for idx, header in enumerate(headers):
        period_num = _extract_period_from_label(header)
        if period_num is not None:
            year_match = re.search(r"(\d{4})", header)
            year = int(year_match.group(1)) if year_match else None
            period_columns.append((idx, header, period_num))
        elif header and "Toplam" not in header and "Kalem" not in header:
            period_columns.append((idx, header, None))

    if not period_columns:
        return

    # Parse data rows
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        # First cell is the line item name
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


def _parse_json_financial_data(
    data: Any,
    period_data: Dict[str, Dict[str, Any]],
) -> None:
    """
    Parse KAP's JSON-embedded financial data.
    KAP can return nested JSON structures with financial line items.
    """
    if isinstance(data, dict):
        # Check if this looks like a financial statement structure
        for key, value in data.items():
            if isinstance(value, dict):
                # Nested: might be period-keyed
                period_num = _extract_period_from_label(str(key))
                if period_num is not None:
                    if key not in period_data:
                        period_data[key] = {}
                    _flatten_financial_json(value, period_data[key])
            elif isinstance(value, list):
                for item in value:
                    _parse_json_financial_data(item, period_data)

    elif isinstance(data, list):
        for item in data:
            _parse_json_financial_data(item, period_data)


def _flatten_financial_json(
    nested: dict,
    flat: dict,
    prefix: str = "",
) -> None:
    """Flatten a nested JSON dict, collecting financial line items."""
    for key, value in nested.items():
        full_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_financial_json(value, flat, f"{full_key}.")
        elif isinstance(value, (int, float)):
            flat[full_key] = value
        elif isinstance(value, str):
            parsed = _safe_float(value)
            if parsed is not None:
                flat[full_key] = parsed
        # Also store under just the leaf name for fuzzy matching
        leaf = full_key.split(".")[-1]
        if leaf not in flat:
            if isinstance(value, (int, float)):
                flat[leaf] = value
            elif isinstance(value, str):
                parsed = _safe_float(value)
                if parsed is not None:
                    flat[leaf] = parsed


# ── Financial Record Builder ─────────────────────────────────────────────────

def _build_financial_record(
    period_label: str,
    items: Dict[str, Any],
) -> Optional[dict]:
    """
    Build a database-ready dict from parsed financial line items.
    Also calculates derived ratios and growth indicators.
    """
    year_match = re.search(r"(\d{4})", period_label)
    if not year_match:
        return None
    year = int(year_match.group(1))

    period = _extract_period_from_label(period_label)
    if period is None:
        return None

    # Extract raw financial values
    revenue = _find_financial_value(items, FINANCIAL_KEYS["revenue"])
    gross_profit = _find_financial_value(items, FINANCIAL_KEYS["gross_profit"])
    ebit = _find_financial_value(items, FINANCIAL_KEYS["ebit"])
    ebitda = _find_financial_value(items, FINANCIAL_KEYS["ebitda"])
    net_profit = _find_financial_value(items, FINANCIAL_KEYS["net_profit"])

    current_assets = _find_financial_value(items, FINANCIAL_KEYS["current_assets"])
    non_current_assets = _find_financial_value(items, FINANCIAL_KEYS["non_current_assets"])
    total_assets = _find_financial_value(items, FINANCIAL_KEYS["total_assets"])
    short_term_debt = _find_financial_value(items, FINANCIAL_KEYS["short_term_debt"])
    long_term_debt = _find_financial_value(items, FINANCIAL_KEYS["long_term_debt"])
    total_debt = _find_financial_value(items, FINANCIAL_KEYS["total_debt"])
    financial_debt = _find_financial_value(items, FINANCIAL_KEYS["financial_debt"])
    cash = _find_financial_value(items, FINANCIAL_KEYS["cash_and_equivalents"])
    equity = _find_financial_value(items, FINANCIAL_KEYS["equity"])
    paid_capital = _find_financial_value(items, FINANCIAL_KEYS["paid_capital"])

    # ── Calculate Derived Metrics ──────────────────────────────────────────
    net_debt = None
    if financial_debt is not None and cash is not None:
        net_debt = financial_debt - cash
    elif total_debt is not None and cash is not None:
        net_debt = total_debt - cash

    current_ratio = _calculate_ratio(current_assets, short_term_debt)

    leverage_ratio = None
    if total_debt is not None and total_assets is not None and total_assets > 0:
        leverage_ratio = total_debt / total_assets

    # Margins
    gross_margin = _calculate_ratio(gross_profit, revenue)
    ebitda_margin = _calculate_ratio(ebitda, revenue)
    net_margin = _calculate_ratio(net_profit, revenue)

    # ROE / ROA
    roe = _calculate_ratio(net_profit, equity)
    roa = _calculate_ratio(net_profit, total_assets)

    return {
        "year": year,
        "period": period,
        # Income Statement
        "revenue": revenue,
        "gross_profit": gross_profit,
        "ebit": ebit,
        "ebitda": ebitda,
        "net_profit": net_profit,
        # Margins
        "gross_margin": gross_margin,
        "ebitda_margin": ebitda_margin,
        "net_margin": net_margin,
        # Balance Sheet
        "current_assets": current_assets,
        "non_current_assets": non_current_assets,
        "total_assets": total_assets,
        "short_term_debt": short_term_debt,
        "long_term_debt": long_term_debt,
        "total_debt": total_debt,
        "financial_debt": financial_debt,
        "cash_and_equivalents": cash,
        "equity": equity,
        "paid_capital": paid_capital,
        # Derived Ratios
        "net_debt": net_debt,
        "current_ratio": current_ratio,
        "leverage_ratio": leverage_ratio,
        "roe": roe,
        "roa": roa,
        # Growth rates (populated later with historical comparison)
        "revenue_yoy_growth": None,
        "revenue_qoq_growth": None,
        "net_profit_yoy_growth": None,
        # Market ratios (populated with live stock price)
        "pe_ratio": None,
        "pb_ratio": None,
        "ev_ebitda": None,
        "ev_revenue": None,
    }


def _compute_growth_rates(
    session, company_id: int, year: int, period: int,
) -> dict:
    """
    Fetch prior-period data to compute YoY and QoQ growth rates.
    """
    growth = {}

    # QoQ: same year, previous quarter
    qoq_map = {3: None, 6: 3, 9: 6, 12: 9}
    prev_qoq = qoq_map.get(period)
    if prev_qoq is not None:
        prev = (
            session.query(Financial)
            .filter_by(company_id=company_id, year=year, period=prev_qoq)
            .first()
        )
        if prev:
            growth["revenue_qoq_growth"] = None  # Set after current record is saved

    # YoY: same period, previous year
    prev_yoy = (
        session.query(Financial)
        .filter_by(company_id=company_id, year=year - 1, period=period)
        .first()
    )
    if prev_yoy:
        growth["_prev_revenue"] = prev_yoy.revenue
        growth["_prev_net_profit"] = prev_yoy.net_profit

    return growth


# ── Module 2 Public Interface ────────────────────────────────────────────────

def run_module2_financials(
    company_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Module 2 entry point:
    1. Get all (or selected) companies from DB
    2. Fetch each company's financial page from KAP
    3. Parse the financial data
    4. Calculate derived ratios and growth rates
    5. Upsert into Financials table

    Returns the total number of financial records upserted.
    """
    logger.info("═══ Module 2: Quarterly Financials — Starting ═══")

    session = get_session()
    count = 0

    try:
        # Get companies to process
        query = session.query(Company).filter(Company.is_active == True)
        if company_ids:
            query = query.filter(Company.id.in_(company_ids))
        if limit:
            query = query.limit(limit)

        companies = query.all()
        total = len(companies)
        logger.info("Processing financials for %d companies", total)

        for idx, company in enumerate(companies):
            try:
                financials = _fetch_company_financials(company)
                if not financials:
                    logger.debug("No financial data for %s", company.ticker)
                    continue

                for period_label, items in financials.items():
                    record = _build_financial_record(period_label, items)
                    if record is None:
                        continue

                    # Compute growth rates
                    growth = _compute_growth_rates(
                        session, company.id, record["year"], record["period"]
                    )

                    # Store previous values for growth calculation
                    prev_revenue = growth.pop("_prev_revenue", None)
                    prev_net_profit = growth.pop("_prev_net_profit", None)

                    # Update growth rates
                    record.update(growth)
                    if prev_revenue is not None and record.get("revenue") is not None:
                        record["revenue_yoy_growth"] = _calculate_growth(
                            record["revenue"], prev_revenue
                        )
                    if prev_net_profit is not None and record.get("net_profit") is not None:
                        record["net_profit_yoy_growth"] = _calculate_growth(
                            record["net_profit"], prev_net_profit
                        )

                    # Upsert
                    upsert_financial(session, company.id, record)
                    count += 1

                session.commit()

                if (idx + 1) % 25 == 0:
                    logger.info("  … %d / %d companies processed", idx + 1, total)

            except Exception as e:
                logger.error(
                    "Error processing %s: %s", company.ticker, e, exc_info=True
                )
                session.rollback()
                continue

        logger.info(
            "═══ Module 2: Complete — %d financial records upserted ═══", count
        )
    except Exception as e:
        session.rollback()
        logger.error("Module 2 failed: %s", e, exc_info=True)
        raise
    finally:
        session.close()

    return count


def _fetch_company_financials(company: Company) -> Dict[str, Dict[str, Any]]:
    """Fetch and parse the financial page for a single company."""
    client = get_client()

    # Build the financial page URL
    slug = company.company_name or company.ticker
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    url = f"{KAP_BASE_URL}/tr/sirket-finansal-bilgileri/{company.mkk_id}-{slug}"

    try:
        resp = client.get_html(url)
        return _parse_financial_page_html(resp.content)
    except Exception as e:
        logger.error("Failed to fetch financials for %s: %s", company.ticker, e)
        return {}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    n = run_module2_financials(limit=limit)
    print(f"Module 2 done. {n} financial records created.")
