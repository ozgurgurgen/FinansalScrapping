"""
Scrape historical BIST stock prices from Yahoo Finance (last 1 year, daily).
Anti-ban: random delays, rotating user agents, batch processing with cooldown.
"""
import sqlite3
import requests
import time
import random
import sys
import io
from datetime import datetime, timedelta
from fake_useragent import UserAgent

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

def p(msg):
    print(msg, flush=True)

DB_PATH = 'finance.db'

def create_session():
    ua = UserAgent()
    s = requests.Session()
    s.headers.update({
        'User-Agent': ua.random,
        'Accept': 'application/json',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    })
    return s

def fetch_history(session, ticker, days=365):
    """Fetch daily OHLCV from Yahoo Finance for a BIST stock."""
    symbol = f'{ticker}.IS'
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=days)).timestamp())
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d'
    
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            result = data.get('chart', {}).get('result', [])
            if not result:
                return []
            
            ts = result[0].get('timestamp', [])
            quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
            
            records = []
            for i, t in enumerate(ts):
                close = quotes['close'][i]
                if close is None:
                    continue
                records.append((
                    ticker,
                    datetime.fromtimestamp(t).strftime('%Y-%m-%d'),
                    quotes['open'][i],
                    quotes['high'][i],
                    quotes['low'][i],
                    close,
                    quotes['volume'][i],
                    close
                ))
            return records
        elif r.status_code == 429:
            p(f'  [429] Rate limited on {ticker}, waiting 30s...')
            time.sleep(30)
            return []
        else:
            return []
    except Exception as e:
        p(f'  Error on {ticker}: {e}')
        return []

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Get all tickers that need price history
    c.execute('SELECT ticker FROM bist_stock_prices ORDER BY ticker')
    all_tickers = [r[0] for r in c.fetchall()]
    total = len(all_tickers)
    p(f'Total tickers: {total}')
    
    # Check which already have recent data
    c.execute('''SELECT ticker FROM bist_price_history 
                 WHERE trade_date >= date('now', '-7 days') 
                 GROUP BY ticker HAVING COUNT(*) > 10''')
    have_recent = set(r[0] for r in c.fetchall())
    
    tickers_to_fetch = [t for t in all_tickers if t not in have_recent]
    p(f'Need to fetch: {len(tickers_to_fetch)} tickers (already have: {len(have_recent)})')
    
    if not tickers_to_fetch:
        p('All tickers already have recent data!')
        db.close()
        return
    
    session = create_session()
    batch_size = 3
    total_inserted = 0
    
    for i, ticker in enumerate(tickers_to_fetch):
        if i % batch_size == 0 and i > 0:
            # Rotate session every batch
            session = create_session()
            # Anti-ban: longer cooldown every 30 tickers
            if i % 30 == 0:
                cooldown = random.uniform(60, 120)
                p(f'  [COOLDOWN] {i}/{len(tickers_to_fetch)} done. Sleeping {cooldown:.0f}s...')
                time.sleep(cooldown)
            else:
                time.sleep(random.uniform(2, 4))
        
        records = fetch_history(session, ticker)
        
        if records:
            c.executemany('''INSERT OR IGNORE INTO bist_price_history 
                (ticker, trade_date, open, high, low, close, volume, adj_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', records)
            db.commit()
            total_inserted += len(records)
            p(f'  [{i+1}/{len(tickers_to_fetch)}] {ticker}: {len(records)} days ({records[0][1]} to {records[-1][1]})')
        else:
            p(f'  [{i+1}/{len(tickers_to_fetch)}] {ticker}: no data')
        
        # Random jitter between requests
        time.sleep(random.uniform(0.5, 1.5))
    
    # Final stats
    c.execute('SELECT COUNT(DISTINCT ticker), COUNT(*) FROM bist_price_history')
    stats = c.fetchone()
    p(f'\nDone! Total: {stats[0]} tickers, {stats[1]} records')
    db.close()

if __name__ == '__main__':
    main()
