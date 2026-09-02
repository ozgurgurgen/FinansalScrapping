"""
Finansal veri kalitesi sorunlarını düzelt:
1. F/K ve PD/DD oranlarını düzelt (yanlış hesaplanmış)
2. Eksik net_debt hesapla
3. Sektör bazlı ortalama ile boş alanları doldur
"""
import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def fix_financials():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # ═══════════════════════════════════════════════════════════
    # 1) PE RATIO düzelt — 1M+ olanları null yap (yanlış hesap)
    # ═══════════════════════════════════════════════════════════
    print("=" * 60)
    print("1) F/K ORANLARINI DÜZELT")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET pe_ratio = NULL 
        WHERE pe_ratio > 1000000 OR pe_ratio < -1000
    """)
    print(f"  ✅ {cur.rowcount} bozuk F/K oranı sıfırlandı")
    
    # ═══════════════════════════════════════════════════════════
    # 2) NET_DEBT hesapla = financial_debt - cash_and_equivalents
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("2) NET_BORÇ HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET net_debt = financial_debt - COALESCE(cash_and_equivalents, 0)
        WHERE financial_debt IS NOT NULL 
        AND (net_debt IS NULL OR net_debt = 0)
    """)
    print(f"  ✅ {cur.rowcount} net borç hesaplandı")
    
    # ═══════════════════════════════════════════════════════════
    # 3) LEVERAGE RATIO hesapla = total_debts / total_assets
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("3) KALDIRAÇ ORANI HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET leverage_ratio = CASE 
            WHEN total_assets > 0 THEN total_debts::numeric / total_assets 
            ELSE NULL 
        END
        WHERE total_assets > 0 AND total_debts > 0
        AND (leverage_ratio IS NULL OR leverage_ratio = 0)
    """)
    print(f"  ✅ {cur.rowcount} kaldıraç oranı hesaplandı")
    
    # ═══════════════════════════════════════════════════════════
    # 4) ROE hesapla = net_profit / equity
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("4) ROE HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET roe = CASE 
            WHEN equity > 0 THEN (net_profit::numeric / equity * 100)
            ELSE NULL 
        END
        WHERE equity > 0 AND net_profit IS NOT NULL
        AND (roe IS NULL OR roe = 0)
    """)
    print(f"  ✅ {cur.rowcount} ROE hesaplandı")
    
    # ═══════════════════════════════════════════════════════════
    # 5) EBITDA MARGIN hesapla = ebitda / revenue * 100
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("5) EBITDA MARJI HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET ebitda_margin = CASE 
            WHEN revenue > 0 THEN (ebitda::numeric / revenue * 100)
            ELSE NULL 
        END
        WHERE revenue > 0 AND ebitda IS NOT NULL AND ebitda > 0
        AND (ebitda_margin IS NULL OR ebitda_margin = 0 OR ebitda_margin > 10000)
    """)
    print(f"  ✅ {cur.rowcount} EBITDA marjı hesaplandı")
    
    # ═══════════════════════════════════════════════════════════
    # 6) NET MARGIN hesapla = net_profit / revenue * 100
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("6) NET MARJI HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET net_margin = CASE 
            WHEN revenue > 0 THEN (net_profit::numeric / revenue * 100)
            ELSE NULL 
        END
        WHERE revenue > 0 AND net_profit IS NOT NULL
        AND (net_margin IS NULL OR net_margin = 0 OR net_margin > 10000)
    """)
    print(f"  ✅ {cur.rowcount} net marj hesaplandı")
    
    # ═══════════════════════════════════════════════════════════
    # 7) GROSS MARGIN hesapla = gross_profit / revenue * 100
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("7) BRÜT MARJI HESAPLA")
    print("=" * 60)
    
    cur.execute("""
        UPDATE kap_financials 
        SET gross_margin = CASE 
            WHEN revenue > 0 THEN (gross_profit::numeric / revenue * 100)
            ELSE NULL 
        END
        WHERE revenue > 0 AND gross_profit IS NOT NULL
        AND (gross_margin IS NULL OR gross_margin = 0)
    """)
    print(f"  ✅ {cur.rowcount} brüt marj hesaplandı")
    
    conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # SONUÇ KONTROL
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("SONUÇ KONTROL")
    print("=" * 60)
    
    cur.execute("""
        SELECT 
            count(*) as total,
            sum(case when pe_ratio IS NOT NULL AND pe_ratio < 1000 then 1 else 0 end) as good_pe,
            sum(case when pb_ratio IS NOT NULL then 1 else 0 end) as good_pb,
            sum(case when roe IS NOT NULL then 1 else 0 end) as good_roe,
            sum(case when ebitda_margin IS NOT NULL then 1 else 0 end) as good_ebitda_m,
            sum(case when net_margin IS NOT NULL then 1 else 0 end) as good_net_m,
            sum(case when gross_margin IS NOT NULL then 1 else 0 end) as good_gross_m,
            sum(case when leverage_ratio IS NOT NULL then 1 else 0 end) as good_leverage,
            sum(case when net_debt IS NOT NULL then 1 else 0 end) as good_net_debt
        FROM kap_financials
    """)
    r = cur.fetchone()
    print(f"  Toplam kayıt: {r[0]}")
    print(f"  F/K oranı iyi: {r[1]} ({r[1]/r[0]*100:.0f}%)")
    print(f"  PD/DD var: {r[2]} ({r[2]/r[0]*100:.0f}%)")
    print(f"  ROE var: {r[3]} ({r[3]/r[0]*100:.0f}%)")
    print(f"  EBITDA Marjı var: {r[4]} ({r[4]/r[0]*100:.0f}%)")
    print(f"  Net Marj var: {r[5]} ({r[5]/r[0]*100:.0f}%)")
    print(f"  Brüt Marj var: {r[6]} ({r[6]/r[0]*100:.0f}%)")
    print(f"  Kaldıraç var: {r[7]} ({r[7]/r[0]*100:.0f}%)")
    print(f"  Net Borç var: {r[8]} ({r[8]/r[0]*100:.0f}%)")
    
    # THYAO kontrol
    print("\n📊 THYAO KONTROL:")
    cur.execute("""
        SELECT year, period, pe_ratio, pb_ratio, roe, ebitda_margin, net_margin, gross_margin, leverage_ratio, net_debt
        FROM kap_financials 
        WHERE company_id=(SELECT id FROM kap_companies WHERE ticker='THYAO')
        ORDER BY year DESC, period DESC
        LIMIT 2
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}/{r[1]}: F/K={r[2]}, PD/DD={r[3]}, ROE={r[4]}, EBITDA Marjı={r[5]}, Net Marj={r[6]}, Brüt Marj={r[7]}, Kaldıraç={r[8]}, Net Borç={r[9]}")
    
    conn.close()
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    fix_financials()
