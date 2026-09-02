"""
Scrape sector info from KAP company summary pages.
Extracts sector/industry classification for each company.
Anti-ban: random delays, rotating user agents.
"""
import sqlite3
import requests
import time
import random
import sys
import io
import json
import re
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = 'finance.db'

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

def extract_sector(html):
    """Extract sector from KAP company summary page."""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    
    # Pattern: "Sektörü[SECTOR NAME]Sermaye"
    m = re.search(r'Sekt[öo]r[üu]\s*([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü\s]+?)(?:Sermaye|İşlem|Kayıtlı)', text)
    if m:
        sector = m.group(1).strip()
        # Clean up sector name
        sector = re.sub(r'\s+', ' ', sector)
        return sector
    
    return None

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Load permaLinks
    with open('kap-pipeline/kap_permaplinks.json', 'r', encoding='utf-8') as f:
        perma_links = json.load(f)
    
    # Get companies that need sector info
    c.execute('''SELECT id, ticker FROM kap_companies 
                 WHERE sector IS NULL OR sector = "" 
                 ORDER BY ticker''')
    companies = c.fetchall()
    
    print(f'Companies needing sector: {len(companies)}')
    
    session = create_session()
    batch_size = 5
    updated = 0
    errors = 0
    
    for i, (co_id, ticker) in enumerate(companies):
        pl = perma_links.get(str(co_id), {})
        perma = pl.get('permaLink', '')
        if not perma:
            continue
        
        if i % batch_size == 0 and i > 0:
            session = create_session()
            if i % 50 == 0:
                cooldown = random.uniform(10, 20)
                print(f'  [COOLDOWN] {i}/{len(companies)} | Updated: {updated} | Errors: {errors}')
                time.sleep(cooldown)
            else:
                time.sleep(random.uniform(1, 2))
        
        url = f'https://kap.org.tr/tr/sirket-bilgileri/ozet/{perma}'
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                sector = extract_sector(r.text)
                if sector:
                    c.execute('UPDATE kap_companies SET sector = ? WHERE id = ?', (sector, co_id))
                    updated += 1
                    if updated % 20 == 0:
                        db.commit()
                        print(f'  [{i+1}/{len(companies)}] {ticker}: {sector[:50]}')
            else:
                errors += 1
        except Exception as e:
            errors += 1
        
        time.sleep(random.uniform(0.3, 0.8))
    
    db.commit()
    
    # Final stats
    c.execute('SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ""')
    total_with_sector = c.fetchone()[0]
    print(f'\nDone! Updated: {updated}, Total with sector: {total_with_sector}, Errors: {errors}')
    
    # Show sector distribution
    c.execute('''SELECT sector, COUNT(*) as cnt FROM kap_companies 
                 WHERE sector IS NOT NULL AND sector != ""
                 GROUP BY sector ORDER BY cnt DESC LIMIT 20''')
    print('\nSector distribution:')
    for sector, cnt in c.fetchall():
        print(f'  {sector}: {cnt}')
    
    db.close()

if __name__ == '__main__':
    main()
