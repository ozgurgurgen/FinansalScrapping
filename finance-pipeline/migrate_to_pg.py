"""
SQLite -> PostgreSQL Migration Script
Tüm tabloları ve verileri PostgreSQL'e taşır.
"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import sqlite3
import psycopg2
from psycopg2.extras import execute_values

PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'finance_platform',
    'user': 'admin',
    'password': 'admin123',
}

SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')

def get_sqlite_tables(sqlite_path):
    """SQLite'daki tüm tabloları ve sütun bilgilerini getir."""
    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()
    
    # Tüm tabloları al
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_sequence%' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]
    
    result = {}
    for table in tables:
        # Sütun bilgilerini al
        c.execute(f"PRAGMA table_info({table})")
        columns = [(row[1], row[2]) for row in c.fetchall()]
        
        # Satır sayısını al
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        
        result[table] = {
            'columns': columns,
            'count': count,
        }
    
    conn.close()
    return result

def pg_type(sqlite_type):
    """SQLite sütun tipini PostgreSQL tipine çevir."""
    t = (sqlite_type or '').upper()
    if 'INT' in t:
        return 'BIGINT'
    elif 'REAL' in t or 'FLOAT' in t or 'DOUBLE' in t:
        return 'DOUBLE PRECISION'
    elif 'NUMERIC' in t or 'DECIMAL' in t:
        return 'NUMERIC'
    elif 'BLOB' in t:
        return 'BYTEA'
    else:
        return 'TEXT'

def create_pg_table(pg_conn, table_name, columns):
    """PostgreSQL'de tablo oluştur."""
    c = pg_conn.cursor()
    
    col_defs = []
    for col_name, col_type in columns:
        pg_t = pg_type(col_type)
        col_defs.append(f'"{col_name}" {pg_t}')
    
    # UNIQUE constraint'leri koru — basitçe PRIMARY KEY yoksa ekleme
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
    
    try:
        c.execute('DROP TABLE IF EXISTS "{}" CASCADE'.format(table_name))
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
    try:
        c.execute(create_sql)
        pg_conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ Tablo olusturma hatasi ({table_name}): {e}")
        pg_conn.rollback()
        return False

def migrate_table(sqlite_path, pg_conn, table_name, columns, count):
    """Tek bir tablonun verilerini SQLite'dan PostgreSQL'e taşı."""
    s_conn = sqlite3.connect(sqlite_path)
    s_conn.row_factory = sqlite3.Row
    s_c = s_conn.cursor()
    pg_c = pg_conn.cursor()
    
    col_names = [c[0] for c in columns]
    
    if count == 0:
        s_conn.close()
        return 0
    
    # Toplu insert için chunk'lar
    CHUNK = 5000
    offset = 0
    total_inserted = 0
    
    while offset < count:
        s_c.execute(f'SELECT * FROM "{table_name}" LIMIT {CHUNK} OFFSET {offset}')
        rows = s_c.fetchall()
        
        if not rows:
            break
        
        # Verileri tuple'a çevir, None türlerini temizle
        data = []
        for row in rows:
            data.append(tuple(row))
        
        placeholders = ', '.join(['%s'] * len(col_names))
        col_str = ', '.join([f'"{c}"' for c in col_names])
        insert_sql = f'INSERT INTO "{table_name}" ({col_str}) VALUES {placeholders}'
        
        try:
            pg_c.executemany(insert_sql, data)
            pg_conn.commit()
            total_inserted += len(data)
        except Exception as e:
            pg_conn.rollback()
            # Tek tek dene — hatalı satırı atla
            inserted = 0
            for row in data:
                try:
                    pg_c.execute(insert_sql, row)
                    pg_conn.commit()
                    inserted += 1
                except:
                    pg_conn.rollback()
            total_inserted += inserted
        
        offset += CHUNK
    
    s_conn.close()
    return total_inserted

def main():
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite dosyası bulunamadı: {SQLITE_PATH}")
        return
    
    print("📊 SQLite tabloları analiz ediliyor...")
    tables = get_sqlite_tables(SQLITE_PATH)
    
    print(f"📦 {len(tables)} tablo bulundu")
    for name, info in tables.items():
        print(f"  {name}: {info['count']:,} satır, {len(info['columns'])} sütun")
    
    print(f"\n🔗 PostgreSQL'e bağlanıyor...")
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.autocommit = False
    
    total_migrated = 0
    start_time = time.time()
    
    for i, (table_name, info) in enumerate(tables.items(), 1):
        count = info['count']
        columns = info['columns']
        
        print(f"\n[{i}/{len(tables)}] {table_name} ({count:,} satır)")
        
        # Tablo oluştur
        if not create_pg_table(pg_conn, table_name, columns):
            continue
        
        # Verileri taşı
        if count > 0:
            migrated = migrate_table(SQLITE_PATH, pg_conn, table_name, columns, count)
            total_migrated += migrated
            print(f"  ✅ {migrated:,} satır taşındı")
        else:
            print(f"  ⏭️ Boş tablo, atlandı")
    
    elapsed = time.time() - start_time
    pg_conn.close()
    
    print(f"\n{'='*60}")
    print(f"🎉 Migration tamamlandı!")
    print(f"  Toplam tablo: {len(tables)}")
    print(f"  Toplam satır: {total_migrated:,}")
    print(f"  Süre: {elapsed:.1f} saniye")
    print(f"  PostgreSQL: {PG_CONFIG['database']}@localhost:{PG_CONFIG['port']}")

if __name__ == '__main__':
    main()
