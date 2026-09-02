# 🔌 Finance Pipeline API Kılavuzu

> **Base URL:** `http://localhost:3000` veya `https://bobby-layout-circles-reform.trycloudflare.com`
> 
> **Toplam:** 10 Endpoint | 43 Tablo | 574 Sütun | 2.2M+ Kayıt

---

## 📋 ENDPOINT LİSTESİ

### 1️⃣ `GET /api/export/companies` — Şirket Listesi
**Açıklama:** BIST'te işlem gören tüm şirketlerin listesi

**Dönen Veri:**
```json
{
  "id": 1,
  "ticker": "THYAO",
  "company_name": "TÜRK HAVA YOLLARI A.Ş.",
  "sector": "Ulaştırma",
  "market": "BIST"
}
```

**Sütunlar:** id, ticker, company_name, sector, market
**Kayıt Sayısı:** 1,014 şirket

---

### 2️⃣ `GET /api/export/search?q={query}` — Şirket Arama
**Açıklama:** Ticker veya şirket adına göre arama

**Parametreler:**
- `q` (zorunlu): Arama terimi (ör: THY, THYAO, Turk Hava)
- `limit` (opsiyonel): Maksimum sonuç (varsayılan: 20)

**Örnek:** `GET /api/export/search?q=THYAO`
```json
[
  {"id": 1, "ticker": "THYAO", "company_name": "TÜRK HAVA YOLLARI A.Ş.", "sector": "Ulaştırma"}
]
```

---

### 3️⃣ `GET /api/export/all/{ticker}` — Bir Varlığın Tüm Verileri
**Açıklama:** Bir şirketin/tenkilin TÜM verilerini tek JSON'da döndürür. **En kapsamlı endpoint.**

**Parametreler:**
- `ticker` (zorunlu): Hisse kodu (ör: THYAO, GARAN, ASELS)

**Dönen Veri Setleri:**

| Veri Seti | İçerik | Kayıt |
|-----------|--------|-------|
| **company** | Şirket bilgisi (ticker, sektör, MKK ID) | 1 |
| **financials** | Gelir, kâr, EBITDA, F/K, PD/DD, ROE, ROA, marjlar, oranlar — **36 sütun** | 1-10 dönem |
| **disclosures** | Son 50 KAP bildirimi (başlık, tarih, kategori, link) | max 50 |
| **shareholders** | Pay sahipleri + oranları + oy hakları | tümü |
| **management** | Yönetim kurulu üyeleri + ünvanları | tümü |
| **subsidiaries** | Bağlı ortaklıklar + % payları | tümü |
| **cashflows** | Operasyonel/yatırım/finansman nakit akışları — **24 sütun** | tüm dönemler |

**Örnek:** `GET /api/export/all/THYAO`

---

### 4️⃣ `GET /api/export/financials/{ticker}` — Finansal Tablolar
**Açıklama:** Bir şirketin tüm finansal verilerini döndürür

**Parametreler:**
- `ticker` (zorunlu): Hisse kodu

**Dönen Alanlar (36 sütun):**

| Kategori | Alanlar |
|----------|---------|
| **Gelir Tablosu** | revenue (hasılat), gross_profit (brüt kâr), ebit, ebitda, net_profit |
| **Bilanço** | total_assets, total_debts, equity, paid_capital |
| **Marjlar** | gross_margin, operating_margin, net_margin, ebitda_margin |
| **Oranlar** | current_ratio, leverage_ratio, roe, roa, pe_ratio, pb_ratio |
| **Piyasa** | fd_ebitda, fd_revenue, market_cap |
| **Büyüme** | revenue_growth_yoy, profit_growth_yoy |
| **Nakit** | cash_and_equivalents, financial_debt, net_debt, current_assets |

---

### 5️⃣ `GET /api/export/funds` — TEFAS Fon Listesi
**Açıklama:** TEFAS'taki tüm yatırım fonlarının listesi

**Parametreler:**
- `limit` (opsiyonel): Maksimum fon (varsayılan: 100)

**Dönen Alanlar:**

| Alan | Açıklama |
|------|----------|
| code | Fon kodu (ör: TCD, GGS, TAU) |
| title | Fon tam adı |
| kind | Fon tipi (YAT=Yatırım, EMK=Emeklilik, BYF=Borsa Yatırım Fonu, DİĞER) |
| current_price | Güncel fiyat (TL) |
| market_cap | Portföy büyüklüğü (TL) |
| investor_count | Yatırımcı sayısı |

**Kayıt Sayısı:** 2,598 fon

---

### 6️⃣ `GET /api/export/fund/{code}` — Fon Detayı + Fiyat Geçmişi
**Açıklama:** Tek bir fondaki detaylı bilgi ve fiyat geçmişi

**Parametreler:**
- `code` (zorunlu): Fon kodu (ör: TCD, GGS, TAU)

**Dönen Veri:**
```json
{
  "fund": {"code": "TAU", "title": "...", "current_price": 0.6509, ...},
  "price_history": [
    {"trade_date": "2026-08-28", "price": 0.6428, "shares_outstanding": ..., "investors_count": ...},
    ...
  ]
}
```

**Fiyat Geçmişi:** Son 5 yıla kadar günlük fiyat, pay adedi, yatırımcı sayısı
**Kayıt Sayısı:** 2,190,736 fiyat kaydı

---

### 7️⃣ `GET /api/export/bulk` — Toplu Export (TÜM Tablolar)
**Açıklama:** TEK istekte tüm tabloları JSON olarak döndürür

**Parametreler:**
- `tables` (opsiyonel): Virgülle ayrılmış tablo listesi
- `limit_per_table` (opsiyonel): Her tabloda maksimum satır

**Dönen Tablolar:**

| Tablo | Kayıt | İçerik |
|-------|-------|--------|
| companies | 1,014 | Şirket listesi |
| financials | 1,387 | Finansal tablolar |
| disclosures | 3,989 | KAP bildirimleri |
| shareholders | 1,153 | Pay sahipleri |
| management | 1,893 | Yönetim kurulu |
| subsidiaries | 1,734 | Bağlı ortaklıklar |
| cashflows | 1,274 | Nakit akış |
| buybacks | 119 | Pay geri alım |
| ipo | 60 | Halka arz |
| funds | 2,598 | TEFAS fonları |
| fund_prices | 2,190,736 | Fon fiyat geçmişi |
| fund_allocations | 2,459 | Fon portföy dağılımı |
| prices | 602 | Güncel hisse fiyatları |
| price_history | 37,641 | Hisse fiyat geçmişi |
| settlement | 602 | Takas/yabancı oranı |
| index | 114 | Endeks bileşenleri |

---

### 8️⃣ `GET /api/export/bulk/csv` — Toplu CSV Export (ZIP)
**Açıklama:** Tüm tabloları CSV olarak tek ZIP dosyasında döndürür

**Parametreler:**
- `tables` (opsiyonel): Hangi tablolar dahil edilecek

**Dönen:** 16 CSV dosyası tek ZIP'te (indirme)

---

### 9️⃣ `GET /api/export/csv/{table}` — Tek Tablo CSV
**Açıklama:** Tek bir tabloyu CSV olarak indir

**Parametreler:**
- `table` (zorunlu): Tablo adı (ör: kap_financials, tefas_funds)

**İzin Verilen Tablolar:**
kap_companies, kap_financials, kap_disclosures, kap_shareholders, kap_management, kap_subsidiaries, kap_cashflows, tefas_funds, bist_stock_prices, bist_price_history, share_buybacks, ipo_data

---

### 🔟 `GET /api/export/schema` — Veritabanı Şeması
**Açıklama:** 43 tablonun tüm sütun bilgilerini döndürür

**Dönen Veri:**
```json
{
  "tables": {
    "kap_financials": [
      {"name": "revenue", "type": "NUMERIC(20,4)"},
      {"name": "gross_profit", "type": "NUMERIC(20,4)"}
    ]
  },
  "total_tables": 43
}
```

---

## 📊 VERİ TABANI TABLO ÖZETİ

| Tablo | Kayıt | Açıklama |
|-------|-------|----------|
| **tefas_fund_prices** | 2,190,736 | TEFAS fon günlük fiyat geçmişi |
| **kap_disclosures** | 3,989 | KAP bildirimleri |
| **assets** | 3,597 | Tüm varlık kayıtları |
| **tefas_funds** | 2,598 | TEFAS fon bilgileri |
| **tefas_fund_allocations** | 2,459 | Fon portföy dağılımı (50+ varlık sınıfı) |
| **kap_management** | 2,056 | Yönetim kurulu üyeleri |
| **disclosure_details** | 2,020 | Bildirim detayları (ihale, blok satış) |
| **subsidiaries** | 1,734 | Bağlı ortaklıklar |
| **management_members** | 1,893 | Yönetim üyeleri (genişletilmiş) |
| **shareholders** | 1,153 | Pay sahipleri |
| **kap_subsidiaries** | 1,157 | Bağlı ortaklıklar (KAP) |
| **companies** | 1,014 | Şirket listesi |
| **kap_companies** | 1,014 | Şirket listesi (KAP) |
| **financials** | 1,387 | Finansal tablolar (36 sütun) |
| **kap_financials** | 1,387 | Finansal tablolar (KAP) |
| **cashflows** | 1,274 | Nakit akış tablosu |
| **kap_cashflows** | 1,274 | Nakit akış (KAP) |
| **bist_price_history** | 37,641 | Hisse fiyat geçmişi |
| **bist_stock_prices** | 602 | Güncel hisse fiyatları |
| **settlement_data** | 602 | Takas/yabancı oranı |
| **share_buybacks** | 119 | Pay geri alım programları |
| **index_constituents** | 114 | Endeks bileşenleri (XU100 vb.) |
| **kap_financial_notes** | 218 | Finansal dipnotlar |
| **kap_portfolio_reports** | 140 | Portföy raporları |
| **ipo_data** | 60 | Halka arz verileri |
| **vap_data** | 67 | VAP verileri (yabancı oranı) |
| **corporate_actions** | 27 | Kurumsal işlemler (temettü/bedelli) |
| **market_indicators** | 16 | Piyasa göstergeleri |
| **market_rates** | 17 | Piyasa kurları (döviz, altın) |
| **fund_stock_holdings** | 793 | Fon hisse senedi holdings |
| **commodity_prices** | 11 | Emtia fiyatları |
| **crypto_prices** | 6 | Kripto fiyatları |
| **pipeline_runs** | 76 | Pipeline çalışma geçmişi |

---

## 🔧 KULLANIM ÖRNEKLERİ

### Python ile
```python
import requests

API = "http://localhost:3000"

# 1. Tüm şirketleri listele
r = requests.get(f"{API}/api/export/companies")
companies = r.json()
print(f"{len(companies)} şirket bulundu")

# 2. THYAO tüm verilerini çek
r = requests.get(f"{API}/api/export/all/THYAO")
data = r.json()
print(f"Finansal: {len(data['financials'])} dönem")
print(f"Bildirim: {len(data['disclosures'])} adet")
print(f"Ortak: {len(data['shareholders'])} adet")

# 3. GARAN finansal verileri
r = requests.get(f"{API}/api/export/financials/GARAN")
fin = r.json()
for f in fin['financials'][:3]:
    print(f"{f['year']}/{f['period']}: Gelir={f['revenue']}, Kâr={f['net_profit']}")

# 4. TEFAS fonlarını çek
r = requests.get(f"{API}/api/export/funds?limit=50")
funds = r.json()
for f in funds[:5]:
    print(f"{f['code']}: {f['current_price']} TL ({f['kind']})")

# 5. Fon detayı + fiyat geçmişi
r = requests.get(f"{API}/api/export/fund/TAU")
detail = r.json()
print(f"Fon: {detail['fund']['title']}")
print(f"Fiyat: {detail['fund']['current_price']} TL")
print(f"Günlük kayıt: {len(detail['price_history'])}")

# 6. Toplu export
r = requests.get(f"{API}/api/export/bulk?tables=companies,financials&limit_per_table=5")
bulk = r.json()
print(f"Şirket: {len(bulk['companies'])}, Finansal: {len(bulk['financials'])}")

# 7. Schema (hangi tablolarda ne var)
r = requests.get(f"{API}/api/export/schema")
schema = r.json()
for table, cols in schema['tables'].items():
    print(f"{table}: {len(cols)} sütun")
```

### JavaScript ile
```javascript
const API = "http://localhost:3000";

// Şirket ara
const res = await fetch(`${API}/api/export/search?q=THYAO`);
const data = await res.json();
console.log(data);

// Tüm veriler
const all = await fetch(`${API}/api/export/all/THYAO`);
const allData = await all.json();
console.log(allData.financials);

// Fon detayı
const fund = await fetch(`${API}/api/export/fund/TAU`);
const fundData = await fund.json();
console.log(fundData.fund.current_price);
```

### cURL ile
```bash
# Tüm şirketler
curl http://localhost:3000/api/export/companies

# THYAO tüm veriler
curl http://localhost:3000/api/export/all/THYAO

# Fon detayı
curl http://localhost:3000/api/export/fund/TAU

# Toplu export
curl http://localhost:3000/api/export/bulk

# CSV indir
curl -o financials.csv http://localhost:3000/api/export/csv/kap_financials
```

---

## 🌐 Erişim Adresleri

| Erişim | URL |
|--------|-----|
| **Local** | `http://localhost:3000` |
| **Public** | `https://bobby-layout-circles-reform.trycloudflare.com` |
| **Swagger** | `http://localhost:3000/docs` |
| **ReDoc** | `http://localhost:3000/redoc` |

---

## 🔑 API Key Authentication

Export endpoint'leri API key gerektirebilir:

```bash
# Header ile
curl -H "X-API-Key: fbkey-..." http://localhost:3000/api/export/companies

# Bearer token ile
curl -H "Authorization: Bearer fbkey-..." http://localhost:3000/api/export/companies

# Query parametresi ile
curl "http://localhost:3000/api/export/companies?api_key=fbkey-..."
```

Dashboard UI endpoint'leri (/, /api/stats, /api/containers) API key gerektirmez.

---

## ⚠️ Notlar

1. **Rate Limiting:** Çoklu isteklerde 429 hatası alabilirsiniz. İstekler arasında 1-2sn bekleyin.
2. **Büyük Veri:** `/api/export/bulk` 2M+ satır döndürebilir. `limit_per_table` kullanarak küçültebilirsiniz.
3. **İlişkisel Veri:** Her veri bir varlık koduna (ticker) bağlıdır. THYAO'ya ait tüm veriler `/api/export/all/THYAO` ile tek seferde alınabilir.
4. **Fiyat Geçmişi:** TEFAS fon fiyatları 5 yıla kadar, BIST hisse fiyatları 1 yıla kadar mevcuttur.
5. **Güncelleme:** Veriler periyodik olarak otomatik güncellenir. Son güncelleme zamanı `/api/tunnel-status` endpoint'inden kontrol edilebilir.
