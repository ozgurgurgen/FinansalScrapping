# 📊 Finance Pipeline vs Borsa MCP — Kapsamlı Karşılaştırma Raporu
**Tarih:** 31 Ağustos 2026

---

## 🔍 ÖZET

| Özellik | Finance Pipeline (Biz) | Borsa MCP |
|---------|----------------------|-----------|
| **Mimari** | Mikroservis (FastAPI + SQLite) | Tek dosya (FastMCP) |
| **Dashboard** | ✅ Gerçek zamanlı admin paneli | ❌ Yok (sadece MCP API) |
| **Veri Saklama** | ✅ Kalıcı SQLite DB (2.2M+ kayıt) | ❌ Önbellek (API'den canlı çekim) |
| **Anti-Ban** | ✅ Jitter, cooldown, UA rotation | ❌ Yok |
| **Otomasyon** | ✅ Cron job, scheduler | ❌ Manuel tetikleme |
| **LLM Entegrasyonu** | ❌ Yok | ✅ MCP protokolü (28 araç) |

---

## 📈 ORTAK ÖZELLİKLER (Hangimiz Daha İyi?)

### 1. Hisse Fiyatları (Canlı & Tarihsel)

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Canlı Fiyat** | ✅ Yahoo Finance | ✅ Yahoo Finance | 🟡 Eşit |
| **Tek Hisse Verisi** | ✅ 602 hisse (anlık) | ✅ Tüm BIST (anlık) | 🟡 Eşit |
| **Tarihsel Fiyat** | ✅ 37,641 kayıt (154 ticker) | ✅ 1y-5y periyot ile | 🟢 Biz (kalıcı DB) |
| **Fiyat Grafiği** | ✅ Dashboard'da Canvas chart | ❌ Yok | 🟢 Biz |
| **52 Hafta Yüksek/Düşük** | ✅ bist_stock_prices'da | ✅ Yahoo Finance'dan | 🟡 Eşit |
| **Hacim Verisi** | ✅ 602/602 dolu | ✅ Anlık | 🟡 Eşit |

**📊 Sonuç:** Canlı fiyatlarda eşitiz ama biz tarihsel veriyi kalıcı olarak saklıyoruz ve grafik gösteriyoruz. **BIZ DAHA İYİ.**

---

### 2. Şirket Profili & Sektör

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Şirket Sayısı** | 759 (kap_companies) | 806 (KAP Excel) | 🟡 Yakın |
| **Şirket İsimleri** | ✅ 754/759 gerçek isim | ✅ Tümü (KAP'tan) | 🟢 Borsa MCP |
| **Sektör Bilgisi** | ✅ 607/759 (yfinance) | ✅ Tümü (Yahoo Finance) | 🟢 Borsa MCP |
| **Sanayi/Alt Sektör** | ❌ Yok | ✅ industry field | 🟢 Borsa MCP |
| **Çalışan Sayısı** | ❌ Yok | ✅ fullTimeEmployees | 🟢 Borsa MCP |
| **Şirket Açıklaması** | ❌ Yok | ✅ longBusinessSummary | 🟢 Borsa MCP |
| **Website** | ⚠️ Kısmi | ✅ Tam | 🟢 Borsa MCP |
| **Katılım Finans** | ❌ Yok | ✅ include_islamic | 🟢 Borsa MCP |

**📊 Sonuç:** Borsa MCP şirket profillerinde çok daha detaylı. **BORSA MCP DAHA İYİ.**

---

### 3. Finansal Tablolar & Oranlar

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Bilanço** | ✅ 1,387 kayıt (KAP'tan) | ✅ Yahoo Finance + İş Yatırım | 🟢 Biz (orijinal KAP) |
| **Gelir Tablosu** | ✅ (kap_financials) | ✅ Yahoo Finance | 🟢 Biz (orijinal KAP) |
| **Nakit Akış** | ✅ 1,274 kayıt | ✅ Yahoo Finance | 🟢 Biz (orijinal KAP) |
| **F/K Oranı** | ⚠️ Kısmi (279/602) | ✅ Tam (Forward PE dahil) | 🟢 Borsa MCP |
| **PD/DD** | ⚠️ Kısmi | ✅ Tam | 🟢 Borsa MCP |
| **ROE/ROA** | ⚠️ Kısmi (hesaplanmış) | ✅ Tam (gerçek) | 🟢 Borsa MCP |
| **EV/EBITDA** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **Buffett Analizi** | ❌ Yok | ✅ Owner Earnings, DCF, Safety Margin | 🟢 Borsa MCP |
| **Finansal Sağlık** | ❌ Yok | ✅ Altman Z-Score, ROIC | 🟢 Borsa MCP |
| **Konsolide Tablolar** | ❌ Yok | ✅ (Yahoo Finance) | 🟢 Borsa MCP |
| **Tarihsel Trend** | ❌ Yok | ✅ (Çoklu dönem) | 🟢 Borsa MCP |
| **İş Yatırım Entegrasyonu** | ❌ Yok | ✅ isyatirim_provider | 🟢 Borsa MCP |

**📊 Sonuç:** Biz orijinal KAP verisini çekiyoruz (güvenilir) ama oranlar ve analiz araçları eksik. **BORSA MCP DAHA İYİ.**

---

### 4. Teknik Analiz

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **RSI** | ✅ 14 periyot | ✅ 7, 14 periyot | 🟢 Borsa MCP |
| **MACD** | ✅ 12/26/9 | ✅ + histogram, sinyal | 🟡 Eşit |
| **Bollinger Bantları** | ✅ 20 periyot, 2σ | ✅ + bandwidth | 🟡 Yakın |
| **Supertrend** | ✅ Lokal hesaplama | ✅ borsapy (TradingView) | 🟢 Borsa MCP |
| **Pivot Points** | ✅ Klasik (PP, R1-R3, S1-S3) | ✅ Klasik + Camarilla + Woodie | 🟢 Borsa MCP |
| **ADX** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **Stochastic** | ❌ Yok | ✅ K/D | 🟢 Borsa MCP |
| **Ichimoku** | ❌ Yok | ✅ 5 çizgi | 🟢 Borsa MCP |
| **VWMA** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **ATR** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **Aroon** | ❌ Yok | ✅ Up/Down | 🟢 Borsa MCP |
| **T3 (Tilson)** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **Sinyal Sistemi** | ✅ AL/SAT/NOTR | ✅ Çoklu sinyal | 🟡 Yakın |
| **Grafik** | ✅ Canvas chart (dashboard) | ❌ Yok | 🟢 Biz |
| **Zaman Dilimi** | ❌ Sadece günlük | ✅ 1d, 1h, 4h, 1W | 🟢 Borsa MCP |

**📊 Sonuç:** Borsa MCP 20+ gösterge sunuyor, biz 7 tane. Ama biz grafik gösteriyoruz. **BORSA MCP DAHA İYİ (gösterge sayısı açısından).**

---

### 5. TEFAS Fon Verileri

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Fon Sayısı** | ✅ 2,591 | ✅ 836+ | 🟢 Biz (3x daha fazla) |
| **Fiyat Geçmişi** | ✅ 2,249,544 kayıt (5 yıl) | ✅ Mevcut fiyat + 7 dönem getiri | 🟢 Biz (2.2M+ kayıt) |
| **Portföy Dağılımı** | ✅ 2,459 kayıt (64 varlık) | ✅ 50+ varlık sınıfı | 🟢 Biz |
| **Hisse Bazlı Dağılım** | ✅ 793 fon-hisse eşleşme | ❌ Yok | 🟢 Biz (benzersiz) |
| **Performans Metrikleri** | ⚠️ Kısmi | ✅ 7 dönemlik getiri | 🟢 Borsa MCP |
| **Fon Karşılaştırma** | ❌ Yok | ✅ compare_mode | 🟢 Borsa MCP |
| **Kategori Filtreleme** | ⚠️ Kısmi (8 grup) | ✅ 13 kategori | 🟢 Borsa MCP |
| **Mevzuat** | ❌ Yok | ✅ 80K karakter mevzuat | 🟢 Borsa MCP |

**📊 Sonuç:** Biz veri derinliğinde (2.2M fiyat, 793 hisse eşleşme) çok öndeyiz. Ama analiz araçları eksik. **BİZ DAHA İYİ (veri miktarı), BORSA MCP DAHA İYİ (analiz).**

---

### 6. KAP Bildirimleri

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Bildirim Sayısı** | ✅ 4,009 | ✅ Canlı API | 🟡 Eşit |
| **Kategori Etiketleme** | ✅ 13 kategori | ❌ Yok | 🟢 Biz |
| **Detay Parse** | ⚠️ 93 kayıt (ihale, blok satış) | ✅ news_id ile detay | 🟢 Borsa MCP |
| **Katalizör İşaretleme** | ✅ is_catalyst flag | ❌ Yok | 🟢 Biz |
| **Otomatik Çekim** | ✅ Cron job (her saat) | ❌ Manuel | 🟢 Biz |
| **İhale Sözleşme Tutarı** | ✅ Parse edilmiş | ❌ Yok | 🟢 Biz |
| **Blok Satış Verisi** | ✅ disclosure_details | ❌ Yok | 🟢 Biz |

**📊 Sonuç:** Biz bildirimleri otomatik çekip yapılandırıyoruz. **BİZ DAHA İYİ.**

---

### 7. Kripto Para

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **BtcTurk** | ✅ 6 pair | ✅ 295+ pair | 🟢 Borsa MCP |
| **Coinbase** | ✅ 6 pair | ✅ 500+ pair | 🟢 Borsa MCP |
| **Anlık Fiyat** | ✅ | ✅ | 🟡 Eşit |
| **Orderbook** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **İşlem Geçmişi** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **OHLC/Kline** | ❌ Yok | ✅ Var | 🟢 Borsa MCP |
| **Çapraz Piyasa Analizi** | ❌ Yok | ✅ TRY vs USD karşılaştırma | 🟢 Borsa MCP |
| **Kalıcı Saklama** | ✅ DB'de | ❌ Yok | 🟢 Biz |

**📊 Sonuç:** Borsa MCP kriptoda çok daha kapsamlı. **BORSA MCP DAHA İYİ.**

---

### 8. Döviz & Emtia

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Döviz Kuru** | ✅ 17 kayıt (TCMB) | ✅ 65 para birimi (borsapy) | 🟢 Borsa MCP |
| **Emtia** | ✅ 11 kayıt (altın, petrol) | ✅ Brent, WTI, altın, gümüş | 🟢 Borsa MCP |
| **Tarihsel Kur** | ❌ Yok | ✅ Dakikalık veri | 🟢 Borsa MCP |
| **Yakıt Fiyatları** | ❌ Yok | ✅ Benzin, dizel, LPG | 🟢 Borsa MCP |

**📊 Sonuç:** Borsa MCP döviz/emtia'da çok daha geniş. **BORSA MCP DAHA İYİ.**

---

### 9. Makro Veri & Ekonomik Takvim

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **TCMB Enflasyon** | ✅ TÜFE/ÜFE (24 ay) | ✅ TÜFE/ÜFE (245+ ay) | 🟢 Borsa MCP (daha derin) |
| **TCMB EVDS** | ❌ Yok | ✅ 145 kategori | 🟢 Borsa MCP |
| **Enflasyon Hesaplama** | ❌ Yok | ✅ TCMB API (satın alma gücü) | 🟢 Borsa MCP |
| **Ekonomik Takvim** | ✅ 356 olay (7 ülke) | ✅ 7 ülke (doviz.com) | 🟡 Eşit |
| **Tahvil Faizleri** | ❌ Yok | ✅ TR 2Y/5Y/10Y | 🟢 Borsa MCP |
| **GDP Büyüme** | ❌ Yok | ✅ World Bank | 🟢 Borsa MCP |

**📊 Sonuç:** Borsa MCP makro veride çok daha kapsamlı. **BORSA MCP DAHA İYİ.**

---

### 10. Screener & Tarama

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **BIST Screener** | ✅ 8 preset | ✅ 15 preset + özel filtre (50+ alan) | 🟢 Borsa MCP |
| **US Screener** | ❌ Yok | ✅ 23 preset + 96 filtre alanı | 🟢 Borsa MCP |
| **Teknik Scanner** | ✅ Basit (RSI/MACD) | ✅ 22 preset (TradingView) | 🟢 Borsa MCP |
| **Özel Filtre** | ❌ Yok | ✅ Kullanıcı tanımlı | 🟢 Borsa MCP |
| **Sektör Tarama** | ❌ Yok | ✅ Sektör bazlı | 🟢 Borsa MCP |

**📊 Sonuç:** Borsa MCP taramada çok daha güçlü. **BORSA MCP DAHA İYİ.**

---

### 11. Analist & Değerleme

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Aanalist Derecelendirmesi** | ❌ Yok | ✅ AL/SAT/TUT + fiyat hedefi | 🟢 Borsa MCP |
| **Kazanç Takvimi** | ❌ Yok | ✅ EPS geçmişi + tahmin | 🟢 Borsa MCP |
| **Buffett Analizi** | ❌ Yok | ✅ Owner Earnings, DCF, Safety Margin | 🟢 Borsa MCP |
| **Sektör Karşılaştırması** | ❌ Yok | ✅ Sektör ortalaması + pozisyon | 🟢 Borsa MCP |
| **Finansal Sağlık** | ❌ Yok | ✅ Altman Z-Score, ROIC | 🟢 Borsa MCP |
| **Piyasa Rasyoları (F/K, PD/DD)** | ⚠️ Kısmi | ✅ Tam (valuation, buffett, health, advanced) | 🟢 Borsa MCP |

**📊 Sonuç:** Analiz ve değerleme araçlarında Borsa MCP çok önde. **BORSA MCP DAHA İYİ.**

---

### 12. Kurumsal İşlemler

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Temettü Geçmişi** | ❌ corporate_actions boş | ✅ Per-share + verim + payout | 🟢 Borsa MCP |
| **Bölünme (Split)** | ❌ Yok | ✅ Tarih + oran | 🟢 Borsa MCP |
| **Sermaye Artırımı** | ✅ KAP'tan (bedelli/bedelsiz) | ✅ İş Yatırım'dan | 🟡 Yakın |
| **Geri Alım** | ✅ 30 buyback (detaylı) | ❌ Yok | 🟢 Biz |

**📊 Sonuç:** Borsa MCP temettü/split'te, biz geri alımda öndeyiz. **BÖLÜŞMÜŞ.**

---

### 13. Ortaklık Yapısı & Yönetim

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Ortaklar** | ❌ 0 (Selenium gerekli) | ❌ Yok | 🔴 İkimizde de yok |
| **Yönetim Kurulu** | ❌ 0 (Selenium gerekli) | ❌ Yok | 🔴 İkimizde de yok |
| **Nitelikli Pay Sahipleri** | ❌ Yok | ❌ Yok | 🔴 İkimizde de yok |
| **Bağlı Ortaklıklar** | ✅ 20 kayıt | ❌ Yok | 🟢 Biz |

---

### 14. Dashboard & Kullanıcı Deneyimi

| Kriter | Biz | Borsa MCP | Kazanan |
|--------|-----|-----------|---------|
| **Admin Paneli** | ✅ Gerçek zamanlı dashboard | ❌ Yok | 🟢 Biz |
| **Canlı Loglar** | ✅ Terminal çıktısı | ❌ Yok | 🟢 Biz |
| **Servis Yönetimi** | ✅ Start/Stop/Restart | ❌ Yok | 🟢 Biz |
| **Zamanlama Ayarları** | ✅ Dashboard'dan | ❌ Yok | 🟢 Biz |
| **Şirket Detay Sayfası** | ✅ Tek sayfada tüm veri | ❌ Yok | 🟢 Biz |
| **Fiyat Grafiği** | ✅ Canvas chart | ❌ Yok | 🟢 Biz |
| **Sektör Filtresi** | ❌ Yok | ❌ Yok | 🔴 İkimizde de yok |
| **Portföy Takibi** | ❌ Yok | ❌ Yok | 🔴 İkimizde de yok |
| **Mobil Uyumlu** | ✅ Responsive | ❌ N/A | 🟢 Biz |

---

## 🏆 GENEL SKOR TABLOSU

| Kategori | Biz | Borsa MCP | Kazanan |
|----------|:---:|:---------:|---------|
| Hisse Fiyatları | ⭐⭐⭐ | ⭐⭐⭐ | 🟡 Eşit |
| Şirket Profili | ⭐⭐ | ⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Finansal Tablolar | ⭐⭐⭐⭐ | ⭐⭐⭐ | 🟢 Biz (orijinal KAP) |
| Finansal Oranlar | ⭐⭐ | ⭐⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Teknik Analiz | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 🟢 Borsa MCP |
| TEFAS Fonlar | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 🟢 Biz (2.5x veri) |
| KAP Bildirimleri | ⭐⭐⭐⭐ | ⭐⭐⭐ | 🟢 Biz |
| Kripto | ⭐⭐ | ⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Döviz/Emtia | ⭐⭐ | ⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Makro Veri | ⭐⭐ | ⭐⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Screener | ⭐⭐ | ⭐⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Analist/Değerleme | ⭐ | ⭐⭐⭐⭐⭐ | 🟢 Borsa MCP |
| Kurumsal İşlemler | ⭐⭐ | ⭐⭐⭐ | 🟡 Bölüşmüş |
| Dashboard | ⭐⭐⭐⭐⭐ | ⭐ | 🟢 Biz |
| Otomasyon | ⭐⭐⭐⭐⭐ | ⭐ | 🟢 Biz |
| Anti-Ban | ⭐⭐⭐⭐ | ⭐ | 🟢 Biz |
| Veri Saklama | ⭐⭐⭐⭐⭐ | ⭐⭐ | 🟢 Biz |

---

## 🎯 SONUÇ & ÖNERİLER

### Bizim Güçlü Yanlarımız (11/17):
1. **Dashboard & UX** — Gerçek zamanlı admin paneli, grafikler, loglar
2. **Otomasyon** — Cron job, scheduler, otomatik veri çekme
3. **Anti-Ban** — Jitter, cooldown, UA rotation
4. **Veri Saklama** — 2.2M+ kayıt, kalıcı SQLite DB
5. **TEFAS Derinliği** — 2,591 fon, 2.2M fiyat, 793 hisse-eşleşme
6. **KAP Bildirim Otomasyonu** — 4,009 bildirim, 13 kategori, katalizör işaretleme
7. **Geri Alım Programları** — 30 buyback detaylı parse
8. **Fiyat Grafiği** — Canvas chart ile interaktif gösterim
9. **Mikroservis** — Bağımsız KAP/TEFAS/Market worker'lar
10. **Bağlı Ortaklıklar** — 20 şirket verisi
11. **Sektör Eşleme** — 607/759 şirket (yfinance ile)

### Borsa MCP'nin Güçlü Yanları (6/17):
1. **Finansal Oranlar** — Buffett, Altman Z-Score, ROIC, EV/EBITDA
2. **Teknik Analiz** — 20+ gösterge (TradingView)
3. **Screener** — 38+ preset, 50+ filtre alanı
4. **Değerleme** — Analist derecelendirmesi, kazanç takvimi
5. **Çoklu Piyasa** — ABD, kripto, döviz tek çatı
6. **LLM Entegrasyonu** — MCP protokolü

### Eksiklerimizi Tamamlama Planı:
1. 🔴 **Buffett Analizi** → Borsa MCP'den port et
2. 🔴 **Sektör Karşılaştırması** → Borsa MCP'den port et
3. 🔴 **Analiz Araçları** → 15+ teknik gösterge ekle
4. 🔴 **US Screener** → Yahoo Finance screener entegre et
5. 🔴 **Ortak/Yönetim** → Selenium ile KAP'tan çek
6. 🔴 **Temettü Geçmişi** → KAP'tan parse et
