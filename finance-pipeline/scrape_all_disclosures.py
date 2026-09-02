#!/usr/bin/env python3
"""
Comprehensive KAP Disclosure Page Scraper
Tender, Transfer (Block Sale), Capital Increase, IPO, Related Party, Buyback
Anti-ban: random delays, user-agent rotation, backoff
"""

import sqlite3
import requests
import time
import random
import re
import unicodedata
import json
import os
import sys
import io
from datetime import datetime
from html.parser import HTMLParser

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')
MAX_RETRIES = 3

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
]


def tr_lower(text):
    """Turkish-safe lowercase"""
    if not text:
        return ''
    t = unicodedata.normalize('NFC', text)
    replacements = {'İ': 'i', 'I': 'ı', 'Ş': 's', 'ş': 's', 'Ç': 'c', 'ç': 'c',
                    'Ğ': 'g', 'ğ': 'g', 'Ü': 'u', 'ü': 'u', 'Ö': 'o', 'ö': 'o'}
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t.lower()


def parse_number(text):
    """Parse Turkish number format: 1.234.567,89"""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if text in ('', '-', 'Yok', 'Bilinmiyor', '—', '–'):
        return None
    # Remove currency symbols
    text = re.sub(r'[₺\$€£]', '', text).strip()
    # Turkish: comma=decimal, dot=thousands
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
        # Handle single dot as thousands separator (e.g., "50.000")
        elif '.' in text:
            parts = text.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                text = text.replace('.', '')
            # Multi-dot: 1.234.567
            elif len(parts) > 2:
                text = text.replace('.', '')
        return float(text)
    except (ValueError, OverflowError):
        return None


class SimpleTableParser(HTMLParser):
    """Simple HTML table extractor"""
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ''
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_script = False
    
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
        elif tag == 'script':
            self.in_script = True
    
    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
        elif tag in ('td', 'th') and self.in_cell:
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
        if self.in_cell and not self.in_script:
            self.current_cell += data


def extract_tables(html):
    """Extract tables from HTML"""
    parser = SimpleTableParser()
    parser.feed(html)
    return parser.tables


def extract_kv_from_explanation(html):
    """Extract key-value pairs from KAP disclosure explanation text"""
    kv = {}
    # Pattern: <strong>Key</strong>...value or Key</td><td>value
    patterns = [
        # <strong>Label</strong> Value
        re.compile(r'<strong[^>]*>([^<]+)</strong>\s*[:\s]*([^<]+)', re.IGNORECASE),
        # Label: Value in td
        re.compile(r'<td[^>]*>\s*([^<]{3,60}?)\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>', re.IGNORECASE),
    ]
    for pat in patterns:
        for m in pat.finditer(html):
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key and val and len(key) < 80:
                kv[tr_lower(key)] = val
    return kv


def scrape_kap_page(disclosure_index, max_retries=MAX_RETRIES):
    """Scrape a single KAP disclosure page"""
    url = f'https://kap.org.tr/tr/Bildirim/{disclosure_index}'
    for attempt in range(max_retries):
        try:
            ua = random.choice(USER_AGENTS)
            s = requests.Session()
            s.headers.update({
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.5',
                'Referer': 'https://kap.org.tr',
            })
            r = s.get(url, timeout=20)
            if r.status_code == 200:
                return r.text
            elif r.status_code == 429:
                wait = 30 + random.uniform(10, 30)
                print(f'  [429] Rate limited. Waiting {wait:.0f}s...')
                time.sleep(wait)
            elif r.status_code == 404:
                print(f'  [404] Page not found: {disclosure_index}')
                return None
            else:
                print(f'  [{r.status_code}] Unexpected status for {disclosure_index}')
                time.sleep(5)
        except Exception as e:
            print(f'  Error: {e}')
            time.sleep(5)
    return None


def parse_tender(html, title=''):
    """Parse tender (ihale) disclosure"""
    result = {}
    kv = extract_kv_from_explanation(html)
    tables = extract_tables(html)
    
    # Search for tender-specific keys
    tender_keys = {
        'client': ['ihaleyi açan', 'ihaleyi acan', 'kurum', 'müstahsil', 'idare', 'alici', 'müşteri'],
        'amount': ['ihale bedeli', 'ihale tutari', 'sozlesme tutari', 'tutar', 'bedel', 'toplam tutar'],
        'description': ['aciklama', 'açıklama', 'konu', 'isim', 'ihale konusu'],
        'date': ['tarih', 'baslangic', 'bitis', 'teslim tarihi'],
        'currency': ['para birimi', 'doviz', 'döviz'],
    }
    
    for key, search_terms in tender_keys.items():
        for kv_key, kv_val in kv.items():
            for term in search_terms:
                if term in kv_key:
                    if key == 'amount':
                        parsed = parse_number(kv_val)
                        if parsed:
                            # Detect currency
                            if 'usd' in kv_val.lower() or '$' in kv_val:
                                result['contract_amount_usd'] = parsed
                            elif 'eur' in kv_val.lower() or '€' in kv_val:
                                result['contract_amount_eur'] = parsed
                            else:
                                result['contract_amount_tl'] = parsed
                    elif key == 'client':
                        result['client_name'] = kv_val[:500]
                    elif key == 'description':
                        result['description'] = kv_val[:500]
                    elif key == 'date':
                        result['delivery_date'] = kv_val[:100]
                    break
    
    # Also check HTML for amount patterns
    if 'contract_amount_tl' not in result:
        # Look for "Ayrılan Fonun Toplam Tutarı (TL)" or similar
        amount_patterns = [
            re.compile(r'(?:tutar[iı]|bedel|tutar)\s*[\(₺]?\s*(?:TL|USD|EUR|TRY)?[\)ernity]*\s*[:\s]*\s*([0-9.,]+)', re.IGNORECASE),
            re.compile(r'([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)', re.IGNORECASE),
        ]
        for pat in amount_patterns:
            m = pat.search(html)
            if m:
                parsed = parse_number(m.group(1))
                if parsed and parsed > 1000:
                    result['contract_amount_tl'] = parsed
                    break
    
    return result


def parse_block_sale(html, title=''):
    """Parse block sale / transfer disclosure"""
    result = {}
    kv = extract_kv_from_explanation(html)
    
    # Block sale keys
    sale_keys = {
        'buyer': ['alan', 'alıcı', 'alici', 'buyer', 'i̇şlem yapan'],
        'seller': ['satan', 'satici', 'satıcı', 'seller'],
        'shares': ['pay adedi', 'pay sayisi', 'hisse adedi', 'miktar', 'adet'],
        'price': ['fiyat', 'islem fiyati', 'işlem fiyatı', 'ortalama fiyat'],
        'ratio': ['oran', 'toplam sermaye', 'pay orani', 'hisse orani'],
    }
    
    for key, search_terms in sale_keys.items():
        for kv_key, kv_val in kv.items():
            for term in search_terms:
                if term in kv_key:
                    if key == 'shares':
                        result['block_shares'] = parse_number(kv_val)
                    elif key == 'price':
                        result['block_price'] = parse_number(kv_val)
                    elif key == 'ratio':
                        result['block_ratio_pct'] = parse_number(kv_val)
                    elif key == 'buyer':
                        result['buyer_name'] = kv_val[:500]
                    elif key == 'seller':
                        result['seller_name'] = kv_val[:500]
                    break
    
    # Also try table-based parsing
    tables = extract_tables(html)
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                val = row[1]
                if 'pay adedi' in label or 'hisse adedi' in label:
                    result['block_shares'] = parse_number(val)
                elif 'fiyat' in label or 'fiyati' in label:
                    result['block_price'] = parse_number(val)
                elif 'oran' in label:
                    result['block_ratio_pct'] = parse_number(val)
                elif 'alan' in label or 'alıcı' in label:
                    result['buyer_name'] = val[:500]
                elif 'satan' in label or 'satıcı' in label:
                    result['seller_name'] = val[:500]
    
    return result


def parse_ipo(html, title=''):
    """Parse IPO (halka arz) disclosure"""
    result = {}
    kv = extract_kv_from_explanation(html)
    tables = extract_tables(html)
    
    ipo_keys = {
        'price': ['halka arz fiyati', 'halka arz fiyatı', 'ihraç fiyatı', 'fiyat'],
        'shares': ['ihraç edilen pay', 'pay sayisi', 'talep edilen pay', 'hisse sayisi'],
        'amount': ['ihraç tutari', 'ihraç tutarı', 'tutar'],
        'discount': ['iskonto', 'indirim'],
        'distribution': ['dagitim', 'dağıtım', 'yontem'],
        'consortium': ['konsorsiyum', 'lead', 'lider'],
        'allocation': ['tahsisat', 'tahsis'],
    }
    
    for key, search_terms in ipo_keys.items():
        for kv_key, kv_val in kv.items():
            for term in search_terms:
                if term in kv_key:
                    if key == 'price':
                        result['ipo_price'] = parse_number(kv_val)
                    elif key == 'shares':
                        result['total_offered_shares'] = parse_number(kv_val)
                    elif key == 'amount':
                        result['offering_amount_tl'] = parse_number(kv_val)
                    elif key == 'discount':
                        result['discount_ratio'] = parse_number(kv_val)
                    elif key == 'distribution':
                        result['distribution_type'] = kv_val[:50]
                    elif key == 'consortium':
                        result['consortium_leader'] = kv_val[:500]
                    break
    
    # Parse from tables
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                val = row[1]
                if 'halka arz' in label and 'fiyat' in label:
                    result['ipo_price'] = parse_number(val)
                elif 'pay' in label and ('adet' in label or 'sayisi' in label or 'sayısı' in label):
                    result['total_offered_shares'] = parse_number(val)
                elif 'tutar' in label and 'ihraç' in label:
                    result['offering_amount_tl'] = parse_number(val)
                elif 'konsorsiyum' in label:
                    result['consortium_leader'] = val[:500]
                elif 'dağıtım' in label or 'dagitim' in label:
                    result['distribution_type'] = val[:50]
    
    # Parse fund usage from explanation
    fund_keywords = {
        'investment': ['yatirim', 'yatırım', 'kapasite'],
        'rd': ['ar-ge', 'ar\\u00e7e', 'teknoloji', 'r&d'],
        'working_capital': ['işletme sermayesi', 'isletme sermayesi', 'calisan sermaye'],
        'debt': ['borc', 'borç', 'finansman'],
    }
    for fkey, terms in fund_keywords.items():
        for kv_key, kv_val in kv.items():
            for term in terms:
                if term in kv_key:
                    pct = parse_number(kv_val)
                    if pct and 0 < pct < 100:
                        col = f'use_of_funds_{fkey}_pct'
                        result[col] = pct
                    break
    
    return result


def parse_capital_increase(html, title=''):
    """Parse capital increase disclosure"""
    result = {}
    kv = extract_kv_from_explanation(html)
    tables = extract_tables(html)
    
    cap_keys = {
        'new_capital': ['yeni sermaye', 'artırılan sermaye', 'artirilan sermaye', 'tavan tutar'],
        'old_capital': ['mevcut sermaye', 'eski sermaye'],
        'ratio': ['bedelli orani', 'bedelli oranı', 'bedelsiz orani', 'ruçhan', 'rüçhan'],
        'price': ['rukun bedeli', 'rüçhan bedeli', 'hisse basi bedel'],
    }
    
    for key, search_terms in cap_keys.items():
        for kv_key, kv_val in kv.items():
            for term in search_terms:
                if term in kv_key:
                    if key in ('new_capital', 'old_capital', 'price'):
                        result[key] = parse_number(kv_val)
                    elif key == 'ratio':
                        result['capital_increase_ratio'] = parse_number(kv_val)
                    break
    
    # Table parsing
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                val = row[1]
                if 'yeni sermaye' in label or 'artırılan' in label:
                    result['new_capital'] = parse_number(val)
                elif 'mevcut sermaye' in label:
                    result['old_capital'] = parse_number(val)
                elif 'bedelli' in label and 'oran' in label:
                    result['capital_increase_ratio'] = parse_number(val)
                elif 'tavan tutar' in label or 'azami' in label:
                    result['max_amount'] = parse_number(val)
    
    return result


def parse_related_party(html, title=''):
    """Parse related party transaction disclosure"""
    result = {}
    kv = extract_kv_from_explanation(html)
    
    rp_keys = {
        'counterparty': ['ilişkili taraf', 'iliskili taraf', 'taraf', 'işlem yapılan'],
        'transaction_type': ['işlem türü', 'isleme turu', 'turu'],
        'amount': ['tutar', 'bedel', 'değer', 'tutarı'],
    }
    
    for key, search_terms in rp_keys.items():
        for kv_key, kv_val in kv.items():
            for term in search_terms:
                if term in kv_key:
                    if key == 'amount':
                        result['contract_amount_tl'] = parse_number(kv_val)
                    elif key == 'counterparty':
                        result['client_name'] = kv_val[:500]
                    elif key == 'transaction_type':
                        result['transaction_type'] = kv_val[:200]
                    break
    
    return result


def update_db(db_path, disclosure_index, fields):
    """Update disclosure_details with scraped data"""
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
    
    # Get all disclosures that need scraping
    c.execute('''
        SELECT dd.id, dd.disclosure_index, dd.detail_type, dd.title, dd.source_url
        FROM disclosure_details dd
        WHERE dd.detail_type IN ('tender','transfer','related_party','capital_increase','ipo','buyback')
        AND (dd.contract_amount_tl IS NULL OR dd.contract_amount_tl = 0)
        AND (dd.block_shares IS NULL OR dd.block_shares = 0)
        AND (dd.client_name IS NULL)
        ORDER BY dd.detail_type, dd.id
    ''')
    to_scrape = c.fetchall()
    db.close()
    
    print(f'=== KAP Disclosure Detail Scraper ===')
    print(f'Total to scrape: {len(to_scrape)}')
    
    # Group by type
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
        dd_id, disclosure_index, detail_type, title, source_url = row
        
        print(f'[{idx+1}/{len(to_scrape)}] [{detail_type}] {disclosure_index} - {str(title)[:50]}')
        
        # Skip if already scraped recently
        time.sleep(random.uniform(2.5, 5.0))
        
        html = scrape_kap_page(disclosure_index)
        if not html:
            total_failed += 1
            print(f'  FAILED to fetch page')
            continue
        
        # Parse based on type
        fields = {}
        if detail_type == 'tender':
            fields = parse_tender(html, title)
        elif detail_type == 'transfer':
            fields = parse_block_sale(html, title)
        elif detail_type == 'ipo':
            fields = parse_ipo(html, title)
        elif detail_type == 'capital_increase':
            fields = parse_capital_increase(html, title)
        elif detail_type == 'related_party':
            fields = parse_related_party(html, title)
        elif detail_type == 'buyback':
            fields = parse_tender(html, title)  # Similar table structure
        
        if fields:
            updated = update_db(DB_PATH, disclosure_index, fields)
            if updated:
                total_updated += 1
                filled = [k for k, v in fields.items() if v is not None and v != '' and v != 0]
                print(f'  Updated: {", ".join(filled)}')
            else:
                total_failed += 1
                print(f'  No fields to update')
        else:
            total_failed += 1
            print(f'  No data parsed')
        
        # Cool-down every 20 requests
        if (idx + 1) % 20 == 0:
            cd = random.uniform(30, 60)
            print(f'\n  --- Cool-down {cd:.0f}s after {idx+1} requests ---\n')
            time.sleep(cd)
    
    print(f'\n=== DONE ===')
    print(f'Updated: {total_updated}')
    print(f'Failed/No data: {total_failed}')


if __name__ == '__main__':
    main()
