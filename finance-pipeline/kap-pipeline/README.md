# 🏦 KAP Pipeline — Kamuyu Aydınlatma Platformu Veri Boru Hattı

> **Sıfır maliyetli, IP engeli olmayan, tam otomatik veri çekme sistemi**
> 
> KAP (kap.org.tr) resmi web sitesinin halka açık AJAX API uç noktalarını kullanarak
> 7 ana veri grubunu çeken, PostgreSQL'e kaydeden production-grade pipeline.

---

## 🏗️ Mimari

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   KAP.org.tr │────▶│  KAP Client  │────▶│   Pipeline    │
│   (Public)   │     │  (Anti-Bot)  │     │  Orchestrator │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
              ┌─────────────────────────────────┤
              │          7 Modules              │
              ├─────────────────────────────────┤
              │ 1. Seed Data (Şirket Listesi)   │
              │ 2. Quarterly Financials         │
              │ 3. Live Feed & Catalysts        │
              │ 4. Corporate Actions            │
              │ 5. Share Buybacks               │
              │ 6. IPO & Prospectus             │
              │ 7. Ownership Structure          │
              └──────────────┬──────────────────┘
                             │
                     ┌───────▼───────┐
                     │  PostgreSQL   │
                     │  (7 Tables)   │
                     └───────────────┘
```

## 📊 Veritabanı Şeması (7 Tablo)

| Tablo | Açıklama |
|-------|----------|
| `companies` | Şirket ana listesi (ticker, mkk_id, ad, sektör) |
| `financials` | Çeyreklik mali tablolar + hesaplanan rasyolar |
| `disclosures` | KAP canlı bildirim akışı + kategori etiketi |
| `order_backlogs` | Yeni iş ilişkileri ve sipariş havuzu |
| `corporate_actions` | Temettü, bedelli/bedelsiz, sermaye hareketleri |
| `share_buybacks` | Pay geri alım programları |
| `ipo_data` | Halka arz verileri ve fon kullanım dağılımı |
| `shareholders` | Ortaklık yapısı ve nitelikli pay sahipleri |

## 🚀 Kurulum

### 1. Bağımlılıkları Yükle

```bash
cd kap-pipeline
pip install -r requirements.txt
```

### 2. PostgreSQL Veritabanı Oluştur

```sql
CREATE DATABASE kap_pipeline;
```

### 3. Ortam Değişkenlerini Ayarla

```bash
export KAP_DB_HOST=localhost
export KAP_DB_PORT=5432
export KAP_DB_NAME=kap_pipeline
export KAP_DB_USER=postgres
export KAP_DB_PASSWORD=your_password
```

> Tablolar ilk çalıştırmada otomatik olarak oluşturulur (SQLAlchemy `create_all`).

### 4. Pipeline'ı Çalıştır

```bash
# Tüm modülleri çalıştır
python pipeline.py full

# Sadece şirket listesini çek
python pipeline.py seed

# Sadece finansal verileri çek (ilk 10 şirket)
python pipeline.py financials --limit 10

# Son 30 günün bildirimlerini çek
python pipeline.py disclosures

# Belirli tarih aralığı
python pipeline.py disclosures --from 2024-01-01 --to 2024-12-31

# Bazı modülleri atlayarak çalıştır
python pipeline.py full --skip module6 module7
```

### 5. Otomatik Zamanlanmış Çalıştırma (Cron)

```bash
# Scheduler'ı başlat (varsayılan: her 5 dk canlı akış, günlük tam pipeline)
python scheduler.py

# Özel interval ile
python scheduler.py --live-interval 10

# Bazı job'ları devre dışı bırakarak
python scheduler.py --no-seed-refresh --no-financials
```

**Varsayılan Zamanlama:**

| Job | Sıklık | Zaman |
|-----|--------|-------|
| Canlı Akış (Module 3) | Her 5 dakika | Piyasa saatleri (10:00-18:00) |
| Tam Pipeline (Modül 1-7) | Her gün | 02:00 TRT (Pazartesi-Cuma) |
| Finansal Veri (Module 2) | Her gün | 04:00 TRT (Pazartesi-Cuma) |
| Şirket Yenileme (Module 1) | Haftalık | Pazar 03:00 TRT |

## 🛡️ Anti-Bot Stratejileri

| Teknik | Uygulama |
|--------|----------|
| **User-Agent Rotasyonu** | Gerçek Chrome tarayıcı UA string'i |
| **Rate Limiting** | Her istek arası rastgele 2-4.5 sn gecikme |
| **Session Cookies** | İlk istekte JSESSIONID alınır, tüm isteklerde korunur |
| **Referer Header** | Tüm isteklerde `https://www.kap.org.tr` referansı |
| **Retry with Backoff** | 429/5xx hatalarda exponential backoff (max 3 deneme) |
| **Upsert Mantığı** | `ON CONFLICT DO NOTHING/UPDATE` ile mükerrer kayıt önleme |

## 📦 Modül Detayları

### Module 1: Tohum Veri (Seed Data)
- `https://www.kap.org.tr/tr/bist-sirketler` → Tüm BIST şirketleri
- Ticker, mkkMemberId, şirket adı, şehir, sektör bilgileri
- Opsiyonel: Detay sayfasından zenginleştirme

### Module 2: Çeyreklik Mali Tablolar
- Gelir tablosu: Hasılat, Brüt Kâr, EBIT, FAVÖK, Net Kâr
- Bilanço: Varlıklar, borçlar, özkaynaklar
- Hesaplanan: Brüt/FAVÖK/Net marjlar, ROE, ROA, cari oran, kaldıraç
- Büyüme: YoY ve QoQ değişim oranları

### Module 3: Canlı Akış & Katalizör
- Otomatik kategori etiketleme (Regex tabanlı)
- Katalizör tespiti (büyüme, yatırım, temettü, ihale vb.)
- Yeni iş ilişkileri / sözleşme çıkarma
- Ciro etkisi hesaplama: `(Sözleşme Tutarı / Son Yıllık Hasılat) × 100`

### Module 4: Kurumsal İşlemler
- Temettü: Brüt/net pay başına tutar, verimi, ex-date, ödeme tarihi
- Sermaye artırımları: Bedelli/bedelsiz oranları, rüçhan tarihleri
- Durum tespiti: Teklif vs. Kesinleşti

### Module 5: Pay Geri Alımları
- Program bütçesi, azami pay adedi
- Geri alınan toplam pay ve ortalama maliyet
- Sermayeye oranı (%)

### Module 6: Halka Arz (IPO)
- Halka arz fiyatı, iskontosu, dağıtım yöntemi
- Konsorsiyum lideri, tahsisat grupları
- Fon kullanım dağılımı: Yatırım / Ar-Ge / İşletme Sermayesi / Borç

### Module 7: Ortaklık Yapısı
- Tüm ortaklar: Pay tutarı, pay oranı, oy hakkı
- Nitelikli ortaklar (>5%): Gerçek zamanlı alım/satım takibi
- Şirket detay sayfasından statik veri çekme

## 🔧 Konfigürasyon

Tüm ayarlar `config.py` dosyasında merkezileştirilmiştir:

- **Veritabanı**: `KAP_DB_*` ortam değişkenleri
- **Rate Limiting**: `RateLimitConfig` sınıfı
- **Kategori Anahtar Kelimeleri**: `CATEGORY_KEYWORDS` sözlüğü
- **Finansal Anahtar İsimleri**: `FINANCIAL_KEYS` (Türkçe etiket eşleme)

## 📋 Production Deployment

```bash
# systemd servisi örneği (Linux)
# /etc/systemd/system/kap-pipeline.service
[Unit]
Description=KAP Pipeline Scheduler
After=network.target postgresql.service

[Service]
Type=simple
User=kap
WorkingDirectory=/opt/kap-pipeline
ExecStart=/opt/kap-pipeline/venv/bin/python scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Crontab alternatifi
# Her 5 dakika canlı akış
*/5 * * * * cd /opt/kap-pipeline && python pipeline.py cron
# Günlük tam pipeline (02:00 TRT = 23:00 UTC)
0 23 * * 1-5 cd /opt/kap-pipeline && python pipeline.py full
```

## ⚠️ Önemli Notlar

1. **Rate Limiting**: KAP IP engeli uygulayabilir. Varsayılan gecikme ayarlarını
   düşürmeyin. Minimum 2sn, önerilen 3-4.5sn.
2. **Veri Güncelliği**: KAP verileri piyasadan 15 dakika gecikmeli olabilir.
3. **Yasal Uyumluluk**: Bu araç yalnızca KAP'ın herkese açık verilerini kullanır.
   KAP'ın Kullanım Koşullarını okuyun.
4. **Sayfa Yapısı Değişikliği**: KAP web sitesi arayüzü değişirse parser'lar
   güncellenmelidir. Her modül hata günlüğü çıktısı verir.

## 📁 Proje Yapısı

```
kap-pipeline/
├── config.py              # Merkezi konfigürasyon
├── database.py            # SQLAlchemy modelleri ve DB yardimcılari
├── client.py              # HTTP istemcisi (anti-bot, rate-limit, retry)
├── module1_seeds.py       # Modül 1: Şirket listesi (tohum veri)
├── module2_financials.py  # Modül 2: Mali tablolar ve rasyolar
├── module3_disclosures.py # Modül 3: Canlı akış ve katalizör
├── module4_corporate.py   # Modül 4: Kurumsal işlemler
├── module5_buybacks.py    # Modül 5: Pay geri alımları
├── module6_ipo.py         # Modül 6: Halka arz analiz
├── module7_ownership.py   # Modül 7: Ortaklık yapısı
├── pipeline.py            # Ana orkestratör ve CLI
├── scheduler.py           # APScheduler zamanlayıcı
├── requirements.txt       # Bağımlılıklar
└── README.md              # Bu dosya
```

---

**Lisans**: Bu proje eğitim ve araştırma amaçlıdır. KAP verilerinin kullanımında
[yasal düzenlemelere](https://www.kap.org.tr/tr/sayfalar/kullanim-sartlari.aspx) uyunuz.
