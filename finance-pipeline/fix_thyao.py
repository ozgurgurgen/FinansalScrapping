"""
THYAO için tüm null verileri doldur.
yfinance + hesaplanan alanlar + KAP API.
"""
import sys, io, psycopg2, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_URL = 'postgresql://admin:admin123@localhost:5432/finance_platform'

def fix_thyao():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # THYAO company_id
    cur.execute("SELECT id FROM kap_companies WHERE ticker='THYAO'")
    cid = cur.fetchone()[0]
    print(f"THYAO company_id: {cid}")
    
    # ═══════════════════════════════════════════════════════════
    # 1) yfinance ile güncel veri çek
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("1) yfinance ile güncel veri")
    print("=" * 60)
    
    try:
        import yfinance as yf
        stock = yf.Ticker("THYAO.IS")
        info = stock.info
        
        price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        pe = info.get('trailingPE')
        pb = info.get('priceToBook')
        market_cap = info.get('marketCap')
        sector = info.get('sector')
        industry = info.get('industry')
        div_yield = info.get('dividendYield')
        eps = info.get('trailingEps')
        
        print(f"  Fiyat: {price} TL")
        print(f"  F/K: {pe}")
        print(f"  PD/DD: {pb}")
        print(f"  Piyasa Değeri: {market_cap:,.0f} TL" if market_cap else "  Piyasa Değeri: yok")
        print(f"  Sektör: {sector}")
        print(f"  Sektör Detayı: {industry}")
        print(f"  Temettü Verimi: {div_yield}")
        print(f"  Fiyat/Kazanç (EPS): {eps}")
        
        # Sektör güncelle
        if sector:
            cur.execute("UPDATE kap_companies SET sector=%s WHERE id=%s", (sector, cid))
        
        # bist_stock_prices güncelle
        if price and price > 0:
            cur.execute("""
                INSERT INTO bist_stock_prices (ticker, price, market_cap, pe_ratio, pb_ratio, updated_at)
                VALUES ('THYAO', %s, %s, %s, %s, NOW())
                ON CONFLICT (ticker) DO UPDATE SET
                    price=EXCLUDED.price, market_cap=EXCLUDED.market_cap,
                    pe_ratio=EXCLUDED.pe_ratio, pb_ratio=EXCLUDED.pb_ratio, updated_at=NOW()
            """, (price, market_cap, pe, pb))
        
        # Finansal tabloları güncelle (en son dönem)
        if pe and pe > 0:
            cur.execute("UPDATE kap_financials SET pe_ratio=%s WHERE company_id=%s AND year='2026' AND period='6'", (pe, cid))
        if pb and pb > 0:
            cur.execute("UPDATE kap_financials SET pb_ratio=%s WHERE company_id=%s AND year='2026' AND period='6'", (pb, cid))
        
    except Exception as e:
        print(f"  ❌ yfinance hatası: {e}")
    
    # ═══════════════════════════════════════════════════════════
    # 2) Tüm dönemler için oranları hesapla
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("2) Finansal oranları hesapla")
    print("=" * 60)
    
    # Tüm THYAO satırlarını al
    cur.execute("""
        SELECT id, year, period, revenue, gross_profit, ebit, ebitda, net_profit,
               total_assets, total_debts, equity, current_ratio
        FROM kap_financials WHERE company_id=%s ORDER BY year DESC, period DESC
    """, (cid,))
    rows = cur.fetchall()
    
    for row in rows:
        fid, year, period, revenue, gp, ebit, ebitda, np, ta, td, eq, cr = row
        
        updates = {}
        
        # gross_margin
        if revenue and revenue > 0 and gp:
            updates['gross_margin'] = round(gp / revenue * 100, 2)
        
        # net_margin
        if revenue and revenue > 0 and np:
            updates['net_margin'] = round(np / revenue * 100, 2)
        
        # ebitda_margin (sadece makul)
        if revenue and revenue > 0 and ebitda and ebitda > 0 and ebitda < revenue * 5:
            updates['ebitda_margin'] = round(ebitda / revenue * 100, 2)
        
        # roe
        if eq and eq > 0 and np:
            updates['roe'] = round(np / eq * 100, 4)
        
        # roa
        if ta and ta > 0 and np:
            updates['roa'] = round(np / ta * 100, 4)
        
        # leverage
        if ta and ta > 0 and td:
            updates['leverage_ratio'] = round(td / ta, 4)
        
        # net_debt
        if td:
            updates['net_debt'] = td  # Nakit verisi olmadığı için sadece borç
        
        if updates:
            set_clause = ', '.join([f"{k}=%s" for k in updates.keys()])
            values = list(updates.values()) + [fid]
            cur.execute(f"UPDATE kap_financials SET {set_clause} WHERE id=%s", values)
            print(f"  ✅ {year}/{period}: {', '.join(updates.keys())}")
    
    # ═══════════════════════════════════════════════════════════
    # 3) KAP API'den finansal detay çek (mümkünse)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("3) KAP API'den finansal detay")
    print("=" * 60)
    
    try:
        # KAP'ın finansal tablo API'si
        url = "https://www.kap.org.tr/tr/api/mkkMembers/detail/THYAO"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        
        if 'financials' in data:
            for fin in data['financials']:
                year = str(fin.get('year', ''))
                period = str(fin.get('period', ''))
                
                # current_assets
                ca = fin.get('donenVarliklar') or fin.get('currentAssets')
                if ca:
                    cur.execute("""
                        UPDATE kap_financials SET current_assets=%s 
                        WHERE company_id=%s AND year=%s AND period=%s AND current_assets IS NULL
                    """, (ca, cid, year, period))
                    print(f"  ✅ {year}/{period}: current_assets={ca}")
                
                # cash
                cash = fin.get('nakitVeNakitBenzerleri') or fin.get('cashAndEquivalents')
                if cash:
                    cur.execute("""
                        UPDATE kap_financials SET cash_and_equivalents=%s 
                        WHERE company_id=%s AND year=%s AND period=%s AND cash_and_equivalents IS NULL
                    """, (cash, cid, year, period))
                    print(f"  ✅ {year}/{period}: cash={cash}")
                
                # financial_debt
                fd = fin.get('finansalBorclar') or fin.get('financialDebt')
                if fd:
                    cur.execute("""
                        UPDATE kap_financials SET financial_debt=%s, total_debt=%s 
                        WHERE company_id=%s AND year=%s AND period=%s AND financial_debt IS NULL
                    """, (fd, fd, cid, year, period))
                    print(f"  ✅ {year}/{period}: financial_debt={fd}")
        
        print(f"  KAP API yanıt anahtarları: {list(data.keys())[:10]}")
        
    except Exception as e:
        print(f"  ⚠️ KAP API hatası: {e}")
    
    # ═══════════════════════════════════════════════════════════
    # 4) KAP Bildirimleri çek
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("4) KAP Bildirimleri")
    print("=" * 60)
    
    try:
        url = "https://www.kap.org.tr/tr/api/disclosure/company/THYAO"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        
        if isinstance(data, list):
            count = 0
            for disc in data[:50]:
                disc_id = disc.get('disclosureId') or disc.get('disclosure_id')
                title = disc.get('title', '')
                pub_date = disc.get('publishDate')
                
                if disc_id:
                    cur.execute("""
                        INSERT INTO kap_disclosures (disclosure_id, company_id, symbol, title, publish_date, source_url)
                        VALUES (%s, %s, 'THYAO', %s, %s, %s)
                        ON CONFLICT (disclosure_id) DO NOTHING
                    """, (disc_id, cid, title, pub_date, f"https://www.kap.org.tr/tr/Bildirim/{disc_id}"))
                    count += 1
            
            conn.commit()
            print(f"  ✅ {count} bildirim kaydedildi")
        else:
            print(f"  Yanıt: {type(data)} — {str(data)[:100]}")
    
    except Exception as e:
        print(f"  ⚠️ KAP Bildirim hatası: {e}")
    
    conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # SONUÇ
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("THYAO SONUÇ")
    print("=" * 60)
    
    cur.execute("SELECT sector FROM kap_companies WHERE id=%s", (cid,))
    print(f"  Sektör: {cur.fetchone()[0]}")
    
    cur.execute("""
        SELECT year, period, revenue, pe_ratio, pb_ratio, roe, gross_margin, net_margin, 
               leverage_ratio, current_assets, cash_and_equivalents, financial_debt, net_debt
        FROM kap_financials WHERE company_id=%s ORDER BY year DESC LIMIT 2
    """, (cid,))
    for r in cur.fetchall():
        print(f"  {r[0]}/{r[1]}:")
        print(f"    Gelir: {r[2]}, F/K: {r[3]}, PD/DD: {r[4]}")
        print(f"    ROE: {r[5]}, Brüt Marj: {r[6]}, Net Marj: {r[7]}")
        print(f"    Kaldıraç: {r[8]}")
        print(f"    Dönen Varlık: {r[9]}, Nakit: {r[10]}, Finansal Borç: {r[11]}, Net Borç: {r[12]}")
    
    cur.execute("SELECT count(*) FROM kap_disclosures WHERE company_id=%s", (cid,))
    print(f"  Bildirim sayısı: {cur.fetchone()[0]}")
    
    conn.close()
    print("\n✅ THYAO düzeltmesi tamamlandı!")

if __name__ == "__main__":
    fix_thyao()
