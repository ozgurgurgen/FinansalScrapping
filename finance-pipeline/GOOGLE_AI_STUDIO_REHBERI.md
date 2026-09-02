# 🔗 Google AI Studio - Finance Pipeline Bağlantı Rehberi

## 📋 Bağlantı Bilgileri

| Bilgi | Değer |
|-------|-------|
| **API Base URL** | `https://signal-invitations-draws-perspectives.trycloudflare.com` |
| **OpenAPI Spec** | `finance-pipeline/openapi_spec.json` |
| **Auth Gerekli mi?** | Hayır (şimdilik) |

---

## 🚀 Adım Adım Kurulum

### Adım 1: Google AI Studio'yu Açın
https://aistudio.google.com/

### Adım 2: Yeni Bir Proje Oluşturun
- "Create New" → "Chat" veya "Application" seçin

### Adım 3: Custom Connector Ekleyin
Sol menüden **"Extensions"** veya **"Tools"** bölümüne gidin:
1. **"Add Extension"** veya **"Add Tool"** tıklayın
2. **"Custom Connector"** seçeneğini seçin
3. **Connector Name:** `Finance Pipeline`
4. **Base URL:** `https://signal-invitations-draws-perspectives.trycloudflare.com`
5. **OpenAPI Spec:** `openapi_spec.json` dosyasını yükleyin

### Adım 4: Tool'ları Test Edin
Bağlantı kurulduktan sonra şu istekleri test edin:

#### Test 1: Şirket Ara
```
THYAO şirketini ara
```
Beklenen yanıt: Türk Hava Yolları bilgileri

#### Test 2: Tüm Verileri Çek
```
THYAO'nun tüm finansal verilerini göster
```
Beklenen yanıt: Finansal tablolar, bildirimler, ortaklar

#### Test 3: Fon Sorgula
```
TCD fonunun detaylarını getir
```
Beklenen yanıt: Fon bilgisi + fiyat geçmişi

---

## 📝 API Endpoint'leri

### 1. Şirket Ara
```
GET /api/export/search?q={arama_terimi}&limit={sayi}
```
**Örnek:** `GET /api/export/search?q=THY`

### 2. Şirket Tüm Veriler
```
GET /api/export/all/{ticker}
```
**Örnek:** `GET /api/export/all/THYAO`

**Dönen Veriler:**
- `company`: Şirket temel bilgisi
- `financials`: Finansal tablolar (gelir, kâr, oranlar)
- `disclosures`: Son 50 bildirim
- `shareholders`: Pay sahipleri
- `management`: Yönetim kurulu
- `subsidiaries`: Bağlı ortaklıklar
- `cashflows`: Nakit akış

### 3. Finansal Veriler
```
GET /api/export/financials/{ticker}
```
**Örnek:** `GET /api/export/financials/ASELS`

**Dönen Alanlar:**
- `revenue`: Hasılat
- `gross_profit`: Brüt Kâr
- `ebitda`: FAVÖK
- `net_profit`: Net Kâr
- `pe_ratio`: F/K Oranı
- `pb_ratio`: PD/DD
- `roe`: Özkaynak Kârlılığı
- `roa`: Aktif Kârlılığı

### 4. TEFAS Fonları
```
GET /api/export/funds?limit={sayi}
```
**Örnek:** `GET /api/export/funds?limit=50`

### 5. Fon Detay
```
GET /api/export/fund/{kod}
```
**Örnek:** `GET /api/export/fund/TCD`

### 6. Tüm Şirketler
```
GET /api/export/companies
```

### 7. Toplu Export
```
GET /api/export/bulk?tables={tablo_listesi}&limit_per_table={limit}
```
**Örnek:** `GET /api/export/bulk?tables=companies,financials`

---

## 💡 Kullanım Örnekleri

### Gemini'ye Sorulabilecek Sorular

**Şirket Analizi:**
- "THYAO'nun son finansal durumu nasıl?"
- "Garanti Bankası'nın F/K oranı nedir?"
- "En kârlı 5 şirketi göster"
- "ASELSAN'ın yönetim kurulu üyeleri kimler?"

**Sektör Analizi:**
- "Bankacılık sektöründeki şirketlerin F/K ortalaması nedir?"
- "Savunma sanayii şirketlerini listele"
- "Gıda sektöründe hangi şirketler kârlı?"

**Bildirim Takibi:**
- "THYAO'nun son bildirimleri neler?"
- "Bugün hangi şirketler bildirim yaptı?"
- "Temettü bildirimi yapan şirketleri göster"

**Fon Analizi:**
- "TCD fonu son 1 ayda nasıl performans gösterdi?"
- "En büyük 5 yatırım fonu hangileri?"
- "Altın fonlarının performansı nasıl?"

---

## ⚠️ Önemli Notlar

1. **Tünel URL'si Değişebilir:** Cloudflare Quick Tunnel her başlatmada URL değiştirir. Kalıcı URL için Cloudflare hesabına bağlanın.

2. **Rate Limit Yok:** Şu an için API'de rate limit yok. Ama aşırı kullanım engellenebilir.

3. **Güvenlik:** Şu an herkes erişebilir. Üretimde API key eklemenizi öneririm.

4. **Büyük Veri:** `/api/export/bulk` endpoint'i 2M+ satır döndürebilir. Yavaş olabilir.

---

## 🔧 Sorun Giderme

### Hata: "Connection refused"
- Tünelin çalıştığını kontrol edin: `curl https://signal-invitations-draws-perspectives.trycloudflare.com/api/export/schema`
- Dashboard'un çalıştığını kontrol edin: `http://localhost:3000`

### Hata: "Timeout"
- Büyük sorgular için `limit_per_table` parametresi kullanın
- Örnek: `?tables=companies,financials&limit_per_table=100`

### Hata: "CORS"
- API'miz CORS destekliyor. Eğer hata alırsanız, dashboard'u yeniden başlatın.

---

## 📞 Destek

Sorun yaşarsanız:
1. API'nin çalıştığını kontrol edin: `curl http://localhost:3000/api/export/schema`
2. Tünelin çalıştığını kontrol edin: `curl https://signal-invitations-draws-perspectives.trycloudflare.com/api/export/schema`
3. Dashboard'u yeniden başlatın: `taskkill //F //IM python.exe` sonra `start_services.py`
