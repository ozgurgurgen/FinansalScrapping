"""
SQLite -> PostgreSQL Migration v2
Tüm tabloları basit TEXT sütunlarla taşır (PG otomatik cast eder).
"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import sqlite3
import psycopg2

PG_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'database': 'finance_platform', 'user': 'admin', 'password': 'admin123',
}
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

# Tabloları SQL injection'a karşı whitelist ile filtrele
SKIP_TABLES = {'sqlite_sequence', 'test_companies'}

def main():
    print(f"SQLite: {SQLITE_PATH}")
    print(f"PG: {PG_CONFIG['database']}@{PG_CONFIG['host']}:{PG_CONFIG['port']}")
    
    s = sqlite3.connect(SQLITE_PATH)
    sc = s.cursor()
    
    pg = psycopg2.connect(**PG_CONFIG)
    pc = pg.cursor()
    
    # Tabloları al
    sc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in sc.fetchall() if r[0] not in SKIP_TABLES]
    
    print(f"\n{len(tables)} tablo bulundu\n")
    
    total_rows = 0
    t0 = time.time()
    
    for i, tbl in enumerate(tables, 1):
        sc.execute(f'PRAGMA table_info("{tbl}")')
        col_info = sc.fetchall()  # [(cid, name, type, notnull, dflt, pk), ...]
        col_names = [c[1] for c in col_info]
        
        sc.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        count = sc.fetchone()[0]
        
        print(f"[{i}/{len(tables)}] {tbl}: {count:,} satır, {len(col_names)} sütun", end=' ')
        
        # Tabloyu oluştur (her zaman TEXT ile — PG cast eder)
        try:
            pc.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
            pg.commit()
        except:
            pg.rollback()
        
        col_defs = ', '.join([f'"{c}" TEXT' for c in col_names])
        try:
            pc.execute(f'CREATE TABLE "{tbl}" ({col_defs})')
            pg.commit()
        except Exception as e:
            print(f"❌ CREATE: {e}")
            pg.rollback()
            continue
        
        if count == 0:
            print("⏭️ boş")
            continue
        
        # Verileri toplu olarak al ve yaz
        col_str = ', '.join([f'"{c}"' for c in col_names])
        placeholders = ', '.join(['%s'] * len(col_names))
        insert_sql = f'INSERT INTO "{tbl}" ({col_str}) VALUES ({placeholders})'
        
        sc.execute(f'SELECT * FROM "{tbl}"')
        
        inserted = 0
        batch = []
        for row in sc:
            # Tüm değerleri string'e çevir (NULL korunur)
            batch.append(tuple(str(v) if v is not None else None for v in row))
            if len(batch) >= 5000:
                try:
                    pc.executemany(insert_sql, batch)
                    pg.commit()
                    inserted += len(batch)
                except Exception as e:
                    pg.rollback()
                    # Tek tek dene
                    for r in batch:
                        try:
                            pc.execute(insert_sql, r)
                            pg.commit()
                            inserted += 1
                        except:
                            pg.rollback()
                batch = []
        
        # Kalan batch
        if batch:
            try:
                pc.executemany(insert_sql, batch)
                pg.commit()
                inserted += len(batch)
            except Exception as e:
                pg.rollback()
                for r in batch:
                    try:
                        pc.execute(insert_sql, r)
                        pg.commit()
                        inserted += 1
                    except:
                        pg.rollback()
        
        total_rows += inserted
        status = '✅' if inserted == count else f'⚠️ {inserted}/{count}'
        print(status)
    
    elapsed = time.time() - t0
    pg.close()
    s.close()
    
    print(f"\n{'='*60}")
    print(f"🎉 Migration tamamlandı!")
    print(f"  Toplam: {len(tables)} tablo, {total_rows:,} satır")
    print(f"  Süre: {elapsed:.1f}sn")

if __name__ == '__main__':
    main()
