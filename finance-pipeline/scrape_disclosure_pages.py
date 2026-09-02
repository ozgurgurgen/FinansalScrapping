#!/usr/bin/env python3
"""Scrape KAP disclosure pages for structured data and update disclosure_details + share_buybacks"""
import sqlite3, re, os, time, sys, io, random, unicodedata
import requests
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')

def tr_lower(text):
    """Turkish-safe lowercasing with ASCII normalization for matching"""
    if not text:
        return ''
    text = unicodedata.normalize('NFC', text)
    result = []
    for ch in text:
        if ch == 'İ': result.append('i')
        elif ch == 'I': result.append('i')
        elif ch == 'Ş': result.append('s')
        elif ch == 'ş': result.append('s')
        elif ch == 'Ç': result.append('c')
        elif ch == 'ç': result.append('c')
        elif ch == 'Ğ': result.append('g')
        elif ch == 'ğ': result.append('g')
        elif ch == 'Ü': result.append('u')
        elif ch == 'ü': result.append('u')
        elif ch == 'Ö': result.append('o')
        elif ch == 'ö': result.append('o')
        else: result.append(ch.lower())
    return ''.join(result)

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.kap.org.tr',
    })
    return s

def parse_number(text):
    """Parse Turkish number format: dots=thousands, comma=decimal"""
    if not text:
        return None
    text = text.strip().replace('\xa0', '').replace('\u2009', '').replace(' ', '')
    if not text or text == '-' or text == '/':
        return None
    has_comma = ',' in text
    has_dot = '.' in text
    if has_comma and has_dot:
        if text.rindex(',') > text.rindex('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif has_comma:
        text = text.replace(',', '.')
    elif has_dot:
        text = text.replace('.', '')
    try:
        val = float(text)
        return val if val != 0 else None
    except:
        return None

def parse_tables_from_html(html):
    """Extract all tables from KAP disclosure page"""
    soup = BeautifulSoup(html, 'html.parser')
    tables = []
    for t in soup.find_all('table'):
        rows = []
        for tr in t.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                rows.append(cells)
        if len(rows) >= 2:
            tables.append(rows)
    return tables

def parse_buyback_from_tables(tables):
    """Parse buyback data from KAP tables"""
    result = {}

    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1]
                if 'ayr' in label and 'fon' in label and 'tutar' in label:
                    val = parse_number(value)
                    if val and val > 1000:
                        result['total_budget_tl'] = val
                elif 'azami' in label and 'pay' in label:
                    val = parse_number(value)
                    if val and val > 100:
                        result['max_shares'] = val
                elif 'sermayeye' in label and 'oran' in label:
                    val = parse_number(value)
                    if val and 0 < val < 100:
                        result['capital_ratio_percent'] = val

    # Parse transaction table (İşlem Tarihi / İşlem Fiyatı header)
    for table in tables:
        if len(table) < 2:
            continue
        header = tr_lower(' '.join(table[0]))
        if 'islem tarihi' in header or 'islem fiyati' in header:
            total_shares = 0
            total_cost = 0
            last_price = None
            for row in table[1:]:
                if len(row) >= 5:
                    shares = parse_number(row[2])
                    price = parse_number(row[4])
                    if shares:
                        total_shares += shares
                    if price:
                        last_price = price
                        if shares:
                            total_cost += shares * price
            if total_shares > 0:
                result['total_bought_shares'] = total_shares
            if total_cost > 0 and total_shares > 0:
                result['avg_buyback_price'] = total_cost / total_shares
            if last_price:
                result['last_transaction_price'] = last_price

    return result

def parse_tender_from_tables(tables):
    """Parse tender/bid data from KAP tables"""
    result = {}

    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1]
                if 'sozlesme' in label and 'tutar' in label:
                    val = parse_number(value)
                    if val and val > 1000:
                        result['contract_amount_tl'] = val
                elif 'musteri' in label or 'kurum' in label:
                    if len(value) > 3 and not parse_number(value):
                        result['client_name'] = value[:200]
                elif 'teslim' in label or 'sure' in label:
                    if len(value) > 2:
                        result['delivery_date'] = value[:100]

    # Also try full row text matching
    for table in tables:
        for row in table:
            text = tr_lower(' '.join(row))
            if 'sozlesme tutari' in text or 'ihale tutari' in text:
                for cell in row:
                    val = parse_number(cell)
                    if val and val > 1000:
                        result['contract_amount_tl'] = val
            if 'musteri' in text or 'taraf' in text:
                for cell in row:
                    if len(cell) > 3 and not parse_number(cell):
                        if 'client_name' not in result:
                            result['client_name'] = cell[:200]

    return result

def parse_block_sale_from_tables(tables):
    """Parse block sale/transfer data from KAP tables"""
    result = {}

    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1]
                if 'nominal tutar' in label or 'pay sayisi' in label:
                    val = parse_number(value)
                    if val and val > 100:
                        result['block_shares'] = val
                elif 'satis fiyati' in label or 'islem fiyati' in label:
                    val = parse_number(value)
                    if val and val > 0:
                        result['block_price'] = val
                elif 'oran' in label and 'sermaye' in label:
                    val = parse_number(value)
                    if val and 0 < val < 100:
                        result['block_ratio_pct'] = val
                elif 'satan' in label or 'satici' in label:
                    if len(value) > 3:
                        result['seller_name'] = value[:200]
                elif 'alan' in label or 'alici' in label:
                    if len(value) > 3:
                        result['buyer_name'] = value[:200]

    return result

def parse_ipo_from_tables(tables):
    """Parse IPO data from KAP tables"""
    result = {}

    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1]
                if 'halka arz fiyati' in label or 'ihale fiyati' in label:
                    val = parse_number(value)
                    if val and val > 0:
                        result['ipo_price'] = val
                elif 'iskonto' in label:
                    val = parse_number(value)
                    if val and 0 < val < 100:
                        result['discount_ratio'] = val
                elif 'dagitim' in label:
                    if 'esit' in value.lower() or 'oransal' in value.lower():
                        result['distribution_type'] = value.strip()
                elif 'konsorsiyum' in label:
                    if len(value) > 3:
                        result['consortium_leader'] = value[:200]
                elif 'yeni yatirim' in label or ('yatirim' in label and 'kapasite' in label):
                    val = parse_number(value)
                    if val and 0 < val <= 100:
                        result['use_of_funds_investment_pct'] = val
                elif 'arge' in label or 'ar-ge' in label:
                    val = parse_number(value)
                    if val and 0 < val <= 100:
                        result['use_of_funds_rd_pct'] = val
                elif 'isletme sermayesi' in label:
                    val = parse_number(value)
                    if val and 0 < val <= 100:
                        result['use_of_funds_working_capital_pct'] = val
                elif 'borc' in label and ('kapatma' in label or 'odeme' in label):
                    val = parse_number(value)
                    if val and 0 < val <= 100:
                        result['use_of_funds_debt_pct'] = val
                elif 'pay sayisi' in label or 'talep edilen' in label:
                    val = parse_number(value)
                    if val and val > 100:
                        result['total_offered_shares'] = val

    return result

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    session = create_session()

    print("=" * 60)
    print("KAP DISCLOSURE PAGE SCRAPER")
    print("=" * 60)

    # Get disclosure_details that need data
    c.execute('''SELECT dd.id, dd.disclosure_index, dd.ticker, dd.title, dd.detail_type,
                        dd.client_name, dd.contract_amount_tl
                 FROM disclosure_details dd
                 WHERE (dd.client_name IS NULL OR dd.client_name = '' OR dd.contract_amount_tl IS NULL)
                   AND dd.disclosure_index IS NOT NULL
                 ORDER BY dd.detail_type''')
    records = c.fetchall()
    print(f"\n{len(records)} disclosure_details need data")

    # Group by type
    by_type = {}
    for r in records:
        t = r[4]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    for t, recs in sorted(by_type.items()):
        print(f"  {t}: {len(recs)} kayit")

    updated = 0
    errors = 0

    for row in records:
        dd_id, disc_index, ticker, title, detail_type, existing_client, existing_amount = row

        if existing_client and existing_amount:
            continue

        url = f'https://www.kap.org.tr/tr/Bildirim/{disc_index}'
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                errors += 1
                continue

            tables = parse_tables_from_html(r.text)

            fields = {}
            if detail_type == 'tender':
                fields = parse_tender_from_tables(tables)
            elif detail_type == 'buyback':
                fields = parse_buyback_from_tables(tables)
            elif detail_type == 'transfer':
                fields = parse_block_sale_from_tables(tables)
            elif detail_type == 'special_event':
                fields = parse_block_sale_from_tables(tables)
            elif detail_type == 'ipo':
                fields = parse_ipo_from_tables(tables)
            elif detail_type == 'capital_increase':
                for table in tables:
                    for row_t in table:
                        text = tr_lower(' '.join(row_t))
                        if 'bedelli' in text:
                            for cell in row_t:
                                val = parse_number(cell)
                                if val and val > 1000:
                                    fields['contract_amount_tl'] = val
            elif detail_type in ('corporate_action', 'financing'):
                for table in tables:
                    for row_t in table:
                        text = tr_lower(' '.join(row_t))
                        if 'tutar' in text:
                            for cell in row_t:
                                val = parse_number(cell)
                                if val and val > 10000:
                                    if 'contract_amount_tl' not in fields:
                                        fields['contract_amount_tl'] = val

            if fields:
                updates = []
                params = []
                for k, v in fields.items():
                    if v is not None:
                        updates.append(f"{k} = ?")
                        params.append(v)
                if updates:
                    params.append(dd_id)
                    c.execute(f"UPDATE disclosure_details SET {', '.join(updates)} WHERE id = ?", params)
                    updated += 1

            time.sleep(random.uniform(2.0, 4.0))

            if updated % 10 == 0 and updated > 0:
                print(f"  ... {updated} guncellendi, {errors} hata")
                db.commit()

        except Exception as e:
            errors += 1
            time.sleep(5)

    db.commit()

    # Now parse buyback disclosures
    print(f"\n{'='*60}")
    print("BUYBACK DISCLOSURE SCRAPING")
    print(f"{'='*60}")

    c.execute('''SELECT sb.id, sb.disclosure_id, sb.total_budget_tl, sb.total_bought_shares
                 FROM share_buybacks sb
                 WHERE sb.total_budget_tl IS NULL OR sb.total_bought_shares IS NULL''')
    buybacks = c.fetchall()
    print(f"{len(buybacks)} buybacks need data")

    bb_updated = 0
    for sb_id, disc_id, existing_budget, existing_bought in buybacks:
        if not disc_id:
            continue

        url = f'https://www.kap.org.tr/tr/Bildirim/{disc_id}'
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                errors += 1
                continue

            tables = parse_tables_from_html(r.text)
            fields = parse_buyback_from_tables(tables)

            if fields:
                updates = []
                params = []
                for k, v in fields.items():
                    if v is not None:
                        updates.append(f"{k} = ?")
                        params.append(v)
                if updates:
                    params.append(sb_id)
                    c.execute(f"UPDATE share_buybacks SET {', '.join(updates)} WHERE id = ?", params)
                    bb_updated += 1

            time.sleep(random.uniform(2.0, 4.0))

            if bb_updated % 10 == 0 and bb_updated > 0:
                print(f"  ... {bb_updated} buyback guncellendi")
                db.commit()

        except Exception as e:
            errors += 1
            time.sleep(5)

    db.commit()

    # Final summary
    print(f"\n{'='*60}")
    print("SONUC")
    print(f"{'='*60}")
    print(f"Disclosure updates: {updated}")
    print(f"Buyback updates: {bb_updated}")
    print(f"Errors: {errors}")

    c.execute('''SELECT detail_type, COUNT(*),
                 SUM(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 ELSE 0 END) as client,
                 SUM(CASE WHEN contract_amount_tl IS NOT NULL THEN 1 ELSE 0 END) as amount,
                 SUM(CASE WHEN block_shares IS NOT NULL THEN 1 ELSE 0 END) as block
                 FROM disclosure_details GROUP BY detail_type''')
    print(f"\nDisclosure details status:")
    for r in c.fetchall():
        print(f"  {r[0]}: total={r[1]}, client={r[2]}, amount={r[3]}, block={r[4]}")

    c.execute('''SELECT COUNT(*) FROM share_buybacks WHERE total_budget_tl IS NOT NULL''')
    print(f"\nBuybacks with budget: {c.fetchone()[0]}")
    c.execute('''SELECT COUNT(*) FROM share_buybacks WHERE total_bought_shares IS NOT NULL''')
    print(f"Buybacks with bought shares: {c.fetchone()[0]}")

    db.close()

if __name__ == '__main__':
    main()
