"""
Module 1 — Seed Data & Company List
------------------------------------
Scrapes the KAP BIST company list page and extracts:
  - Ticker (Borsa Kodu)
  - MKK Member ID (mkkMemberId)
  - Company name, city, sector, market
  - Static paid-capital information

Saves / upserts into the Companies table.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from client import get_client
from config import CONFIG, ENDPOINTS, KAP_BASE_URL
from database import Company, get_session, upsert_company

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_turkish_number(text: str) -> Optional[float]:
    """Parse a Turkish-formatted number: '1.234.567,89' → 1234567.89"""
    if not text:
        return None
    text = text.strip().replace("\xa0", "").replace(" ", "")
    # Remove thousand separators (.) and swap decimal comma
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_mkk_id_from_link(href: str) -> Optional[str]:
    """
    From a company detail link like:
      /tr/sirket-bilgileri-genel/12345-sirket-adi
    Extract the numeric MKK ID (12345).
    """
    match = re.search(r"/(\d+)-", href)
    return match.group(1) if match else None


# ── Main Scraping Logic ─────────────────────────────────────────────────────

def scrape_company_list() -> List[dict]:
    """
    Scrape the BIST company list page and return a list of company dicts.
    Each dict contains: ticker, mkk_id, company_name, city, sector, etc.
    """
    client = get_client()
    logger.info("Fetching company list from %s", ENDPOINTS["company_list"])

    resp = client.get_html(
        ENDPOINTS["company_list"],
        rate_min=CONFIG.rate.company_detail_min_delay,
        rate_max=CONFIG.rate.company_detail_max_delay,
    )
    soup = BeautifulSoup(resp.content, "html.parser")

    companies: List[dict] = []

    # ── Strategy 1: Parse the table rows from the BIST companies page ──────
    # KAP renders a table with class "table" or a list of company cards.
    # Each company row contains: ticker link, company name, city, sector.

    # Try finding company rows in the main listing table
    rows = soup.select("table tbody tr")
    if rows:
        logger.info("Found %d table rows on company list page", len(rows))
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            company_data = _parse_company_row(cells)
            if company_data:
                companies.append(company_data)
        return companies

    # ── Strategy 2: Parse company cards/divs (alternative layout) ──────────
    # KAP sometimes uses a card layout with specific CSS classes
    company_cards = soup.select(".company-item, .comp-cell, [data-company]")
    if company_cards:
        logger.info("Found %d company cards on page", len(company_cards))
        for card in company_cards:
            company_data = _parse_company_card(card)
            if company_data:
                companies.append(company_data)
        return companies

    # ── Strategy 3: Parse anchor links containing company info ─────────────
    # Look for links like /tr/sirket-bilgileri-genel/{mkkId}-{slug}
    detail_links = soup.find_all("a", href=re.compile(r"sirket-bilgileri-genel"))
    if detail_links:
        logger.info("Found %d detail links on page", len(detail_links))
        seen_tickers = set()
        for link in detail_links:
            href = link.get("href", "")
            mkk_id = _extract_mkk_id_from_link(href)
            ticker = _extract_ticker_from_link(link, href)
            name = link.get_text(strip=True)

            if ticker and mkk_id and ticker not in seen_tickers:
                seen_tickers.add(ticker)
                companies.append({
                    "ticker": ticker,
                    "mkk_id": mkk_id,
                    "company_name": name if name and name != ticker else None,
                    "city": None,
                    "sector": None,
                    "market": None,
                    "index_group": None,
                    "is_active": True,
                    "paid_capital_static": None,
                    "website": None,
                })
        return companies

    # ── Strategy 4: Look for JavaScript-embedded JSON data ─────────────────
    scripts = soup.find_all("script")
    for script in scripts:
        text = script.string or ""
        # KAP sometimes embeds company data as JS variables
        json_match = re.search(
            r'(?:var|let|const)\s+\w+\s*=\s*(\[.*?\]);',
            text, re.DOTALL
        )
        if json_match:
            import json
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list) and len(data) > 0:
                    logger.info("Found embedded JSON with %d items", len(data))
                    # Try to parse the JSON structure
                    for item in data:
                        if isinstance(item, dict):
                            ticker = (
                                item.get("stockCode") or item.get("symbol")
                                or item.get("code") or item.get("ticker")
                            )
                            mkk_id = (
                                str(item.get("mkkMemberId") or item.get("memberId")
                                    or item.get("id") or "")
                            )
                            name = (
                                item.get("companyName") or item.get("title")
                                or item.get("name") or item.get("unvan")
                            )
                            if ticker and mkk_id:
                                companies.append({
                                    "ticker": str(ticker).strip(),
                                    "mkk_id": mkk_id.strip(),
                                    "company_name": name,
                                    "city": item.get("city") or item.get("sehir"),
                                    "sector": item.get("sector") or item.get("sektor"),
                                    "market": item.get("market") or item.get("pazar"),
                                    "index_group": item.get("indexGroup") or item.get("endeks"),
                                    "is_active": True,
                                    "paid_capital_static": item.get("paidCapital")
                                        or item.get("sermaye"),
                                    "website": item.get("website") or item.get("internetAdresi"),
                                })
            except (json.JSONDecodeError, TypeError):
                pass

    if not companies:
        logger.warning(
            "No companies parsed from the list page. "
            "KAP may have changed its layout."
        )
    else:
        logger.info("Total companies parsed from list: %d", len(companies))

    return companies


def _parse_company_row(cells) -> Optional[dict]:
    """Parse a table row's cells into a company dict."""
    # Typical KAP table columns: No, Kod, Unvan, Şehir, ...
    try:
        texts = [c.get_text(strip=True) for c in cells]
        links = [c.find("a") for c in cells]

        ticker = None
        mkk_id = None
        name = None

        # Find ticker from the link in any cell
        for link in links:
            if link:
                href = link.get("href", "")
                if "sirket-bilgileri" in href or "ozet" in href:
                    mkk_id = _extract_mkk_id_from_link(href)
                    ticker_text = link.get_text(strip=True)
                    if ticker_text and len(ticker_text) <= 10:
                        ticker = ticker_text.upper()
                        break

        # If no link found, try second cell as ticker
        if not ticker and len(texts) >= 2:
            candidate = texts[1].strip()
            if candidate and len(candidate) <= 10 and candidate.isalpha():
                ticker = candidate.upper()

        if not ticker or not mkk_id:
            return None

        # Company name is usually the longest text cell
        name = texts[2] if len(texts) > 2 else None
        city = texts[3] if len(texts) > 3 else None

        return {
            "ticker": ticker,
            "mkk_id": mkk_id,
            "company_name": name,
            "city": city,
            "sector": None,
            "market": None,
            "index_group": None,
            "is_active": True,
            "paid_capital_static": None,
            "website": None,
        }
    except (IndexError, ValueError):
        return None


def _parse_company_card(card) -> Optional[dict]:
    """Parse a company card div into a company dict."""
    try:
        link = card.find("a", href=re.compile(r"sirket|ozet"))
        if not link:
            return None

        href = link.get("href", "")
        mkk_id = _extract_mkk_id_from_link(href)
        ticker = link.get_text(strip=True).upper()
        name = card.get_text(strip=True)

        if not ticker or not mkk_id:
            return None

        return {
            "ticker": ticker,
            "mkk_id": mkk_id,
            "company_name": name if name != ticker else None,
            "city": None,
            "sector": None,
            "market": None,
            "index_group": None,
            "is_active": True,
            "paid_capital_static": None,
            "website": None,
        }
    except (AttributeError, ValueError):
        return None


def _extract_ticker_from_link(link_element, href: str) -> Optional[str]:
    """Extract ticker from an anchor element or its href."""
    text = link_element.get_text(strip=True)
    if text and len(text) <= 10 and text.isalpha():
        return text.upper()

    # Sometimes the ticker is embedded in the URL slug
    slug_match = re.search(r"/(\d+)-([a-z]+)-", href, re.IGNORECASE)
    if slug_match:
        return slug_match.group(2).upper()

    return None


# ── Company Detail Enrichment ────────────────────────────────────────────────

def enrich_company_detail(company: Company) -> dict:
    """
    Fetch the company detail page and extract additional info:
    - Sector, market, index group, website
    - Static paid capital
    """
    client = get_client()
    url = f"{ENDPOINTS['company_detail']}/{company.mkk_id}-{company.ticker.lower()}"

    logger.info("Enriching detail for %s (mkk=%s)", company.ticker, company.mkk_id)
    try:
        resp = client.get_html(
            url,
            rate_min=CONFIG.rate.company_detail_min_delay,
            rate_max=CONFIG.rate.company_detail_max_delay,
        )
    except Exception as e:
        logger.error("Failed to fetch detail for %s: %s", company.ticker, e)
        return {}

    soup = BeautifulSoup(resp.content, "html.parser")
    updates = {}

    # Parse info pairs: title → value
    title_els = soup.select(
        ".comp-cell-row-div.vtable.infoColumn.backgroundThemeForTitle"
    )
    value_els = soup.select(
        ".comp-cell-row-div.vtable.infoColumn.backgroundThemeForValue"
    )

    info_map = {}
    for title_el, value_el in zip(title_els, value_els):
        key = title_el.get_text(strip=True)
        val = value_el.get_text(strip=True)
        info_map[key] = val

    # Map KAP fields to our columns
    field_mapping = {
        "Şirketin Sektörü": "sector",
        "Sermaye Piyasası Aracının İşlem Gördüğü Pazar": "market",
        "Şirketin Dahil Olduğu Endeksler": "index_group",
        "İnternet Adresi": "website",
        "Ödenmiş/Çıkarılmış Sermaye": "paid_capital_static",
    }

    for kap_key, db_field in field_mapping.items():
        val = info_map.get(kap_key)
        if val and val != "Bilgi Mevcut Değil":
            if db_field == "paid_capital_static":
                updates[db_field] = _parse_turkish_number(val)
            else:
                updates[db_field] = val

    return updates


# ── Module 1 Public Interface ────────────────────────────────────────────────

def run_module1_seed_data(enrich_details: bool = False) -> int:
    """
    Module 1 entry point:
    1. Scrape company list from KAP
    2. Upsert each company into the database
    3. Optionally enrich with detail page data

    Returns the total number of companies upserted.
    """
    logger.info("═══ Module 1: Seed Data — Starting ═══")

    companies = scrape_company_list()
    if not companies:
        logger.error("No companies found. Aborting Module 1.")
        return 0

    session = get_session()
    count = 0

    try:
        for company_data in companies:
            db_company = upsert_company(session, company_data)
            count += 1

            if enrich_details and db_company:
                updates = enrich_company_detail(db_company)
                if updates:
                    for key, val in updates.items():
                        setattr(db_company, key, val)
                    session.commit()
                    logger.debug("Enriched %s: %s", db_company.ticker, updates)

            if count % 50 == 0:
                session.commit()
                logger.info("  … %d / %d companies processed", count, len(companies))

        session.commit()
        logger.info(
            "═══ Module 1: Complete — %d companies upserted ═══", count
        )
    except Exception as e:
        session.rollback()
        logger.error("Module 1 failed: %s", e, exc_info=True)
        raise
    finally:
        session.close()

    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run_module1_seed_data(enrich_details=False)
    print(f"Module 1 done. {n} companies processed.")
