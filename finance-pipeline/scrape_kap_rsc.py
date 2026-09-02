#!/usr/bin/env python3
"""
Parse KAP disclosure pages by extracting RSC payload tables.
KAP uses Next.js with React Server Components. The actual table content
is embedded in self.__next_f.push() calls with \\u003c encoding for HTML.
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import re
import time
import random
import sqlite3
import unicodedata
from html.parser import HTMLParser

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def tr_lower(text):
    """Turkish-safe lowercase"""
    if not text:
        return ''
    t = unicodedata.normalize('NFC', text)
    replacements = {'\u0130': 'i', 'I': '\u0131', '\u015e': 's', '\u015f': 's',
                    '\u00c7': 'c', '\u00e7': 'c', '\u011e': 'g', '\u011f': 'g',
                    '\u00dc': 'u', '\u00fc': 'u', '\u00d6': 'o', '\u00f6': 'o'}
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t.lower()


def parse_number(text):
    """Parse Turkish number format: 1.234.567,89"""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if text in ('', '-', 'Yok', 'Bilinmiyor', '\u2014', '\u2013'):
        return None
    text = re.sub(r'[\u20ba\$?\u20ac\u00a3]', '', text).strip()
    text = text.replace(' ', '')
    try:
        if ',' in text and '.' in text:
            if text.rindex(',') > text.rindex('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            parts = text.split(',')
            if len(parts[-1]) <= 2:
                text = text.replace(',', '.')
            else:
                text = text.replace(',', '')
        elif '.' in text:
            parts = text.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                text = text.replace('.', '')
            elif len(parts) > 2:
                text = text.replace('.', '')
        return float(text)
    except (ValueError, OverflowError):
        return None


class SimpleTableParser(HTMLParser):
    """Simple HTML table parser"""
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ''
        self.in_table = False
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.current_cell = ''

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag == 'table' and self.in_table:
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def fetch_kap_page(disclosure_index, max_retries=3):
    """Fetch a KAP disclosure page with anti-ban"""
    for attempt in range(max_retries):
        try:
            ua = random.choice(USER_AGENTS)
            s = requests.Session()
            s.headers.update({
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://kap.org.tr/tr/Bildirimler',
                'Connection': 'keep-alive',
            })
            r = s.get(f'https://kap.org.tr/tr/Bildirim/{disclosure_index}', timeout=20)
            if r.status_code == 200:
                return r.text
            elif r.status_code == 429:
                wait = 30 + random.uniform(10, 30)
                print(f'  [429] Rate limited. Waiting {wait:.0f}s...')
                time.sleep(wait)
            else:
                print(f'  [{r.status_code}] for {disclosure_index}')
                time.sleep(3)
        except Exception as e:
            print(f'  Error: {e}')
            time.sleep(5)
    return None


def decode_rsc_table(raw_html):
    """Extract and decode the table content from KAP's RSC payload."""
    # Find the RSC push that contains \\u003ctable
    push_pattern = re.compile(r'self\.__next_f\.push\(\[1,(.*?)\]\)', re.DOTALL)

    for m in push_pattern.finditer(raw_html):
        content = m.group(1)
        if '\\u003ctable' in content and len(content) > 1000:
            # Remove outer quotes if present
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]

            # Decode HTML entities from RSC encoding
            decoded = content
            decoded = decoded.replace('\\u003c', '<')
            decoded = decoded.replace('\\u003e', '>')
            decoded = decoded.replace('\\u0026', '&')
            decoded = decoded.replace('\\u0027', "'")
            decoded = decoded.replace('\\u0022', '"')
            decoded = decoded.replace('\\r\\n', '\n')
            decoded = decoded.replace('\\r', '')
            decoded = decoded.replace('\\n', '\n')
            decoded = decoded.replace('\\t', '\t')

            # Parse tables
            parser = SimpleTableParser()
            try:
                parser.feed(decoded)
            except Exception:
                pass
            return parser.tables

    return []


def extract_kv_from_tables(tables):
    """Extract key-value pairs from parsed tables."""
    kv = {}
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1] if len(row) > 1 else ''
                if label and value and label != value:
                    kv[label] = value
    return kv


def parse_disclosure_content(html):
    """Parse a KAP disclosure page and extract structured data."""
    tables = decode_rsc_table(html)
    kv = extract_kv_from_tables(tables)

    result = {'kv': kv, 'tables_count': len(tables), 'raw_kv_count': len(kv)}
    return result


def parse_tender_data(kv):
    """Parse tender-specific fields from key-value pairs."""
    result = {}
    for key, val in kv.items():
        # Client/institution
        if any(w in key for w in ['a\u00e7an', 'kurum', 'idare', 'al\u0131c\u0131', 'm\u00fc\u015ftahsil', 'alici']):
            result['client_name'] = val[:500]
        # Amount
        if any(w in key for w in ['bedel', 'tutar', 'sozle\u015fe', 'bedel', 'toplam tutar', 'tutar\u0131']):
            parsed = parse_number(val)
            if parsed and parsed > 1000:
                if any(c in val.lower() for c in ['usd', '$']):
                    result['contract_amount_usd'] = parsed
                elif any(c in val.lower() for c in ['eur', '\u20ac']):
                    result['contract_amount_eur'] = parsed
                else:
                    result['contract_amount_tl'] = parsed
        # Description
        if any(w in key for w in ['a\u00e7\u0131klama', 'konu', 'aiklama']):
            result['description'] = val[:500]
    return result


def parse_block_sale_data(kv):
    """Parse block sale/transfer specific fields."""
    result = {}
    for key, val in kv.items():
        if any(w in key for w in ['pay adedi', 'hisse adedi', 'adet']):
            result['block_shares'] = parse_number(val)
        if any(w in key for w in ['fiyat', 'fiyati', 'ortalama']):
            result['block_price'] = parse_number(val)
        if any(w in key for w in ['oran', 'y\u00fcksek']):
            result['block_ratio_pct'] = parse_number(val)
        if any(w in key for w in ['alan', 'al\u0131c\u0131']):
            result['buyer_name'] = val[:500]
        if any(w in key for w in ['satan', 'sat\u0131c\u0131']):
            result['seller_name'] = val[:500]
    return result


def parse_ipo_data(kv):
    """Parse IPO-specific fields."""
    result = {}
    for key, val in kv.items():
        if any(w in key for w in ['halka arz', 'ihra\u00e7 fi']):
            result['ipo_price'] = parse_number(val)
        if 'pay' in key and any(w in key for w in ['adet', 'say', 'talep']):
            result['total_offered_shares'] = parse_number(val)
        if 'tutar' in key:
            result['offering_amount_tl'] = parse_number(val)
        if 'konsorsiyum' in key or 'lider' in key:
            result['consortium_leader'] = val[:500]
        if 'da\u011f\u0131t\u0131m' in key or 'dagitim' in key:
            result['distribution_type'] = val[:50]
        if 'iskonto' in key:
            result['discount_ratio'] = parse_number(val)
    return result


def parse_capital_increase_data(kv):
    """Parse capital increase fields."""
    result = {}
    for key, val in kv.items():
        if any(w in key for w in ['yeni sermaye', 'art\u0131r\u0131lan', 'tavan']):
            result['new_capital'] = parse_number(val)
        if 'mevcut sermaye' in key:
            result['old_capital'] = parse_number(val)
        if any(w in key for w in ['bedelli', 'bedelsiz', 'r\u00fc\u00e7han']):
            result['capital_increase_ratio'] = parse_number(val)
    return result


def parse_related_party_data(kv):
    """Parse related party transaction fields."""
    result = {}
    for key, val in kv.items():
        if any(w in key for w in ['ili\u015fkili taraf', 'iliskili', 'taraf', 'i\u015flem yap']):
            if 'tutar' not in key:
                result['client_name'] = val[:500]
        if any(w in key for w in ['tutar', 'bedel', 'de\u011fer']):
            parsed = parse_number(val)
            if parsed:
                result['contract_amount_tl'] = parsed
    return result


def update_disclosure_detail(db_path, disclosure_index, fields):
    """Update disclosure_details with scraped data."""
    if not fields:
        return False

    set_clauses = []
    values = []
    for key, val in fields.items():
        if val is not None and val != '' and val != 0:
            set_clauses.append(f'{key} = ?')
            values.append(val)

    if not set_clauses:
        return False

    values.append(disclosure_index)
    sql = f"UPDATE disclosure_details SET {', '.join(set_clauses)} WHERE disclosure_index = ?"

    db = sqlite3.connect(db_path, timeout=10)
    c = db.cursor()
    try:
        c.execute(sql, values)
        db.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f'  DB Error: {e}')
        db.rollback()
        return False
    finally:
        db.close()


def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()

    # Get disclosures that need scraping
    c.execute('''
        SELECT dd.id, dd.disclosure_index, dd.detail_type, dd.title
        FROM disclosure_details dd
        WHERE dd.detail_type IN ('tender','transfer','related_party','capital_increase','ipo','buyback')
        AND (dd.contract_amount_tl IS NULL OR dd.contract_amount_tl = 0)
        AND (dd.block_shares IS NULL OR dd.block_shares = 0)
        AND (dd.client_name IS NULL)
        ORDER BY dd.detail_type, dd.id
    ''')
    to_scrape = c.fetchall()
    db.close()

    print(f'=== KAP RSC Disclosure Scraper ===')
    print(f'Total to scrape: {len(to_scrape)}')

    by_type = {}
    for row in to_scrape:
        t = row[2]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(row)
    for t, items in by_type.items():
        print(f'  {t}: {len(items)}')
    print()

    total_updated = 0
    total_failed = 0

    for idx, row in enumerate(to_scrape):
        dd_id, disclosure_index, detail_type, title = row

        print(f'[{idx+1}/{len(to_scrape)}] [{detail_type}] {disclosure_index} - {str(title)[:50]}')

        time.sleep(random.uniform(3.0, 6.0))

        html = fetch_kap_page(disclosure_index)
        if not html:
            total_failed += 1
            print(f'  FAILED to fetch')
            continue

        result = parse_disclosure_content(html)
        kv = result['kv']

        if not kv:
            total_failed += 1
            print(f'  No KV data found (tables: {result["tables_count"]})')
            continue

        # Parse based on type
        fields = {}
        if detail_type == 'tender':
            fields = parse_tender_data(kv)
        elif detail_type == 'transfer':
            fields = parse_block_sale_data(kv)
        elif detail_type == 'ipo':
            fields = parse_ipo_data(kv)
        elif detail_type == 'capital_increase':
            fields = parse_capital_increase_data(kv)
        elif detail_type == 'related_party':
            fields = parse_related_party_data(kv)
        elif detail_type == 'buyback':
            fields = parse_tender_data(kv)  # Similar structure

        if fields:
            updated = update_disclosure_detail(DB_PATH, disclosure_index, fields)
            if updated:
                total_updated += 1
                filled = [k for k, v in fields.items() if v is not None and v != '' and v != 0]
                print(f'  Updated: {", ".join(filled)}')
            else:
                total_failed += 1
                print(f'  Fields found but DB update failed')
        else:
            total_failed += 1
            print(f'  No structured data in KV ({len(kv)} keys): {list(kv.keys())[:5]}')

        # Cool-down every 15 requests
        if (idx + 1) % 15 == 0:
            cd = random.uniform(30, 60)
            print(f'\n  --- Cool-down {cd:.0f}s after {idx+1} requests ---\n')
            time.sleep(cd)

    print(f'\n=== DONE ===')
    print(f'Updated: {total_updated}')
    print(f'Failed/No data: {total_failed}')


if __name__ == '__main__':
    main()
