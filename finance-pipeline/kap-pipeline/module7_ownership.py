"""
Module 7 - Ortaklik Yapisi & Nitelikli Pay Sahipleri
====================================================
Sirketlerin ortaklik yapisi bilgilerini KAP HTML sayfalarindan ceker.
Company tablosundaki permaLink bilgisini kullanarak dogrudan URL olusturur.

- Tum ortaklar: pay tutari, pay orani, oy orani
- Nitelikli ortaklar: %5'ten fazla paya sahip
- Gercek zamanli islemler: Module 3'ten gelen bildirimlerden
"""

import logging
import re
from datetime import date, datetime
from typing import List, Optional

from bs4 import BeautifulSoup

import json
import os

from client import get_client
from config import KAP_BASE_URL
from database import (
    Company,
    Disclosure,
    Shareholder,
    get_session,
)

logger = logging.getLogger(__name__)

# Load permaLinks from JSON file
PERMA_FILE = os.path.join(os.path.dirname(__file__), "kap_permaplinks.json")


def _load_perma_links() -> dict:
    """Load permaLinks JSON: {company_id: {permaLink, oid, title}}"""
    if os.path.exists(PERMA_FILE):
        with open(PERMA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _parse_tr_number(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.strip().replace("\xa0", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


# ── Ownership Table Parser ──────────────────────────────────────────────────

def _parse_ownership_table(html: bytes) -> List[dict]:
    """Parse ownership structure from KAP HTML."""
    soup = BeautifulSoup(html, "html.parser")
    shareholders = []

    # Strategy 1: Find table with ownership headers
    for table in soup.find_all("table"):
        txt = table.get_text().lower()
        if any(kw in txt for kw in ["ortak", "pay tutarı", "pay oranı", "oy oranı", "sermaye payı"]):
            rows = table.find_all("tr")
            result = _parse_table_rows(rows)
            if result:
                return result

    # Strategy 2: Find by section header
    for section in soup.find_all(["div", "section"]):
        header = section.find(["h2", "h3", "h4", "strong", "b"])
        if header and any(kw in header.get_text().lower() for kw in ["ortaklık", "pay sahibi"]):
            table = section.find("table")
            if table:
                result = _parse_table_rows(table.find_all("tr"))
                if result:
                    return result

    # Strategy 3: Look for structured data in scripts
    for script in soup.find_all("script"):
        text = script.string or ""
        json_match = re.search(r"(?:shareholders|ortaklar)\s*[:=]\s*(\[.*?\])", text, re.DOTALL)
        if json_match:
            try:
                import json
                data = json.loads(json_match.group(1))
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("ad") or ""
                        shares = item.get("shares") or item.get("payTutari")
                        ratio = item.get("ratio") or item.get("payOrani")
                        if name:
                            shareholders.append({
                                "holder_name": name,
                                "shares_amount": _parse_tr_number(str(shares)) if shares else None,
                                "share_ratio_percent": float(ratio) if ratio else None,
                                "voting_power_percent": float(ratio) if ratio else None,
                                "holder_type": "CORPORATE" if any(
                                    kw in name.upper() for kw in ["A.Ş.", "AŞ", "HOLDİNG", "FON", "BANK"]
                                ) else "REAL_PERSON",
                                "is_qualified": (float(ratio) if ratio else 0) > 5.0,
                            })
            except (json.JSONDecodeError, TypeError):
                pass

    return shareholders


def _parse_table_rows(rows) -> List[dict]:
    """Parse table rows into shareholder dicts."""
    shareholders = []
    if len(rows) < 2:
        return shareholders

    # Check first row for headers
    header_cells = rows[0].find_all(["th", "td"])
    headers = [c.get_text(strip=True).lower() for c in header_cells]

    # Identify columns
    name_col = shares_col = ratio_col = vote_col = None
    for i, h in enumerate(headers):
        if any(kw in h for kw in ["ortak", "adı", "soyadı", "unvan"]):
            name_col = i
        elif any(kw in h for kw in ["pay tutar", "tutar", "adet"]):
            shares_col = i
        elif any(kw in h for kw in ["pay oranı", "oran"]):
            ratio_col = i
        elif any(kw in h for kw in ["oy oranı", "oy"]):
            vote_col = i

    name_col = name_col or 0
    shares_col = shares_col or min(1, len(headers) - 1)
    ratio_col = ratio_col or min(2, len(headers) - 1)
    vote_col = vote_col or ratio_col

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        cell_texts = [c.get_text(strip=True) for c in cells]

        if not cell_texts or cell_texts[0].lower() in ["toplam", "total", ""]:
            continue

        if len(cell_texts) <= name_col:
            continue

        name = cell_texts[name_col].strip()
        if not name or name.lower() == "toplam":
            continue

        shares_text = cell_texts[shares_col] if shares_col < len(cell_texts) else ""
        ratio_text = cell_texts[ratio_col] if ratio_col < len(cell_texts) else ""
        vote_text = cell_texts[vote_col] if vote_col < len(cell_texts) else ""

        shares_amount = _parse_tr_number(shares_text)
        share_ratio = _parse_tr_number(ratio_text.replace("%", ""))
        vote_ratio = _parse_tr_number(vote_text.replace("%", ""))

        holder_type = "CORPORATE" if any(
            kw in name.upper() for kw in ["A.Ş.", "AŞ", "HOLDİNG", "FON", "BANK", "ŞİRKET"]
        ) else "REAL_PERSON"

        shareholders.append({
            "holder_name": name,
            "shares_amount": shares_amount,
            "share_ratio_percent": share_ratio,
            "voting_power_percent": vote_ratio or share_ratio,
            "holder_type": holder_type,
            "is_qualified": (share_ratio or 0) > 5.0,
        })

    return shareholders


def _fetch_ownership_page(company: Company, perma_links: dict) -> Optional[bytes]:
    """Fetch company info page and extract ownership data."""
    client = get_client()

    # Build URL using permaLink from JSON
    pl = perma_links.get(str(company.id), {})
    perma = pl.get("permaLink", "")

    if perma:
        url = f"{KAP_BASE_URL}/tr/sirket-bilgileri-genel/{perma}"
    else:
        slug = (company.company_name or company.ticker).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        url = f"{KAP_BASE_URL}/tr/sirket-bilgileri-genel/{company.mkk_id}-{slug}"

    try:
        resp = client.get_html(url)
        return resp.content
    except Exception as e:
        logger.error(f"  Failed to fetch ownership for {company.ticker}: {e}")
        return None


# ── Module 7 Main Function ──────────────────────────────────────────────────

def run_module7_ownership(
    company_ids: Optional[List[int]] = None,
    max_companies: int = 0,
) -> int:
    """
    Module 7 entry point:
    1. For each company, fetch ownership page from KAP
    2. Parse ownership table
    3. Save shareholders to database
    4. Also link real-time shareholder transactions from Module 3

    Args:
        company_ids: Specific company IDs to process (0 = all)
        max_companies: Max companies to process (0 = all)
    """
    logger.info("=" * 60)
    logger.info("Module 7: Ortaklik Yapisi")
    logger.info("=" * 60)

    session = get_session()
    count = 0
    perma_links = _load_perma_links()
    logger.info(f"Loaded {len(perma_links)} permaLinks")

    # Get companies
    query = session.query(Company).filter(Company.is_active == True)
    if company_ids:
        query = query.filter(Company.id.in_(company_ids))

    companies = query.all()
    if max_companies > 0:
        companies = companies[:max_companies]

    logger.info(f"Islenen sirket sayisi: {len(companies)}")

    for idx, company in enumerate(companies):
        try:
            html = _fetch_ownership_page(company, perma_links)
            if not html:
                continue

            shareholders = _parse_ownership_table(html)
            if not shareholders:
                logger.debug(f"  {company.ticker}: ortaklik verisi bulunamadi")
                continue

            today = date.today()

            for sh_data in shareholders:
                # Upsert
                existing = (
                    session.query(Shareholder)
                    .filter_by(company_id=company.id, holder_name=sh_data["holder_name"])
                    .first()
                )

                if existing:
                    existing.shares_amount = sh_data.get("shares_amount")
                    existing.share_ratio_percent = sh_data.get("share_ratio_percent")
                    existing.voting_power_percent = sh_data.get("voting_power_percent")
                    existing.holder_type = sh_data.get("holder_type")
                    existing.is_qualified = sh_data.get("is_qualified", False)
                    existing.snapshot_date = today
                else:
                    shareholder = Shareholder(
                        company_id=company.id,
                        holder_name=sh_data["holder_name"],
                        shares_amount=sh_data.get("shares_amount"),
                        share_ratio_percent=sh_data.get("share_ratio_percent"),
                        voting_power_percent=sh_data.get("voting_power_percent"),
                        holder_type=sh_data.get("holder_type"),
                        is_qualified=sh_data.get("is_qualified", False),
                        snapshot_date=today,
                    )
                    session.add(shareholder)

                count += 1

            session.commit()

            if (idx + 1) % 25 == 0:
                logger.info(f"  [{idx+1}/{len(companies)}] tamamlandi")

            # Rate limit
            import time
            time.sleep(1.5)

        except Exception as e:
            logger.error(f"  {company.ticker}: {e}")
            session.rollback()
            continue

    # Link real-time shareholder transactions from Module 3
    _link_transactions(session)
    session.commit()

    session.close()

    logger.info("=" * 60)
    logger.info(f"Module 7 TAMAMLANDI: {count} ortaklik kaydi")
    logger.info("=" * 60)
    return count


def _link_transactions(session) -> None:
    """Link disclosure-based shareholder transactions to ownership table."""
    from sqlalchemy import or_

    transactions = (
        session.query(Disclosure)
        .filter(
            or_(
                Disclosure.title.ilike("%nitelikli pay sahibi%"),
                Disclosure.title.ilike("%pay alım satım%"),
                Disclosure.title.ilike("%pay satışı%"),
                Disclosure.title.ilike("%pay alımı%"),
            )
        )
        .order_by(Disclosure.publish_date.desc())
        .limit(200)
        .all()
    )

    for disc in transactions:
        if not disc.company_id:
            continue

        # Pattern: "X A.Ş. tarafından pay alımı/satışı"
        name_match = re.match(
            r"^(.+?)\s+(?:tarafından\s+)?(?:pay\s+(?:alım|satış|alımı|satımı))",
            disc.title,
            re.I,
        )

        if name_match:
            holder_name = name_match.group(1).strip()
            shareholder = (
                session.query(Shareholder)
                .filter_by(company_id=disc.company_id, holder_name=holder_name)
                .first()
            )
            if shareholder:
                shareholder.disclosure_id = disc.disclosure_id
                shareholder.updated_at = datetime.utcnow()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = run_module7_ownership()
    print(f"Module 7 done. {n} shareholder records.")
