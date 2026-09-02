"""
Tüm tablolardaki company_id eşleştirmelerini düzeltir.
"""
import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def fix_all():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # ═══════════════════════════════════════════════════════════
    # A) KAP_DISCLOSURES - symbol üzerinden company_id düzelt
    # ═══════════════════════════════════════════════════════════
    print("=" * 60)
    print("A) kap_disclosures company_id düzelt")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_disclosures d
        SET company_id = c.id
        FROM kap_companies c
        WHERE UPPER(d.symbol) = UPPER(c.ticker)
        AND (d.company_id IS NULL OR d.company_id = 0 OR d.company_id != c.id)
    """)
    print(f"  ✅ {cur.rowcount} bildirim düzeltildi")
    
    # disclosure_details - ticker düzelt
    cur.execute("""
        UPDATE disclosure_details dd
        SET ticker = UPPER(d.symbol)
        FROM kap_disclosures d
        WHERE dd.disclosure_index = d.disclosure_id
        AND (dd.ticker IS NULL OR dd.ticker = '')
    """)
    print(f"  ✅ {cur.rowcount} bildirim detayı düzeltildi")
    
    # ═══════════════════════════════════════════════════════════
    # B) KAP_SHAREHOLDERS - disclosure_id üzerinden eşleştir
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("B) kap_shareholders company_id düzelt")
    print("=" * 60)
    
    # disclosure_id ile eşleştir
    cur.execute("""
        UPDATE kap_shareholders sh
        SET company_id = d.company_id
        FROM kap_disclosures d
        WHERE sh.disclosure_id = d.disclosure_id
        AND d.company_id IS NOT NULL AND d.company_id > 0
        AND (sh.company_id IS NULL OR sh.company_id = 0)
    """)
    print(f"  ✅ {cur.rowcount} ortaklık düzeltildi (disclosure_id)")
    
    # ═══════════════════════════════════════════════════════════
    # C) KAP_MANAGEMENT - disclosure_id üzerinden eşleştir
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("C) kap_management company_id düzelt")
    print("=" * 60)
    
    # disclosure_id ile eşleştir
    cur.execute("""
        UPDATE kap_management m
        SET company_id = d.company_id
        FROM kap_disclosures d
        WHERE m.disclosure_id = d.disclosure_id
        AND d.company_id IS NOT NULL AND d.company_id > 0
        AND (m.company_id IS NULL OR m.company_id = 0)
    """)
    print(f"  ✅ {cur.rowcount} yönetim düzeltildi (disclosure_id)")
    
    # ═══════════════════════════════════════════════════════════
    # D) SHAREHOLDERS (genişletilmiş tablo) - disclosure_id ile
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("D) shareholders company_id düzelt")
    print("=" * 60)
    
    cur.execute("""
        UPDATE shareholders sh
        SET company_id = d.company_id
        FROM kap_disclosures d
        WHERE sh.disclosure_id = d.disclosure_id
        AND d.company_id IS NOT NULL AND d.company_id > 0
        AND (sh.company_id IS NULL OR sh.company_id = 0)
    """)
    print(f"  ✅ {cur.rowcount} ortaklık düzeltildi")
    
    # ═══════════════════════════════════════════════════════════
    # E) MANAGEMENT_MEMBERS - disclosure_id ile
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("E) management_members company_id düzelt")
    print("=" * 60)
    
    cur.execute("""
        UPDATE management_members mm
        SET company_id = d.company_id
        FROM kap_disclosures d
        WHERE mm.disclosure_id = d.disclosure_id
        AND d.company_id IS NOT NULL AND d.company_id > 0
        AND (mm.company_id IS NULL OR mm.company_id = 0)
    """)
    print(f"  ✅ {cur.rowcount} yönetim üyesi düzeltildi")
    
    conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # SONUÇ KONTROL
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("SONUÇ KONTROL - THYAO")
    print("=" * 60)
    
    cur.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    thyao_id = cur.fetchone()
    if thyao_id:
        for table in ['kap_disclosures', 'kap_shareholders', 'kap_management', 'kap_subsidiaries']:
            cur.execute(f"SELECT count(*) FROM {table} WHERE company_id={thyao_id[0]}")
            cnt = cur.fetchone()[0]
            status = "✅" if cnt > 0 else "❌"
            print(f"  {status} {table}: {cnt} kayıt")
    
    print("\n📊 GENEL DURUM:")
    for table, label in [
        ('kap_disclosures', 'Bildirimler'),
        ('kap_shareholders', 'Ortaklar'),
        ('kap_management', 'Yönetim'),
        ('kap_subsidiaries', 'Bağlı Ortaklıklar'),
    ]:
        cur.execute(f"SELECT count(*) FROM {table} WHERE company_id IS NOT NULL AND company_id > 0")
        with_id = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {table}")
        total = cur.fetchone()[0]
        pct = (with_id/total*100) if total > 0 else 0
        print(f"  {label}: {with_id}/{total} ({pct:.0f}%)")
    
    conn.close()
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    fix_all()
