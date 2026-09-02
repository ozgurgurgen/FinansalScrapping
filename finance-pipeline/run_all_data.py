#!/usr/bin/env python3
"""
run_all_data.py — Tüm Verileri Çek
====================================
Mevcut API'leri kullanarak tüm verileri tek seferde çeker:
  1. Exchange Rates (ExchangeRate-API — ücretsiz)
  2. Commodities: Gold, Silver, Copper (Yahoo Finance — ücretsiz)
  3. ETFs: SPY, QQQ, GLD, XLF (Yahoo Finance — ücretsiz)
  4. Crypto: BTC, ETH (CoinGecko — ücretsiz)
  5. TEFAS: Fon listesi, fiyat geçmişi, gruplar, türler
  6. KAP: Bildirimler, kurumsal, geri alım, IPO (yeni API)
"""

import os
import sys
import time
import random
import json
import logging
import sqlite3
from datetime import datetime, timedelta, date

import requests

# ── Setup ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_all_data")

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")

ANTI_BOT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def jitter(min_s=2.0, max_s=5.0):
    time.sleep(random.uniform(min_s, max_s))


# ══════════════════════════════════════════════════════════════════════════════
# 1. EXCHANGE RATES
# ══════════════════════════════════════════════════════════════════════════════

def fetch_exchange_rates(db):
    """Fetch USD/TRY, USD/JPY, EUR/TRY, GBP/TRY, etc."""
    log.info("=" * 60)
    log.info("1. EXCHANGE RATES (ExchangeRate-API)")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(ANTI_BOT_HEADERS)

    try:
        r = session.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        r.raise_for_status()
        data = r.json()
        rates = data.get("rates", {})

        pairs = {
            "USD_TRY": "TRY",
            "USD_JPY": "JPY",
            "USD_EUR": "EUR",
            "USD_GBP": "GBP",
            "USD_CHF": "CHF",
        }

        count = 0
        for pair, cur in pairs.items():
            if cur in rates:
                rate = rates[cur]
                # EUR/TRY = USD/TRY / USD/EUR etc. for cross rates
                if pair == "EUR_TRY" and "TRY" in rates and "EUR" in rates:
                    rate = rates["TRY"] / rates["EUR"]
                elif pair == "GBP_TRY" and "TRY" in rates and "GBP" in rates:
                    rate = rates["TRY"] / rates["GBP"]

                db.execute(
                    "INSERT OR REPLACE INTO market_rates (pair, rate, source, updated_at) VALUES (?, ?, ?, ?)",
                    (pair, rate, "open.er-api.com", datetime.utcnow().isoformat()),
                )
                log.info(f"  {pair}: {rate:.4f}")
                count += 1

        db.commit()
        log.info(f"  ✅ {count} exchange rates saved")
        return count

    except Exception as e:
        log.error(f"  ❌ Exchange rates error: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. COMMODITIES (Yahoo Finance)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_commodities(db):
    """Fetch gold, silver, copper, crude oil from Yahoo Finance."""
    log.info("=" * 60)
    log.info("2. COMMODITIES (Yahoo Finance)")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(ANTI_BOT_HEADERS)

    commodities = {
        "gold_ons": ("GC=F", "USD/oz"),
        "silver_ons": ("SI=F", "USD/oz"),
        "copper": ("HG=F", "USD/lb"),
        "crude_oil": ("CL=F", "USD/bbl"),
    }

    count = 0
    for name, (symbol, unit) in commodities.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1d", "range": "1d"}
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("previousClose")

            if price:
                price = float(price)
                db.execute(
                    "INSERT OR REPLACE INTO commodity_prices (name, price, unit, source, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (name, price, unit, "finance.yahoo.com", datetime.utcnow().isoformat()),
                )
                log.info(f"  {name}: ${price:.2f} ({unit})")
                count += 1
        except Exception as e:
            log.warning(f"  {name}: ❌ {e}")

        jitter(1.5, 3.0)

    db.commit()
    log.info(f"  ✅ {count} commodities saved")
    return count


# ══════════════════════════════════════════════════════════════════════════════
# 3. ETF PRICES (Yahoo Finance)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_etfs(db):
    """Fetch key ETF prices from Yahoo Finance."""
    log.info("=" * 60)
    log.info("3. ETF PRICES (Yahoo Finance)")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(ANTI_BOT_HEADERS)

    etfs = {
        "ETF_SPY": "SPY",
        "ETF_QQQ": "QQQ",
        "ETF_GLD": "GLD",
        "ETF_XLF": "XLF",
        "ETF_TLT": "TLT",
        "ETF_VTI": "VTI",
        "ETF_IWM": "IWM",
    }

    count = 0
    for name, symbol in etfs.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1d", "range": "1d"}
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("previousClose")

            if price:
                price = float(price)
                db.execute(
                    "INSERT OR REPLACE INTO commodity_prices (name, price, unit, source, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (name, price, "USD", "finance.yahoo.com", datetime.utcnow().isoformat()),
                )
                log.info(f"  {symbol}: ${price:.2f}")
                count += 1
        except Exception as e:
            log.warning(f"  {symbol}: ❌ {e}")

        jitter(1.5, 3.0)

    db.commit()
    log.info(f"  ✅ {count} ETFs saved")
    return count


# ══════════════════════════════════════════════════════════════════════════════
# 4. CRYPTO (CoinGecko)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_crypto(db):
    """Fetch BTC, ETH, and other crypto prices from CoinGecko."""
    log.info("=" * 60)
    log.info("4. CRYPTO (CoinGecko)")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(ANTI_BOT_HEADERS)

    try:
        ids = "bitcoin,ethereum,tether,binancecoin,solana,ripple"
        r = session.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids, "vs_currencies": "usd"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        symbol_map = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "tether": "USDT",
            "binancecoin": "BNB",
            "solana": "SOL",
            "ripple": "XRP",
        }

        count = 0
        for coin, info in data.items():
            pair = f"{symbol_map.get(coin, coin.upper())}_USD"
            price = float(info["usd"])
            db.execute(
                "INSERT OR REPLACE INTO crypto_prices (pair, price, source, updated_at) VALUES (?, ?, ?, ?)",
                (pair, price, "coingecko.com", datetime.utcnow().isoformat()),
            )
            log.info(f"  {pair}: ${price:,.2f}")
            count += 1

        db.commit()
        log.info(f"  ✅ {count} crypto prices saved")
        return count

    except Exception as e:
        log.error(f"  ❌ Crypto error: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# 5. TEFAS FUND DATA
# ══════════════════════════════════════════════════════════════════════════════

def fetch_tefas_data(db):
    """Fetch TEFAS fund list, groups, subtypes, and recent prices."""
    log.info("=" * 60)
    log.info("5. TEFAS FUND DATA")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update({
        **ANTI_BOT_HEADERS,
        "Referer": "https://www.tefas.gov.tr/",
        "X-Requested-With": "XMLHttpRequest",
    })

    count = 0

    # 5a. Fund Groups
    try:
        r = session.post("https://www.tefas.gov.tr/api/funds/fonGrupGetir", json={}, timeout=15)
        r.raise_for_status()
        resp = r.json()
        groups = resp.get("resultList", resp) if isinstance(resp, dict) else resp
        if isinstance(groups, list):
            for g in groups:
                db.execute(
                    "INSERT OR REPLACE INTO tefas_fund_groups (group_code, group_name, updated_at) VALUES (?, ?, ?)",
                    (g.get("fonKodu", ""), g.get("fonAdi", ""), datetime.utcnow().isoformat()),
                )
            log.info(f"  Fund Groups: {len(groups)}")
            db.commit()
    except Exception as e:
        log.warning(f"  Fund Groups error: {e}")

    jitter(1, 2)

    # 5b. Fund Subtypes
    try:
        r = session.post("https://www.tefas.gov.tr/api/funds/fonTurGetir", json={}, timeout=15)
        r.raise_for_status()
        resp = r.json()
        subtypes = resp.get("resultList", resp) if isinstance(resp, dict) else resp
        if isinstance(subtypes, list):
            for s in subtypes:
                db.execute(
                    "INSERT OR REPLACE INTO tefas_fund_subtypes (subtype_code, subtype_name, updated_at) VALUES (?, ?, ?)",
                    (s.get("fonKodu", ""), s.get("fonAdi", ""), datetime.utcnow().isoformat()),
                )
            log.info(f"  Fund Subtypes: {len(subtypes)}")
            db.commit()
    except Exception as e:
        log.warning(f"  Fund Subtypes error: {e}")

    jitter(1, 2)

    # 5c. Fund List + Basic Info
    try:
        r = session.post("https://www.tefas.gov.tr/api/funds/fonUnvanAra", json={}, timeout=15)
        r.raise_for_status()
        resp = r.json()
        funds = resp.get("resultList", resp) if isinstance(resp, dict) else resp
        if isinstance(funds, list):
            log.info(f"  Total funds found: {len(funds)}")

            saved = 0
            for f in funds[:500]:  # First 500 for speed
                code = f.get("fonKodu", "")
                name = f.get("fonUnvan", "")
                if not code:
                    continue
                db.execute(
                    "INSERT OR REPLACE INTO tefas_funds (fund_code, fund_name, fund_type, is_active, updated_at) VALUES (?, ?, ?, 1, ?)",
                    (code, name, f.get("fonTuru", ""), datetime.utcnow().isoformat()),
                )
                saved += 1

            log.info(f"  Saved {saved} funds")
            db.commit()
            count += saved
    except Exception as e:
        log.warning(f"  Fund List error: {e}")

    jitter(2, 3)

    # 5d. Recent Fund Prices (today's data via fonBilgiGetir)
    try:
        today = date.today().strftime("%d.%m.%Y")
        r = session.post(
            "https://www.tefas.gov.tr/api/funds/fonBilgiGetir",
            json={"TARIH": today},
            timeout=15,
        )
        r.raise_for_status()
        resp = r.json()
        price_data = resp.get("resultList", resp) if isinstance(resp, dict) else resp

        saved_prices = 0
        if isinstance(price_data, list):
            for p in price_data:
                code = p.get("fonKodu", "")
                price = p.get("sonFiyat") or p.get("fonFiyat")
                shares = p.get("payAdet")
                value = p.get("portBuyukluk") or p.get("portfoyDeger")
                investors = p.get("yatirimciSayi")

                if code and price is not None:
                    db.execute(
                        """INSERT OR REPLACE INTO tefas_fund_prices 
                           (fund_code, price_date, price, total_value, shares_count, participant_count, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (code, date.today().isoformat(), float(price),
                         float(value) if value else None,
                         float(shares) if shares else None,
                         int(investors) if investors else None,
                         datetime.utcnow().isoformat()),
                    )
                    saved_prices += 1

        log.info(f"  Today's prices: {saved_prices} funds")
        db.commit()
        count += saved_prices

    except Exception as e:
        log.warning(f"  Fund Prices error: {e}")

    log.info(f"  ✅ TEFAS total: {count} records")
    return count


# ══════════════════════════════════════════════════════════════════════════════
# 6. KAP DATA (New API)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_kap_data(db):
    """Fetch KAP data using the new Next.js backend API endpoints."""
    log.info("=" * 60)
    log.info("6. KAP DATA (kap.org.tr)")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update({
        **ANTI_BOT_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # First visit to get session cookie
    try:
        r = session.get("https://www.kap.org.tr/tr/bist-sirketler", timeout=15)
        log.info(f"  KAP session: {r.status_code}, cookies: {len(session.cookies)}")
    except Exception as e:
        log.error(f"  KAP session error: {e}")
        return 0

    jitter(2, 3)

    # Set API headers
    api_headers = {
        "Accept": "application/json",
        "Referer": "https://www.kap.org.tr/tr/bist-sirketler",
        "Origin": "https://www.kap.org.tr",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
    }

    count = 0

    # 6a. Company List
    log.info("  --- Company List ---")
    try:
        r = session.post(
            "https://www.kap.org.tr/tr/api/member/filter",
            json={},
            headers=api_headers,
            timeout=15,
        )
        if r.status_code == 200:
            companies = r.json()
            if isinstance(companies, list):
                for c in companies:
                    db.execute(
                        """INSERT OR REPLACE INTO kap_companies 
                           (mkk_id, ticker, company_name, sector, market, is_active, updated_at)
                           VALUES (?, ?, ?, ?, ?, 1, ?)""",
                        (str(c.get("memberId", "")), c.get("symbol", ""),
                         c.get("companyTitle", ""), c.get("sector", ""),
                         c.get("market", ""), datetime.utcnow().isoformat()),
                    )
                log.info(f"  Companies: {len(companies)}")
                db.commit()
                count += len(companies)
            else:
                log.warning(f"  Companies: unexpected format {type(companies)}")
        else:
            log.warning(f"  Companies API: {r.status_code}")
    except Exception as e:
        log.warning(f"  Companies error: {e}")

    jitter(2, 3)

    # 6b. Disclosures (last 7 days)
    log.info("  --- Disclosures ---")
    try:
        r = session.post(
            "https://www.kap.org.tr/tr/api/disclosure/list/main",
            json={},
            headers=api_headers,
            timeout=15,
        )
        if r.status_code == 200:
            disclosures = r.json()
            if isinstance(disclosures, list):
                saved = 0
                for d in disclosures:
                    try:
                        disc_id = str(d.get("disclosureId", d.get("id", "")))
                        if not disc_id:
                            continue
                        db.execute(
                            """INSERT OR REPLACE INTO kap_disclosures
                               (disclosure_id, symbol, company_id, title, category, 
                                publish_date, source_url, is_catalyst, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                            (disc_id, d.get("symbol", ""),
                             str(d.get("memberId", "")),
                             d.get("subject", d.get("title", "")),
                             d.get("category", ""),
                             d.get("publishDate", ""),
                             f"https://www.kap.org.tr/tr/bildirim/{disc_id}",
                             datetime.utcnow().isoformat()),
                        )
                        saved += 1
                    except Exception:
                        pass
                log.info(f"  Disclosures: {saved}")
                db.commit()
                count += saved
        else:
            log.warning(f"  Disclosures API: {r.status_code}")
    except Exception as e:
        log.warning(f"  Disclosures error: {e}")

    jitter(2, 3)

    # 6c. Corporate Actions
    log.info("  --- Corporate Actions ---")
    try:
        r = session.post(
            "https://www.kap.org.tr/tr/api/ca/allCa",
            json={},
            headers=api_headers,
            timeout=15,
        )
        if r.status_code == 200:
            actions = r.json()
            if isinstance(actions, list):
                saved = 0
                for a in actions:
                    try:
                        db.execute(
                            """INSERT OR REPLACE INTO kap_corporate_actions
                               (mkk_id, company_name, action_type, description, 
                                ratio_percent, ex_date, status, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (str(a.get("memberId", "")),
                             a.get("companyTitle", ""),
                             a.get("type", a.get("actionType", "")),
                             a.get("description", ""),
                             a.get("ratio"),
                             a.get("exDate", ""),
                             a.get("status", ""),
                             datetime.utcnow().isoformat()),
                        )
                        saved += 1
                    except Exception:
                        pass
                log.info(f"  Corporate Actions: {saved}")
                db.commit()
                count += saved
        else:
            log.warning(f"  Corporate Actions API: {r.status_code}")
    except Exception as e:
        log.warning(f"  Corporate Actions error: {e}")

    log.info(f"  ✅ KAP total: {count} records")
    return count


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("🚀 TÜM VERİLER ÇEKILIYOR...")
    log.info(f"Database: {DB_PATH}")
    start = time.time()

    db = sqlite3.connect(DB_PATH)

    # Ensure tables exist
    db.executescript("""
        CREATE TABLE IF NOT EXISTS market_rates (
            pair TEXT PRIMARY KEY,
            rate REAL,
            source TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS commodity_prices (
            name TEXT PRIMARY KEY,
            price REAL,
            unit TEXT,
            source TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS crypto_prices (
            pair TEXT PRIMARY KEY,
            price REAL,
            source TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS market_indicators (
            name TEXT PRIMARY KEY,
            value REAL,
            category TEXT,
            source TEXT,
            description TEXT,
            updated_at TEXT
        );
    """)
    db.commit()

    total = 0

    try:
        total += fetch_exchange_rates(db)
    except Exception as e:
        log.error(f"Exchange rates failed: {e}")

    try:
        total += fetch_commodities(db)
    except Exception as e:
        log.error(f"Commodities failed: {e}")

    try:
        total += fetch_etfs(db)
    except Exception as e:
        log.error(f"ETFs failed: {e}")

    try:
        total += fetch_crypto(db)
    except Exception as e:
        log.error(f"Crypto failed: {e}")

    try:
        total += fetch_tefas_data(db)
    except Exception as e:
        log.error(f"TEFAS failed: {e}")

    try:
        total += fetch_kap_data(db)
    except Exception as e:
        log.error(f"KAP failed: {e}")

    elapsed = int(time.time() - start)
    log.info("=" * 60)
    log.info(f"🎉 TAMAMLANDI! Toplam: {total} kayıt ({elapsed}s)")
    log.info("=" * 60)

    # Print summary
    log.info("\n📊 Veritabanı Özeti:")
    for table in ["market_rates", "commodity_prices", "crypto_prices",
                   "tefas_funds", "tefas_fund_prices",
                   "kap_companies", "kap_disclosures", "kap_corporate_actions"]:
        try:
            cnt = db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
            log.info(f"  {table}: {cnt}")
        except:
            log.info(f"  {table}: (tablo yok)")

    db.close()


if __name__ == "__main__":
    main()
