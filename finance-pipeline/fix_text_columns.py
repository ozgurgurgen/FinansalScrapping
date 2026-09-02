"""
PostgreSQL TEXT sütunlarını doğru tiplere dönüştür.
Sütun isimlerine bakarak otomatik tespit eder.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import psycopg2

PG = {'host':'localhost','port':5432,'database':'finance_platform','user':'admin','password':'admin123'}

# Sayısal olması gereken sütun kalıpları
NUMERIC_KEYWORDS = [
    # Temel sayısal
    'id', 'count', 'total', 'amount', 'price', 'ratio', 'percent', 'pct',
    'yield', 'return', 'rate', 'index', 'rank', 'order', 'level', 'size',
    'volume', 'market_cap', 'shares', 'investors', 'years', 'months',
    # Finansal
    'revenue', 'profit', 'loss', 'income', 'expense', 'cost', 'debt',
    'equity', 'asset', 'liability', 'cash', 'capital', 'budget', 'value',
    'ebitda', 'ebit', 'net_profit', 'gross_profit', 'operating',
    'financing', 'investing', 'capex', 'depreciation', 'amortization',
    # Rasyo
    'pe_ratio', 'pb_ratio', 'ev_', 'roe', 'roa', 'margin',
    'current_ratio', 'leverage', 'net_debt', 'total_debts',
    'total_assets', 'paid_capital', 'share_percent',
    # Fiyat
    'price', 'bid', 'ask', 'high', 'low', 'open', 'close', 'adj',
    'first_price', 'last_price', 'min_price', 'max_price', 'avg_price',
    'total_return', 'annualized', 'return_pct',
    # Dağılım (tefas)
    'stock', 'bond', 'deposit', 'repo', 'gold', 'forex', 'fund_',
    'bill', 'certificate', 'securities', 'derivative', 'tmm',
    # Sayısal integer
    'shares_count', 'outstanding', 'nominal', 'seats', 'members_count',
    'total_funds', 'total_funds_in_portfolio', 'investor_count',
    # IDs (integer olarak kalmalı)
    'company_id', 'fund_id', 'disclosure_id', 'parent_id',
]

# Tip belirleme fonksiyonu
def decide_type(col_name, sample_values):
    """Sütun ismini ve örnek değerleri analiz edip PostgreSQL tipini belirle."""
    cn = col_name.lower()
    
    # ID sütunları
    if cn == 'id' or cn.endswith('_id'):
        return 'BIGINT'
    
    # TIMESTAMP / DATE
    if 'date' in cn or 'time' in cn or 'created' in cn or 'updated' in cn or 'published' in cn or 'finished' in cn or 'started' in cn or 'ex_date' in cn or 'payment_date' in cn:
        # Değerleri kontrol et
        for v in sample_values:
            if v and ('-' in str(v) or ':' in str(v)):
                if len(str(v)) > 10:  # datetime
                    return 'TIMESTAMP'
                else:  # date
                    return 'DATE'
    
    # BOOLEAN
    if 'is_' in cn or 'has_' in cn or 'active' in cn or 'enabled' in cn:
        for v in sample_values:
            if v in ('True', 'False', '1', '0', 'true', 'false'):
                return 'BOOLEAN'
    
    # LARGEINT (çok büyük sayılar)
    if 'market_cap' in cn or 'total_value' in cn or 'portfolio' in cn:
        return 'NUMERIC(18,2)'
    
    # Yüzde / ratio (ondalıklı)
    if 'ratio' in cn or 'percent' in cn or 'pct' in cn or 'yield' in cn or 'return' in cn or 'margin' in cn or '_rate' in cn:
        return 'NUMERIC(12,4)'
    
    # Fiyat (ondalıklı)
    if 'price' in cn or 'value_tl' in cn or 'value_usd' in cn or 'amount' in cn or 'budget' in cn or 'cost' in cn:
        return 'NUMERIC(18,4)'
    
    # Sayısal (ondalıklı)
    if 'share' in cn or 'shares' in cn or 'count' in cn or 'investors' in cn or 'members' in cn:
        # Integer olabilir ama NUMERIC güvenli
        return 'NUMERIC(18,2)'
    
    # Diğer sayısal kalıpları kontrol et
    for kw in NUMERIC_KEYWORDS:
        if kw in cn:
            return 'NUMERIC(18,4)'
    
    # JSON / TEXT array
    if 'json' in cn or 'data' in cn or 'result' in cn or 'items' in cn:
        return 'TEXT'
    
    return None  # TEXT olarak kalsın

def main():
    conn = psycopg2.connect(**PG)
    c = conn.cursor()
    
    # Tüm tabloları al
    c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    tables = [r[0] for r in c.fetchall()]
    
    total_changes = 0
    
    for table in tables:
        # Sütun bilgilerini al
        c.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = c.fetchall()
        
        text_cols = [(name, dtype) for name, dtype in columns if dtype == 'text']
        if not text_cols:
            continue
        
        changes = []
        for col_name, _ in text_cols:
            # Örnek değerleri al
            try:
                c.execute(f'SELECT DISTINCT "{col_name}" FROM "{table}" WHERE "{col_name}" IS NOT NULL AND "{col_name}" != \'\' LIMIT 5')
                samples = [str(r[0]) for r in c.fetchall()]
            except:
                samples = []
            
            new_type = decide_type(col_name, samples)
            if new_type:
                changes.append((col_name, new_type))
        
        if changes:
            print(f'\n  {table}: {len(changes)} sütun değiştirilecek')
            
            for col_name, new_type in changes:
                try:
                    # Boş stringleri NULL'a çevir
                    c.execute(f'UPDATE "{table}" SET "{col_name}" = NULL WHERE "{col_name}" = \'\'')
                    
                    # TYPE CHANGE
                    c.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col_name}" TYPE {new_type} USING "{col_name}"::{new_type}')
                    conn.commit()
                    print(f'    {col_name}: TEXT -> {new_type} ✅')
                    total_changes += 1
                except Exception as e:
                    conn.rollback()
                    print(f'    {col_name}: HATA - {str(e)[:80]} ❌')
    
    conn.close()
    print(f'\n{"="*50}')
    print(f'Toplam değişiklik: {total_changes} sütun')

if __name__ == '__main__':
    main()
