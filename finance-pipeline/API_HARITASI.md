# 🗺️ FİNANS PIPELINE — KAPSAMLI API HARİTASI

> **Base URL:** `https://signal-invitations-draws-perspectives.trycloudflare.com`
> **Local URL:** `http://localhost:3000`
> **Toplam Tablo:** 43 | **Toplam Sütun:** 335 | **Toplam Kayıt:** 2.2M+

---

## 📋 ENDPOINTS ÖZETİ

| # | Endpoint | Veri | Satır | Açıklama |
|---|----------|------|-------|----------|
| 1 | `GET /api/export/companies` | Şirketler | 1,014 | Tüm BIST şirketleri |
| 2 | `GET /api/export/search?q=` | Arama | Değişken | Ticker/ad ile arama |
| 3 | `GET /api/export/all/{ticker}` | Tek Şirket | Değişken | Bir varlığın HER ŞEYİ |
| 4 | `GET /api/export/financials/{ticker}` | Finansal | Değişken | Gelir, kâr, oranlar |
| 5 | `GET /api/export/funds` | Fonlar | 2,598 | TEFAS fon listesi |
| 6 | `GET /api/export/fund/{code}` | Fon Detay | Değişken | Fon + fiyat geçmişi |
| 7 | `GET /api/export/bulk` | Toplu | 2.2M+ | TÜM tablolar tek JSON |
| 8 | `GET /api/export/bulk/csv` | Toplu CSV | 2.2M+ | TÜM tablolar tek ZIP |
| 9 | `GET /api/export/csv/{table}` | Tek Tablo | Değişken | Tek tablo CSV |
| 10 | `GET /api/export/schema` | Şema | 43 | DB yapısı bilgisi |

---

## 1️⃣ `GET /api/export/companies`

**Açıklama:** BIST'teki tüm şirketlerin listesi

**Parametre:** Yok

**Dönen Sütunlar (9):**
| Sütun | Tip | Açıklama | Örnek |
|-------|-----|----------|-------|
| `id` | BIGINT | Benzersiz ID | 1 |
| `ticker` | TEXT | Hisse kodu | THYAO |
| `mkk_id` | TEXT | MKK üye ID | 12345 |
| `company_name` | TEXT | Şirket adı | Türk Hava Yolları |
| `sector` | TEXT | Sektör | Ulaştırma |
| `market` | TEXT | Piyasa | BIST |
| `is_active` | BOOLEAN | Aktif mi | true |
| `created_at` | TIMESTAMP | Oluşturma | 2026-08-28 |
| `updated_at` | TIMESTAMP | Güncelleme | 2026-08-31 |

---

## 2️⃣ `GET /api/export/search?q={arama}&limit={n}`

**Açıklama:** Ticker veya şirket adına göre arama

**Parametreler:**
| Parametre | Zorunlu | Tip | Varsayılan | Açıklama |
|-----------|---------|-----|------------|----------|
| `q` | ✅ | string | — | Arama terimi |
| `limit` | ❌ | int | 20 | Maks sonuç |

**Dönen Sütunlar (4):**
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | TEXT | Hisse kodu |
| `company_name` | TEXT | Şirket adı |
| `sector` | TEXT | Sektör |
| `market` | TEXT | Piyasa |

---

## 3️⃣ `GET /api/export/all/{ticker}` ⭐ EN KAPSAMLI

**Açıklama:** Bir varlığın **TÜM** verileri tek JSON'da

**URL Parametresi:**
| Parametre | Zorunlu | Açıklama |
|-----------|---------|----------|
| `ticker` | ✅ | Hisse kodu (THYAO, ASELS, GARAN) |

**Dönen 7 Veri Seti:**

### 3a. `company` — Şirket Temel Bilgisi
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `id` | BIGINT | ID |
| `ticker` | TEXT | Hisse kodu |
| `mkk_id` | TEXT | MKK ID |
| `company_name` | TEXT | Şirket adı |
| `sector` | TEXT | Sektör |
| `market` | TEXT | Piyasa |
| `is_active` | BOOLEAN | Aktif mi |

### 3b. `financials` — Finansal Tablolar (tüm dönemler)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `year` | TEXT | Yıl |
| `period` | TEXT | Dönem (3,6,9,12) |
| `revenue` | NUMERIC | Hasılat (TL) |
| `gross_profit` | NUMERIC | Brüt Kâr (TL) |
| `ebit` | NUMERIC | EBIT (TL) |
| `ebitda` | NUMERIC | FAVÖK (TL) |
| `net_profit` | NUMERIC | Net Kâr (TL) |
| `total_assets` | NUMERIC | Toplam Aktif |
| `total_debts` | NUMERIC | Toplam Borç |
| `equity` | NUMERIC | Özkaynaklar |
| `paid_capital` | NUMERIC | Ödenmiş Sermaye |
| `current_ratio` | NUMERIC | Cari Oran |
| `leverage_ratio` | NUMERIC | Kaldıraç |
| `roe` | NUMERIC | ROE |
| `roa` | NUMERIC | ROA |
| `gross_margin` | NUMERIC | Brüt Marj |
| `ebitda_margin` | NUMERIC | FAVÖK Marjı |
| `net_margin` | NUMERIC | Net Marj |
| `pe_ratio` | NUMERIC | F/K |
| `pb_ratio` | NUMERIC | PD/DD |
| `ev_ebitda` | NUMERIC | FD/FAVÖK |
| `ev_revenue` | NUMERIC | FD/Satışlar |
| `revenue_yoy` | NUMERIC | Gelir Yıllık Büyüme |
| `net_profit_yoy` | NUMERIC | Kâr Yıllık Büyüme |
| `current_assets` | NUMERIC | Dönen Varlıklar |
| `cash_and_equivalents` | NUMERIC | Nakit |
| `financial_debt` | NUMERIC | Finansal Borç |
| `net_debt` | NUMERIC | Net Borç |

### 3c. `disclosures` — Son 50 Bildirim
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `id` | BIGINT | ID |
| `disclosure_id` | BIGINT | KAP bildirim indeksi |
| `symbol` | TEXT | Hisse kodu |
| `title` | TEXT | Bildirim başlığı |
| `category` | TEXT | Kategori |
| `disclosure_type` | TEXT | Bildirim tipi |
| `publish_date` | TIMESTAMP | Yayın tarihi |
| `source_url` | TEXT | KAP linki |
| `is_catalyst` | BOOLEAN | Katalizör mü? |

### 3d. `shareholders` — Pay Sahipleri
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `holder_name` | TEXT | Hissedar adı |
| `shares_amount` | NUMERIC | Pay adedi |
| `share_ratio_percent` | NUMERIC | Pay oranı (%) |
| `voting_power_percent` | NUMERIC | Oy hakkı (%) |
| `holder_type` | TEXT | Tip (kurumsal/bireysel) |
| `is_qualified` | TEXT | Nitelikli mi? |

### 3e. `management` — Yönetim Kurulu
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `name` | TEXT | Üye adı |
| `title` | TEXT | Ünvan |
| `member_type` | TEXT | Üye tipi |

### 3f. `subsidiaries` — Bağlı Ortaklıklar
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `name` | TEXT | Ortaklık adı |
| `share_percent` | NUMERIC | Sermayedeki pay (%) |
| `country` | TEXT | Ülke |
| `activity` | TEXT | Faaliyet alanı |
| `relation_type` | TEXT | İlişki tipi |

### 3g. `cashflows` — Nakit Akış
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `year` | TEXT | Yıl |
| `period` | TEXT | Dönem |
| `operating_cash_flow` | NUMERIC | Operasyonel CF |
| `investing_cash_flow` | NUMERIC | Yatırım CF |
| `financing_cash_flow` | NUMERIC | Finansman CF |
| `capex` | NUMERIC | Sermaye Harcaması |
| `opening_cash` | NUMERIC | Başlangıç Nakdi |
| `closing_cash` | NUMERIC | Kapanış Nakdi |

---

## 4️⃣ `GET /api/export/financials/{ticker}`

**Açıklama:** Bir şirketin tüm dönem finansal verileri

**28 Sütun:** (3b ile aynı — financials seti)

---

## 5️⃣ `GET /api/export/funds?limit={n}`

**Açıklama:** TEFAS fon listesi

**Parametre:**
| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| `limit` | 100 | Maks fon sayısı |

**Dönen Sütunlar (11):**
| Sütun | Tip | Açıklama | Örnek |
|-------|-----|----------|-------|
| `code` | TEXT | Fon kodu | TCD |
| `title` | TEXT | Fon adı | Turkish Corporate Debt |
| `kind` | TEXT | Tip | YAT/EMK/BYF |
| `current_price` | NUMERIC | Güncel fiyat | 1.0456 |
| `daily_return_pct` | NUMERIC | Günlük getiri | 0.12 |
| `shares_outstanding` | NUMERIC | Pay adedi | 125000000 |
| `market_cap` | NUMERIC | Portföy büyüklüğü | 890000000 |
| `category` | TEXT | Kategori | Tahvil |
| `category_rank` | NUMERIC | Sıralama | 5 |
| `investor_count` | NUMERIC | Yatırımcı sayısı | 3420 |
| `fund_group` | TEXT | Fon grubu | BYF |

---

## 6️⃣ `GET /api/export/fund/{code}`

**Açıklama:** Bir fondaki detay + fiyat geçmişi

**URL Parametresi:**
| Parametre | Zorunlu | Açıklama |
|-----------|---------|----------|
| `code` | ✅ | Fon kodu (TCD, GGS) |

**Dönen Veriler:**
| Alan | Tip | Açıklama |
|------|-----|----------|
| `code` | TEXT | Fon kodu |
| `title` | TEXT | Fon adı |
| `kind` | TEXT | Tip |
| `current_price` | NUMERIC | Güncel fiyat |
| `market_cap` | NUMERIC | Büyüklük |
| `price_history` | ARRAY | Günlük fiyat geçmişi |

**price_history dizisi:**
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `date` | DATE | İşlem tarihi |
| `price` | NUMERIC | Birim fiyat |
| `shares_outstanding` | NUMERIC | Pay adedi |
| `investors_count` | NUMERIC | Yatırımcı |
| `market_cap` | NUMERIC | Büyüklük |

---

## 7️⃣ `GET /api/export/bulk?tables={tablolar}&limit_per_table={limit}` ⭐

**Açıklama:** Tek istekte **TÜM tabloların** verileri

**Parametreler:**
| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| `tables` | TÜMÜ | Virgülle ayrılmış tablo listesi |
| `limit_per_table` | 0 (sınırsız) | Her tabloda maks satır |

**Kullanılabilir Tablolar:**
| Kısa İsim | Tam Tablo Adı | Kayıt |
|-----------|---------------|-------|
| `companies` | kap_companies | 1,014 |
| `financials` | kap_financials | 1,387 |
| `disclosures` | kap_disclosures | 3,989 |
| `shareholders` | kap_shareholders | 1,014 |
| `management` | kap_management | 2,056 |
| `subsidiaries` | kap_subsidiaries | 1,157 |
| `cashflows` | kap_cashflows | 1,274 |
| `buybacks` | share_buybacks | 119 |
| `ipo` | ipo_data | 60 |
| `funds` | tefas_funds | 2,598 |
| `fund_prices` | tefas_fund_prices | 2,190,736 |
| `fund_allocations` | tefas_fund_allocations | 2,459 |
| `prices` | bist_stock_prices | 602 |
| `price_history` | bist_price_history | 37,641 |
| `settlement` | settlement_data | 602 |
| `index` | index_constituents | 114 |
| `vap` | vap_data | 67 |
| `disclosure_details` | kap_disclosure_details | 2,020 |
| `corporate_actions` | kap_corporate_actions | 27 |
| `financial_notes` | kap_financial_notes | 218 |
| `portfolio_reports` | kap_portfolio_reports | 58 |
| `market_indicators` | market_indicators | — |

**Dönen JSON Yapısı:**
```json
{
  "companies": [...],
  "financials": [...],
  "disclosures": [...],
  "_meta": {
    "tables_requested": ["companies", "financials"],
    "tables_returned": ["companies", "financials"],
    "row_counts": {"companies": 1014, "financials": 1387},
    "total_rows": 2401
  }
}
```

---

## 8️⃣ `GET /api/export/bulk/csv?tables={tablolar}`

**Açıklama:** TÜM tabloların CSV'leri tek ZIP'te

**İndirilen ZIP İçeriği:**
```
finance_pipeline_export.zip
├── kap_companies.csv
├── kap_financials.csv
├── kap_disclosures.csv
├── kap_shareholders.csv
├── kap_management.csv
├── kap_subsidiaries.csv
├── kap_cashflows.csv
├── tefas_funds.csv
├── tefas_fund_prices.csv
├── tefas_fund_allocations.csv
├── bist_stock_prices.csv
├── bist_price_history.csv
├── settlement_data.csv
├── share_buybacks.csv
├── ipo_data.csv
└── index_constituents.csv
```

---

## 9️⃣ `GET /api/export/csv/{table}`

**Açıklama:** Tek tabloyu CSV olarak indir

**İzin Verilen Tablolar:**
`kap_companies`, `kap_financials`, `kap_disclosures`, `kap_shareholders`, `kap_management`, `kap_subsidiaries`, `kap_cashflows`, `tefas_funds`, `bist_stock_prices`, `bist_price_history`, `share_buybacks`, `ipo_data`

---

## 🔟 `GET /api/export/schema`

**Açıklama:** Veritabanı şeması (43 tablo, tüm sütunlar)

---

## 📊 KAPSAMLI TABLO DETAYLARI

### `kap_financials` — 32 Sütun (Finansal Tablolar)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_id` | BIGINT | FOREIGN KEY |
| `year` | TEXT | Yıl |
| `period` | TEXT | Dönem |
| `revenue` | NUMERIC | Hasılat |
| `gross_profit` | NUMERIC | Brüt Kâr |
| `ebit` | NUMERIC | EBIT |
| `ebitda` | NUMERIC | FAVÖK |
| `net_profit` | NUMERIC | Net Kâr |
| `total_assets` | NUMERIC | Toplam Aktif |
| `total_debts` | NUMERIC | Toplam Borç |
| `equity` | NUMERIC | Özkaynaklar |
| `paid_capital` | NUMERIC | Ödenmiş Sermaye |
| `current_ratio` | NUMERIC | Cari Oran |
| `leverage_ratio` | NUMERIC | Kaldıraç |
| `roe` | NUMERIC | ROE |
| `roa` | NUMERIC | ROA |
| `gross_margin` | NUMERIC | Brüt Marj |
| `ebitda_margin` | NUMERIC | FAVÖK Marjı |
| `net_margin` | NUMERIC | Net Marj |
| `pe_ratio` | NUMERIC | F/K |
| `pb_ratio` | NUMERIC | PD/DD |
| `ev_ebitda` | NUMERIC | FD/FAVÖK |
| `ev_revenue` | NUMERIC | FD/Satışlar |
| `revenue_yoy` | NUMERIC | Gelir YB |
| `net_profit_yoy` | NUMERIC | Kâr YB |
| `current_assets` | NUMERIC | Dönen Varlıklar |
| `cash_and_equivalents` | NUMERIC | Nakit |
| `financial_debt` | NUMERIC | Finansal Borç |
| `net_debt` | NUMERIC | Net Borç |

### `bist_stock_prices` — 19 Sütun (Güncel Fiyatlar)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | TEXT | Hisse kodu |
| `company_name` | TEXT | Şirket adı |
| `price` | NUMERIC | Güncel fiyat |
| `previous_close` | NUMERIC | Önceki kapanış |
| `day_high` | NUMERIC | Gün içi yüksek |
| `day_low` | NUMERIC | Gün içi düşük |
| `volume` | NUMERIC | İşlem hacmi |
| `market_cap` | NUMERIC | Piyasa değeri |
| `pe_ratio` | NUMERIC | F/K |
| `pb_ratio` | NUMERIC | PD/DD |
| `dividend_yield` | NUMERIC | Temettü verimi |
| `week52_high` | NUMERIC | 52 hafta yüksek |
| `week52_low` | NUMERIC | 52 hafta düşük |
| `day_change_pct` | NUMERIC | Günlük değişim |
| `is_xu100` | BOOLEAN | XU100'de mi? |
| `is_xbank` | BOOLEAN | XBANK'ta mı? |

### `tefas_fund_allocations` — 64 Sütun (Fon Portföy Dağılımı)
| Ana Kategori | Sütunlar |
|--------------|----------|
| **Hisse Senedi** | `stock` |
| **Tahvil** | `treasury_bill`, `government_bond`, `government_bonds_and_bills_fx` |
| **Mevduat** | `term_deposit`, `term_deposit_tl`, `term_deposit_d`, `term_deposit_au` |
| **Repo** | `repo`, `reverse_repo` |
| **Eurobond** | `eurobonds` |
| **Döviz** | `foreign_currency_bills`, `fx_payable_bills` |
| **Kıymetli Maden** | `precious_metals`, `precious_metals_byf`, `precious_metals_kba` |
| **Gayrimenkul** | `real_estate_certificate`, `real_estate_fund`, `real_estate_investment` |
| **Yabancı** | `foreign_stock`, `foreign_etf`, `foreign_security` |
| **Diğer** | `commercial_paper`, `bank_bills`, `derivatives`, `other` |

### `settlement_data` — 10 Sütun (Takas Verileri)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | TEXT | Hisse kodu |
| `trade_date` | DATE | İşlem tarihi |
| `foreign_ratio_pct` | NUMERIC | Yabancı oranı (%) |
| `base_ratio_pct` | NUMERIC | Base oranı (%) |
| `common_ratio_pct` | NUMERIC | Common oranı (%) |
| `foreign_shares` | NUMERIC | Yabancı pay adedi |
| `total_shares` | NUMERIC | Toplam pay |
| `free_float_pct` | NUMERIC | Halka açıklık (%) |

### `kap_shareholders` — 12 Sütun (Pay Sahipleri)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `holder_name` | TEXT | Hissedar adı |
| `shares_amount` | NUMERIC | Pay adedi |
| `share_ratio_percent` | NUMERIC | Pay oranı (%) |
| `voting_power_percent` | NUMERIC | Oy hakkı (%) |
| `holder_type` | TEXT | Tip |
| `is_qualified` | TEXT | Nitelikli mi? |

### `kap_disclosures` — 12 Sütun (Bildirimler)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `disclosure_id` | BIGINT | KAP indeksi |
| `symbol` | TEXT | Hisse kodu |
| `title` | TEXT | Başlık |
| `category` | TEXT | Kategori |
| `disclosure_type` | TEXT | Tip |
| `publish_date` | TIMESTAMP | Tarih |
| `source_url` | TEXT | Link |
| `is_catalyst` | BOOLEAN | Katalizör? |

### `kap_subsidiaries` — 9 Sütun (Bağlı Ortaklıklar)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `name` | TEXT | Ortaklık adı |
| `share_percent` | NUMERIC | Pay (%) |
| `country` | TEXT | Ülke |
| `activity` | TEXT | Faaliyet |
| `relation_type` | TEXT | İlişki tipi |

### `share_buybacks` — 13 Sütun (Geri Alım)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `total_budget_tl` | NUMERIC | Toplam bütçe (TL) |
| `max_shares` | NUMERIC | Azami pay |
| `total_bought_shares` | NUMERIC | Alınan pay |
| `capital_ratio_percent` | NUMERIC | Sermaye oranı (%) |
| `avg_buyback_price` | NUMERIC | Ort. fiyat |
| `total_spent_tl` | NUMERIC | Harcanan (TL) |

### `ipo_data` — 16 Sütun (Halka Arz)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `company_name` | TEXT | Şirket |
| `ticker` | TEXT | Hisse kodu |
| `ipo_date` | DATE | Halka arz tarihi |
| `ipo_price` | NUMERIC | Halka arz fiyatı |
| `discount_ratio` | NUMERIC | İskonto (%) |
| `distribution_type` | TEXT | Dağıtım yöntemi |
| `consortium_leader` | TEXT | Konsorsiyum lideri |
| `use_of_funds_investment_pct` | NUMERIC | Yatırım (%) |
| `use_of_funds_rd_pct` | NUMERIC | Ar-Ge (%) |
| `use_of_funds_working_capital_pct` | NUMERIC | İşletme sermayesi (%) |
| `use_of_funds_debt_pct` | NUMERIC | Borç kapatma (%) |

### `vap_data` — 12 Sütun (VAP Verileri)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | TEXT | Hisse kodu |
| `foreign_ratio` | NUMERIC | Yabancı oranı (%) |
| `local_institutional` | TEXT | Yerli kurumsal |
| `local_individual` | NUMERIC | Yerli bireysel |
| `public_float_pct` | NUMERIC | Halka açıklık (%) |
| `market_cap` | NUMERIC | Piyasa değeri |

### `index_constituents` — 5 Sütun (Endeks Bileşenleri)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `index_name` | TEXT | Endeks adı (XU100, XBANK) |
| `ticker` | TEXT | Hisse kodu |
| `weight_pct` | NUMERIC | Ağırlık (%) |

### `bist_price_history` — 10 Sütun (Fiyat Geçmişi)
| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `ticker` | TEXT | Hisse kodu |
| `trade_date` | DATE | İşlem tarihi |
| `open` | NUMERIC | Açılış |
| `high` | NUMERIC | Yüksek |
| `low` | NUMERIC | Düşük |
| `close` | NUMERIC | Kapanış |
| `volume` | NUMERIC | Hacim |
| `adj_close` | NUMERIC | Düzeltilmiş kapanış |

---

## 💻 KULLANIM ÖRNEKLERİ

### Python — Tüm Verileri Çek
```python
import requests

API = "https://signal-invitations-draws-perspectives.trycloudflare.com"

# Tüm şirketler
r = requests.get(f"{API}/api/export/companies")
companies = r.json()

# THYAO tüm veriler
r = requests.get(f"{API}/api/export/all/THYAO")
thyao = r.json()

# Toplu export
r = requests.get(f"{API}/api/export/bulk?tables=companies,financials,shareholders")
data = r.json()
```

### JavaScript — Fon Analizi
```javascript
const API = "https://signal-invitations-draws-perspectives.trycloudflare.com";

// Fon listesi
const funds = await fetch(`${API}/api/export/funds?limit=500`).then(r => r.json());

// Fon detay
const fund = await fetch(`${API}/api/export/fund/TCD`).then(r => r.json());
console.log(`${fund.title}: ${fund.price_history.length} günlük veri`);
```

### SQL — Direkt PostgreSQL
```sql
-- En kârlı 10 şirket
SELECT c.ticker, c.company_name, f.net_margin
FROM kap_companies c
JOIN kap_financials f ON f.company_id = c.id
WHERE f.period = '12' AND f.net_margin > 0
ORDER BY f.net_margin DESC LIMIT 10;

-- XU100 şirketlerinin F/K ortalaması
SELECT AVG(f.pe_ratio) as ort_fk
FROM kap_financials f
JOIN index_constituents ic ON ic.ticker = (SELECT ticker FROM kap_companies WHERE id = f.company_id)
WHERE f.period = '12' AND f.pe_ratio > 0;
```

---

## 🔗 PUBLIC URL
```
https://signal-invitations-draws-perspectives.trycloudflare.com
```

## 🔗 LOCAL URL
```
http://localhost:3000
```

## 🔗 PostgreSQL
```
postgresql://admin:admin123@localhost:5432/finance_platform
```
