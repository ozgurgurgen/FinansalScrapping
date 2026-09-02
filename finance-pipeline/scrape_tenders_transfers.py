#!/usr/bin/env python3
"""Scrape KAP tender and block sale disclosures for structured data.
Optimized for rate-limit avoidance: long delays, single session, early exit on 429."""
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
    if not text or text == '-' or text == '/': return None
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

def parse_tables(html):
    soup = BeautifulSoup(html, 'html.parser')
    tables = []
    for t in soup.find_all('table'):
        rows = []
        for tr in t.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td','th'])]
            if cells: rows.append(cells)
        if len(rows) >= 2: tables.append(rows)
    return tables

def parse_tender(tables, title=''):
    """Parse tender/contract disclosure from KAP tables"""
    result = {}
    title_lower = tr_lower(title) if title else ''
    
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1] if len(row) > 1 else ''
                
                # Contract amount patterns
                if any(kw in label for kw in ['sozlesme tutari', 'ihale tutari', 'satis tutari', 'deger', 'bedel']):
                    val = parse_number(value)
                    if val and val > 1000:
                        if 'contract_amount_tl' not in result:
                            result['contract_amount_tl'] = val
                
                # Client/customer name
                if any(kw in label for kw in ['musteri', 'kurum', 'taraf', 'alici', 'isveren', 'idare']):
                    if len(value) > 3 and not parse_number(value):
                        result['client_name'] = value[:200]
                
                # Delivery date
                if any(kw in label for kw in ['teslim', 'sure', 'takvim', 'baslangic', 'bitis']):
                    if len(value) > 2:
                        result['delivery_date'] = value[:100]
                
                # Seller/buyer
                if any(kw in label for kw in ['satan', 'satici', 'veren']):
                    if len(value) > 3:
                        result['seller_name'] = value[:200]
                if any(kw in label for kw in ['alan', 'alici', 'alan']):
                    if len(value) > 3:
                        result['buyer_name'] = value[:200]
                
                # Block shares/price
                if any(kw in label for kw in ['adet', 'pay sayisi', 'nominal']):
                    val = parse_number(value)
                    if val and val > 100:
                        result['block_shares'] = val
                
                if any(kw in label for kw in ['satis fiyati', 'islem fiyati', 'fiyat']):
                    val = parse_number(value)
                    if val and val > 0:
                        result['block_price'] = val
                
                # Ratio
                if any(kw in label for kw in ['oran', 'yuzde', 'pay orani']):
                    val = parse_number(value)
                    if val and 0 < val < 100:
                        result['block_ratio_pct'] = val
    
    # Fallback: scan full text for amounts
    if 'contract_amount_tl' not in result:
        for table in tables:
            for row in table:
                text = ' '.join(row)
                # Look for TL amounts in text
                tl_matches = re.findall(r'([\d.]+,\d+)\s*(?:TL|₺|TRY)', text)
                if not tl_matches:
                    tl_matches = re.findall(r'([\d.]+)\s*(?:TL|₺|TRY)', text)
                for m in tl_matches:
                    val = parse_number(m)
                    if val and val > 10000:
                        result['contract_amount_tl'] = val
                        break
    
    return result

def parse_block_sale(tables, title=''):
    """Parse block sale/transfer disclosure from KAP tables"""
    result = {}
    
    for table in tables:
        for row in table:
            if len(row) >= 2:
                label = tr_lower(row[0])
                value = row[1]
                
                # Nominal amount / shares
                if any(kw in label for kw in ['nominal tutar', 'pay sayisi', 'adet', 'miktar']):
                    val = parse_number(value)
                    if val and val > 100:
                        result['block_shares'] = val
                
                # Price
                if any(kw in label for kw in ['satis fiyati', 'islem fiyati', 'birim fiyat', 'fiyat']):
                    val = parse_number(value)
                    if val and val > 0:
                        result['block_price'] = val
                
                # Ratio
                if any(kw in label for kw in ['sermayeye orani', 'pay orani', 'oran']):
                    val = parse_number(value)
                    if val and 0 < val < 100:
                        result['block_ratio_pct'] = val
                
                # Seller
                if any(kw in label for kw in ['satan', 'satici', 'nakte donusturen']):
                    if len(value) > 3:
                        result['seller_name'] = value[:200]
                
                # Buyer
                if any(kw in label for kw in ['alan', 'alici', 'nakte donusturen']):
                    if len(value) > 3:
                        result['buyer_name'] = value[:200]
    
    # Fallback: parse full row text for adet/fiyat
    if 'block_shares' not in result:
        for table in tables:
            for row in table:
                text = ' '.join(row).lower()
                if 'adet' in text:
                    for cell in row:
                        val = parse_number(cell)
                        if val and val > 100:
                            result['block_shares'] = val
                            break
    
    if 'block_price' not in result:
        for table in tables:
            for row in table:
                text = ' '.join(row).lower()
                if 'fiyat' in text:
                    for cell in row:
                        val = parse_number(cell)
                        if val and val > 0:
                            result['block_price'] = val
                            break
    
    return result

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    print("=" * 60)
    print("KAP TENDER & BLOCK SALE SCRAPER")
    print("=" * 60)
    
    # Get all tender + transfer disclosures that need data
    c.execute('''SELECT dd.id, dd.disclosure_index, dd.ticker, dd.title, dd.detail_type,
                        dd.client_name, dd.contract_amount_tl, dd.block_shares
                 FROM disclosure_details dd
                 WHERE dd.detail_type IN ('tender', 'transfer')
                   AND dd.disclosure_index IS NOT NULL
                   AND (dd.client_name IS NULL OR dd.client_name = '' OR dd.contract_amount_tl IS NULL OR dd.block_shares IS NULL)
                 ORDER BY dd.detail_type, dd.disclosure_index DESC''')
    records = c.fetchall()
    print(f"\n{len(records)} disclosures to scrape (tender + transfer)")
    
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.kap.org.tr',
    })
    
    updated = 0
    errors = 0
    rate_limited = False
    
    for i, (dd_id, disc_index, ticker, title, detail_type, existing_client, existing_amount, existing_block) in enumerate(records):
        if rate_limited:
            break
        
        # Skip if already has all data
        if detail_type == 'tender' and existing_client and existing_amount:
            continue
        if detail_type == 'transfer' and existing_block:
            continue
        
        url = f'https://www.kap.org.tr/tr/Bildirim/{disc_index}'
        try:
            r = s.get(url, timeout=15)
            
            if r.status_code == 429:
                print(f"\n  ⚠️ RATE LIMIT at {i+1}/{len(records)} — stopping")
                rate_limited = True
                break
            
            if r.status_code != 200:
                errors += 1
                continue
            
            tables = parse_tables(r.text)
            
            if detail_type == 'tender':
                fields = parse_tender(tables, title)
            else:
                fields = parse_block_sale(tables, title)
            
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
                    # Show what we extracted
                    summary = ', '.join(f'{k}={str(v)[:40]}' for k, v in fields.items())
                    print(f"  ✅ {ticker}: {summary[:100]}")
            
            # Rate limit: 3-5 seconds between requests
            time.sleep(random.uniform(3.0, 5.0))
            
            if (i+1) % 5 == 0:
                print(f"  ... {i+1}/{len(records)} processed, {updated} updated")
                db.commit()
                
        except Exception as e:
            errors += 1
            print(f"  ❌ {ticker}: {str(e)[:60]}")
            time.sleep(5)
    
    db.commit()
    
    # Summary
    print(f"\n{'='*60}")
    print("SONUC")
    print(f"{'='*60}")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print(f"Rate limited: {rate_limited}")
    
    c.execute('''SELECT detail_type, COUNT(*),
                 SUM(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 ELSE 0 END) as client,
                 SUM(CASE WHEN contract_amount_tl IS NOT NULL THEN 1 ELSE 0 END) as amount,
                 SUM(CASE WHEN block_shares IS NOT NULL THEN 1 ELSE 0 END) as block
                 FROM disclosure_details
                 WHERE detail_type IN ('tender','transfer')
                 GROUP BY detail_type''')
    for r in c.fetchall():
        print(f"  {r[0]}: total={r[1]}, client={r[2]}, amount={r[3]}, block={r[4]}")
    
    db.close()

if __name__ == '__main__':
    main()
