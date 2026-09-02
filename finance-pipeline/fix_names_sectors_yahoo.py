#!/usr/bin/env python3
"""
Fix company names and sectors using Yahoo Finance API.
All tickers in bist_stock_prices will get real names and sector info.
Anti-ban: random UA, jitter, cooldown.
"""
import sys, io, os, time, random, re, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
]

SECTOR_MAP = {
    'Financial Services': 'Bankacilik',
    'Insurance': 'Sigorta',
    'Technology': 'Teknoloji',
    'Industrials': 'Imalat',
    'Consumer Cyclical': 'Perakende',
    'Consumer Defensive': 'Gida',
    'Healthcare': 'Saglik',
    'Energy': 'Enerji',
    'Basic Materials': 'Maden',
    'Communication Services': 'Iletisim',
    'Real Estate': 'Gayrimenkul',
    'Utilities': 'Altyapi',
}

def fetch_yahoo_profile(ticker, session):
    """Fetch company profile from Yahoo Finance quoteSummary API."""
    yf_ticker = f'{ticker}.IS'
    url = f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{yf_ticker}?modules=assetProfile,summaryDetail,price'
    try:
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            result = data.get('quoteSummary', {}).get('result', [{}])[0]
            
            name = None
            sector = None
            industry = None
            
            # From price module
            price_data = result.get('price', {})
            if price_data:
                name = price_data.get('shortName') or price_data.get('longName')
            
            # From assetProfile
            profile = result.get('assetProfile', {})
            if profile:
                sector = profile.get('sector')
                industry = profile.get('industry')
            
            return {
                'name': name,
                'sector': sector,
                'industry': industry,
            }
        elif r.status_code == 429:
            print(f'    [429] Rate limit - waiting 30s...')
            time.sleep(30)
            return None
    except Exception as e:
        pass
    return None

def fix_company_names_and_sectors(db):
    """Fix all company names and sectors using Yahoo Finance."""
    import requests
    
    c = db.cursor()
    
    # Get all tickers from bist_stock_prices (602 tickers we know exist)
    c.execute('SELECT ticker, company_name FROM bist_stock_prices')
    all_tickers = c.fetchall()
    print(f'[YAHOO] {len(all_tickers)} ticker isleniyor')
    
    session = requests.Session()
    
    updated_names = 0
    updated_sectors = 0
    errors = 0
    
    for i, (ticker, current_name) in enumerate(all_tickers):
        if i % 30 == 0:
            print(f'  [{i}/{len(all_tickers)}] isim={updated_names}, sektor={updated_sectors}, hata={errors}')
            time.sleep(random.uniform(5, 10))  # Cooldown
        
        profile = fetch_yahoo_profile(ticker, session)
        
        if profile:
            if profile['name']:
                # Update companies table
                c.execute('''UPDATE companies SET company_name = ? 
                            WHERE ticker = ? AND (company_name IS NULL OR company_name = '' 
                            OR LENGTH(company_name) <= 3 OR company_name IN ('-','ISTANBUL','ANKARA','IZMIR','BURSA','KOCAELI','ANTALYA','ADANA'))''',
                         (profile['name'], ticker))
                # Also update bist_stock_prices
                c.execute('UPDATE bist_stock_prices SET company_name = ? WHERE ticker = ?',
                         (profile['name'], ticker))
                updated_names += 1
            
            if profile['sector']:
                sector = SECTOR_MAP.get(profile['sector'], profile['sector'])
                c.execute('''UPDATE companies SET sector = ? 
                            WHERE ticker = ? AND (sector IS NULL OR sector = '')''',
                         (sector, ticker))
                updated_sectors += 1
            
            # Store industry as extra info
            if profile['industry']:
                c.execute('''UPDATE companies SET sector = ? 
                            WHERE ticker = ? AND (sector IS NULL OR sector = '')''',
                         (profile['industry'], ticker))
                if c.rowcount > 0:
                    updated_sectors += 1
        else:
            errors += 1
        
        # Rotate UA every 10 requests
        if i % 10 == 0:
            session.headers['User-Agent'] = random.choice(UA_LIST)
        
        time.sleep(random.uniform(1.0, 2.5))
    
    db.commit()
    print(f'\n[YAHOO] Tamamlandi: {updated_names} isim, {updated_sectors} sektor guncellendi, {errors} hata')
    
    # Final count
    c.execute('SELECT COUNT(*) FROM companies WHERE company_name IS NOT NULL AND LENGTH(company_name) > 3')
    named = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != ""')
    sectored = c.fetchone()[0]
    print(f'[YAHOO] Final: {named}/759 isimli, {sectored}/759 sektorlu')
    
    return updated_names, updated_sectors

def main():
    db = sqlite3.connect(DB_PATH)
    
    print('='*60)
    print('YAHOO FINANCE ILE ISIM + SEKTOR DUZELTME')
    print('='*60)
    
    fix_company_names_and_sectors(db)
    
    db.close()

if __name__ == '__main__':
    main()
