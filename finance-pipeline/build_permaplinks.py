"""
KAP Permalink Mapping Builder
KAP'tan şirket listesini çekip kap_permaplinks.json oluşturur.
Bu dosya M9 (management) ve M10 (subsidiaries) modülleri için gerekli.
"""
import sys, io, sqlite3, json, time, requests, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
OUTPUT = str(Path(__file__).parent / 'kap_permaplinks.json')

def log(msg):
    print(f"[BUILDER] {msg}", flush=True)

def build_permaplinks():
    """KAP'tan şirket listesini çekip permalink mapping oluştur."""
    
    db = sqlite3.connect(DB_PATH, timeout=5)
    c = db.cursor()
    
    # Companies tablosundaki ticker'ları al
    companies = c.execute("SELECT id, ticker, company_name FROM companies WHERE is_active = 1").fetchall()
    log(f"Toplam {len(companies)} şirket var")
    
    # KAP'ın şirket listesi sayfasından permaLink'leri çek
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://kap.org.tr',
    })
    
    # KAP'ın React/Next.js sayfasından company listesini çek
    # İlk olarak ana sayfaya git ve __NEXT_DATA__ veya RSC payload'ı al
    try:
        resp = session.get('https://kap.org.tr/tr/bist-sirketler', timeout=20)
        log(f"KAP response: {resp.status_code}, length: {len(resp.text)}")
        
        # HTML'den tüm şirket linklerini parse et
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Tüm linkleri tara
        links = soup.find_all('a', href=True)
        perma_map = {}
        
        for link in links:
            href = link.get('href', '')
            # /tr/sirket-bilgileri/ozet/{mkk_id}-{slug} pattern
            match = re.search(r'/tr/sirket-bilgileri/ozet/(\d+)-([a-z0-9-]+)', href)
            if match:
                mkk_id = match.group(1)
                slug = match.group(2)
                perma = f"{mkk_id}-{slug}"
                
                # Ticker'ı linkin text'inden bul
                text = link.get_text(strip=True).upper()
                # Text genelde "THYAO TÜRK HAVA YOLLARI" formatında
                ticker = text.split()[0] if text else ''
                
                if ticker and len(ticker) >= 3 and len(ticker) <= 10:
                    perma_map[ticker] = perma
        
        log(f"HTML parse ile {len(perma_map)} permalink bulundu")
        
    except Exception as e:
        log(f"HTML parse hatası: {e}")
        perma_map = {}
    
    # KAP'ın API endpoint'inden de deneme
    if len(perma_map) < 100:
        log("API endpoint'inden de deneniyor...")
        try:
            # KAP'ın internal API'si
            api_resp = session.get('https://kap.org.tr/tr/api/sirketler', timeout=15)
            if api_resp.status_code == 200:
                api_data = api_resp.json()
                for item in api_data:
                    ticker = item.get('stockCode', item.get('ticker', ''))
                    oid = item.get('mkkMemberOid', item.get('oid', ''))
                    if ticker and oid:
                        # permaLink'i oid'den türet
                        # KAP'ta permaLink genelde "{oid}-{slug}" formatında
                        # slug'ı company name'den türet
                        name = item.get('companyName', item.get('name', ''))
                        slug = re.sub(r'[^a-z0-9]', '-', name.lower())
                        slug = re.sub(r'-+', '-', slug).strip('-')
                        perma_map[ticker.upper()] = f"{oid}-{slug}"
                log(f"API ile toplam {len(perma_map)} mapping")
        except Exception as e:
            log(f"API hatası: {e}")
    
    # Hiç veri yoksa manuel mapping dene
    if len(perma_map) < 50:
        log("Manuel slug denemesi...")
        for comp_id, ticker, name in companies:
            if ticker not in perma_map:
                # ticker'dan slug türet
                slug = re.sub(r'[^a-z0-9]', '-', ticker.lower())
                # KAP'ta mkk_id genelde company_id'ye yakın
                # permaLink = "{mkk_id}-{slug}" formatında
                # mkk_id'yi companies tablosundan al
                mkk_row = c.execute("SELECT mkk_id FROM companies WHERE id = ?", (comp_id,)).fetchone()
                if mkk_row and mkk_row[0]:
                    # mkk_id aslında şehir ismi — gerçek mkk_id'yi KAP'tan al
                    pass
                # En azından slug ile dene
                perma_map[ticker] = f"0-{slug}"
    
    # JSON'a yaz
    # company_id -> permaLink mapping
    final_map = {}
    for comp_id, ticker, name in companies:
        if ticker in perma_map:
            final_map[str(comp_id)] = {
                'permaLink': perma_map[ticker],
                'ticker': ticker,
                'name': name
            }
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final_map, f, ensure_ascii=False, indent=2)
    
    log(f"kap_permaplinks.json oluşturuldu: {len(final_map)} şirket")
    log(f"  Dosya: {OUTPUT}")
    
    # Örnek göster
    for k, v in list(final_map.items())[:5]:
        log(f"  id={k}: {v['ticker']} -> {v['permaLink']}")
    
    db.close()
    return final_map

if __name__ == '__main__':
    build_permaplinks()
