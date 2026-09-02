"""
KAPSAMLI KAP SCRAPER
Tüm eksik verileri KAP'tan çeker:
1. Bildirimler (Disclosure API - batch)
2. Ortaklar (Playwright ile şirket sayfasından)
3. Yönetim Kurulu (Playwright ile)
4. Bağlı Ortaklıklar (Playwright ile)
5. Nakit Akış Detayları (Playwright ile)

Anti-bot: Random delay, UA rotation, batch cooldown
"""
import psycopg2
import requests
import time
import random
import sys
import io
import json
import re
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
]

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://kap.org.tr',
        'Origin': 'https://kap.org.tr'
    })
    return s

def safe_delay(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))


def parse_kap_date(date_str):
    """KAP tarih formatini ISO formatina cevir"""
    if not date_str:
        return None
    try:
        # Try DD.MM.YYYY HH:MM:SS
        if '.' in str(date_str) and len(str(date_str)) > 10:
            dt = datetime.strptime(str(date_str), '%d.%m.%Y %H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        # Try DD.MM.YYYY
        elif '.' in str(date_str):
            dt = datetime.strptime(str(date_str), '%d.%m.%Y')
            return dt.strftime('%Y-%m-%d')
        # Already ISO
        return str(date_str)[:19]
    except:
        return str(date_str)[:10]


def scrape_disclosures(session, conn, batch_days=90):
    """Batch disclosure API ile bildirimleri çek"""
    c = conn.cursor()
    
    print("\n[1] BILDIRIMLER (Disclosure API)...")
    
    # Son X gün için bildirimleri çek
    to_date = datetime.now().strftime('%Y-%m-%d')
    from_date = (datetime.now() - timedelta(days=batch_days)).strftime('%Y-%m-%d')
    
    all_disclosures = []
    
    # 6 ayar parçaya böl (rate-limit için)
    for i in range(6):
        chunk_from = (datetime.now() - timedelta(days=batch_days - i*15)).strftime('%Y-%m-%d')
        chunk_to = (datetime.now() - timedelta(days=batch_days - (i+1)*15)).strftime('%Y-%m-%d') if i < 5 else to_date
        
        try:
            r = session.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
                json={'fromDate': chunk_from, 'toDate': chunk_to},
                timeout=30)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    all_disclosures.extend(data)
                    print(f"  Chunk {i+1}/6: {len(data)} bildirim ({chunk_from} ~ {chunk_to})")
            else:
                print(f"  Chunk {i+1}/6: HTTP {r.status_code}")
        except Exception as e:
            print(f"  Chunk {i+1}/6 HATA: {e}")
        
        safe_delay(3, 6)
    
    print(f"  Toplam: {len(all_disclosures)} bildirim çekildi")
    
    # Company ticker -> id mapping
    c.execute("SELECT ticker, id FROM kap_companies")
    ticker_map = {r[0].upper(): r[1] for r in c.fetchall()}
    
    # Disclosures kaydet
    saved = 0
    for disc in all_disclosures:
        stocks = (disc.get('relatedStocks', '') or '').upper()
        if not stocks:
            continue
        
        # Her hisse için ayrı kayıt
        for ticker in stocks.split(','):
            ticker = ticker.strip()
            if ticker in ticker_map:
                company_id = ticker_map[ticker]
                title = disc.get('kapTitle', '') or disc.get('summary', '')
                pub_date = disc.get('publishDate', '')
                disc_class = disc.get('disclosureClass', '')
                disc_type = disc.get('disclosureType', '')
                
                # Duplicate kontrol - title benzerligi ile
                safe_pub_date = parse_kap_date(pub_date)
                c.execute("""SELECT 1 FROM kap_disclosures 
                    WHERE company_id=%s AND title=%s""",
                    (company_id, title))
                if not c.fetchone():
                    c.execute("""INSERT INTO kap_disclosures 
                        (company_id, symbol, title, category, publish_date)
                        VALUES (%s, %s, %s, %s, %s)""",
                        (company_id, ticker, title, disc_class or disc_type, safe_pub_date))
                    saved += 1
    
    conn.commit()
    print(f"  Yeni bildirim: {saved} kaydedildi")
    return saved


def scrape_company_kap_page(session, conn, ticker, company_id):
    """Playwright yerine requests ile KAP şirket sayfasını çek (hızlı)"""
    c = conn.cursor()
    
    try:
        url = f'https://kap.org.tr/tr/sirket-bilgileri/ozet/{ticker}'
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return {}
        
        html = r.text
        result = {}
        
        # Parse shareholder from HTML
        # Shareholder pattern: <table> içinde "Pay Sahipleri" başlığı
        # KAP Next.js site'sinde JSON data embedded olabilir
        
        # Try to find __NEXT_DATA__ JSON
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if next_data_match:
            try:
                nd = json.loads(next_data_match.group(1))
                props = nd.get('props', {}).get('pageProps', {})
                
                # Shareholders
                shareholders = props.get('shareholders', props.get('ortaklar', []))
                if shareholders:
                    for sh in shareholders:
                        name = sh.get('name', sh.get('ortakAdi', ''))
                        ratio = sh.get('ratio', sh.get('payOrani', 0))
                        voting = sh.get('votingPower', sh.get('oyOrani', 0))
                        if name:
                            c.execute("""INSERT INTO kap_shareholders 
                                (company_id, holder_name, share_ratio_percent, voting_power_percent)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT DO NOTHING""",
                                (company_id, name, float(ratio) if ratio else 0, float(voting) if voting else 0))
                            result['shareholders'] = result.get('shareholders', 0) + 1
                
                # Management
                management = props.get('boardMembers', props.get('yonetimKurulu', []))
                if management:
                    for mg in management:
                        name = mg.get('name', mg.get('adSoyad', ''))
                        title = mg.get('title', mg.get('unvan', ''))
                        if name:
                            c.execute("""INSERT INTO kap_management 
                                (company_id, name, title)
                                VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING""",
                                (company_id, name, title))
                            result['management'] = result.get('management', 0) + 1
                
                # Subsidiaries
                subsidiaries = props.get('subsidiaries', props.get('bagliOrtakliklar', []))
                if subsidiaries:
                    for sub in subsidiaries:
                        name = sub.get('name', sub.get('ortaklikAdi', ''))
                        share = sub.get('sharePercent', sub.get('payOrani', 0))
                        if name:
                            c.execute("""INSERT INTO kap_subsidiaries 
                                (company_id, subsidiary_name, share_percent)
                                VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING""",
                                (company_id, name, float(share) if share else 0))
                            result['subsidiaries'] = result.get('subsidiaries', 0) + 1
                            
            except json.JSONDecodeError:
                pass
        
        # Fallback: HTML parsing for shareholder table
        if not result.get('shareholders'):
            # Look for shareholder data in table rows
            sh_pattern = re.findall(r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>([\d,\.]+)\s*%</td>', html, re.S)
            if sh_pattern:
                for name, ratio in sh_pattern[:20]:  # Max 20 shareholders
                    name = re.sub(r'<[^>]+>', '', name).strip()
                    ratio_val = float(ratio.replace(',', '.'))
                    if name and len(name) > 2:
                        c.execute("""INSERT INTO kap_shareholders 
                            (company_id, holder_name, share_ratio_percent)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING""",
                            (company_id, name, ratio_val))
                        result['shareholders'] = result.get('shareholders', 0) + 1
        
        conn.commit()
        return result
        
    except Exception as e:
        return {'error': str(e)}


def scrape_kap_financial_page(session, conn, ticker, company_id):
    """KAP'tan finansal tablo sayfasını çek - cashflow detayları için"""
    c = conn.cursor()
    
    try:
        # KAP financial info page
        url = f'https://kap.org.tr/tr/sirket-finansal-bilgileri/{ticker}'
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return {}
        
        html = r.text
        result = {}
        
        # __NEXT_DATA__ JSON parse
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if next_data_match:
            nd = json.loads(next_data_match.group(1))
            props = nd.get('props', {}).get('pageProps', {})
            
            # Cashflow data
            cashflows = props.get('cashFlow', props.get('cashflow', []))
            if cashflows:
                for cf in cashflows:
                    year = cf.get('year', cf.get('yil'))
                    period = cf.get('period', cf.get('donem'))
                    if year and period:
                        c.execute("""UPDATE kap_cashflows 
                            SET depreciation=%s, capex=%s, 
                                investing_cash_flow=%s, financing_cash_flow=%s
                            WHERE company_id=%s AND year=%s AND period=%s""",
                            (cf.get('depreciation'), cf.get('capex'),
                             cf.get('investingCashFlow', cf.get('yatirimFaaliyetleri')),
                             cf.get('financingCashFlow', cf.get('finansmanFaaliyetleri')),
                             company_id, str(year), str(period)))
                        result['cashflows'] = result.get('cashflows', 0) + 1
            
            # Financial details
            financials = props.get('financials', props.get('finansalTablolar', []))
            if financials:
                for fin in financials:
                    year = fin.get('year', fin.get('yil'))
                    period = fin.get('period', fin.get('donem'))
                    if year and period:
                        c.execute("""UPDATE kap_financials 
                            SET current_assets=%s, cash_and_equivalents=%s, 
                                financial_debt=%s, total_debt=%s
                            WHERE company_id=%s AND year=%s AND period=%s
                            AND (current_assets IS NULL)""",
                            (fin.get('currentAssets', fin.get('donenVarliklar')),
                             fin.get('cashAndEquivalents', fin.get('nakitVeNakitBenzerleri')),
                             fin.get('financialDebt', fin.get('finansalBorclar')),
                             fin.get('totalDebt', fin.get('toplamBorc')),
                             company_id, str(year), str(period)))
                        result['financials'] = result.get('financials', 0) + 1
        
        conn.commit()
        return result
        
    except Exception as e:
        return {'error': str(e)}


def main():
    conn = psycopg2.connect(DB_URL)
    c = conn.cursor()
    
    print("=" * 60)
    print("KAPSAMLI KAP SCRAPER")
    print("=" * 60)
    
    # Get all companies
    c.execute("SELECT id, ticker FROM kap_companies ORDER BY id")
    companies = c.fetchall()
    print(f"Toplam {len(companies)} şirket")
    
    # 1. Disclosure batch scrape
    session = create_session()
    scrape_disclosures(session, conn, batch_days=180)
    
    safe_delay(5, 8)
    
    # 2. Company pages scrape (shareholder, management, subsidiaries)
    print(f"\n[2] SIRKET SAYFALARI (toplam {len(companies)} sirket)...")
    
    success = 0
    failed = 0
    
    for idx, (company_id, ticker) in enumerate(companies):
        # Her 20 şirkette session yenile
        if idx % 20 == 0:
            session = create_session()
            if idx > 0:
                print(f"  [Cooldown] 30sn bekleniyor...")
                time.sleep(30)
        
        # Company page
        result = scrape_company_kap_page(session, conn, ticker, company_id)
        
        if 'error' not in result:
            success += 1
            items = sum(v for k, v in result.items() if isinstance(v, int) and k != 'error')
            if items > 0:
                print(f"  [{idx+1}/{len(companies)}] {ticker}: {result}")
        else:
            failed += 1
            if idx < 5:
                print(f"  [{idx+1}/{len(companies)}] {ticker}: HATA - {result['error'][:50]}")
        
        safe_delay(2, 4)
    
    print(f"\n  Sirket sayfasi: {success} basarili, {failed} basarisiz")
    
    # 3. Financial page scrape
    print(f"\n[3] FINANSAL SAYFALAR...")
    session = create_session()
    
    fin_success = 0
    for idx, (company_id, ticker) in enumerate(companies[:100]):  # First 100
        if idx % 20 == 0:
            session = create_session()
            if idx > 0:
                time.sleep(30)
        
        result = scrape_kap_financial_page(session, conn, ticker, company_id)
        if 'error' not in result:
            fin_success += 1
            items = sum(v for k, v in result.items() if isinstance(v, int) and k != 'error')
            if items > 0:
                print(f"  [{idx+1}] {ticker}: {result}")
        
        safe_delay(2, 4)
    
    print(f"  Finansal sayfa: {fin_success} basarili")
    
    # Final stats
    print("\n" + "=" * 60)
    print("FINAL DURUM")
    print("=" * 60)
    
    for tbl, col in [('kap_disclosures','company_id'), ('kap_shareholders','company_id'), 
                      ('kap_management','company_id'), ('kap_subsidiaries','company_id')]:
        c.execute(f"SELECT COUNT(*) FROM {tbl}")
        total = c.fetchone()[0]
        c.execute(f"SELECT COUNT(DISTINCT {col}) FROM {tbl} WHERE {col} IS NOT NULL")
        companies_with = c.fetchone()[0]
        print(f"  {tbl}: {total} kayit, {companies_with} sirket")
    
    conn.close()
    print("\nTAMAMLANDI!")


if __name__ == '__main__':
    main()
