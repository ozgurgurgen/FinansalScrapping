"""
Scrape shareholder and management data from KAP company pages.
Uses the new KAP Next.js RSC payload parsing approach.
Anti-ban: random delays, rotating user agents, batch processing.
"""
import sqlite3
import requests
import time
import random
import sys
import io
import json
import re
import unicodedata
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = 'finance.db'
KAP_BASE = 'https://kap.org.tr'

def tr_lower(s):
    """Turkish-safe lowercase that handles İ/Ş/Ç/Ğ/Ü/Ö"""
    s = unicodedata.normalize('NFC', s)
    mapping = {'İ': 'i', 'I': 'ı', 'Ş': 's', 'Ç': 'c', 'Ğ': 'g', 'Ü': 'u', 'Ö': 'o'}
    for k, v in mapping.items():
        s = s.replace(k, v)
    return s.lower()

def create_session():
    from fake_useragent import UserAgent
    ua = UserAgent()
    s = requests.Session()
    s.headers.update({
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'tr-TR,tr;q=0.9',
    })
    return s

def fetch_company_page(session, ticker, perma_link):
    """Fetch a KAP company page and extract RSC payload."""
    url = f'{KAP_BASE}/tr/sirket-bilgileri/ozet/{perma_link}'
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            return None
        return r.text
    except Exception as e:
        return None

def parse_rsc_payload(html):
    """Extract and decode RSC payload from KAP page."""
    # Find self.__next_f.push() calls
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"([^"]+)"\]\)', html)
    if not pushes:
        return ""
    
    decoded_parts = []
    for push in pushes:
        # Decode unicode escapes
        try:
            decoded = push.encode('utf-8').decode('unicode_escape')
            decoded_parts.append(decoded)
        except:
            decoded_parts.append(push)
    
    return '\n'.join(decoded_parts)

def extract_shareholders_from_rsc(rsc_text, ticker):
    """Extract shareholder data from RSC payload."""
    shareholders = []
    
    # Look for shareholder table data patterns
    # KAP RSC payloads contain JSON-like structures with shareholder info
    
    # Pattern: "ortak" or "shareholder" sections
    # The data is often in nested JSON structures
    
    # Try to find holder names and ratios
    # Common patterns in KAP RSC:
    # "holderName":"...", "sharePercent":...
    # or table rows with name, shares, ratio
    
    # Pattern 1: JSON-style holder data
    holder_pattern = re.findall(
        r'"(?:holderName|name|ortakAdi|paySahibiAdi)"\s*:\s*"([^"]+)".*?"(?:sharePercent|ratio|payOrani|oran)"\s*:\s*([\d.,]+)',
        rsc_text, re.I
    )
    for name, ratio in holder_pattern:
        if name and len(name) > 2 and not name.isdigit():
            shareholders.append({
                'name': name.strip(),
                'ratio': float(ratio.replace(',', '.')),
                'type': 'CORPORATE' if any(k in name.upper() for k in ['A.Ş.', 'A.S.', 'HOLDING', 'FON', 'BANK', 'PORTFÖY']) else 'REAL_PERSON'
            })
    
    # Pattern 2: Table-like structures with pipe separators
    table_pattern = re.findall(
        r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü\s\.]{5,50})\s*[|\|]\s*([\d.,]+)\s*%',
        rsc_text
    )
    for name, ratio in table_pattern:
        name = name.strip()
        if name and not name.isdigit() and len(name) > 3:
            shareholders.append({
                'name': name,
                'ratio': float(ratio.replace(',', '.')),
                'type': 'CORPORATE' if any(k in name.upper() for k in ['A.Ş.', 'A.S.', 'HOLDING', 'FON', 'BANK']) else 'REAL_PERSON'
            })
    
    return shareholders

def extract_management_from_rsc(rsc_text, ticker):
    """Extract management board data from RSC payload."""
    members = []
    
    # Look for management board patterns
    # Pattern 1: JSON-style member data
    member_pattern = re.findall(
        r'"(?:memberName|yoneticiAdi|boardMember)"\s*:\s*"([^"]+)".*?"(?:title|unvan|gorevi)"\s*:\s*"([^"]+)"',
        rsc_text, re.I
    )
    for name, title in member_pattern:
        if name and len(name) > 2 and not name.isdigit():
            members.append({'name': name.strip(), 'title': title.strip()})
    
    # Pattern 2: "Başkan", "CEO", "Genel Müdür" keywords near names
    role_pattern = re.findall(
        r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,40})\s*(?:Başkan|CEO|Genel Müdür|Müdür|Bağımsız Üye)',
        rsc_text
    )
    for name in role_pattern:
        name = name.strip()
        if name and not name.isdigit() and len(name) > 3:
            members.append({'name': name, 'title': 'Board Member'})
    
    return members

def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    
    # Load permaLinks
    import os
    perma_path = os.path.join('kap-pipeline', 'kap_permaplinks.json')
    if not os.path.exists(perma_path):
        print('ERROR: kap_permaplinks.json not found')
        return
    
    with open(perma_path, 'r', encoding='utf-8') as f:
        perma_links = json.load(f)
    
    # Get companies that need shareholder/management data
    c.execute('''SELECT id, ticker, company_name FROM kap_companies 
                 WHERE is_active = 1 ORDER BY ticker''')
    companies = c.fetchall()
    
    # Check which already have good data
    c.execute('''SELECT DISTINCT company_id FROM kap_shareholders 
                 WHERE holder_name LIKE "% %" AND LENGTH(holder_name) > 3''')
    have_shareholders = set(r[0] for r in c.fetchall())
    
    c.execute('''SELECT DISTINCT company_id FROM kap_management 
                 WHERE name LIKE "% %" AND LENGTH(name) > 3''')
    have_management = set(r[0] for r in c.fetchall())
    
    to_scrape = [(co.id, co.ticker, co.company_name) for co in companies 
                 if co.id not in have_shareholders or co.id not in have_management]
    
    print(f'Total companies: {len(companies)}')
    print(f'Already have shareholders: {len(have_shareholders)}')
    print(f'Already have management: {len(have_management)}')
    print(f'Need scraping: {len(to_scrape)}')
    
    if not to_scrape:
        print('All companies already have data!')
        db.close()
        return
    
    session = create_session()
    batch_size = 5
    total_sh = 0
    total_mgmt = 0
    errors = 0
    
    for i, (company_id, ticker, name) in enumerate(to_scrape[:100]):  # Start with 100
        pl = perma_links.get(str(company_id), {})
        perma = pl.get('permaLink', '')
        if not perma:
            continue
        
        if i % batch_size == 0 and i > 0:
            session = create_session()
            if i % 25 == 0:
                cooldown = random.uniform(15, 30)
                print(f'  [COOLDOWN] {i}/{len(to_scrape)} | SH:{total_sh} MGMT:{total_mgmt} ERR:{errors}')
                time.sleep(cooldown)
            else:
                time.sleep(random.uniform(2, 4))
        
        html = fetch_company_page(session, ticker, perma)
        if not html:
            errors += 1
            continue
        
        rsc = parse_rsc_payload(html)
        
        # Extract shareholders
        if company_id not in have_shareholders:
            sh = extract_shareholders_from_rsc(rsc, ticker)
            if sh:
                for holder in sh[:20]:  # Max 20 shareholders per company
                    c.execute('''INSERT OR IGNORE INTO kap_shareholders 
                        (company_id, holder_name, share_ratio_percent, holder_type, is_qualified)
                        VALUES (?, ?, ?, ?, ?)''',
                        (company_id, holder['name'][:500], holder['ratio'],
                         holder['type'], holder.get('ratio', 0) > 5.0))
                total_sh += len(sh[:20])
                db.commit()
        
        # Extract management
        if company_id not in have_management:
            mgmt = extract_management_from_rsc(rsc, ticker)
            if mgmt:
                for member in mgmt[:20]:  # Max 20 members per company
                    c.execute('''INSERT OR IGNORE INTO kap_management 
                        (company_id, name, title, member_type)
                        VALUES (?, ?, ?, ?)''',
                        (company_id, member['name'][:500], member['title'], 'member'))
                total_mgmt += len(mgmt[:20])
                db.commit()
        
        if (i + 1) % 10 == 0:
            print(f'  [{i+1}/{min(100, len(to_scrape))}] {ticker}: SH={total_sh} MGMT={total_mgmt}')
        
        time.sleep(random.uniform(0.5, 1.5))
    
    print(f'\nDone! Shareholders: {total_sh}, Management: {total_mgmt}, Errors: {errors}')
    db.close()

if __name__ == '__main__':
    main()
