#!/usr/bin/env python3
"""Fix ALL company names and sectors using yfinance. Anti-ban: jitter, cooldown."""
import sys, io, os, time, random, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

import yfinance as yf

SECTOR_MAP = {
    'Financial Services': 'Bankacilik',
    'Insurance': 'Sigorta',
    'Technology': 'Teknoloji',
    'Industrials': 'Imalat',
    'Consumer Cyclical': 'Perakende/Tuketim',
    'Consumer Defensive': 'Gida/Tuketim',
    'Healthcare': 'Saglik',
    'Energy': 'Enerji',
    'Basic Materials': 'Maden/Malzeme',
    'Communication Services': 'Iletisim',
    'Real Estate': 'Gayrimenkul',
    'Utilities': 'Altyapi',
}

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    # Get all tickers
    c.execute('SELECT ticker, company_name FROM bist_stock_prices')
    all_tickers = c.fetchall()
    total = len(all_tickers)
    print(f'[YAHOO] {total} ticker isleniyor...')

    updated_names = 0
    updated_sectors = 0
    errors = 0

    for i, (ticker, current_name) in enumerate(all_tickers):
        if i % 25 == 0 and i > 0:
            print(f'  [{i}/{total}] isim={updated_names} sektor={updated_sectors} hata={errors}')
            db.commit()
            time.sleep(random.uniform(8, 15))  # Cooldown

        try:
            t = yf.Ticker(f'{ticker}.IS')
            info = t.info or {}

            name = info.get('shortName') or info.get('longName')
            sector_raw = info.get('sector', '')
            industry = info.get('industry', '')
            sector = SECTOR_MAP.get(sector_raw, sector_raw)

            if name and len(name) > 2:
                c.execute('''UPDATE companies SET company_name = ? WHERE ticker = ?''', (name, ticker))
                c.execute('''UPDATE bist_stock_prices SET company_name = ? WHERE ticker = ?''', (name, ticker))
                updated_names += 1

            if sector and sector != '?':
                c.execute('''UPDATE companies SET sector = ? WHERE ticker = ? AND (sector IS NULL OR sector = '')''', (sector, ticker))
                updated_sectors += 1
            elif industry and industry != '?':
                c.execute('''UPDATE companies SET sector = ? WHERE ticker = ? AND (sector IS NULL OR sector = '')''', (industry, ticker))
                if c.rowcount > 0:
                    updated_sectors += 1

        except Exception as e:
            errors += 1
            if '429' in str(e) or 'Too Many' in str(e):
                print(f'  [429] Rate limit - 30sn bekleme')
                time.sleep(30)

        time.sleep(random.uniform(0.8, 2.0))

    db.commit()

    print(f'\n[YAHOO] TAMAM: {updated_names} isim, {updated_sectors} sektor, {errors} hata')

    # Final stats
    c.execute('SELECT COUNT(*) FROM companies WHERE company_name IS NOT NULL AND LENGTH(company_name) > 3')
    named = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != ""')
    sectored = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM companies')
    total_co = c.fetchone()[0]
    print(f'[FINAL] {named}/{total_co} isimli, {sectored}/{total_co} sektorlu')

    # Show sector distribution
    c.execute('SELECT sector, COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != "" GROUP BY sector ORDER BY COUNT(*) DESC')
    print('\nSECTOR DAGILIMI:')
    for row in c.fetchall():
        print(f'  {row[0]}: {row[1]}')

    db.close()

if __name__ == '__main__':
    main()
