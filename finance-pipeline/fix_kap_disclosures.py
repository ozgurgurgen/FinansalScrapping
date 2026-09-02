"""
THYAO icin KAP'tan bildirim, ortaklik, yonetim verisini cekip DB'ye yazar.
Ayni zamanda buyuk sirketler icin de aynisini yapar.
"""
import sys, io, time, random, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psycopg2
import requests

DB = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.kap.org.tr',
        'Referer': 'https://www.kap.org.tr/tr/bildirim-sorgulama',
    })
    return s

def fetch_disclosures(session, from_date='2020-01-01', to_date='2026-12-31'):
    """KAP'tan tum bildirimleri cek."""
    print(f'  Disclosure cekiliyor: {from_date} -> {to_date}')
    all_discs = []
    
    # KAP sayfa bazli cekim yapar, max 200 kayit/sayfa
    page = 1
    while True:
        try:
            r = session.post(
                'https://www.kap.org.tr/tr/api/disclosure/members/byCriteria',
                json={'fromDate': from_date, 'toDate': to_date},
                timeout=30
            )
            if r.status_code != 200:
                print(f'  KAP {r.status_code}')
                break
            data = r.json()
            if not data:
                break
            all_discs.extend(data)
            print(f'  Sayfa {page}: {len(data)} bildirim cekildi (toplam: {len(all_discs)})')
            if len(data) < 200:
                break
            page += 1
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f'  Hata: {e}')
            break
    
    return all_discs

def parse_ownership(summary):
    """Ownership parse."""
    holders = []
    # Pattern: "X A.Ş. - Y Pay Sahipleri Bildirimi (%Z.00 Pay Oranı)"
    m = re.search(r'(.+?)\s*[-–]\s*\d+\s*Pay\s*Sahibi.*?(\d+[\.,]?\d*)\s*%\s*Pay\s*Oran', summary, re.I)
    if m:
        holders.append((m.group(1).strip(), float(m.group(2).replace(',', '.'))))
    return holders

def parse_management(summary):
    """Management/YK parse."""
    members = []
    # Various patterns for board member disclosures
    if any(kw in summary.lower() for kw in ['yonetim kurulu', 'yönetim kurulu', 'başkan', 'genel müdür', 'genel mudur']):
        members.append(('Yönetim Kurulu', summary[:100]))
    return members

def save_to_db(db, company_id, ticker, disclosures):
    """Bildirimleri DB'ye kaydet."""
    c = db.cursor()
    saved = 0
    owners_saved = 0
    mgmt_saved = 0
    
    for disc in disclosures:
        stock = (disc.get('stockCodes', '') or '').strip().upper()
        summary = (disc.get('summary', '') or '').strip()
        disc_date = disc.get('publishDate', '') or disc.get('date', '')
        disc_id = str(disc.get('disclosureIndex', ''))
        disc_class = disc.get('disclosureClass', '') or ''
        
        if not stock or ticker not in stock:
            continue
        
        # Disclosure kaydet
        c.execute("""INSERT INTO kap_disclosures (company_id, disclosure_id, symbol, title, category, 
                    disclosure_type, publish_date, source_url, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING""", 
                    (company_id, disc_id, ticker, summary[:500], disc_class, disc_class, disc_date,
                     f'https://www.kap.org.tr/tr/Bildirim/{disc_id}'))
        saved += 1
        
        # Ownership parse
        holders = parse_ownership(summary)
        for h_name, h_ratio in holders:
            c.execute("""INSERT INTO kap_shareholders (company_id, holder_name, share_ratio_percent, 
                        holder_type, created_at) VALUES (%s, %s, %s, 'Bireysel', NOW()) 
                        ON CONFLICT DO NOTHING""", (company_id, h_name, h_ratio))
            owners_saved += 1
    
    db.commit()
    return saved, owners_saved, mgmt_saved

def fetch_company_page(session, ticker):
    """KAP sirket sayfasindan ortaklik ve yonetim bilgisi cek."""
    # Try to get shareholders from company info API
    try:
        r = session.post(
            'https://www.kap.org.tr/tr/api/company-shareholder/byCriteria',
            json={'stockCode': ticker},
            timeout=20
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return data
    except:
        pass
    return []

# ========== ANA CALISMA ==========
if __name__ == '__main__':
    db = psycopg2.connect(DB)
    c = db.cursor()
    
    session = create_session()
    
    # Buyuk sirketleri hedefle
    c.execute("""
        SELECT c.id, c.ticker, c.company_name FROM kap_companies c
        LEFT JOIN kap_disclosures d ON d.company_id = c.id
        WHERE c.ticker IN ('THYAO','GARAN','ASELS','BIMAS','AKBNK','EREGL','SAHOL',
            'TUPRS','KCHOL','SISE','FROTO','HEKTS','TCELL','TTKOM','VAKBN','YKBNK',
            'HALKB','ISCTR','TOASO','TAVHL','VESTL','KONTR','ODAS','ENKAI','KRDMD',
            'SASA','KERVT','DEVA','MPARK','AYDEM','BRYAT','EKGYO','ISMEN','ICBCT',
            'AKFGY','ISGYO','NTHOL','DOHOL','BERA','EGEEN','GWIND','REEDR','TKFEN',
            'ALARK','AYEN','AYES','BIMAS','BTCIM','CANTE','CIMSA','DIRIT','DYOBY',
            'EGEPO','EGGUB','EGPRO','EKOS','EMNIS','ENJSA','ENKAI','ERBOS','EREGL',
            'FENER','FONET','FORMT','FRIGO','GESAN','GOLTS','GUBRF','GZNMI','HALKB',
            'HLGYO','IEYHO','IHAAS','IHEVA','IHGZT','ISMEN','IZENR','IZFAS','IZINV',
            'IZMDC','IZYMO','IZYPO','JANTS','KAREL','KARSN','KATMR','KCAER','KCHOL',
            'KENT','Kervana','KFEIN','KLSER','KLGYO','KLNMA','KLSER','KMPUR','KONTR',
            'KONCY','KONYA','KOPOL','KORDS','KRGYO','KRONT','KRPLS','KRSTL','KRTEK',
            'KRMDO','KRVMD','KSTUR','KUVVA','KUYAS','KZBGY','KZGYO','LIDER','LKMNH',
            'MAGEN','MAKIM','MAKTK','MARBL','MARTI','MARTI','MEDTR','MEGAP','MEGIR',
            'MERKO','MERIT','MERYS','META','METUR','MGROS','MIPAZ','MPARK','MTRYO',
            'MZHOL','NATEN','NETAS','NIBAS','NTGAZ','NTHOL','NUHCM','ODAS','ODGP',
            'ONCSM','ORCAY','ORGE','ORMA','OSMEN','OSTIM','OTKAR','OTTO','OYAYO',
            'OYLUM','OYYAT','OZGYO','OZRDN','OZSUB','OZYSU','PAGYO','PAMEL','PAPIL',
            'PARSN','PASEU','PCILT','PDTC','PETKM','PETUN','PGSUS','PIIMN','PKART',
            'PLTUR','PNLSN','PNLSN','PNSUT','POLHO','POLTK','PRDGS','PRKME','PRKAB',
            'PSGYO','QNBFB','QNBFL','RALYH','RASHY','REEDR','RGYAS','RODRG','ROYAL',
            'RYGYO','RYSAS','SAFKR','SAHOL','SAMAT','SANFM','SANKO','SARKY',' SASA',
            'SDTTR','SEGYO','SEKFK','SEKUR','SELEC','SELGD','SELVA','SEYKM','SILVR',
            'SISE','SKBNK','SKYLP','SMART','SNGYO','SNICA','SNKRN','SNYHM','SOKE',
            'SRVGY','SUMAS','SUNTK','SUWEN','TABGD','TATGD','TAVHL','TCELL','TEKTU',
            'TERA','TEZOL','TGSAS','THYAO','TKFEN','TKNSA','TLMAN','TMSN','TNZTP',
            'TOKTİ','TOMTR','TORUM','TOASO','TRCAS','TRGYO','TRILC','TRCAS','TRGYO',
            'TSGYO','TSKB','TTKOM','TTK芙','TTRAK','TUCLK','TUKAS','TUREX','TURSG',
            'UFUK','ULKER','ULUFA','ULUFA','ULUJR','ULUSE','ULUUN','UMPAS','UNLU',
            'USAK','UZERB','UZERB','VAKBN','VAKFN','VAKKO','VBTYZ','VERUS','VESTL',
            'VESTY','VKFNC','VKGYO','VKING','VKFNÇ','VNMED','VRGYO','YAPRK','YATAS',
            'YEOTK','YESIL','YGGYO','YGYO','YKBNK','YKSLN','YONGA','YUNSA','YYAPI',
            'YYLGD','YYLGN','ZEDUR','ZEYAB','ZOREN','ZRGYO')
        GROUP BY c.id, c.ticker, c.company_name
        HAVING COUNT(d.id) = 0
        LIMIT 100
    """)
    no_disc = c.fetchall()
    print(f'\nBildirimi olmayan {len(no_disc)} sirket icin KAP API cekiliyor...')
    
    total_disc = 0
    for i, (cid, ticker, name) in enumerate(no_disc):
        print(f'\n[{i+1}/{len(no_disc)}] {ticker} ({name})')
        
        # Disclosure cek
        discs = fetch_disclosures(session, from_date='2020-01-01', to_date='2026-12-31')
        saved, owners, mgmt = save_to_db(db, cid, ticker, discs)
        total_disc += saved
        print(f'  -> {saved} bildirim, {owners} ortaklik')
        
        time.sleep(random.uniform(3, 5))
    
    # Final stats
    c.execute("SELECT COUNT(*) FROM kap_disclosures")
    print(f'\n=== TOPLAM DISCLOSURE: {c.fetchone()[0]} ===')
    
    c.execute("SELECT COUNT(*) FROM kap_shareholders")
    print(f'TOPLAM SHAREHOLDER: {c.fetchone()[0]}')
    
    # THYAO check
    c.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    tid = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM kap_disclosures WHERE company_id=%s", (tid,))
    print(f'THYAO disclosures: {c.fetchone()[0]}')
    c.execute("SELECT COUNT(*) FROM kap_shareholders WHERE company_id=%s", (tid,))
    print(f'THYAO shareholders: {c.fetchone()[0]}')
    
    db.close()
    print('\nTAMAMLANDI!')
