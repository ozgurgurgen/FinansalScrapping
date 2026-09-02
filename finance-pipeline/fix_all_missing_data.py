#!/usr/bin/env python3
"""Fix ALL missing data: sector mapping, company names, shareholders, management, etc."""
import sys, io, os, time, random, re, json, sqlite3, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

def tr_lower(s):
    if not s: return ''
    reps = {'I': 'ı', 'İ': 'i', 'Ş': 's', 'ş': 's', 'Ç': 'c', 'ç': 'c',
            'Ğ': 'g', 'ğ': 'g', 'Ü': 'u', 'ü': 'u', 'Ö': 'o', 'ö': 'o'}
    r = s
    for k, v in reps.items():
        r = r.replace(k, v)
    return r.lower()

# ══════════════════════════════════════════════════════════════════
# 1. SECTOR MAPPING BY KEYWORD
# ══════════════════════════════════════════════════════════════════
SECTOR_KEYWORDS = [
    ('Bankacılık', ['bank']),
    ('Sigorta', ['sigorta']),
    ('Holding', ['holding']),
    ('Enerji', ['enerji', 'elektrik', 'jeotermal', 'ruzgar', 'gunes', 'gjfneş', 'hidro', 'jes']),
    ('Petrol/Gaz', ['petrol', 'dogalgaz', 'doğalgaz', 'petro']),
    ('GYO', ['gyo']),
    ('Gayrimenkul', ['gayrimenkul', 'inşaat', 'insaat', 'yapi', 'yapı', 'konut', 'yapi ve ticaret']),
    ('Turizm/Otel', ['turizm', 'otel', 'tour', 'tatil', 'resort']),
    ('Teknoloji', ['teknoloji', 'yazilim', 'yazılım', 'bilisim', 'bilişim', 'dijital']),
    ('İmalat', ['imalat', 'üretim', 'uretim', 'fabrika', 'sanayi']),
    ('Otomotiv', ['otomotiv', 'oto ']),
    ('Tekstil', ['tekstil', 'giyim', 'deri', 'konfeksiyon']),
    ('Gıda', ['gıda', 'gida', 'yem', 'sut', 'süt', 'cay', 'çay', 'seker', 'şeker']),
    ('Tarım', ['tarim', 'tarım', 'tarım-']),
    ('Maden', ['maden', 'celik', 'çelik', 'metal', 'aluminyum', 'alüminyum']),
    ('Çimento/Cam', ['çimento', 'cimento', 'cam', 'beton']),
    ('Kağıt', ['kagit', 'kağıt', 'ambalaj']),
    ('Kimya', ['kimya', 'ilac', 'ilaç', 'pharma']),
    ('Perakende', ['perakende', 'magaza', 'mağaza', 'market']),
    ('Ulaşım', ['ulasim', 'ulaşım', 'tasima', 'taşıma', 'havacilik', 'havacılık', 'denizcilik']),
    ('Lojistik', ['lojistik', 'nakliye', 'depolama']),
    ('Savunma', ['savunma', 'defense', 'aselsan']),
    ('Mücevher', ['mucevher', 'mücevher', 'altin', 'altın', 'kuyum']),
    ('Medya', ['medya', 'yayin', 'yayın', 'tv', 'gazete']),
    ('Spor', ['spor', 'futbol', 'basket']),
    ('İletişim', ['iletisim', 'iletişim', 'telekom']),
    ('Menkul', ['menkul', 'kıymet']),
    ('Demir Yolu', ['demiryolu', 'raylı']),
    ('Ormancılık', ['orman', 'kereste', 'ahsap']),
]

def assign_sectors(db):
    """Keyword-based sector assignment for companies."""
    c = db.cursor()
    c.execute('''SELECT id, ticker, company_name FROM companies 
                 WHERE (sector IS NULL OR sector = '') 
                 AND company_name IS NOT NULL AND company_name != '' ''')
    companies = c.fetchall()
    print(f'[SECTOR] {len(companies)} sirketin sectoru eksik')
    
    assigned = 0
    for cid, ticker, name in companies:
        nl = tr_lower(name or '')
        for sector, keywords in SECTOR_KEYWORDS:
            for kw in keywords:
                if kw.lower() in nl:
                    c.execute('UPDATE companies SET sector = ? WHERE id = ?', (sector, cid))
                    assigned += 1
                    break
            else:
                continue
            break
    
    db.commit()
    print(f'[SECTOR] {assigned} sirkete sector atandi')
    
    # Final stats
    c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != ""')
    total = c.fetchone()[0]
    c.execute('SELECT sector, COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != "" GROUP BY sector ORDER BY COUNT(*) DESC')
    print(f'[SECTOR] Toplam: {total}/759 dolu')
    for row in c.fetchall():
        print(f'  {row[0]}: {row[1]}')
    
    return assigned

# ══════════════════════════════════════════════════════════════════
# 2. KAP SHAREHOLDERS via RSC Page Parsing
# ══════════════════════════════════════════════════════════════════
def scrape_kap_shareholders(db):
    """Scrape shareholders from KAP company pages using RSC parsing."""
    import requests
    
    c = db.cursor()
    # Get top 50 companies by disclosure count (most important ones)
    c.execute('''
        SELECT c.id, c.ticker, c.company_name FROM companies c
        WHERE (SELECT COUNT(*) FROM disclosures d WHERE d.symbol = c.ticker) > 3
        AND NOT EXISTS (SELECT 1 FROM shareholders s WHERE s.company_id = c.id)
        ORDER BY (SELECT COUNT(*) FROM disclosures d WHERE d.symbol = c.ticker) DESC
        LIMIT 50
    ''')
    companies = c.fetchall()
    print(f'\n[SHAREHOLDERS] {len(companies)} sirket icin cekilecek')
    
    ua_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    ]
    
    count = 0
    for i, (cid, ticker, name) in enumerate(companies):
        if i % 10 == 0:
            print(f'  [{i}/{len(companies)}] Ortak: {count}...')
            time.sleep(random.uniform(3, 6))
        
        try:
            s = requests.Session()
            s.headers.update({
                'User-Agent': random.choice(ua_list),
                'Accept': 'text/html,application/xhtml+xml',
                'Referer': 'https://kap.org.tr',
            })
            url = f'https://kap.org.tr/tr/sirket-bilgileri/genel/{ticker}'
            r = s.get(url, timeout=15)
            
            if r.status_code != 200:
                time.sleep(random.uniform(2, 4))
                continue
            
            # Parse RSC payload for shareholder data
            text = r.text
            # Look for shareholder patterns in RSC script tags
            # Pattern: holderName, shareRatio in the RSC JSON
            # KAP's RSC uses unicode escaped strings
            decoded = text
            try:
                # Find all __next_f.push payloads
                pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', text, re.DOTALL)
                for push in pushes:
                    try:
                        d = push.encode('raw_unicode_escape').decode('unicode_escape')
                    except:
                        d = push
                    decoded += d
            except:
                pass
            
            # Try to find shareholder data
            # Pattern: "holderName":"xxx" or "name":"xxx" with share info
            sh_matches = re.findall(
                r'"(?:holderName|name|paySahibi|holder_name)"\s*:\s*"([^"]+)".*?"(?:shareRatio|rate|payOrani|share_ratio)"\s*:\s*([\d.,]+)',
                decoded, re.DOTALL
            )
            
            if sh_matches:
                for sh_name, sh_ratio in sh_matches:
                    if sh_name and len(sh_name) > 2 and sh_name not in ('null', 'undefined', ''):
                        try:
                            ratio = float(sh_ratio.replace(',', '.'))
                        except:
                            ratio = None
                        c.execute('''INSERT OR IGNORE INTO shareholders 
                                     (company_id, holder_name, share_ratio_percent, holder_type)
                                     VALUES (?, ?, ?, ?)''',
                                 (cid, sh_name.strip(), ratio, 
                                  'CORPORATE' if any(kw in sh_name.lower() for kw in ['a.ş', 'ltd', 'holding', 'bank', 'sigorta']) else 'INDIVIDUAL'))
                        count += 1
        except Exception as e:
            pass
        
        time.sleep(random.uniform(2, 4))
    
    db.commit()
    print(f'[SHAREHOLDERS] Toplam: {count} ortak kaydi')
    return count

# ══════════════════════════════════════════════════════════════════
# 3. FIX FINANCIAL RATIOS
# ══════════════════════════════════════════════════════════════════
def fix_financial_ratios(db):
    """Calculate missing financial ratios."""
    c = db.cursor()
    
    # Calculate net_debt where missing
    c.execute('''
        UPDATE financials SET net_debt = (
            SELECT COALESCE(
                (SELECT f2.total_debt FROM financials f2 WHERE f2.id = financials.id), 0) 
            - COALESCE(
                (SELECT f2.cash_and_equivalents FROM financials f2 WHERE f2.id = financials.id), 0)
        )
        WHERE net_debt IS NULL AND total_debt IS NOT NULL
    ''')
    print(f'[RATIOS] net_debt hesaplandi: {c.rowcount}')
    
    # Calculate missing PE ratio from price data
    c.execute('''
        UPDATE financials SET pe_ratio = (
            SELECT bp.price / NULLIF(f.net_profit / NULLIF(f.paid_capital, 0), 0)
            FROM bist_stock_prices bp
            JOIN companies comp ON comp.ticker = bp.ticker
            WHERE comp.id = financials.company_id
            AND f.year = financials.year AND f.period = financials.period
        )
        WHERE pe_ratio IS NULL AND net_profit IS NOT NULL AND net_profit > 0
        AND paid_capital IS NOT NULL AND paid_capital > 0
    ''')
    print(f'[RATIOS] PE hesaplandi: {c.rowcount}')
    
    # Calculate ROE where missing (net_profit / equity * 100)
    c.execute('''
        UPDATE financials SET roe = (net_profit * 100.0 / equity)
        WHERE roe IS NULL AND net_profit IS NOT NULL AND equity IS NOT NULL AND equity > 0
    ''')
    print(f'[RATIOS] ROE hesaplandi: {c.rowcount}')
    
    # Calculate ROA where missing (net_profit / total_assets * 100)
    c.execute('''
        UPDATE financials SET roa = (net_profit * 100.0 / total_assets)
        WHERE roa IS NULL AND net_profit IS NOT NULL AND total_assets IS NOT NULL AND total_assets > 0
    ''')
    print(f'[RATIOS] ROA hesaplandi: {c.rowcount}')
    
    # Calculate gross_margin
    c.execute('''
        UPDATE financials SET gross_margin = (gross_profit * 100.0 / revenue)
        WHERE gross_margin IS NULL AND gross_profit IS NOT NULL AND revenue IS NOT NULL AND revenue > 0
    ''')
    print(f'[RATIOS] gross_margin hesaplandi: {c.rowcount}')
    
    # Calculate ebitda_margin
    c.execute('''
        UPDATE financials SET ebitda_margin = (ebitda * 100.0 / revenue)
        WHERE ebitda_margin IS NULL AND ebitda IS NOT NULL AND revenue IS NOT NULL AND revenue > 0
    ''')
    print(f'[RATIOS] ebitda_margin hesaplandi: {c.rowcount}')
    
    # Calculate net_margin
    c.execute('''
        UPDATE financials SET net_margin = (net_profit * 100.0 / revenue)
        WHERE net_margin IS NULL AND net_profit IS NOT NULL AND revenue IS NOT NULL AND revenue > 0
    ''')
    print(f'[RATIOS] net_margin hesaplandi: {c.rowcount}')
    
    # Calculate leverage_ratio (total_debt / total_assets)
    c.execute('''
        UPDATE financials SET leverage_ratio = (total_debt * 100.0 / total_assets)
        WHERE leverage_ratio IS NULL AND total_debt IS NOT NULL AND total_assets IS NOT NULL AND total_assets > 0
    ''')
    print(f'[RATIOS] leverage_ratio hesaplandi: {c.rowcount}')
    
    db.commit()

# ══════════════════════════════════════════════════════════════════
# 4. LINK ALL DATA TO TICKERS
# ══════════════════════════════════════════════════════════════════
def link_data_to_tickers(db):
    """Ensure all data has proper company_id/ticker links."""
    c = db.cursor()
    
    # Link disclosures to companies
    c.execute('''
        UPDATE disclosures SET company_id = (
            SELECT c.id FROM companies c WHERE c.ticker = disclosures.symbol
        )
        WHERE company_id IS NULL AND symbol IS NOT NULL
    ''')
    print(f'[LINK] disclosures company_id: {c.rowcount}')
    
    # Link shareholders to companies via ticker name matching
    c.execute('''
        UPDATE shareholders SET company_id = (
            SELECT c.id FROM companies c WHERE c.ticker = shareholders.holder_name
        )
        WHERE company_id IS NULL AND holder_name IN (SELECT ticker FROM companies)
    ''')
    print(f'[LINK] shareholders company_id: {c.rowcount}')
    
    # Link share_buybacks
    c.execute('''
        UPDATE share_buybacks SET company_id = (
            SELECT d.company_id FROM disclosures d WHERE d.id = share_buybacks.disclosure_id
        )
        WHERE company_id IS NULL AND disclosure_id IS NOT NULL
    ''')
    print(f'[LINK] buybacks company_id: {c.rowcount}')
    
    # Link disclosure_details to companies
    c.execute('''
        UPDATE disclosure_details SET ticker = (
            SELECT d.symbol FROM disclosures d 
            WHERE d.disclosure_id = disclosure_details.disclosure_index
        )
        WHERE ticker IS NULL AND disclosure_index IS NOT NULL
    ''')
    print(f'[LINK] disclosure_details ticker: {c.rowcount}')
    
    db.commit()

# ══════════════════════════════════════════════════════════════════
# 5. REBUILD ASSET_FULL VIEW
# ══════════════════════════════════════════════════════════════════
def rebuild_asset_view(db):
    """Rebuild the asset_full view with latest data."""
    c = db.cursor()
    c.execute('DROP VIEW IF EXISTS asset_full')
    c.execute('''
        CREATE VIEW IF NOT EXISTS asset_full AS
        SELECT 
            c.id, c.ticker, c.company_name, c.sector, c.market, c.is_active,
            bp.price, bp.market_cap, bp.pe_ratio, bp.pb_ratio, bp.dividend_yield,
            bp.day_change_pct, bp.volume, bp.week52_high, bp.week52_low, bp.is_xu100,
            (SELECT f.net_profit FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_net_profit,
            (SELECT f.revenue FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_revenue,
            (SELECT f.ebitda FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_ebitda,
            (SELECT f.total_debt FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_total_debt,
            (SELECT f.equity FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_equity,
            (SELECT f.roe FROM financials f WHERE f.company_id = c.id ORDER BY f.year DESC, f.period DESC LIMIT 1) as latest_roe
        FROM companies c
        LEFT JOIN bist_stock_prices bp ON bp.ticker = c.ticker
        WHERE c.ticker IS NOT NULL AND c.ticker != ''
    ''')
    print('[VIEW] asset_full yeniden olusturuldu')
    db.commit()

# ══════════════════════════════════════════════════════════════════
# 6. SUMMARY
# ══════════════════════════════════════════════════════════════════
def print_summary(db):
    c = db.cursor()
    print('\n' + '='*60)
    print('FINAL VERI DURUMU')
    print('='*60)
    
    tables = {
        'companies': None,
        'financials': None,
        'cash_flows': None,
        'disclosures': None,
        'bist_stock_prices': None,
        'bist_price_history': None,
        'shareholders': None,
        'management_members': None,
        'share_buybacks': None,
        'disclosure_details': None,
        'settlement_data': None,
        'corporate_actions': None,
        'tefas_funds': None,
        'tefas_fund_prices': None,
        'tefas_fund_allocations': None,
        'fund_stock_holdings': None,
        'market_rates': None,
        'market_indicators': None,
    }
    
    for t in tables.keys():
        try:
            c.execute(f'SELECT COUNT(*) FROM {t}')
            cnt = c.fetchone()[0]
            extra = ''
            if t == 'companies':
                c.execute('SELECT COUNT(*) FROM companies WHERE sector IS NOT NULL AND sector != ""')
                sec = c.fetchone()[0]
                extra = f' ({sec} sectorlu)'
            elif t == 'financials':
                c.execute('SELECT COUNT(DISTINCT company_id) FROM financials')
                extra = f' ({c.fetchone()[0]} sirket)'
            elif t == 'disclosures':
                c.execute('SELECT COUNT(DISTINCT symbol) FROM disclosures WHERE symbol IS NOT NULL')
                extra = f' ({c.fetchone()[0]} sirket)'
            elif t == 'bist_price_history':
                c.execute('SELECT COUNT(DISTINCT ticker) FROM bist_price_history')
                extra = f' ({c.fetchone()[0]} ticker)'
            elif t == 'tefas_fund_prices':
                c.execute('SELECT COUNT(DISTINCT code) FROM tefas_fund_prices')
                extra = f' ({c.fetchone()[0]} fon)'
            print(f'  {t:30s}: {cnt:>8,}{extra}')
        except Exception as e:
            print(f'  {t:30s}: HATA - {e}')
    
    print('='*60)

# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    db = sqlite3.connect(DB_PATH)
    
    print('='*60)
    print('TUM EKSIK VERILERI TAMAMLAMA')
    print('='*60)
    
    # 1. Sector mapping
    assign_sectors(db)
    
    # 2. Link data to tickers
    link_data_to_tickers(db)
    
    # 3. Fix financial ratios
    fix_financial_ratios(db)
    
    # 4. Rebuild asset view
    rebuild_asset_view(db)
    
    # 5. Try shareholders
    try:
        scrape_kap_shareholders(db)
    except Exception as e:
        print(f'[SHAREHOLDERS] Hata: {e}')
    
    # 6. Summary
    print_summary(db)
    
    db.close()
    print('\nTamamlandi!')

if __name__ == '__main__':
    main()
