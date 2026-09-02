#!/usr/bin/env python3
"""Scrape KAP tender and block sale disclosures — optimized v2"""
import sqlite3, re, os, time, sys, io, random, unicodedata
import requests
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')

def tr_lower(text):
    if not text: return ''
    text = unicodedata.normalize('NFC', text)
    result = []
    for ch in text:
        if ch == 'İ': result.append('i')
        elif ch == 'I': result.append('i')
        elif ch in ('Ş','ş'): result.append('s')
        elif ch in ('Ç','ç'): result.append('c')
        elif ch in ('Ğ','ğ'): result.append('g')
        elif ch in ('Ü','ü'): result.append('u')
        elif ch in ('Ö','ö'): result.append('o')
        else: result.append(ch.lower())
    return ''.join(result)

def parse_number(text):
    if not text: return None
    text = text.strip().replace('\xa0','').replace('\u2009','').replace(' ','')
    if not text or text == '-': return None
    has_comma = ',' in text; has_dot = '.' in text
    if has_comma and has_dot:
        if text.rindex(',') > text.rindex('.'):
            text = text.replace('.', '').replace(',', '.')
        else: text = text.replace(',', '')
    elif has_comma: text = text.replace(',', '.')
    elif has_dot: text = text.replace('.', '')
    try:
        val = float(text)
        return val if val != 0 else None
    except: return None

def parse_tender(html):
    result = {}
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    
    # 1. Extract tender value (TL)
    tl_patterns = [
        r'(?:KDV\s+Hariç\s+)?(?:toplam|bedeli|degeri|tutar[ıi])\s*[:=]?\s*([\d.]+(?:,\d+)?)\s*(?:TL|TRY|₺)',
        r'([\d.]+(?:,\d+)?)\s*(?:TL|TRY|₺)\s*\((?:Bir|İki|Üç|Dört|Beş|Altı|Yedi|Sekiz|Dokuz|On)',
        r'([\d.]+,\d+)\s*(?:TL|TRY)',
        r'(?:sözleşme|ihale)\s+(?:bedeli|tutarı|değeri)\s*[:=]?\s*([\d.]+(?:,\d+)?)',
    ]
    for pat in tl_patterns:
        m = re.search(pat, text, re.I)
        if m:
            val_str = m.group(1).replace('.', '').replace(',', '.')
            try:
                val = float(val_str)
                if val > 1000:
                    result['contract_amount_tl'] = val
                    break
            except: pass
    
    # 2. Extract USD amount
    m_usd = re.search(r'([\d,.]+)\s*(?:USD|ABD Dolar[ıi]?)', text, re.I)
    if m_usd:
        val = parse_number(m_usd.group(1))
        if val and val > 1000:
            result['contract_amount_usd'] = val
    
    # 3. Extract customer from explanation text
    # Pattern: "X Company ... tarafından düzenlenen"
    customer_patterns = [
        r'(?:A\.Ş\.|AŞ|A\.Ş\.)\s*[\(（]?(\w+)[\)）]?\s+(?:tarafından|adına|için)',
        r'(\w+(?:\s+\w+)?(?:\s+A\.Ş\.|sizör|Ofisi|Bakanlığı|Genel Müdürlüğü))',
    ]
    for pat in customer_patterns:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip()
            if len(name) > 3 and 'oda_' not in name.lower():
                result['client_name'] = name[:200]
                break
    
    # 4. Delivery/subject from table
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            cells = [td.get_text(strip=True) for td in row.find_all(['td','th'])]
            if len(cells) >= 2:
                label = tr_lower(cells[0])
                if 'ihale konusu' in label or 'subject of tender' in label:
                    if i+1 < len(rows):
                        next_cells = [td.get_text(strip=True) for td in rows[i+1].find_all(['td','th'])]
                        for cell in next_cells:
                            if cell and len(cell) > 5 and 'oda_' not in cell.lower():
                                result['seller_name'] = cell[:200]
                                break
                if 'ihale sonucu' in label or 'tender result' in label:
                    if i+1 < len(rows):
                        next_cells = [td.get_text(strip=True) for td in rows[i+1].find_all(['td','th'])]
                        for cell in next_cells:
                            if cell and len(cell) > 2:
                                result['delivery_date'] = cell[:100]
                                break
    
    return result

def parse_block_sale(html):
    result = {}
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    
    # 1. Nominal/shares amount
    patterns_shares = [
        r'([\d.]+(?:,\d+)?)\s*(?:adet|pay|lot)',
        r'nominal\s+(?:tutarı|miktarı)?\s*[:=]?\s*([\d.]+(?:,\d+)?)',
    ]
    for pat in patterns_shares:
        m = re.search(pat, text, re.I)
        if m:
            val = parse_number(m.group(1))
            if val and val > 100:
                result['block_shares'] = val
                break
    
    # 2. Block price
    price_patterns = [
        r'(?:satış fiyatı|fiyat|birim)\s*[:=]?\s*([\d,.]+)\s*(?:TL|TRY)',
        r'([\d,.]+)\s*(?:TL|TRY|₺)\s*(?:bedel|fiyat)',
    ]
    for pat in price_patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = parse_number(m.group(1))
            if val and val > 0:
                result['block_price'] = val
                break
    
    # 3. Ratio
    m = re.search(r'oran[ıi]?\s*[:=]?\s*%?([\d,.]+)\s*%', text, re.I)
    if not m:
        m = re.search(r'([\d,.]+)\s*%\s*(?:pay|oran|sermaye)', text, re.I)
    if m:
        val = parse_number(m.group(1))
        if val and 0 < val < 100:
            result['block_ratio_pct'] = val
    
    # 4. Seller/buyer from table
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            cells = [td.get_text(strip=True) for td in row.find_all(['td','th'])]
            if len(cells) >= 2:
                label = tr_lower(cells[0])
                if 'satan' in label or 'satici' in label or 'nakte' in label:
                    if i+1 < len(rows):
                        nc = [td.get_text(strip=True) for td in rows[i+1].find_all(['td','th'])]
                        for c in nc:
                            if c and len(c) > 3 and 'oda_' not in c.lower():
                                result['seller_name'] = c[:200]
                                break
                if 'alan' in label and 'alici' in label:
                    if i+1 < len(rows):
                        nc = [td.get_text(strip=True) for td in rows[i+1].find_all(['td','th'])]
                        for c in nc:
                            if c and len(c) > 3 and 'oda_' not in c.lower():
                                result['buyer_name'] = c[:200]
                                break
    
    return result

def main():
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    c = db.cursor()
    
    print("=" * 60)
    print("KAP TENDER & BLOCK SALE SCRAPER v2")
    print("=" * 60)
    
    # Get disclosures needing data
    c.execute('''SELECT dd.id, dd.disclosure_index, dd.ticker, dd.title, dd.detail_type
                 FROM disclosure_details dd
                 WHERE dd.detail_type IN ('tender', 'transfer')
                   AND dd.disclosure_index IS NOT NULL
                   AND (dd.client_name IS NULL OR dd.client_name = '' OR dd.contract_amount_tl IS NULL)
                 ORDER BY dd.detail_type, dd.disclosure_index DESC''')
    records = c.fetchall()
    print(f"\n{len(records)} disclosures to scrape")
    
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://www.kap.org.tr',
    })
    
    updated = 0; errors = 0; rate_limited = False
    
    for i, (dd_id, disc_index, ticker, title, detail_type) in enumerate(records):
        if rate_limited: break
        
        url = f'https://www.kap.org.tr/tr/Bildirim/{disc_index}'
        try:
            r = s.get(url, timeout=15)
            if r.status_code == 429:
                print(f"\n⚠️ RATE LIMIT at {i+1}/{len(records)}")
                rate_limited = True
                break
            if r.status_code != 200:
                errors += 1; continue
            
            if detail_type == 'tender':
                fields = parse_tender(r.text)
            else:
                fields = parse_block_sale(r.text)
            
            if fields:
                updates = []; params = []
                for k, v in fields.items():
                    if v is not None:
                        updates.append(f"{k} = ?")
                        params.append(v)
                if updates:
                    params.append(dd_id)
                    c.execute(f"UPDATE disclosure_details SET {', '.join(updates)} WHERE id = ?", params)
                    updated += 1
                    summary = ', '.join(f'{k}={str(v)[:50]}' for k, v in fields.items())
                    print(f"  ✅ {ticker}: {summary[:120]}")
            
            db.commit()
            time.sleep(random.uniform(4.0, 7.0))
            
            if (i+1) % 5 == 0:
                print(f"  ... {i+1}/{len(records)} processed, {updated} updated")
                
        except Exception as e:
            errors += 1
            print(f"  ❌ {ticker}: {str(e)[:60]}")
            time.sleep(5)
    
    db.commit()
    
    print(f"\n{'='*60}")
    print(f"Updated: {updated} | Errors: {errors} | Rate limited: {rate_limited}")
    
    c.execute('''SELECT detail_type, COUNT(*),
                 SUM(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN contract_amount_tl IS NOT NULL THEN 1 ELSE 0 END),
                 SUM(CASE WHEN block_shares IS NOT NULL THEN 1 ELSE 0 END)
                 FROM disclosure_details WHERE detail_type IN ('tender','transfer')
                 GROUP BY detail_type''')
    for r in c.fetchall():
        print(f"  {r[0]}: total={r[1]}, client={r[2]}, amount={r[3]}, block={r[4]}")
    
    db.close()

if __name__ == '__main__':
    main()
