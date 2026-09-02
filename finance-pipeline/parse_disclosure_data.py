#!/usr/bin/env python3
"""Parse disclosure details to extract structured data from titles and raw_content"""
import sqlite3, re, os, time, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')

def parse_amount(text):
    """Extract TL/USD/EUR amounts from text"""
    amounts = {'tl': None, 'usd': None, 'eur': None}
    # Turkish number format: 1.234.567,89 or 1,234,567.89
    patterns = [
        (r'([\d.]+,\d+)\s*(?:TL|₺|TRY)', 'tl'),
        (r'([\d,]+\.?\d*)\s*(?:TL|₺|TRY)', 'tl'),
        (r'([\d.]+,\d+)\s*(?:USD|\$|ABD)', 'usd'),
        (r'([\d,]+\.?\d*)\s*(?:USD|\$|ABD)', 'usd'),
        (r'([\d.]+,\d+)\s*(?:EUR|€)', 'eur'),
        (r'([\d,]+\.?\d*)\s*(?:EUR|€)', 'eur'),
    ]
    for pat, currency in patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = m.group(1).replace('.', '').replace(',', '.')
            try:
                amounts[currency] = float(val)
            except:
                pass
    return amounts

def parse_percentage(text):
    """Extract percentage from text"""
    m = re.search(r'%([\d,\.]+)', text)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None

def parse_tender(title, raw_content=''):
    """Parse tender/bid disclosure"""
    result = {}
    combined = f"{title} {raw_content}"
    
    # Client/institution name
    # Patterns: "X firmasının ihalesi", "X tarafından"
    m = re.search(r'([\w\s]+?)(?:\s+(?: firması| tarafından| adına|ın |in |un |ün ))', combined)
    if m:
        result['client_name'] = m.group(1).strip()[:200]
    
    # Contract amount
    amounts = parse_amount(combined)
    if amounts['tl']:
        result['contract_amount_tl'] = amounts['tl']
    if amounts['usd']:
        result['contract_amount_usd'] = amounts['usd']
    if amounts['eur']:
        result['contract_amount_eur'] = amounts['eur']
    
    return result

def parse_block_sale(title, raw_content=''):
    """Parse block sale/transfer disclosure"""
    result = {}
    combined = f"{title} {raw_content}"
    
    # Block shares count
    m = re.search(r'([\d.]+(?:,\d+)?)\s*(?:adet|pay|lot)', combined)
    if m:
        val = m.group(1).replace('.', '').replace(',', '.')
        try:
            result['block_shares'] = float(val)
        except:
            pass
    
    # Block price
    amounts = parse_amount(combined)
    if amounts['tl']:
        result['block_price'] = amounts['tl']
    
    # Ratio
    pct = parse_percentage(combined)
    if pct:
        result['block_ratio_pct'] = pct
    
    # Buyer/seller names
    m = re.search(r'(?:satan|satıcı)\s*:?\s*([\w\s]+?)(?:\s*,|\s*\()', combined)
    if m:
        result['seller_name'] = m.group(1).strip()[:200]
    m = re.search(r'(?:alan|alıcı)\s*:?\s*([\w\s]+?)(?:\s*,|\s*\()', combined)
    if m:
        result['buyer_name'] = m.group(1).strip()[:200]
    
    return result

def parse_qualified_investor(title, raw_content=''):
    """Parse qualified investor sale disclosure"""
    result = {}
    combined = f"{title} {raw_content}"
    
    # Investor name
    m = re.search(r'([\w\s]+?)(?:\s+(?:A\.Ş|Bank|Finans|Yatırım|Menkul|Portföy|emekli|sandık))', combined)
    if m:
        result['qi_investor'] = m.group(1).strip()[:200]
    
    # Shares
    m = re.search(r'([\d.]+(?:,\d+)?)\s*(?:adet|pay|lot)', combined)
    if m:
        val = m.group(1).replace('.', '').replace(',', '.')
        try:
            result['qi_shares'] = float(val)
        except:
            pass
    
    # Price
    amounts = parse_amount(combined)
    if amounts['tl']:
        result['qi_price'] = amounts['tl']
    
    return result

def parse_capital_increase(title, raw_content=''):
    """Parse capital increase disclosure"""
    result = {}
    combined = f"{title} {raw_content}"
    
    # Amount
    amounts = parse_amount(combined)
    if amounts['tl']:
        result['contract_amount_tl'] = amounts['tl']
    
    return result

def parse_buyback_detail(title, raw_content=''):
    """Parse buyback program disclosure"""
    result = {}
    combined = f"{title} {raw_content}"
    
    # Total budget
    amounts = parse_amount(combined)
    if amounts['tl']:
        result['total_budget_tl'] = amounts['tl']
    
    # Max shares
    m = re.search(r'(?:azami|en fazla|max).*?([\d.]+(?:,\d+)?)\s*(?:adet|pay|lot)', combined, re.I)
    if m:
        val = m.group(1).replace('.', '').replace(',', '.')
        try:
            result['max_shares'] = float(val)
        except:
            pass
    
    # Bought shares
    m = re.search(r'(?:geri alınan|satın alınan|alınan).*?([\d.]+(?:,\d+)?)\s*(?:adet|pay|lot)', combined, re.I)
    if m:
        val = m.group(1).replace('.', '').replace(',', '.')
        try:
            result['total_bought_shares'] = float(val)
        except:
            pass
    
    # Avg price
    m = re.search(r'(?:ortalama|maliyet|fiyat).*?([\d.]+(?:,\d+)?)\s*(?:TL|₺)', combined, re.I)
    if m:
        val = m.group(1).replace('.', '').replace(',', '.')
        try:
            result['avg_buyback_price'] = float(val)
        except:
            pass
    
    return result

def main():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    print("=" * 60)
    print("DISCLOSURE DETAIL PARSER")
    print("=" * 60)
    
    # 1. Parse disclosure_details structured fields
    c.execute('SELECT id, ticker, title, detail_type, client_name, contract_amount_tl FROM disclosure_details')
    rows = c.fetchall()
    print(f"\n{len(rows)} disclosure_details kaydı taranacak")
    
    updated = 0
    for row in rows:
        dd_id, ticker, title, detail_type, existing_client, existing_amount = row
        
        # Skip if already has data
        if existing_client and existing_amount:
            continue
        
        # Get raw content from kap_disclosures
        c.execute('SELECT raw_content FROM kap_disclosures WHERE disclosure_id = (SELECT disclosure_index FROM disclosure_details WHERE id = ?)', (dd_id,))
        raw_row = c.fetchone()
        raw_content = raw_row[0] if raw_row else ''
        
        fields = {}
        if detail_type == 'tender':
            fields = parse_tender(title, raw_content)
        elif detail_type == 'transfer':
            fields = parse_block_sale(title, raw_content)
        elif detail_type == 'special_event':
            # Check if it's a qualified investor sale
            if 'nitelikli' in (title or '').lower() or 'nitelikli' in (raw_content or '').lower():
                fields = parse_qualified_investor(title, raw_content)
            else:
                fields = parse_block_sale(title, raw_content)
        elif detail_type == 'capital_increase':
            fields = parse_capital_increase(title, raw_content)
        
        if fields:
            updates = []
            params = []
            for k, v in fields.items():
                if v is not None:
                    updates.append(f"{k} = ?")
                    params.append(v)
            if updates:
                params.append(dd_id)
                c.execute(f"UPDATE disclosure_details SET {', '.join(updates)} WHERE id = ?", params)
                updated += 1
    
    db.commit()
    print(f"  Disclosure details güncellendi: {updated}")
    
    # 2. Parse buyback disclosures
    print(f"\nPay geri alım detayları parse ediliyor...")
    c.execute('''SELECT sb.id, sb.company_id, sb.disclosure_id, d.title, d.raw_content
                 FROM share_buybacks sb
                 LEFT JOIN kap_disclosures d ON sb.disclosure_id = d.disclosure_id
                 WHERE sb.total_budget_tl IS NULL OR sb.total_bought_shares IS NULL''')
    buybacks = c.fetchall()
    print(f"  {len(buybacks)} geri alım kaydı")
    
    bb_updated = 0
    for sb_id, company_id, disc_id, title, raw in buybacks:
        if not title and not raw:
            continue
        fields = parse_buyback_detail(title or '', raw or '')
        if fields:
            updates = []
            params = []
            for k, v in fields.items():
                if v is not None:
                    updates.append(f"{k} = ?")
                    params.append(v)
            if updates:
                params.append(sb_id)
                c.execute(f"UPDATE share_buybacks SET {', '.join(updates)} WHERE id = ?", params)
                bb_updated += 1
    
    db.commit()
    print(f"  Geri alım güncellendi: {bb_updated}")
    
    # 3. Check final status
    print(f"\n{'='*60}")
    print("SONUÇ")
    print(f"{'='*60}")
    
    c.execute('''SELECT detail_type, COUNT(*),
                 SUM(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 ELSE 0 END) as client,
                 SUM(CASE WHEN contract_amount_tl IS NOT NULL THEN 1 ELSE 0 END) as amount,
                 SUM(CASE WHEN block_shares IS NOT NULL THEN 1 ELSE 0 END) as block,
                 SUM(CASE WHEN qi_investor IS NOT NULL AND qi_investor != '' THEN 1 ELSE 0 END) as qi
                 FROM disclosure_details GROUP BY detail_type''')
    for r in c.fetchall():
        print(f"  {r[0]}: total={r[1]}, client={r[2]}, amount={r[3]}, block={r[4]}, qi={r[5]}")
    
    c.execute('''SELECT COUNT(*) FROM share_buybacks 
                 WHERE total_budget_tl IS NOT NULL OR total_bought_shares IS NOT NULL''')
    print(f"\n  Buybacks with data: {c.fetchone()[0]}")
    
    db.close()

if __name__ == '__main__':
    main()
