"""
KAP Bildirimlerinden Kurumsal İşlemler (Temettü/B Bedelli/Bedelsiz) Parse
"""
import sys, io, sqlite3, re, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')

def create_tables(db):
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS corporate_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            ticker TEXT,
            disclosure_id INTEGER,
            action_type TEXT,
            title TEXT,
            gross_per_share REAL,
            net_per_share REAL,
            yield_pct REAL,
            bonus_ratio REAL,
            rights_ratio REAL,
            ex_date TEXT,
            payment_date TEXT,
            status TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

def parse_number(text):
    """Parse Turkish number format"""
    if not text:
        return None
    text = text.strip().replace('.', '').replace(',', '.')
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text)
    except:
        return None

def parse_dividend(title, body):
    """Temettü bildiriminden veri çıkar"""
    result = {'action_type': 'DIVIDEND'}
    
    # Hisse başına brüt temettü
    patterns_gross = [
        r'[Hh]isse\s*[Bb]a[sş]ına\s*[Bb]rüt\s*[Tt]emettü\s*[:\s]*(\d+[.,]?\d*)\s*(?:TL|₺|Yeni\s*TL)',
        r'[Bb]rüt\s*[Tt]emettü\s*[:\s]*(\d+[.,]?\d*)\s*(?:TL|₺)',
        r'[Tt]emettü\s*[Tt]utar[iİı]\s*[:\s]*(\d+[.,]?\d*)\s*(?:TL|₺)',
    ]
    for pat in patterns_gross:
        m = re.search(pat, title + ' ' + body)
        if m:
            result['gross_per_share'] = parse_number(m.group(1))
            break
    
    # Net temettü
    patterns_net = [
        r'[Nn]et\s*[Tt]emettü\s*[:\s]*(\d+[.,]?\d*)\s*(?:TL|₺)',
        r'[Hh]isse\s*[Bb]a[sş]ına\s*[Nn]et\s*[:\s]*(\d+[.,]?\d*)',
    ]
    for pat in patterns_net:
        m = re.search(pat, title + ' ' + body)
        if m:
            result['net_per_share'] = parse_number(m.group(1))
            break
    
    # Tarih patterns
    ex_match = re.search(r'[Hh]ak\s*[Kk]ullan[ıi]m\s*[Tt]arihi\s*[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})', title + ' ' + body)
    if ex_match:
        result['ex_date'] = ex_match.group(1)
    
    pay_match = re.search(r'[Öö]deme\s*[Tt]arihi\s*[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})', title + ' ' + body)
    if pay_match:
        result['payment_date'] = pay_match.group(1)
    
    # Onay durumu
    if 'kesinleşti' in title.lower() or 'kesin' in title.lower():
        result['status'] = 'APPROVED'
    elif 'teklif' in title.lower() or 'öneri' in title.lower():
        result['status'] = 'PROPOSAL'
    else:
        result['status'] = 'UNKNOWN'
    
    return result

def parse_bonus_or_rights(title, body):
    """Bedelli/Bedelsiz parse"""
    result = {}
    combined = title + ' ' + body
    
    # Bedelsiz
    if 'bedelsiz' in combined.lower():
        result['action_type'] = 'BONUS_ISSUE'
        m = re.search(r'(\d+[.,]?\d*)\s*(?:[Bb]edelsiz\s*[Pp]ay|[Tt]\'ye\s*[Bb]edelsiz)', combined)
        if m:
            result['bonus_ratio'] = parse_number(m.group(1))
    
    # Bedelli
    elif 'bedelli' in combined.lower():
        result['action_type'] = 'RIGHTS_ISSUE'
        m = re.search(r'%(\d+[.,]?\d*)\s*[Bb]edelli', combined)
        if m:
            result['rights_ratio'] = parse_number(m.group(1))
    
    return result

def parse_corporate_actions():
    db = sqlite3.connect(DB_PATH, timeout=10)
    create_tables(db)
    c = db.cursor()
    
    # Get dividend/bonus/rights related disclosures
    c.execute("""
        SELECT d.id, d.symbol, d.title, d.raw_content, d.company_id, d.publish_date
        FROM disclosures d
        WHERE d.title LIKE '%temettü%' OR d.title LIKE '%Temettü%'
           OR d.title LIKE '%T Temettü%'
           OR d.title LIKE '%bedelsiz%'
           OR d.title LIKE '%bedelli%'
           OR d.title LIKE '%sermaye%'
           OR d.title LIKE '%Sermaye%'
           OR d.title LIKE '%dividend%'
           OR d.title LIKE '%hisse başına%'
        ORDER BY d.publish_date DESC
    """)
    disc_rows = c.fetchall()
    
    # Also check disclosure_details
    c.execute("""
        SELECT dd.disclosure_index, dd.title, dd.detail_type
        FROM disclosure_details dd
        WHERE dd.detail_type LIKE '%temettü%'
           OR dd.detail_type LIKE '%dividend%'
           OR dd.detail_type LIKE '%bonus%'
           OR dd.detail_type LIKE '%rights%'
    """)
    detail_rows = c.fetchall()
    
    print(f"Temettü/sermaye bildirimi: {len(disc_rows)}")
    print(f"Disclosure detail ilgili: {len(detail_rows)}")
    
    parsed = 0
    skipped = 0
    
    for disc_id, symbol, title, content, company_id, pub_date in disc_rows:
        body = content or ''
        
        # Skip if already parsed
        c.execute("SELECT COUNT(*) FROM corporate_actions WHERE disclosure_id = ?", (disc_id,))
        if c.fetchone()[0] > 0:
            skipped += 1
            continue
        
        # Determine action type
        is_dividend = any(w in (title + body).lower() for w in ['temettü', 'temettu', 'dividend', 'hisse başına'])
        is_bonus = 'bedelsiz' in (title + body).lower()
        is_rights = 'bedelli' in (title + body).lower()
        
        if is_dividend:
            data = parse_dividend(title, body)
        elif is_bonus or is_rights:
            data = parse_bonus_or_rights(title, body)
        else:
            continue
        
        data['company_id'] = company_id
        data['ticker'] = symbol
        data['disclosure_id'] = disc_id
        data['title'] = title
        data['description'] = (body[:500] if body else '')
        
        try:
            c.execute("""
                INSERT INTO corporate_actions 
                (company_id, ticker, disclosure_id, action_type, title, 
                 gross_per_share, net_per_share, yield_pct, bonus_ratio, rights_ratio,
                 ex_date, payment_date, status, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('company_id'), data.get('ticker'), data.get('disclosure_id'),
                data.get('action_type', 'UNKNOWN'), data.get('title', ''),
                data.get('gross_per_share'), data.get('net_per_share'),
                data.get('yield_pct'), data.get('bonus_ratio'), data.get('rights_ratio'),
                data.get('ex_date'), data.get('payment_date'), data.get('status'),
                data.get('description', '')
            ))
            parsed += 1
        except Exception as e:
            print(f"  DB hatası: {e}")
    
    db.commit()
    
    # Also parse disclosure_details
    for dd_index, dd_title, dd_type in detail_rows:
        c.execute("SELECT COUNT(*) FROM corporate_actions WHERE disclosure_id = (SELECT id FROM disclosures WHERE disclosure_index = ?)", (dd_index,))
        if c.fetchone()[0] > 0:
            continue
        
        # Try to find company
        c.execute("SELECT id, symbol, company_id FROM disclosures WHERE disclosure_index = ?", (dd_index,))
        disc_info = c.fetchone()
        if not disc_info:
            continue
        
        disc_id, symbol, cid = disc_info
        data = parse_dividend(dd_title, '') if 'temettü' in dd_type.lower() else parse_bonus_or_rights(dd_title, '')
        
        if data.get('action_type'):
            data['company_id'] = cid
            data['ticker'] = symbol
            data['disclosure_id'] = disc_id
            data['title'] = dd_title
            
            try:
                c.execute("""
                    INSERT INTO corporate_actions 
                    (company_id, ticker, disclosure_id, action_type, title, 
                     gross_per_share, net_per_share, yield_pct, bonus_ratio, rights_ratio,
                     ex_date, payment_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('company_id'), data.get('ticker'), data.get('disclosure_id'),
                    data.get('action_type', 'UNKNOWN'), data.get('title', ''),
                    data.get('gross_per_share'), data.get('net_per_share'),
                    data.get('yield_pct'), data.get('bonus_ratio'), data.get('rights_ratio'),
                    data.get('ex_date'), data.get('payment_date'), data.get('status'),
                    data.get('description', '')
                ))
                parsed += 1
            except:
                pass
    
    db.commit()
    
    # Summary
    c.execute("SELECT COUNT(*) FROM corporate_actions")
    total = c.fetchone()[0]
    c.execute("SELECT action_type, COUNT(*) FROM corporate_actions GROUP BY action_type")
    types = c.fetchall()
    
    print(f"\n=== KURUMSAL İŞLEM SONUCU ===")
    print(f"Toplam kayıt: {total}")
    for t, cnt in types:
        print(f"  {t}: {cnt}")
    
    db.close()
    return parsed

if __name__ == '__main__':
    parse_corporate_actions()
