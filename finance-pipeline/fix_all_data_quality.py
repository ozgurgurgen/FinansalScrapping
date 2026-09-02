"""
Comprehensive Data Quality Fix Script
Fixes all identified issues across all database tables.
"""
import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = 'finance.db'

def fix_companies_sector_market(db):
    """Fix kap_companies sector/market from KAP disclosure data."""
    c = db.cursor()
    c.execute('SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ""')
    before = c.fetchone()[0]
    
    # Map known sectors from company names
    sector_map = {
        'BANK': 'Bankacilik', 'FINANS': 'Finans', 'HOLDING': 'Holding',
        'SIGORTA': 'Sigorta', 'GAYRIMENKUL': 'Gayrimenkul',
        'CELIK': 'Celik', 'ENERJI': 'Enerji', 'PETROKIMYA': 'Petrokimya',
        'OTOMOTIV': 'Otomotiv', 'GIDA': 'Gida', 'TEKSTIL': 'Tekstil',
        'TELEKOM': 'Telekomunikasyon', 'ULASIM': 'Ulasim', 'TICARET': 'Ticaret',
        'YAPI': 'Insaat', 'INSaat': 'Insaat', 'MADENCILIK': 'Madencilik',
        'TURIZM': 'Turizm', 'SAGLIK': 'Saglik', 'EGITIM': 'Egitim',
        'BILISIM': 'Bilisim', 'YAZILIM': 'Bilisim', 'TEKNOLOJI': 'Teknoloji',
    }
    
    c.execute('SELECT id, ticker, company_name FROM kap_companies WHERE sector IS NULL OR sector = ""')
    companies = c.fetchall()
    updated = 0
    for co_id, ticker, name in companies:
        if not name:
            continue
        name_upper = name.upper()
        for kw, sector in sector_map.items():
            if kw in name_upper:
                c.execute('UPDATE kap_companies SET sector = ? WHERE id = ?', (sector, co_id))
                updated += 1
                break
    
    # Set market based on ticker patterns
    c.execute('SELECT id, ticker FROM kap_companies WHERE market IS NULL OR market = ""')
    for co_id, ticker in c.fetchall():
        if ticker.endswith('GYO'):
            c.execute('UPDATE kap_companies SET market = "GYO" WHERE id = ?', (co_id,))
        elif ticker.endswith('YAT'):
            c.execute('UPDATE kap_companies SET market = "Yatirim Ortakligi" WHERE id = ?', (co_id,))
        elif ticker.endswith('-Menkul'):
            c.execute('UPDATE kap_companies SET market = "Menkul Degerler" WHERE id = ?', (co_id,))
        else:
            c.execute('UPDATE kap_companies SET market = "BIST" WHERE id = ?', (co_id,))
        updated += 1
    
    db.commit()
    c.execute('SELECT COUNT(*) FROM kap_companies WHERE sector IS NOT NULL AND sector != ""')
    after = c.fetchone()[0]
    print(f'  Companies sector/market: {before} -> {after} ({updated} updated)')

def fix_duplicate_shares(db):
    """Remove duplicate shareholder records."""
    c = db.cursor()
    c.execute('''DELETE FROM kap_shareholders WHERE id NOT IN (
        SELECT MIN(id) FROM kap_shareholders GROUP BY company_id, holder_name
    )''')
    dupes = c.rowcount
    db.commit()
    if dupes:
        print(f'  Removed {dupes} duplicate shareholders')

def fix_bad_subsidiary_names(db):
    """Fix subsidiary names that are just numbers."""
    c = db.cursor()
    c.execute('DELETE FROM kap_subsidiaries WHERE name IS NULL OR LENGTH(name) < 3 OR name LIKE "%1" AND LENGTH(name) < 5')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} bad subsidiary records')

def fix_corporate_actions(db):
    """Fix corporate actions with empty financial details."""
    c = db.cursor()
    # Remove records where ALL important fields are empty
    c.execute('''DELETE FROM kap_corporate_actions 
        WHERE gross_per_share IS NULL AND net_per_share IS NULL 
        AND yield_percent IS NULL AND ratio_percent IS NULL''')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} empty corporate actions')

def fix_ipo_data(db):
    """Fix IPO data - remove records with no useful info."""
    c = db.cursor()
    c.execute('''DELETE FROM ipo_data 
        WHERE ipo_price IS NULL AND offering_amount_tl IS NULL 
        AND total_offered_shares IS NULL''')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} empty IPO records')

def fix_disclosure_details(db):
    """Fix disclosure details - remove records with no parsed data."""
    c = db.cursor()
    c.execute('''DELETE FROM disclosure_details 
        WHERE client_name IS NULL AND contract_amount_tl IS NULL
        AND block_shares IS NULL AND qi_investor IS NULL''')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} empty disclosure details')

def fix_portfolio_reports(db):
    """Fix portfolio reports - remove empty records."""
    c = db.cursor()
    c.execute('''DELETE FROM kap_portfolio_reports 
        WHERE symbol IS NULL OR symbol = ""''')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} portfolio reports with no symbol')

def fix_financial_notes(db):
    """Fix financial notes - remove empty records."""
    c = db.cursor()
    c.execute('DELETE FROM kap_financial_notes WHERE content_text IS NULL OR content_text = ""')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} empty financial notes')

def fix_settlement_data(db):
    """Fix settlement data - remove records with no ratio data."""
    c = db.cursor()
    c.execute('DELETE FROM settlement_data WHERE base_ratio_pct IS NULL AND common_ratio_pct IS NULL')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} empty settlement records')

def fix_share_buybacks(db):
    """Fix share buybacks - calculate capital_ratio from available data."""
    c = db.cursor()
    # Calculate capital_ratio_percent where missing
    c.execute('''UPDATE share_buybacks 
        SET capital_ratio_percent = CASE 
            WHEN total_bought_shares > 0 AND max_shares > 0 
            THEN (total_bought_shares * 100.0 / max_shares) 
            ELSE NULL END
        WHERE capital_ratio_percent IS NULL AND total_bought_shares > 0 AND max_shares > 0
    ''')
    updated = c.rowcount
    
    # Remove buybacks with no useful data at all
    c.execute('''DELETE FROM share_buybacks 
        WHERE total_budget_tl IS NULL AND total_bought_shares IS NULL''')
    deleted = c.rowcount
    db.commit()
    print(f'  Buybacks: {updated} ratios calculated, {deleted} empty removed')

def fix_index_constituents(db):
    """Fix index constituents - set default weight."""
    c = db.cursor()
    c.execute('UPDATE index_constituents SET weight_pct = 1.0 WHERE weight_pct IS NULL')
    updated = c.rowcount
    db.commit()
    if updated:
        print(f'  Updated {updated} index constituent weights')

def fix_disclosures_company_id(db):
    """Fix disclosures with missing company_id."""
    c = db.cursor()
    # Try to match by symbol
    c.execute('''UPDATE kap_disclosures 
        SET company_id = (SELECT id FROM kap_companies WHERE ticker = kap_disclosures.symbol LIMIT 1)
        WHERE company_id IS NULL AND symbol IS NOT NULL AND symbol != ""
    ''')
    updated = c.rowcount
    db.commit()
    if updated:
        print(f'  Linked {updated} disclosures to companies')

def fix_tefas_funds(db):
    """Fix TEFAS fund group/subtype from fund data."""
    c = db.cursor()
    c.execute('''UPDATE tefas_funds 
        SET fund_group = CASE 
            WHEN title LIKE '%Hisse%' OR title LIKE '%HISSE%' THEN 'Hisse'
            WHEN title LIKE '%Borclanma%' OR title LIKE '%Tahvil%' THEN 'Borclanma'
            WHEN title LIKE '%Para Piyasa%' OR title LIKE '%PPY%' THEN 'Para Piyasasi'
            WHEN title LIKE '%Karma%' THEN 'Karma'
            WHEN title LIKE '%Alternatif%' THEN 'Alternatif'
            ELSE 'Diger'
        END
        WHERE fund_group IS NULL OR fund_group = ""
    ''')
    updated = c.rowcount
    db.commit()
    if updated:
        print(f'  Updated {updated} TEFAS fund groups')

def fix_assets(db):
    """Fix assets table - remove records with no useful data."""
    c = db.cursor()
    c.execute('DELETE FROM assets WHERE name IS NULL OR LENGTH(name) < 3')
    deleted = c.rowcount
    db.commit()
    if deleted:
        print(f'  Removed {deleted} bad asset records')

def recalculate_pe_pb(db):
    """Recalculate PE/PB ratios for stocks that have financials."""
    c = db.cursor()
    updated = 0
    
    # Get companies with both price and financials
    c.execute('''
        SELECT bp.ticker, bp.price, bp.market_cap, 
               kf.net_profit, kf.equity, kf.revenue, kf.year, kf.period
        FROM bist_stock_prices bp
        JOIN kap_companies co ON co.ticker = bp.ticker
        JOIN kap_financials kf ON kf.company_id = co.id
        WHERE kf.net_profit > 0 AND bp.price > 0
        AND kf.period = 12
        ORDER BY co.ticker, kf.year DESC, kf.period DESC
    ''')
    
    seen_tickers = set()
    for ticker, price, mc, net_profit, equity, revenue, year, period in c.fetchall():
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)
        
        # PE = Market Cap / Net Profit (annualized)
        # If period is not 12, annualize
        if net_profit and price:
            pe = price / (net_profit * 1000000 / (mc / price)) if mc and net_profit else None
            # Simpler: PE = price / EPS where EPS = net_profit / shares
            # But we don't have shares, so use market_cap approach
            if mc and net_profit > 0:
                pe = mc / (net_profit * 1000000)  # net_profit in millions
                c.execute('UPDATE bist_stock_prices SET pe_ratio = ? WHERE ticker = ?', 
                         (round(pe, 2), ticker))
                updated += 1
        
        # PB = Market Cap / Equity
        if mc and equity and equity > 0:
            pb = mc / (equity * 1000000)  # equity in millions
            c.execute('UPDATE bist_stock_prices SET pb_ratio = ? WHERE ticker = ?',
                     (round(pb, 2), ticker))
    
    db.commit()
    print(f'  Recalculated PE/PB for {updated} stocks')

def main():
    db = sqlite3.connect(DB_PATH)
    print('=== VERI KALITESI DUZELTME SCRIPTI ===')
    print()
    
    print('[1] Companies sector/market duzeltme...')
    fix_companies_sector_market(db)
    
    print('[2] Duplicate shareholder temizleme...')
    fix_duplicate_shares(db)
    
    print('[3] Bad subsidiary names temizleme...')
    fix_bad_subsidiary_names(db)
    
    print('[4] Empty corporate actions temizleme...')
    fix_corporate_actions(db)
    
    print('[5] Empty IPO data temizleme...')
    fix_ipo_data(db)
    
    print('[6] Empty disclosure details temizleme...')
    fix_disclosure_details(db)
    
    print('[7] Empty portfolio reports temizleme...')
    fix_portfolio_reports(db)
    
    print('[8] Empty financial notes temizleme...')
    fix_financial_notes(db)
    
    print('[9] Empty settlement data temizleme...')
    fix_settlement_data(db)
    
    print('[10] Share buybacks duzeltme...')
    fix_share_buybacks(db)
    
    print('[11] Index constituents duzeltme...')
    fix_index_constituents(db)
    
    print('[12] Disclosures company_id baglama...')
    fix_disclosures_company_id(db)
    
    print('[13] TEFAS fund groups duzeltme...')
    fix_tefas_funds(db)
    
    print('[14] Assets temizleme...')
    fix_assets(db)
    
    print('[15] PE/PB recalculate...')
    recalculate_pe_pb(db)
    
    # Final summary
    print()
    print('=== FINAL DURUM ===')
    c = db.cursor()
    tables = [
        ('kap_companies', 'Sirketler'), ('kap_financials', 'Finansal'),
        ('kap_disclosures', 'Bildirimler'), ('bist_stock_prices', 'BIST Fiyat'),
        ('bist_price_history', 'Fiyat Gecmisi'),
        ('tefas_funds', 'TEFAS Fon'), ('tefas_fund_prices', 'TEFAS Fiyat'),
        ('share_buybacks', 'Geri Alim'), ('ipo_data', 'IPO'),
        ('kap_corporate_actions', 'Kurumsal'), ('index_constituents', 'Endeks'),
        ('settlement_data', 'Takas'),
    ]
    for tbl, label in tables:
        try:
            c.execute(f'SELECT COUNT(*) FROM [{tbl}]')
            print(f'  {label}: {c.fetchone()[0]:,}')
        except:
            pass
    
    db.close()
    print()
    print('Tamamlandi!')

if __name__ == '__main__':
    main()
