"""
Finance Pipeline API Client
Bu dosyayı diğer web uygulamasına import ederek verilere erişebilirsin.

Kullanım:
    from api_client import FinanceClient
    
    client = FinanceClient()  # default: http://localhost:3000
    
    # Tüm şirketleri listele
    companies = client.get_companies()
    
    # Bir şirketin tüm verileri
    thyao = client.get_all("THYAO")
    
    # Finansal veriler
    fins = client.get_financials("ASELS")
    
    # Arama
    results = client.search("Garanti")
    
    # Fon listesi
    funds = client.get_funds(limit=500)
    
    # Fon detay
    fund = client.get_fund("TCD")
    
    # CSV indir
    client.download_csv("kap_companies", "sirketler.csv")
    
    # PostgreSQL'e direkt bağlan
    df = client.to_dataframe("SELECT * FROM kap_financials WHERE year=2025")
"""

import requests
import json
import csv
import io
from typing import Optional, Dict, List, Any


class FinanceClient:
    """Finance Pipeline API istemcisi."""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def _get(self, path: str, **params) -> Any:
        """Genel GET isteği."""
        r = self.session.get(f"{self.base_url}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def _get_raw(self, path: str) -> requests.Response:
        """Ham yanıt döndürür (CSV indirme için)."""
        r = self.session.get(f"{self.base_url}{path}", timeout=60)
        r.raise_for_status()
        return r
    
    # ─── Schema ───────────────────────────────────────────────────────────
    
    def get_schema(self) -> Dict:
        """Veritabanı şemasını döndürür."""
        return self._get("/api/export/schema")
    
    # ─── Şirketler ────────────────────────────────────────────────────────
    
    def get_companies(self) -> List[Dict]:
        """Tüm şirketlerin listesini döndürür."""
        return self._get("/api/export/companies")
    
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Ticker veya şirket adına göre arama."""
        return self._get("/api/export/search", q=query, limit=limit)
    
    # ─── Finansal Veriler ─────────────────────────────────────────────────
    
    def get_financials(self, ticker: str) -> Dict:
        """Bir şirketin tüm dönem finansal verileri."""
        return self._get(f"/api/export/financials/{ticker.upper()}")
    
    def get_all(self, ticker: str) -> Dict:
        """Bir varlığın TÜM verileri tek JSON'da."""
        return self._get(f"/api/export/all/{ticker.upper()}")
    
    # ─── TEFAS Fonları ───────────────────────────────────────────────────
    
    def get_funds(self, limit: int = 100) -> List[Dict]:
        """TEFAS fon listesi."""
        return self._get("/api/export/funds", limit=limit)
    
    def get_fund(self, code: str) -> Dict:
        """Bir fonun detayı + fiyat geçmişi."""
        return self._get(f"/api/export/fund/{code.upper()}")
    
    # ─── CSV Export ───────────────────────────────────────────────────────
    
    def download_csv(self, table: str, save_path: Optional[str] = None) -> str:
        """Tabloyu CSV olarak indirir. save_path verilmezse string olarak döndürür."""
        r = self._get_raw(f"/api/export/csv/{table}")
        if save_path:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return save_path
        return r.text
    
    def csv_to_list(self, table: str) -> List[Dict]:
        """CSV'yi Dict listesine çevirir."""
        r = self._get_raw(f"/api/export/csv/{table}")
        reader = csv.DictReader(io.StringIO(r.text))
        return list(reader)
    
    # ─── Pandas DataFrame ─────────────────────────────────────────────────
    
    def to_dataframe(self, query: str = None, table: str = None):
        """
        SQL sorgusu veya tablo adı ile DataFrame döndürür.
        pandas ve psycopg2 gerekli.
        """
        import pandas as pd
        
        if table:
            return pd.read_sql_table(table, "postgresql://admin:admin123@localhost:5432/finance_platform")
        elif query:
            return pd.read_sql_query(query, "postgresql://admin:admin123@localhost:5432/finance_platform")
        else:
            raise ValueError("query veya table parametresi gerekli")
    
    # ─── Toplu Export ─────────────────────────────────────────────────────
    
    def export_all_companies(self, save_path: str = "all_companies.json"):
        """Tüm şirketlerin tüm verilerini JSON'a export eder."""
        companies = self.get_companies()
        all_data = {}
        for co in companies:
            ticker = co["ticker"]
            all_data[ticker] = self.get_all(ticker)
            print(f"✓ {ticker}")
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        print(f"Toplam {len(all_data)} şirket kaydedildi: {save_path}")
        return all_data
    
    # ─── Pratik Sorgular ─────────────────────────────────────────────────
    
    def get_top_profitable(self, limit: int = 10) -> List[Dict]:
        """En kârlı şirketleri döndürür."""
        companies = self.get_companies()
        results = []
        for co in companies:
            try:
                fin = self.get_financials(co["ticker"])
                if fin["financials"]:
                    latest = fin["financials"][0]
                    if latest.get("net_margin") and latest["net_margin"] > 0:
                        results.append({
                            "ticker": co["ticker"],
                            "name": co["company_name"],
                            "sector": co["sector"],
                            "net_margin": latest["net_margin"],
                            "roe": latest.get("roe", 0),
                            "pe_ratio": latest.get("pe_ratio", 0),
                            "revenue": latest.get("revenue", 0),
                        })
            except Exception:
                continue
        
        results.sort(key=lambda x: x["net_margin"], reverse=True)
        return results[:limit]


# ─── Kullanım Örnekleri ───────────────────────────────────────────────────

if __name__ == "__main__":
    client = FinanceClient()
    
    # Test
    companies = client.get_companies()
    print(f"Toplam {len(companies)} şirket")
    
    # THYAO tüm veriler
    thyao = client.get_all("THYAO")
    print(f"\nTHYAO:")
    print(f"  Finansal dönem: {len(thyao['financials'])}")
    print(f"  Bildirim: {len(thyao['disclosures'])}")
    print(f"  Ortak: {len(thyao['shareholders'])}")
    print(f"  YK: {len(thyao['management'])}")
    print(f"  Bağlı Ortaklık: {len(thyao['subsidiaries'])}")
    
    # En kârlı 5 şirket
    top = client.get_top_profitable(5)
    print("\nEn Kârlı 5 Şirket:")
    for co in top:
        print(f"  {co['ticker']}: %{co['net_margin']*100:.1f} net marj")
    
    # Fon listesi
    funds = client.get_funds(10)
    print(f"\nİlk 10 fon:")
    for f in funds:
        print(f"  {f['code']}: {f['title']} ({f['kind']})")
