#!/usr/bin/env python3
"""
Scrape ALL missing data: sectors, shareholders, management, settlement, corporate actions.
Anti-ban: random user-agent rotation, jitter, exponential backoff.
"""
import sys, io, os, time, random, re, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

# Anti-ban session
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]

def create_session():
    import requests
    s = requests.Session()
    s.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://kap.org.tr',
        'Connection': 'keep-alive',
    })
    return s

def safe_get(url, session=None, retries=3, timeout=15):
    """GET with anti-ban: retry on 429/503, random jitter."""
    if session is None:
        session = create_session()
    for attempt in range(retries):
        try:
            # Rotate UA every 5 requests
            if attempt > 0:
                session.headers['User-Agent'] = random.choice(USER_AGENTS)
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (429, 503, 502):
                wait = (2 ** attempt) * random.uniform(5, 10)
                print(f'  [WARN] {resp.status_code} - waiting {wait:.1f}s...')
                time.sleep(wait)
            elif resp.status_code == 404:
                return None
            else:
                print(f'  [WARN] HTTP {resp.status_code} for {url[:60]}')
                time.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f'  [ERR] {e}')
            time.sleep(random.uniform(3, 6))
    return None

def tr_lower(s):
    """Turkish-aware lowercase."""
    if not s:
        return ''
    replacements = {'İ': 'i', 'I': 'ı', 'Ş': 's', 'ş': 's', 'Ç': 'c', 'ç': 'c',
                    'Ğ': 'g', 'ğ': 'g', 'Ü': 'u', 'ü': 'u', 'Ö': 'o', 'ö': 'o'}
    result = s
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result.lower()

def parse_number(s):
    """Turkish number format: 1.234.567,89 -> 1234567.89"""
    if not s or s.strip() in ('', '-', '—', 'YOK'):
        return None
    s = s.strip().replace(' ', '')
    # Remove TL, USD, EUR etc
    s = re.sub(r'(TL|USD|EUR|TRL|TRY)', '', s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    # Turkish format: dots = thousands, comma = decimal
    if ',' in s and '.' in s:
        if s.rindex(',') > s.rindex('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts[-1]) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    # Handle negative
    neg = s.startswith('-')
    if neg:
        s = s[1:]
    s = s.replace(' ', '')
    try:
        val = float(s)
        return -val if neg else val
    except:
        return None

def get_companies_without_sector(db):
    c = db.cursor()
    c.execute('''
        SELECT c.id, c.ticker, c.company_name 
        FROM companies c 
        WHERE (c.sector IS NULL OR c.sector = '')
        AND c.ticker IS NOT NULL AND c.ticker != ''
        ORDER BY c.ticker
    ''')
    return c.fetchall()

def scrape_sector_from_kap(session, ticker, company_id, db):
    """Scrape sector from KAP company summary page."""
    url = f'https://kap.org.tr/tr/Bildirim/Tum-Bildirimler?amperCompanyCode={ticker}'
    resp = safe_get(url, session)
    if not resp:
        return False
    
    text = resp.text
    
    # Extract from RSC payload - sector info
    # Look for sector keywords
    sector_map = {
        'banka': 'Bankacılık', 'bankacilik': 'Bankacılık',
        'sigorta': 'Sigorta', 'holding': 'Holding',
        'gayrimenkul': 'Gayrimenkul', 'gyo': 'GYO',
        'turizm': 'Turizm', 'otel': 'Turizm/Otel',
        'imalat': 'Imalat', 'uretim': 'Imalat',
        'enerji': 'Enerji', 'elektrik': 'Enerji',
        'iletisim': 'Iletisim', 'telekom': 'Iletisim',
        'insaat': 'Insaat', 'altyapi': 'Insaat',
        'perakende': 'Perakende', 'magaza': 'Perakende',
        'gida': 'Gida', 'tarim': 'Tarim',
        'maden': 'Maden', 'demir': 'Maden',
        'ulaşım': 'Ulasim', 'ulasim': 'Ulasim',
        'tasima': 'Ulasim', 'lojistik': 'Ulasim',
        'tekstil': 'Tekstil', 'giyim': 'Tekstil',
        'otomotiv': 'Otomotiv', 'yedek': 'Otomotiv',
        'kimya': 'Kimya', 'ilaç': 'Kimya',
        'bilişim': 'Teknoloji', 'yazilim': 'Teknoloji',
        'teknoloji': 'Teknoloji', 'dijital': 'Teknoloji',
        'demir celik': 'Celik', 'celik': 'Celik',
        'cimento': 'Cimento', 'cam': 'Cam',
        'kaagit': 'Kaagit', 'ambalaj': 'Ambalaj',
        'petrol': 'Petrol', 'dogalgaz': 'Dogalgaz',
        'su': 'Altyapi', 'tarim': 'Tarim',
        'ormancilik': 'Tarim', 'avukat': 'Hizmet',
        'danismanlik': 'Hizmet', 'hizmet': 'Hizmet',
        'yatirim': 'Yatirim', 'fon': 'Yatirim',
        'sirket': 'Holding',
    }
    
    text_lower = tr_lower(text)
    for keyword, sector in sector_map.items():
        if keyword in text_lower:
            db.execute('UPDATE companies SET sector = ? WHERE id = ?', (sector, company_id))
            db.commit()
            return True
    return False

def scrape_shareholders_from_kap_api(session, ticker, company_id, db):
    """Try to scrape shareholders from KAP disclosure API."""
    # Use KAP company page with disclosure index for ortaklık yapısı
    url = f'https://kap.org.tr/tr/sirket-bilgileri/genel/{ticker}'
    resp = safe_get(url, session)
    if not resp:
        return 0
    
    count = 0
    text = resp.text
    
    # Try to extract shareholder info from RSC payload
    # Look for pattern: "holderName":"...", "shareRatio":...
    holder_pattern = re.findall(r'"holderName"\s*:\s*"([^"]+)".*?"shareRatio"\s*:\s*([\d.,]+)', text)
    
    if not holder_pattern:
        # Try alternative pattern
        holder_pattern = re.findall(r'"name"\s*:\s*"([^"]+)".*?"rate"\s*:\s*([\d.,]+)', text)
    
    if holder_pattern:
        for name, ratio in holder_pattern:
            if name and len(name) > 2 and name not in ('null', 'undefined'):
                try:
                    db.execute('''
                        INSERT OR IGNORE INTO shareholders 
                        (company_id, holder_name, share_ratio_percent, holder_type)
                        VALUES (?, ?, ?, 'INSTITUTIONAL')
                    ''', (company_id, name.strip(), parse_number(ratio)))
                    count += 1
                except:
                    pass
        if count > 0:
            db.commit()
    
    return count

def scrape_management_from_kap(session, ticker, company_id, db):
    """Try to scrape management members from KAP."""
    # KAP yonetim sayfasi
    url = f'https://kap.org.tr/tr/sirket-bilgileri/yonetim/{ticker}'
    resp = safe_get(url, session)
    if not resp:
        return 0
    
    count = 0
    text = resp.text
    
    # Try to find management names in RSC payload
    # Pattern: name + title pairs
    mgmt_pattern = re.findall(r'"name"\s*:\s*"([^"]+)".*?"title"\s*:\s*"([^"]+)"', text)
    
    if not mgmt_pattern:
        # Try simpler pattern
        mgmt_pattern = re.findall(r'"memberName"\s*:\s*"([^"]+)".*?"memberTitle"\s*:\s*"([^"]+)"', text)
    
    if mgmt_pattern:
        for name, title in mgmt_pattern:
            if name and len(name) > 3 and name not in ('null', 'undefined'):
                try:
                    db.execute('''
                        INSERT OR IGNORE INTO management_members 
                        (company_id, name, title, member_type)
                        VALUES (?, ?, ?, 'BOARD')
                    ''', (company_id, name.strip(), title.strip()))
                    count += 1
                except:
                    pass
        if count > 0:
            db.commit()
    
    return count

def scrape_settlement_data(session, db):
    """Scrape settlement (takas) data from KAP."""
    print('\n=== SETTLEMENT DATA (TAKAS) ===')
    
    # KAP settlement page
    url = 'https://kap.org.tr/tr/takas-verileri'
    resp = safe_get(url, session)
    if not resp:
        print('Settlement sayfasi erisilemedi')
        return 0
    
    count = 0
    text = resp.text
    
    # Parse settlement data from page
    # Pattern: ticker + foreign ratio
    settlement_pattern = re.findall(
        r'"stockCode"\s*:\s*"([^"]+)".*?"foreignRatio"\s*:\s*([\d.,]+)',
        text
    )
    
    if settlement_pattern:
        for ticker, foreign_ratio in settlement_pattern:
            ratio = parse_number(foreign_ratio)
            if ratio is not None and 0 <= ratio <= 100:
                db.execute('''
                    INSERT OR REPLACE INTO settlement_data 
                    (ticker, trade_date, foreign_ratio_pct, updated_at)
                    VALUES (?, date('now'), ?, datetime('now'))
                ''', (ticker, ratio))
                count += 1
        db.commit()
    
    print(f'Settlement: {count} kayıt')
    return count

def scrape_corporate_actions(session, db):
    """Scrape corporate actions (temettü, bedelli, bedelsiz) from KAP disclosures."""
    print('\n=== CORPORATE ACTIONS ===')
    
    # Get disclosure types that are corporate actions
    c = db.cursor()
    c.execute('''
        SELECT d.id, d.symbol, d.title, d.disclosure_type, d.publish_date
        FROM disclosures d
        WHERE (d.title LIKE '%temettü%' OR d.title LIKE '%Temettü%' 
               OR d.title LIKE '%bedelli%' OR d.title LIKE '%Bedelli%'
               OR d.title LIKE '%bedelsiz%' OR d.title LIKE '%Bedelsiz%'
               OR d.title LIKE '%bölünme%' OR d.title LIKE '%Bölünme%'
               OR d.title LIKE '%Sermaye Artırımı%' OR d.title LIKE '%sermaye%')
        AND NOT EXISTS (SELECT 1 FROM corporate_actions ca WHERE ca.disclosure_id = d.id)
        ORDER BY d.publish_date DESC
        LIMIT 500
    ''')
    disclosures = c.fetchall()
    print(f'{len(disclosures)} potansiyel kurumsal islem bildirimi')
    
    count = 0
    for i, (disc_id, symbol, title, dtype, pub_date) in enumerate(disclosures):
        if i % 10 == 0:
            print(f'  [{i}/{len(disclosures)}]...')
            time.sleep(random.uniform(1, 3))
        
        # Determine action type
        title_lower = tr_lower(title)
        if 'temettü' in title_lower or 'kar payi' in title_lower:
            action_type = 'DIVIDEND'
        elif 'bedelli' in title_lower:
            action_type = 'CAPITAL_INCREASE'
        elif 'bedelsiz' in title_lower:
            action_type = 'BONUS_ISSUE'
        elif 'bolunme' in title_lower:
            action_type = 'SPLIT'
        else:
            action_type = 'OTHER'
        
        # Get company_id
        c.execute('SELECT id FROM companies WHERE ticker = ?', (symbol,))
        row = c.fetchone()
        if not row:
            continue
        company_id = row[0]
        
        # Try to fetch detail page for amounts
        if symbol and disc_id:
            detail_url = f'https://kap.org.tr/tr/Bildirim/{disc_id}'
            resp = safe_get(detail_url, session)
            
            gross_per_share = None
            net_per_share = None
            ratio_pct = None
            
            if resp:
                text = resp.text
                # Try to extract gross/net from tables
                # gross = "Brüt Temettü" or "Hisse Başına Brüt"
                gross_match = re.search(r'[Bb]r.t.*?[Tt]emett.*?(\d[\d.,]+)', text)
                if gross_match:
                    gross_per_share = parse_number(gross_match.group(1))
                
                net_match = re.search(r'[Nn]et.*?[Tt]emett.*?(\d[\d.,]+)', text)
                if net_match:
                    net_per_share = parse_number(net_match.group(1))
                
                # Bedelli ratio
                ratio_match = re.search(r'[Bb]edelli.*?%(\d[\d.,]+)', text)
                if ratio_match:
                    ratio_pct = parse_number(ratio_match.group(1))
            
            db.execute('''
                INSERT OR IGNORE INTO corporate_actions
                (company_id, disclosure_id, action_type, gross_per_share, net_per_share,
                 ratio_percent, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (company_id, disc_id, action_type, gross_per_share, net_per_share, ratio_pct, title))
            count += 1
            
            if count % 20 == 0:
                db.commit()
        
        # Anti-ban jitter
        time.sleep(random.uniform(1.5, 3.5))
    
    db.commit()
    print(f'Corporate actions: {count} kayıt')
    return count

def main():
    import requests
    db = sqlite3.connect(DB_PATH)
    
    print('='*60)
    print('EKSIK VERI TAMPLAMA SCRAPER')
    print('='*60)
    
    session = create_session()
    
    # === 1. SECTOR SCRAPING ===
    print('\n=== 1. SECTOR BILGISI ===')
    missing_sectors = get_companies_without_sector(db)
    print(f'{len(missing_sectors)} sirketin sectoru eksik')
    
    sector_count = 0
    for i, (cid, ticker, name) in enumerate(missing_sectors):
        if i % 50 == 0:
            print(f'  [{i}/{len(missing_sectors)}] Sector: {sector_count} guncellendi...')
            time.sleep(random.uniform(3, 6))
        
        if scrape_sector_from_kap(session, ticker, cid, db):
            sector_count += 1
        
        time.sleep(random.uniform(1.5, 3.5))
    
    print(f'Toplam sector guncellendi: {sector_count}')
    
    # === 2. SHAREHOLDERS ===
    print('\n=== 2. ORTAKLIK YAPISI ===')
    # Get companies with most disclosures (more likely to have shareholder data)
    c = db.cursor()
    c.execute('''
        SELECT c.id, c.ticker FROM companies c
        WHERE (SELECT COUNT(*) FROM disclosures d WHERE d.symbol = c.ticker) > 5
        AND NOT EXISTS (SELECT 1 FROM shareholders s WHERE s.company_id = c.id)
        ORDER BY (SELECT COUNT(*) FROM disclosures d WHERE d.symbol = c.ticker) DESC
        LIMIT 200
    ''')
    sh_companies = c.fetchall()
    print(f'{len(sh_companies)} sirket icin ortak bilgisi cekilecek')
    
    sh_count = 0
    for i, (cid, ticker) in enumerate(sh_companies):
        if i % 20 == 0:
            print(f'  [{i}/{len(sh_companies)}] Ortak: {sh_count} guncellendi...')
            time.sleep(random.uniform(5, 10))
        
        n = scrape_shareholders_from_kap_api(session, ticker, cid, db)
        sh_count += n
        
        time.sleep(random.uniform(2, 4))
    
    print(f'Toplam ortak kaydi: {sh_count}')
    
    # === 3. MANAGEMENT ===
    print('\n=== 3. YONETIM KURULU ===')
    mgmt_count = 0
    for i, (cid, ticker) in enumerate(sh_companies[:100]):
        if i % 15 == 0:
            print(f'  [{i}/100] Yonetim: {mgmt_count} guncellendi...')
            time.sleep(random.uniform(5, 10))
        
        n = scrape_management_from_kap(session, ticker, cid, db)
        mgmt_count += n
        
        time.sleep(random.uniform(2, 4))
    
    print(f'Toplam yonetim kaydi: {mgmt_count}')
    
    # === 4. SETTLEMENT DATA ===
    scrape_settlement_data(session, db)
    
    # === 5. CORPORATE ACTIONS ===
    scrape_corporate_actions(session, db)
    
    # === FINAL SUMMARY ===
    print('\n=== OZET ===')
    c = db.cursor()
    c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != ""')
    print(f'Sector: {c.fetchone()[0]}')
    c.execute('SELECT COUNT(*) FROM shareholders')
    print(f'Ortaklar: {c.fetchone()[0]}')
    c.execute('SELECT COUNT(*) FROM management_members')
    print(f'Yonetim: {c.fetchone()[0]}')
    c.execute('SELECT COUNT(*) FROM settlement_data')
    print(f'Settlement: {c.fetchone()[0]}')
    c.execute('SELECT COUNT(*) FROM corporate_actions')
    print(f'Corporate Actions: {c.fetchone()[0]}')
    
    db.close()
    print('\nTamamlandi!')

if __name__ == '__main__':
    main()
