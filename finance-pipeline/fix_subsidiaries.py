"""
Fix subsidiaries table:
1. Remove metadata rows (Ticaret Ünvanı, Şirketin Faaliyet Konusu etc.)
2. Extract share_percent from KAP subsidiary disclosure pages
"""
import sys, io, sqlite3, requests, time, random, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = 'finance.db'

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://www.kap.org.tr',
    })
    return s

def parse_share_percent(text):
    """Extract percentage from text like '%56,89' or '56.89%'"""
    if not text:
        return None
    # Try patterns: %56,89 or 56,89% or 56.89%
    m = re.search(r'(\d+[.,]\d+)\s*%', text)
    if m:
        return float(m.group(1).replace(',', '.'))
    m = re.search(r'%\s*(\d+[.,]\d+)', text)
    if m:
        return float(m.group(1).replace(',', '.'))
    m = re.search(r'(\d+[.,]\d+)', text)
    if m:
        val = float(m.group(1).replace(',', '.'))
        if 0 < val <= 100:
            return val
    return None

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    
    # Step 1: Remove metadata rows
    meta_names = ['Ticaret Ünvanı', 'Şirketin Faaliyet Konusu', 'Ticaret Unvani', 'Sermaye']
    deleted = 0
    for name in meta_names:
        c.execute("DELETE FROM subsidiaries WHERE name LIKE ?", (f'%{name}%',))
        deleted += c.rowcount
    db.commit()
    print(f"1. Metadata satirlari silindi: {deleted}", flush=True)
    
    # Step 2: Try to extract share_percent from KAP disclosure pages
    # Get companies that have subsidiaries but share_percent=0
    c.execute("""
        SELECT s.id, s.company_id, s.name, c.ticker, c.company_name
        FROM subsidiaries s
        JOIN companies c ON s.company_id = c.id
        WHERE (s.share_percent IS NULL OR s.share_percent = 0)
        AND c.ticker IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 200
    """)
    targets = c.fetchall()
    print(f"2. share_percent=0 olan subsidiary: {len(targets)}", flush=True)
    
    # Group by company_id to avoid duplicate requests
    companies = {}
    for sid, cid, name, ticker, cname in targets:
        if cid not in companies:
            companies[cid] = {'ticker': ticker, 'name': cname, 'subs': []}
        companies[cid]['subs'].append({'id': sid, 'name': name})
    
    print(f"3. {len(companies)} farkli sirket icin KAP'a gidilecek", flush=True)
    
    s = create_session()
    updated = 0
    
    for i, (cid, info) in enumerate(companies.items()):
        ticker = info['ticker']
        subs = info['subs']
        
        try:
            # Try to get subsidiary data from KAP company page
            # Use the disclosure API to find "Ortaklık Yapısı" or "İştirak" disclosures
            resp = s.get(f'https://www.kap.org.tr/tr/sirket-bilgileri/genel/{ticker}', timeout=10)
            time.sleep(random.uniform(2, 4))
            
            if resp.status_code == 200:
                text = resp.text
                # Look for percentage patterns near subsidiary names
                for sub in subs:
                    sub_name = sub['name'].upper()
                    # Search for this name in the page text
                    idx = text.upper().find(sub_name[:20])
                    if idx >= 0:
                        # Look for percentage in surrounding 500 chars
                        surrounding = text[max(0, idx-200):idx+300]
                        pct = parse_share_percent(surrounding)
                        if pct:
                            c.execute("UPDATE subsidiaries SET share_percent = ? WHERE id = ?", (pct, sub['id']))
                            updated += 1
            
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(companies)}] Updated: {updated}", flush=True)
                db.commit()
                
        except Exception as e:
            pass
        
        time.sleep(random.uniform(1, 3))
    
    db.commit()
    db.close()
    
    print(f"\n=== SONUC ===", flush=True)
    print(f"  Silinen metadata: {deleted}", flush=True)
    print(f"  Guncellenen share_percent: {updated}", flush=True)

if __name__ == '__main__':
    main()
