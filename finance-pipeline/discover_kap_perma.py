"""
KAP Permalink Discovery — her şirket için gerçek sayfa URL'ini bulur.
KAP'ın company detail sayfasından company_id -> permalink eşleştirmesi yapar.
"""
import sys, io, sqlite3, json, time, random, re, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = str(Path(__file__).parent / 'finance.db')
OUTPUT = str(Path(__file__).parent / 'kap_permaplinks.json')
PROGRESS = str(Path(__file__).parent / 'perma_progress.json')

def log(msg):
    print(f"[PERMA] {msg}", flush=True)

def load_progress():
    if Path(PROGRESS).exists():
        return json.loads(Path(PROGRESS).read_text(encoding='utf-8'))
    return {"done": {}, "failed": {}}

def save_progress(state):
    Path(PROGRESS).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://kap.org.tr',
    })
    return s

def discover_permalink(session, ticker):
    """Tek bir şirket için KAP permalink'ini keşfet."""
    try:
        # KAP'ın arama API'sini kullan
        search_url = f"https://kap.org.tr/tr/api/search?q={ticker}"
        resp = session.get(search_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Sonuçlarda company page link ara
            for item in data if isinstance(data, list) else []:
                url = item.get('url', item.get('link', ''))
                if '/sirket-bilgileri/' in url:
                    # URL'den permalink extract et
                    match = re.search(r'/sirket-bilgileri/\w+/(\d+-[a-z0-9-]+)', url)
                    if match:
                        return match.group(1)
        
        # Fallback: KAP'ın finansal sayfasından redirect kontrolü
        fin_url = f"https://kap.org.tr/tr/sirket-finansal-bilgileri/{ticker.lower()}"
        resp = session.get(fin_url, timeout=10, allow_redirects=True)
        if resp.url != fin_url:
            # Redirect oldu — URL'den permalink extract et
            match = re.search(r'/sirket-finansal-bilgileri/(\d+-[a-z0-9-]+)', resp.url)
            if match:
                return match.group(1)
        
        return None
    except Exception as e:
        return None

def build_mapping():
    """Tüm şirketler için permalink mapping oluştur."""
    db = sqlite3.connect(DB_PATH, timeout=5)
    c = db.cursor()
    
    # Companies tablosundaki tüm ticker'ları al
    companies = c.execute("""
        SELECT id, ticker, company_name, mkk_id 
        FROM companies 
        WHERE is_active = 1
        ORDER BY ticker
    """).fetchall()
    
    log(f"Toplam {len(companies)} şirket — permalink keşfi başlıyor...")
    
    state = load_progress()
    session = create_session()
    
    new_found = 0
    errors = 0
    
    for idx, (comp_id, ticker, name, mkk_id) in enumerate(companies):
        # Zaten işlendi mi?
        if str(comp_id) in state["done"]:
            continue
        
        # Permalink keşfet
        perma = discover_permalink(session, ticker)
        
        if perma:
            state["done"][str(comp_id)] = {
                "permaLink": perma,
                "ticker": ticker,
                "name": name
            }
            new_found += 1
        else:
            state["failed"][str(comp_id)] = ticker
        
        # Rate-limit koruması
        time.sleep(random.uniform(2.0, 4.0))
        
        # Her 50 istekte bir session yenile
        if (idx + 1) % 50 == 0:
            session.close()
            session = create_session()
            save_progress(state)
            log(f"  [{idx+1}/{len(companies)}] Yeni: {new_found}, Hata: {errors}, Toplam: {len(state['done'])}")
        
        # 429 kontrolü
        if errors > 10:
            log(f"  Çok hata — 60sn dinleniyor...")
            time.sleep(60)
            session.close()
            session = create_session()
            errors = 0
    
    session.close()
    save_progress(state)
    
    # JSON'a yaz
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(state["done"], f, ensure_ascii=False, indent=2)
    
    log(f"\n=== SONUÇ ===")
    log(f"Toplam: {len(companies)} şirket")
    log(f"Bulunan: {len(state['done'])} permalink")
    log(f"Bulunamayan: {len(state['failed'])}")
    log(f"Dosya: {OUTPUT}")
    
    db.close()

if __name__ == '__main__':
    build_mapping()
