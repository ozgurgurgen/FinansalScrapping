# 🏦 Finance Pipeline — REST API Dökümanı

> **Base URL:** `http://localhost:3000`
> **Veritabanı:** PostgreSQL `finance_platform`
> **Toplam Tablo:** 43 | **Toplam Kayıt:** 2.2M+

---

## 📋 İçindekiler

1. [Hızlı Başlangıç](#hızlı-başlangıç)
2. [Veritabanı Şeması](#veritabanı-şeması)
3. [Export API Endpoint'leri](#export-api-endpointleri)
4. [Veri Tabloları](#veri-tabloları)
5. [Kullanım Örnekleri](#kullanım-örnekleri)

---

## 1. Hızlı Başlangıç

### Doğrudan PostgreSQL Bağlantısı
```
Host:     localhost
Port:     5432
Database: finance_platform
User:     admin
Password: admin123
URL:      postgresql://admin:admin123@localhost:5432/finance_platform
```

### Python ile Bağlantı
```python
import psycopg2
conn = psycopg2.connect("postgresql://admin:admin123@localhost:5432/finance_platform")
# veya SQLAlchemy
from sqlalchemy import create_engine
engine = create_engine("postgresql://admin:admin123@localhost:5432/finance_platform")
```

### JavaScript/Node.js ile Bağlantı
```javascript
const { Pool } = require('pg');
const pool = new Pool({
  host: 'localhost', port: 5432,
  database: 'finance_platform', user: 'admin', password: 'admin123'
});
```

---

## 2. Veritabanı Şeması

| # | Tablo | Kayıt | Açıklama |
|---|-------|-------|----------|
| 1 | `kap_companies` | 1,014 | BIST şirketleri (ticker, sektör, MKK ID) |
| 2 | `kap_financials` | 1,387 | Çeyreklik/yıllık finansal tablolar |
| 3 | `kap_disclosures` | 3,989 | KAP bildirimleri (tarih, kategori, link) |
| 4 | `kap_disclosure_details` | 2,020 | Bildirim detayları (ihale, blok satış) |
| 5 | `kap_shareholders` | 1,014 | Pay sahipleri (isim, oran, oy hakkı) |
| 6 | `kap_management` | 2,056 | Yönetim kurulu üyeleri |
| 7 | `kap_subsidiaries` | 1,157 | Bağlı ortaklıklar (% pay ile) |
| 8 | `kap_cashflows` | 1,274 | Nakit akış tabloları |
| 9 | `kap_financial_notes` | 218 | Finansal dipnotlar |
| 10 | `kap_portfolio_reports` | 58 | Portföy raporları |
| 11 | `kap_corporate_actions` | 27 | Kurumsal işlemler (temettü, sermaye) |
| 12 | `share_buybacks` | 119 | Pay geri alım programları |
| 13 | `ipo_data` | 60 | Halka arz verileri |
| 14 | `bist_stock_prices` | 602 | Güncel hisse fiyatları |
| 15 | `bist_price_history` | 2,190,736 | Günlük fiyat geçmişi |
| 16 | `settlement_data` | 602 | Takas/yabancı oranı verileri |
| 17 | `index_constituents` | 114 | Endeks bileşenleri (XU100, XBANK) |
| 18 | `tefas_funds` | 2,598 | TEFAS fon bilgileri |
| 19 | `tefas_fund_prices` | 2,159,021 | Fon fiyat geçmişi |
| 20 | `tefas_fund_allocations` | 2,459 | Fon portföy dağılımları |
| 21 | `tefas_announcements` | 12 | Fon duyuruları |
| 22 | `vap_data` | 67 | VAP (veri analiz) verileri |
| 23 | `order_backlogs` | — | Sipariş/Ihale backlog |
| 24 | `market_indicators` | — | Piyasa göstergeleri |
| 25 | `pipeline_runs` | — | Pipeline çalıştırma geçmişi |

---

## 3. Export API Endpoint'leri

### 🔍 `GET /api/export/schema`
Tüm tabloların şema bilgisini döndürür (sütun adları + tipleri).

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/schema
```

**Örnek Yanıt:**
```json
{
  "tables": {
    "kap_companies": [
      {"name": "id", "type": "BIGINT"},
      {"name": "ticker", "type": "VARCHAR(10)"},
      {"name": "company_name", "type": "VARCHAR(255)"},
      {"name": "sector", "type": "VARCHAR(100)"},
      {"name": "market", "type": "VARCHAR(20)"},
      {"name": "mkk_id", "type": "VARCHAR(100)"}
    ],
    "kap_financials": [
      {"name": "company_id", "type": "BIGINT"},
      {"name": "year", "type": "BIGINT"},
      {"name": "period", "type": "BIGINT"},
      {"name": "revenue", "type": "NUMERIC"},
      {"name": "gross_profit", "type": "NUMERIC"},
      {"name": "ebitda", "type": "NUMERIC"},
      {"name": "net_profit", "type": "NUMERIC"},
      {"name": "pe_ratio", "type": "NUMERIC"},
      {"name": "pb_ratio", "type": "NUMERIC"}
    ]
  },
  "total_tables": 43
}
```

**Kullanım:** Diğer uygulamalar bu endpoint'i çağırarak veritabanındaki tüm tabloları ve sütunları keşfedebilir.

---

### 🏢 `GET /api/export/companies`
Tüm BIST şirketlerinin listesini döndürür.

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/companies
```

**Örnek Yanıt:**
```json
[
  {"id": 1, "ticker": "THYAO", "company_name": "Türk Hava Yolları", "sector": "Ulaştırma", "market": "BIST"},
  {"id": 2, "ticker": "ASELS", "company_name": "ASELSAN Elektronik", "sector": "Savunma", "market": "BIST"},
  {"id": 3, "ticker": "GARAN", "company_name": "Garanti Bankası", "sector": "Bankacılık", "market": "BIST"}
]
```

---

### 🔎 `GET /api/export/search?q={sorgu}&limit={n}`
Ticker veya şirket adına göre arama.

**Parametreler:**
| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `q` | ✅ | — | Arama terimi (kısmi eşleşme) |
| `limit` | ❌ | 20 | Maksimum sonuç sayısı |

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/search?q=THY
GET http://localhost:3000/api/export/search?q=banka&limit=10
```

**Örnek Yanıt:**
```json
[
  {"ticker": "THYAO", "company_name": "Türk Hava Yolları A.Ş.", "sector": "Ulaştırma", "market": "BIST"}
]
```

---

### 📊 `GET /api/export/financials/{ticker}`
Belirli bir şirketin tüm dönem finansal verilerini döndürür.

**URL Parametresi:**
| Parametre | Zorunlu | Açıklama |
|-----------|---------|----------|
| `ticker` | ✅ | Hisse kodu (ör: THYAO) |

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/financials/THYAO
GET http://localhost:3000/api/export/financials/ASELS
```

**Örnek Yanıt:**
```json
{
  "ticker": "THYAO",
  "company_name": "Türk Hava Yolları A.Ş.",
  "financials": [
    {
      "id": 101,
      "company_id": 1,
      "year": 2025,
      "period": 6,
      "revenue": 385000000000,
      "gross_profit": 154000000000,
      "ebitda": 88500000000,
      "net_profit": 52000000000,
      "total_assets": 620000000000,
      "total_debts": 380000000000,
      "equity": 240000000000,
      "paid_capital": 12000000000,
      "current_ratio": 1.25,
      "leverage_ratio": 0.61,
      "pe_ratio": 5.2,
      "pb_ratio": 2.1,
      "roe": 0.216,
      "roa": 0.083,
      "gross_margin": 0.40,
      "net_margin": 0.135,
      "ebitda_margin": 0.23
    }
  ]
}
```

**Finansal Sütunlar:**

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `year` | INT | Yıl |
| `period` | INT | Dönem (3,6,9,12=yıllık) |
| `revenue` | NUMERIC | Hasılat / Net Satışlar |
| `gross_profit` | NUMERIC | Brüt Kâr |
| `ebitda` | NUMERIC | FAVÖK |
| `net_profit` | NUMERIC | Net Dönem Kârı |
| `total_assets` | NUMERIC | Toplam Aktifler |
| `total_debts` | NUMERIC | Toplam Borçlar |
| `equity` | NUMERIC | Toplam Özkaynaklar |
| `paid_capital` | NUMERIC | Ödenmiş Sermaye |
| `current_ratio` | NUMERIC | Cari Oran |
| `leverage_ratio` | NUMERIC | Kaldıraç Oranı |
| `pe_ratio` | NUMERIC | Fiyat/Kazanç |
| `pb_ratio` | NUMERIC | Fiyat/Defter |
| `roe` | NUMERIC | Özkaynak Kârlılığı |
| `roa` | NUMERIC | Aktif Kârlılığı |
| `gross_margin` | NUMERIC | Brüt Kâr Marjı |
| `net_margin` | NUMERIC | Net Kâr Marjı |
| `ebitda_margin` | NUMERIC | FAVÖK Marjı |

---

### 🎯 `GET /api/export/all/{ticker}`
Bir varlığın **TÜM** verilerini tek JSON'da döndürür. En kapsamlı endpoint.

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/all/THYAO
```

**Örnek Yanıt Yapısı:**
```json
{
  "ticker": "THYAO",
  "company": {
    "id": 1, "ticker": "THYAO",
    "company_name": "Türk Hava Yolları A.Ş.",
    "sector": "Ulaştırma", "market": "BIST",
    "mkk_id": "12345", "is_active": true
  },
  "financials": [
    {"year": 2025, "period": 6, "revenue": 385000000000, ...},
    {"year": 2024, "period": 12, "revenue": 692000000000, ...}
  ],
  "disclosures": [
    {
      "id": 501, "symbol": "THYAO",
      "title": "2025/6 Aylık Faaliyet Raporu",
      "category": "Finansal_Rapor",
      "publish_date": "2025-08-15T10:00:00",
      "source_url": "https://kap.org.tr/tr/Bildirim/12345"
    }
  ],
  "shareholders": [
    {"name": "Turkey Wealth Fund", "share_percent": 49.12, "vote_right_percent": 49.12},
    {"name": "Yabancı Yatırımcılar", "share_percent": 28.35, "vote_right_percent": 28.35}
  ],
  "management": [
    {"name": "Ahmet Bolat", "title": "Yönetim Kurulu Başkanı", "since": "2021-08-01"},
    {"name": "İlker Aycı", "title": "Yönetim Kurulu Üyesi", "since": "2023-05-15"}
  ],
  "subsidiaries": [
    {"name": "Turkish Technic", "share_percent": 100.0, "type": "subsidiary"},
    {"name": "THY Havacılık Akademisi", "share_percent": 100.0, "type": "subsidiary"}
  ],
  "cashflows": [
    {
      "year": 2025, "period": 6,
      "operating_cf": 45000000000,
      "investing_cf": -22000000000,
      "financing_cf": -15000000000
    }
  ]
}
```

**Dönen Veri Setleri:**
| Alan | Tablo | Maks Kayıt | Açıklama |
|------|-------|-----------|----------|
| `company` | kap_companies | 1 | Şirket temel bilgisi |
| `financials` | kap_financials | ~20 | Finansal tablolar (tüm dönemler) |
| `disclosures` | kap_disclosures | 50 | Son 50 bildirim |
| `shareholders` | kap_shareholders | ~20 | Pay sahipleri |
| `management` | kap_management | ~20 | Yönetim kurulu |
| `subsidiaries` | kap_subsidiaries | ~50 | Bağlı ortaklıklar |
| `cashflows` | kap_cashflows | ~10 | Nakit akış |

---

### 📥 `GET /api/export/csv/{table}`
Tabloyu CSV dosyası olarak indirir.

**İzin Verilen Tablolar:**
`kap_companies`, `kap_financials`, `kap_disclosures`, `kap_shareholders`, `kap_management`, `kap_subsidiaries`, `kap_cashflows`, `tefas_funds`, `bist_stock_prices`, `bist_price_history`, `share_buybacks`, `ipo_data`

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/csv/kap_companies
GET http://localhost:3000/api/export/csv/kap_financials
GET http://localhost:3000/api/export/csv/bist_price_history
```

**Yanıt:** `Content-Type: text/csv` dosya olarak indirilir.

---

### 💰 `GET /api/export/funds`
TEFAS fon listesini döndürür.

**Parametreler:**
| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `limit` | ❌ | 100 | Maksimum fon sayısı |

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/funds
GET http://localhost:3000/api/export/funds?limit=500
```

**Örnek Yanıt:**
```json
[
  {
    "code": "ACD",
    "title": "ACD Fonu",
    "kind": "YAT",
    "current_price": 1.2345,
    "market_cap": 1250000000,
    "investor_count": 15230
  }
]
```

**Fon Tipleri (kind):**
| Kod | Açıklama |
|-----|----------|
| `YAT` | Yatırım Fonu |
| `EMK` | Emeklilik Yatırım Fonu |
| `BYF` | Borsa Yatırım Fonu |

---

### 📈 `GET /api/export/fund/{code}`
Tek bir fonun detaylı bilgisi + fiyat geçmişi.

**Örnek İstek:**
```http
GET http://localhost:3000/api/export/fund/TCD
GET http://localhost:3000/api/export/fund/GGS
```

**Örnek Yanıt:**
```json
{
  "code": "TCD",
  "title": "Turkish Corporate Debt Fund",
  "kind": "YAT",
  "current_price": 1.0456,
  "market_cap": 890000000,
  "investor_count": 3420,
  "price_history": [
    {
      "date": "2025-01-02",
      "price": 1.0234,
      "market_cap": 870000000,
      "investors_count": 3380
    },
    {
      "date": "2025-01-03",
      "price": 1.0267,
      "market_cap": 875000000,
      "investors_count": 3395
    }
  ]
}
```

---

## 4. Veri Tabloları (Detaylı)

### `kap_companies` — Şirket Ana Tablosu

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `id` | BIGINT | Benzersiz ID (PRIMARY KEY) |
| `ticker` | VARCHAR(10) | Hisse kodu (THYAO, ASELS, vb.) |
| `mkk_id` | VARCHAR(100) | MKK üye ID'si |
| `company_name` | TEXT | Şirket tam adı |
| `sector` | VARCHAR(100) | Sektör (Gıda, Bankacılık, vb.) |
| `market` | VARCHAR(20) | Piyasa (BIST, XBANK, XU100) |
| `is_active` | BOOLEAN | Aktif mi? |

### `kap_financials` — Finansal Tablolar

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY → kap_companies.id |
| `year` | INT | Yıl |
| `period` | INT | Dönem (3=Q1, 6=Q2, 9=Q3, 12=Yıllık) |
| `revenue` | NUMERIC | Hasılat (TL) |
| `gross_profit` | NUMERIC | Brüt Kâr (TL) |
| `ebitda` | NUMERIC | FAVÖK (TL) |
| `net_profit` | NUMERIC | Net Kâr (TL) |
| `total_assets` | NUMERIC | Toplam Aktif (TL) |
| `total_debts` | NUMERIC | Toplam Borç (TL) |
| `net_debt` | NUMERIC | Net Borç (TL) |
| `equity` | NUMERIC | Özkaynaklar (TL) |
| `paid_capital` | NUMERIC | Ödenmiş Sermaye (TL) |
| `current_ratio` | NUMERIC | Cari Oran |
| `leverage_ratio` | NUMERIC | Kaldıraç Oranı |
| `pe_ratio` | NUMERIC | F/K Oranı |
| `pb_ratio` | NUMERIC | PD/DD Oranı |
| `roe` | NUMERIC | ROE |
| `roa` | NUMERIC | ROA |
| `gross_margin` | NUMERIC | Brüt Kâr Marjı |
| `net_margin` | NUMERIC | Net Kâr Marjı |
| `ebitda_margin` | NUMERIC | FAVÖK Marjı |

### `kap_disclosures` — KAP Bildirimleri

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `id` | BIGINT | Benzersiz ID |
| `disclosure_id` | VARCHAR(50) | KAP bildirim indeksi |
| `symbol` | VARCHAR(10) | Hisse kodu |
| `company_id` | BIGINT | FOREIGN KEY → kap_companies.id |
| `title` | TEXT | Bildirim başlığı |
| `category` | VARCHAR(50) | Kategori (Finansal_Rapor, Temettu, vb.) |
| `publish_date` | TIMESTAMP | Yayın tarihi |
| `source_url` | TEXT | KAP linki |
| `is_catalyst` | BOOLEAN | Katalizör mü? |

### `kap_shareholders` — Pay Sahipleri

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY |
| `name` | TEXT | Hissedar adı |
| `share_percent` | NUMERIC | Pay oranı (%) |
| `vote_right_percent` | NUMERIC | Oy hakkı (%) |

### `kap_management` — Yönetim Kurulu

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY |
| `name` | TEXT | Üye adı |
| `title` | TEXT | Ünvan (YK Başkanı, Üye, vb.) |
| `since` | TEXT | Görev başlangıcı |

### `kap_subsidiaries` — Bağlı Ortaklıklar

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY |
| `name` | TEXT | Bağlı ortaklık adı |
| `share_percent` | NUMERIC | Sermayedeki pay (%) |
| `type` | TEXT | İlişki tipi (subsidiary, affiliate, investment) |

### `kap_cashflows` — Nakit Akış

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY |
| `year` | INT | Yıl |
| `period` | INT | Dönem |
| `operating_cf` | NUMERIC | Operasyonel nakit akışı |
| `investing_cf` | NUMERIC | Yatırım nakit akışı |
| `financing_cf` | NUMERIC | Finansman nakit akışı |

### `tefas_funds` — TEFAS Fonları

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `id` | BIGINT | Benzersiz ID |
| `code` | VARCHAR(20) | Fon kodu (TCD, GGS, vb.) |
| `title` | TEXT | Fon tam adı |
| `kind` | VARCHAR(10) | Tip (YAT, EMK, BYF) |
| `current_price` | NUMERIC | Güncel fiyat |
| `market_cap` | NUMERIC | Toplam portföy büyüklüğü |
| `investor_count` | INT | Yatırımcı sayısı |

### `tefas_fund_prices` — Fon Fiyat Geçmişi

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `fund_id` | BIGINT | FOREIGN KEY → tefas_funds.id |
| `trade_date` | DATE | İşlem tarihi |
| `price` | NUMERIC | Birim fiyat |
| `market_cap` | NUMERIC | Portföy büyüklüğü |
| `investors_count` | INT | Yatırımcı sayısı |

### `tefas_fund_allocations` — Fon Portföy Dağılımları

| Sütun | Tip | Açıklama |
|-------|-------|----------|
| `fund_id` | BIGINT | FOREIGN KEY |
| `trade_date` | DATE | Tarih |
| `stock` | NUMERIC | Hisse Senedi (%) |
| `government_bond` | NUMERIC | Devlet Tahvili (%) |
| `treasury_bill` | NUMERIC | Hazine Bonosu (%) |
| `eurobonds` | NUMERIC | Eurobond (%) |
| `foreign_equity` | NUMERIC | Yabancı Hisse (%) |
| `repo` | NUMERIC | Repo (%) |
| `reverse_repo` | NUMERIC | Ters Repo (%) |
| `term_deposit` | NUMERIC | Vadeli Mevduat (%) |
| `precious_metals` | NUMERIC | Kıymetli Maden (%) |
| `participation_account` | NUMERIC | Kar Paylı Mevduat (%) |
| `commercial_paper` | NUMERIC | Ticari Kâğıt (%) |
| `fund_participation_certificate` | NUMERIC | Fon Katılım Belgesi (%) |
| ... | ... | (50+ varlık sınıfı) |

### `bist_stock_prices` — Güncel Fiyatlar

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | VARCHAR(10) | Hisse kodu |
| `price` | NUMERIC | Güncel fiyat (TL) |
| `change_pct` | NUMERIC | Günlük değişim (%) |
| `volume` | NUMERIC | İşlem hacmi |
| `market_cap` | NUMERIC | Piyasa değeri |
| `pe_ratio` | NUMERIC | F/K |
| `pb_ratio` | NUMERIC | PD/DD |

### `bist_price_history` — Fiyat Geçmişi

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | VARCHAR(10) | Hisse kodu |
| `trade_date` | DATE | İşlem tarihi |
| `open` | NUMERIC | Açılış |
| `high` | NUMERIC | Yüksek |
| `low` | NUMERIC | Düşük |
| `close` | NUMERIC | Kapanış |
| `volume` | NUMERIC | Hacim |

---

## 5. Kullanım Örnekleri

### Python — Bir Şirketin Tüm Verilerini Çek
```python
import requests

r = requests.get("http://localhost:3000/api/export/all/THYAO")
data = r.json()

print(f"Şirket: {data['company']['company_name']}")
print(f"Finansal dönem sayısı: {len(data['financials'])}")
print(f"Bildirim sayısı: {len(data['disclosures'])}")
print(f"Ortak sayısı: {len(data['shareholders'])}")
print(f"YK üye sayısı: {len(data['management'])}")
print(f"Bağlı ortaklık: {len(data['subsidiaries'])}")
```

### Python — Tüm Şirketleri DataFrame'e Çek
```python
import requests
import pandas as pd

# Tüm şirketler
companies = requests.get("http://localhost:3000/api/export/companies").json()
df = pd.DataFrame(companies)

# Finansal verileri ekle
for _, row in df.iterrows():
    fin = requests.get(f"http://localhost:3000/api/export/financials/{row['ticker']}").json()
    if fin['financials']:
        latest = fin['financials'][0]
        df.loc[df['ticker'] == row['ticker'], 'revenue'] = latest.get('revenue', 0)
        df.loc[df['ticker'] == row['ticker'], 'pe_ratio'] = latest.get('pe_ratio', 0)
```

### JavaScript — Fiyat Geçmişi Çek
```javascript
const response = await fetch('http://localhost:3000/api/export/fund/TCD');
const fund = await response.json();

console.log(`${fund.title}: ${fund.current_price} TL`);
console.log(`${fund.price_history.length} günlük veri`);

// Son 30 gün
const last30 = fund.price_history.slice(-30);
last30.forEach(d => {
  console.log(`${d.date}: ${d.price} TL`);
});
```

### Python — CSV Olarak İndir
```python
import requests

# Tüm şirketler CSV
r = requests.get("http://localhost:3000/api/export/csv/kap_companies")
with open("sirketler.csv", "wb") as f:
    f.write(r.content)

# Tüm finansal veriler CSV
r = requests.get("http://localhost:3000/api/export/csv/kap_financials")
with open("finansallar.csv", "wb") as f:
    f.write(r.content)
```

### Python — Tüm Verileri Toplu Çek (Batch Export)
```python
import requests, json

# 1. Şirket listesini çek
companies = requests.get("http://localhost:3000/api/export/companies").json()

# 2. Her şirket için tüm verileri çek
all_data = {}
for co in companies:
    ticker = co['ticker']
    data = requests.get(f"http://localhost:3000/api/export/all/{ticker}").json()
    all_data[ticker] = data
    print(f"✓ {ticker}: {len(data['financials'])} finansal, {len(data['disclosures'])} bildirim")

# 3. Kaydet
with open("all_companies_data.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f"Toplam {len(all_data)} şirket kaydedildi.")
```

### Direkt SQL Sorguları (PostgreSQL)
```sql
-- En kârlı 10 şirket (son yıllık veri)
SELECT c.ticker, c.company_name, f.net_margin, f.roe
FROM kap_companies c
JOIN kap_financials f ON f.company_id = c.id
WHERE f.period = 12 AND f.net_margin > 0
ORDER BY f.net_margin DESC
LIMIT 10;

-- En çok bildirim yapan 10 şirket
SELECT c.ticker, c.company_name, COUNT(*) as bildirim_sayisi
FROM kap_disclosures d
JOIN kap_companies c ON c.id = d.company_id
GROUP BY c.ticker, c.company_name
ORDER BY bildirim_sayisi DESC
LIMIT 10;

-- XU100'deki şirketlerin F/K ortalaması
SELECT AVG(f.pe_ratio) as ort_fk
FROM kap_financials f
JOIN index_constituents ic ON ic.ticker = f.company_id::text
WHERE f.period = 12 AND f.pe_ratio > 0;

-- THYAO'nun tüm finansal verileri
SELECT * FROM kap_financials
WHERE company_id = (SELECT id FROM kap_companies WHERE ticker = 'THYAO')
ORDER BY year DESC, period DESC;

-- Bir fonun fiyat geçmişi
SELECT fp.trade_date, fp.price, fp.market_cap
FROM tefas_fund_prices fp
JOIN tefas_funds tf ON tf.id = fp.fund_id
WHERE tf.code = 'TCD'
ORDER BY fp.trade_date;
```

---

## 🔗 Google AI Studio Bağlantı

### Public API URL
```
https://signal-invitations-draws-perspectives.trycloudflare.com
```

### OpenAPI Specification
`finance-pipeline/openapi_spec.json` dosyasını Google AI Studio'ya import edin.

### Tool Tanımları
`finance-pipeline/google_ai_tools.json` dosyasını Google AI Studio'ya yükleyin.

### Kullanım
Gemini'ye şu gibi sorular sorabilirsiniz:
- "THYAO'nun finansal durumu nasıl?"
- "En kârlı 5 şirketi göster"
- "TCD fonunun fiyat trendi nasıl?"
- "Bankacılık sektöründeki şirketlerin F/K ortalaması nedir?"

Daha fazla bilgi için `GOOGLE_AI_STUDIO_REHBERI.md` dosyasına bakın.

---

## 📝 Notlar

1. **Kimlik Gerekmez:** Tüm endpoint'ler açık (auth yok). Üretimde `API_KEY` veya `Bearer Token` eklemenizi öneririm.

2. **Büyük Veri:** `bist_price_history` tablosu 2.1M+ satır içeriyor. CSV export'u uzun sürebilir.

3. **Güncellik:** Veriler Worker'lar tarafından periyodik olarak güncellenir. En son güncelleme zamanı `pipeline_runs` tablosunda.

4. **Port Mapping:**
   | Servis | Port |
   |--------|------|
   | Dashboard + API | 3000 |
   | KAP Worker | 8001 |
   | TEFAS Worker | 8002 |
   | PostgreSQL | 5432 |
