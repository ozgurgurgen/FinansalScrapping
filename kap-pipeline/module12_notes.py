"""
Module 12 — Finansal Dipnotlar
================================
KAP'tan şirketlerin finansal dipnot bilgilerini çeker.

Bu modül KAP bildirimlerinden "Finansal Dipnot" kategorisindeki
bildirimleri indirip saklar. Dipnotlar genellikle PDF veya HTML
formatında gelir ve şirketin geleceğe yönelik risk raporlarını,
muhsasit bilgilerini ve detaylı açıklamaları içerir.

Not: Dipnotlar tam metin olarak saklanır, yapılandırılmış veriye
dönüştürülmesi ileri seviye NLP gerektirir.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from client import get_client
from config import CONFIG, KAP_BASE_URL
from database import (
    Company,
    Disclosure,
    FinancialNote,
    get_session,
)

logger = logging.getLogger(__name__)


def _fetch_disclosure_content(disclosure) -> Optional[str]:
    """Fetch the content of a disclosure document."""
    if not disclosure.source_url:
        return None

    client = get_client()
    try:
        response = client.get(disclosure.source_url)
        if response.status_code != 200:
            return None

        # Check content type
        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator="\n", strip=True)
            return text[:10000]  # Limit to 10KB

        elif "application/pdf" in content_type:
            # For PDF, store the URL for manual review
            return f"[PDF Document: {disclosure.source_url}]"

        else:
            return response.text[:10000]

    except Exception as e:
        logger.error("Error fetching disclosure %s: %s", disclosure.disclosure_id, e)
        return None


def _classify_note_type(title: str) -> str:
    """Classify the note type based on the disclosure title."""
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["dipnot", "note", "açıklama"]):
        return "financial_note"
    if any(kw in title_lower for kw in ["risk", "riskler"]):
        return "risk_report"
    if any(kw in title_lower for kw =["muhsasit", "bilanço dışı"]):
        return "off_balance_sheet"
    if any(kw in title_lower for kw in ["derkenar", "ek"]):
        return "supplement"
    return "general"


# ── Module 12 Public Interface ────────────────────────────────────────────────

def run_module12_notes(
    days: int = 90,
    limit: int = 100,
) -> int:
    """
    Module 12: Fetch financial notes from recent disclosures.
    """
    logger.info("═══ Module 12: Financial Notes — Starting ═══")

    session = get_session()
    count = 0

    try:
        # Find financial note disclosures
        since = datetime.utcnow() - timedelta(days=days)

        disclosures = session.query(Disclosure).filter(
            Disclosure.publish_date >= since,
            Disclosure.category == "FINANSAL_RAPOR",
        ).order_by(Disclosure.publish_date.desc()).limit(limit).all()

        logger.info("Found %d financial report disclosures to check", len(disclosures))

        for disc in disclosures:
            try:
                # Check if already processed
                existing = session.query(FinancialNote).filter(
                    FinancialNote.disclosure_id == disc.disclosure_id,
                ).first()
                if existing:
                    continue

                content = _fetch_disclosure_content(disc)
                if not content:
                    continue

                note = FinancialNote(
                    disclosure_id=disc.disclosure_id,
                    company_id=disc.company_id,
                    symbol=disc.symbol,
                    title=disc.title,
                    note_type=_classify_note_type(disc.title),
                    content_text=content,
                    source_url=disc.source_url,
                    publish_date=disc.publish_date,
                )
                session.add(note)
                session.commit()
                count += 1

                if count % 25 == 0:
                    logger.info("  [%d] %d notes saved so far", len(disclosures), count)

            except Exception as e:
                logger.error("Error processing note %s: %s", disc.disclosure_id, e)
                session.rollback()

    finally:
        session.close()

    logger.info("═══ Module 12: Complete — %d financial notes saved ═══", count)
    return count
