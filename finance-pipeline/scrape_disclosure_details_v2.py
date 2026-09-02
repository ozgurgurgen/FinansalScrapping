"""
KAP Disclosure Detail Scraper v2
- Resume-able queue sistemi
- Exponential backoff + jitter  
- Persistent browser context (cookie korur)
- Disclosure detail tablosunu doldurur
"""
import sys, io, sqlite3, time, random, re, json, os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
QUEUE_FILE = str(Path(__file__).parent / 'disclosure_queue.json')

def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    return {'pending': [], 'done': [], 'failed': []}

def save_queue(queue):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f)

def parse_number(text):
    if not text or text.strip() in ['-', '—', '', 'n/a']:
        return None
    text = text.strip().replace('(', '').replace(')', '')
    text = text.replace('.', '').replace(',', '.')
    text = re.sub(r'[^\d.\-]', '', text)
    try:
        return float(text)
    except:
        return None

def extract_tender_info(text):
    """İhale sonuç bilgilerini parse et"""
    result = {}
    
    # Sözleşme tutarı
    patterns_amount = [
        r'[Ss]özleşme\s+[Tt]utar[ıi]\s*[:\s]*([\d.,]+)\s*(?:TL|₺|USD|EUR|ABD\s*Doları|Euro)',
        r'[Tt]oplam\s+[Tt]utar\s*[:\s]*([\d.,]+)',
        r'[İi]hale\s+[Tt]utar[ıi]\s*[:\s]*([\d.,]+)',
        r'(\d[\d.,]+)\s*(?:TL|₺)\s*[Ss]özleşme',
    ]
    for pat in patterns_amount:
        m = re.search(pat, text)
        if m:
            result['contract_amount_tl'] = parse_number(m.group(1))
            break
    
    # USD tutarı
    usd_match = re.search(r'([\d.,]+)\s*(?:USD|ABD\s*Doları)', text)
    if usd_match:
        result['contract_amount_usd'] = parse_number(usd_match.group(1))
    
    # EUR tutarı
    eur_match = re.search(r'([\d.,]+)\s*(?:EUR|Euro)', text)
    if eur_match:
        result['contract_amount_eur'] = parse_number(eur_match.group(1))
    
    # Müşteri/Kurum
    client_patterns = [
        r'[Mm]üşteri\s*[:\s]*(.+?)(?:\n|$)',
        r'[Kk]urum\s*[:\s]*(.+?)(?:\n|$)',
        r'[İi]dare\s*[:\s]*(.+?)(?:\n|$)',
        r'[Ss]ipariş\s+[Ss]ahibi\s*[:\s]*(.+?)(?:\n|$)',
    ]
    for pat in client_patterns:
        m = re.search(pat, text)
        if m:
            result['client_name'] = m.group(1).strip()[:200]
            break
    
    return result

def extract_block_sale_info(text):
    """Blok satış bilgilerini parse et"""
    result = {}
    
    # Pay adedi
    shares_match = re.search(r'([\d.,]+)\s*(?:adet|pay)', text, re.IGNORECASE)
    if shares_match:
        result['block_shares'] = parse_number(shares_match.group(1))
    
    # Fiyat
    price_match = re.search(r'([\d.,]+)\s*(?:TL|₺)\s*(?:birim|pay\s*başına|fiyat)', text, re.IGNORECASE)
    if price_match:
        result['block_price'] = parse_number(price_match.group(1))
    
    # Toplam tutar
    total_match = re.search(r'[Tt]oplam\s*[:\s]*([\d.,]+)\s*(?:TL|₺)', text)
    if total_match:
        result['total_amount'] = parse_number(total_match.group(1))
    
    return result

def extract_qualified_investor_info(text):
    """Nitelikli yatırımcıya satış bilgisi"""
    result = {}
    
    amount_match = re.search(r'([\d.,]+)\s*(?:TL|₺)', text)
    if amount_match:
        result['amount_tl'] = parse_number(amount_match.group(1))
    
    shares_match = re.search(r'([\d.,]+)\s*(?:adet|pay)', text, re.IGNORECASE)
    if shares_match:
        result['shares'] = parse_number(shares_match.group(1))
    
    return result

def scrape_disclosure_detail(page, disclosure_index):
    """Tek bir bildirim detay sayfasını çek"""
    url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
    
    try:
        page.goto(url, timeout=15000, wait_until='domcontentloaded')
        time.sleep(1.5)
        
        # Get page text
        text = page.inner_text('body')
        html = page.content()
        
        # Determine type
        is_tender = any(w in text.lower() for w in ['ihale', 'kazanılan', 'sözleşme', 'tenkid'])
        is_block = any(w in text.lower() for w in ['blok satış', 'toplu alım', 'pazarlık usulü'])
        is_qualified = any(w in text.lower() for w in ['nitelikli yatırımcı', 'nitelikli'])
        is_dividend = any(w in text.lower() for w in ['temettü', 'kar payı', 'dividend'])
        is_capital = any(w in text.lower() for w in ['sermaye artırımı', 'bedelli', 'bedelsiz'])
        
        detail_type = 'OTHER'
        detail_data = {}
        
        if is_tender:
            detail_type = 'TENDER'
            detail_data = extract_tender_info(text)
        elif is_block:
            detail_type = 'BLOCK_SALE'
            detail_data = extract_block_sale_info(text)
        elif is_qualified:
            detail_type = 'QUALIFIED_INVESTOR'
            detail_data = extract_qualified_investor_info(text)
        elif is_dividend:
            detail_type = 'DIVIDEND'
        elif is_capital:
            detail_type = 'CAPITAL'
        
        return {
            'detail_type': detail_type,
            'data': detail_data,
            'text_preview': text[:500]
        }
        
    except Exception as e:
        return {'error': str(e)}

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    c = db.cursor()
    queue = load_queue()
    
    # Build queue from disclosures that don't have detail records
    if not queue['pending']:
        c.execute("""
            SELECT d.id, d.disclosure_index, d.symbol, d.title, d.company_id
            FROM disclosures d
            LEFT JOIN disclosure_details dd ON dd.disclosure_index = d.disclosure_index
            WHERE dd.id IS NULL
            AND d.disclosure_index IS NOT NULL
            AND d.disclosure_index != ''
            ORDER BY d.publish_date DESC
        """)
        rows = c.fetchall()
        queue['pending'] = [
            {'disc_id': r[0], 'disc_index': r[1], 'symbol': r[2], 'title': r[3], 'company_id': r[4]}
            for r in rows
        ]
        save_queue(queue)
        print(f"Queue oluşturuldu: {len(queue['pending'])} bildirim")
    
    print(f"Pending: {len(queue['pending'])}, Done: {len(queue['done'])}, Failed: {len(queue['failed'])}")
    
    if not queue['pending']:
        print("Tümü tamamlanmış!")
        db.close()
        return
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], capture_output=True)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], capture_output=True)
        from playwright.sync_api import sync_playwright
    
    batch_size = min(50, len(queue['pending']))  # 50'şer çek
    batch = queue['pending'][:batch_size]
    
    updated = 0
    errors = 0
    backoff = 2.0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul'
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        page = context.new_page()
        
        for i, item in enumerate(batch):
            disc_index = item['disc_index']
            
            try:
                result = scrape_disclosure_detail(page, disc_index)
                
                if 'error' in result:
                    errors += 1
                    backoff = min(backoff * 1.5, 30.0)
                    
                    if '429' in result['error'] or '403' in result['error'] or 'timeout' in result['error'].lower():
                        print(f"  ⚠️ Rate limit/ban algılandı! Backoff: {backoff:.1f}s")
                        time.sleep(backoff)
                        # Don't remove from queue - retry later
                        continue
                else:
                    # Insert into disclosure_details
                    data = result.get('data', {})
                    
                    try:
                        c.execute("""
                            INSERT OR IGNORE INTO disclosure_details 
                            (disclosure_index, ticker, title, detail_type, 
                             client_name, contract_amount_tl, contract_amount_usd, contract_amount_eur,
                             block_shares, block_price)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            disc_index,
                            item['symbol'],
                            item['title'],
                            result.get('detail_type', 'OTHER'),
                            data.get('client_name'),
                            data.get('contract_amount_tl'),
                            data.get('contract_amount_usd'),
                            data.get('contract_amount_eur'),
                            data.get('block_shares') or data.get('shares'),
                            data.get('block_price') or data.get('price'),
                        ))
                        db.commit()
                        updated += 1
                    except Exception as e:
                        pass
                    
                    backoff = 2.0  # Reset backoff on success
                
                queue['done'].append(disc_index)
                queue['pending'].remove(item)
                
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(batch)}] {updated} güncellendi, {errors} hata")
                    save_queue(queue)
                
                # Jitter delay
                time.sleep(random.uniform(2.0, 5.0))
                
            except Exception as e:
                errors += 1
                queue['failed'].append(item)
                queue['pending'].remove(item)
                time.sleep(random.uniform(3.0, 7.0))
        
        browser.close()
    
    save_queue(queue)
    db.close()
    
    print(f"\n=== DİSCLOSURE DETAY SONUCU ===")
    print(f"Güncellenen: {updated}, Hata: {errors}")
    print(f"Kalan: {len(queue['pending'])}")

if __name__ == '__main__':
    main()
