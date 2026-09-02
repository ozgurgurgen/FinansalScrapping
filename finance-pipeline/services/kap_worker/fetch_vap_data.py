"""
VAP (Veri Analiz Platformu) Data Fetcher
=========================================
Extracts market-wide statistics from vap.org.tr main page.
No public API available — parses HTML for structured data.

Data sources:
- vap.org.tr main page: Market cap, investor counts, foreign/local ratios
- VAP yatirimci-istatistikleri: Investor demographics
- VAP endeksler: REKS, MKK indices
"""

import os
import sys
import json
import sqlite3
import logging
import time
import re
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [VAP] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "finance.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _parse_number(text):
    """Parse Turkish-formatted number like '38,68' or '23.459.693'."""
    if not text:
        return None
    text = text.strip().replace("₺", "").replace("%", "").strip()
    # Remove thousand separators (dots) and convert comma to decimal point
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_metric(html_text, keyword, context_lines=2):
    """Extract a numeric value near a keyword in text."""
    lines = html_text.split("\n")
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            # Look at surrounding lines for the value
            for j in range(max(0, i - context_lines), min(len(lines), i + context_lines + 1)):
                nums = re.findall(r"[\d.,]+", lines[j])
                for n in nums:
                    val = _parse_number(n)
                    if val and val > 0:
                        return val
    return None


def fetch_vap_main_page():
    """Fetch and parse the VAP main page for market-wide statistics."""
    logger.info("Fetching VAP main page...")
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        r = session.get("https://www.vap.org.tr/", timeout=20)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch VAP: {e}")
        return {}

    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    data = {}

    # Parse key metrics from the page
    # The page has a structured format with labels and values
    for i, line in enumerate(lines):
        # Toplam Piyasa Değeri
        if "toplam piyasa" in line.lower() and "değeri" in line.lower():
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"₺([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and val > 100:  # Must be in billions+
                        data["total_market_cap_try"] = val
                        break

        # Yatırımcı Sayısı
        if "yatırımcı" in line.lower() and "sayısı" in line.lower():
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"([\d.,]+)\s*(Milyon|Milyar)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    unit = m.group(2)
                    if unit == "Milyon":
                        data["total_investors"] = int(val * 1_000_000)
                    elif unit == "Milyar":
                        data["total_investors"] = int(val * 1_000_000_000)
                    break

        # Kayıtlı Yatırımcı
        if "kayıtlı" in line.lower() and "yatırımcı" not in line.lower():
            for j in range(i, min(len(lines), i + 3)):
                m = re.search(r"([\d.,]+)\s*(Milyon)", lines[j])
                if m:
                    data["registered_investors"] = int(_parse_number(m.group(1)) * 1_000_000)
                    break

        # Bakiyeli Yatırımcı
        if "bakiyeli" in line.lower():
            for j in range(i, min(len(lines), i + 3)):
                m = re.search(r"([\d.,]+)\s*(Milyon)", lines[j])
                if m:
                    data["active_investors"] = int(_parse_number(m.group(1)) * 1_000_000)
                    break

        # Pay Senedi Piyasa Değeri
        if "pay senedi" in line.lower() and "piyasa" in line.lower():
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"₺([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and val > 10:
                        data["equity_market_cap"] = val
                        break

        # Fon Piyasa Değeri
        if "fon" in line.lower() and "piyasa" in line.lower() and "değeri" in line.lower():
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"₺([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and val > 1:
                        data["fund_market_cap"] = val
                        break

        # Yabancı Oranı
        if "yabancı" in line.lower() and ("oran" in line.lower() or "%" in line.lower()):
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"%([\d.,]+)", lines[j])
                if m:
                    data["foreign_ratio_pct"] = _parse_number(m.group(1))
                    break

        # REKS-TÜM (format: label on one line, value on next)
        if line.strip() == "REKS-TÜM":
            if i + 1 < len(lines):
                m = re.search(r"([\d.,]+)", lines[i + 1])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 10 < val < 100:
                        data["reks_value"] = val

        # REKS YERLİ
        if "REKS" in line and "YERLİ" in lines[i + 1] if i + 1 < len(lines) else False:
            if i + 2 < len(lines):
                m = re.search(r"([\d.,]+)", lines[i + 2])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 10 < val < 100:
                        data["reks_local"] = val

        # REKS YABANCI
        if "REKS" in line and "YABANCI" in lines[i + 1] if i + 1 < len(lines) else False:
            if i + 2 < len(lines):
                m = re.search(r"([\d.,]+)", lines[i + 2])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 10 < val < 100:
                        data["reks_foreign"] = val

        # Kurumsal Yönetim Olgunluk Endeksi
        if "kurumsal yönetim" in line.lower() and "olgunluk" in line.lower() and "endeks" in line.lower():
            for j in range(i + 1, min(len(lines), i + 5)):
                m = re.search(r"([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 50 < val < 100:
                        data["corporate_governance_index"] = val
                        break

        # MKK Ciro Endeksi (format: label, then period like '2026/1Ç', then value)
        if line.strip() == "MKK CİRO ENDEKSİ":
            for j in range(i + 1, min(len(lines), i + 5)):
                # Skip period lines (contain / or Ç)
                if "/" in lines[j] or "Ç" in lines[j]:
                    continue
                m = re.search(r"([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 100 < val < 10000:
                        data["mkk_turnover_index"] = val
                        break

        # MKK Kâr Endeksi
        if line.strip() == "MKK KÂR ENDEKSİ" or line.strip() == "MKK KAR ENDEKSİ":
            for j in range(i + 1, min(len(lines), i + 5)):
                if "/" in lines[j] or "Ç" in lines[j]:
                    continue
                m = re.search(r"([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 100 < val < 10000:
                        data["mkk_profit_index"] = val
                        break

        # MKK Temettü Ödeme Endeksi
        if line.strip() == "MKK Temettü Ödeme Endeksi":
            for j in range(i + 1, min(len(lines), i + 5)):
                m = re.search(r"([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 100 < val < 10000:
                        data["mkk_dividend_payment_index"] = val
                        break

        # MKK Temettü Yayılım Endeksi
        if line.strip() == "MKK Temettü Yayılım Endeksi":
            for j in range(i + 1, min(len(lines), i + 5)):
                m = re.search(r"([\d.,]+)", lines[j])
                if m:
                    val = _parse_number(m.group(1))
                    if val and 1 < val < 100:
                        data["mkk_dividend_spread_index"] = val
                        break

        # İşlem Gören Şirket Sayısı
        if "işlem gören" in line.lower() and "şirket" in line.lower():
            for j in range(i, min(len(lines), i + 3)):
                m = re.search(r"(\d+)", lines[j])
                if m:
                    val = int(m.group(1))
                    if 100 < val < 1000:
                        data["traded_companies"] = val
                        break

        # Halka Arz
        if "halka arz" in line.lower() and "2026" in line:
            for j in range(i, min(len(lines), i + 5)):
                m = re.search(r"(\d+)\s*şirket", lines[j], re.I)
                if m:
                    data["ipo_count_2026"] = int(m.group(1))
                    break

    logger.info(f"Parsed {len(data)} metrics from VAP main page")
    return data


def save_vap_data(data):
    """Save VAP market data to database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table already exists with columns: id, name, value, category, source, description, updated_at, created_at
    pass

    today = date.today().isoformat()
    saved = 0

    indicator_map = {
        "total_market_cap_try": ("Toplam Piyasa Değeri", "Trilyon ₺"),
        "total_investors": ("Toplam Yatırımcı Sayısı", "Kişi"),
        "registered_investors": ("Kayıtlı Yatırımcı", "Kişi"),
        "active_investors": ("Bakiyeli Yatırımcı", "Kişi"),
        "equity_market_cap": ("Pay Senedi Piyasa Değeri", "Trilyon ₺"),
        "fund_market_cap": ("Fon Piyasa Değeri", "Trilyon ₺"),
        "foreign_ratio_pct": ("Yabancı Yatırımcı Oranı", "%"),
        "reks_value": ("Risk Eğilim Endeksi (REKS)", "Puan"),
        "corporate_governance_index": ("Kurumsal Yönetim Olgunluk Endeksi", "Puan"),
        "reks_local": ("REKS Yerli", "Puan"),
        "reks_foreign": ("REKS Yabancı", "Puan"),
        "mkk_turnover_index": ("MKK Ciro Endeksi", "Puan"),
        "mkk_profit_index": ("MKK Kâr Endeksi", "Puan"),
        "mkk_dividend_payment_index": ("MKK Temettü Ödeme Endeksi", "Puan"),
        "mkk_dividend_spread_index": ("MKK Temettü Yayılım Endeksi", "Puan"),
        "traded_companies": ("İşlem Gören Şirket Sayısı", "Adet"),
        "ipo_count_2026": ("2026 Halka Arz Sayısı", "Adet"),
    }

    for key, value in data.items():
        if key in indicator_map and value is not None:
            name, unit = indicator_map[key]
            try:
                c.execute("""
                    INSERT OR REPLACE INTO market_indicators 
                    (name, value, category, source, description, updated_at, created_at)
                    VALUES (?, ?, ?, 'VAP', ?, datetime('now'), datetime('now'))
                """, (name, value, unit, f'VAP {today}'))
                saved += 1
            except Exception as e:
                logger.error(f"Error saving {name}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Saved {saved} indicators to database")
    return saved


def run():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("VAP DATA FETCHER")
    logger.info("=" * 60)

    data = fetch_vap_main_page()
    if data:
        save_vap_data(data)
        logger.info(f"\nFetched data:")
        for k, v in data.items():
            logger.info(f"  {k}: {v}")
    else:
        logger.warning("No data fetched from VAP")


if __name__ == "__main__":
    run()
