# Finance Pipeline — Mikroservis Mimarisi

KAP ve TEFAS veri boru hatlarini bagimsiz mikroservis olarak calistiran, Docker uzerinden yonetilen production-grade sistem.

## Mimari

```
┌──────────────────────────────────────────────────────────────┐
│                   Admin Dashboard (:3000)                     │
│          Docker Soketi ile konteyner yonetimi                │
│       Start/Stop/Restart/Trigger + Canli Loglar              │
└──────────────┬──────────────────────┬────────────────────────┘
               │                      │
    ┌──────────▼──────────┐ ┌────────▼───────────────┐
    │   KAP Worker (:8002)│ │  TEFAS Worker (:8001)  │
    │  Sirket + Finansal  │ │  Fon Fiyat + Portfoy   │
    │  Bildirim + Kurumsal│ │  5 Yillik Gecmis       │
    └──────────┬──────────┘ └────────┬───────────────┘
               │                      │
    ┌──────────▼──────────────────────▼───────────────┐
    │           PostgreSQL (:5432)                     │
    │        Ortak Veritabani (finance_platform)       │
    └─────────────────────────────────────────────────┘
```

## Hizli Baslatma

```bash
# Tum servisleri baslat
docker-compose up -d --build

# Sadece belirli servis
docker-compose up -d tefas_worker
docker-compose up -d kap_worker

# Loglari izle
docker-compose logs -f admin_dashboard

# Durum kontrolu
docker-compose ps
```

## Erisim Noktalari

| Servis | URL | Aciklama |
|--------|-----|----------|
| Admin Dashboard | http://localhost:3000 | Yonetim paneli |
| KAP Worker API | http://localhost:8002 | KAP servis API |
| TEFAS Worker API | http://localhost:8001 | TEFAS servis API |
| PostgreSQL | localhost:5432 | Veritabani |

## Servisler

### KAP Worker (:8002)
BIST sirket listesi, mali tablolar, bildirim akisi, kurumsal islemler, geri alim, IPO verilerini ceker.
- Cron: Her gun 02:00 Istanbul
- Manuel: `POST /api/scrape/now`

### TEFAS Worker (:8001)
TEFAS uzerindeki tum fonlarin (YAT/EMK/BYF) son 5 yillik fiyat ve portfoy dagilim verilerini ceker.
- 28 gunluk chunking ile TEFAS limitlerini asar
- Cron: Her gun 03:00 Istanbul
- Manuel: `POST /api/scrape/now`

### Admin Dashboard (:3000)
Tum servisleri Docker soketi uzerinden yonetir:
- Servis durumu (RUNNING/STOPPED)
- Start/Stop/Restart kontrol
- Manuel veri cekimi tetikleme
- Canli log izleme (3sn auto-refresh)
- Pipeline calistirma gecmisi

## API Referansi

### Admin Dashboard
```
GET  /api/containers              — Tum konteyner durumlari
GET  /api/containers/{name}       — Tek konteyner detayi
POST /api/containers/{name}/start — Konteyner baslat
POST /api/containers/{name}/stop  — Konteyner durdur
POST /api/containers/{name}/restart — Konteyner yeniden baslat
POST /api/containers/{name}/trigger — Veri cekimi tetikle
GET  /api/containers/{name}/logs   — Canli loglar
GET  /api/stats                    — Genel istatistikler
GET  /api/pipeline/runs            — Calistirma gecmisi
```

### TEFAS Worker
```
GET  /health           — Saglik kontrolu
GET  /api/status       — Durum ve istatistikler
POST /api/scrape/now   — Tam tarama baslat
GET  /api/logs         — Isleme loglari
```

### KAP Worker
```
GET  /health           — Saglik kontrolu
GET  /api/status       — Durum ve istatistikler
POST /api/scrape/now   — Tum modulleri calistir
POST /api/scrape/{mod} — Tek modul calistir
GET  /api/logs         — Isleme loglari
```

## Veritabani Tablolari

### KAP Tablolari
- `kap_companies` — BIST sirket listesi
- `kap_financials` — Mali tablolar ve rasyolar
- `kap_disclosures` — Bildirim akisi
- `kap_corporate_actions` — Temettu ve sermaye islemleri

### TEFAS Tablolari
- `tefas_funds` — Fon listesi (YAT/EMK/BYF)
- `tefas_fund_prices` — Gunluk fon fiyatlari
- `tefas_fund_allocations` — Portfoy dagilim oranlari (25+ sinif)

### Ortak Tablo
- `pipeline_runs` — Calistirma gecmisi ve loglar

## Gelistirme

```bash
# Yerel gelistirme (Docker yoksa)
pip install -r services/tefas_worker/requirements.txt
pip install -r services/admin_dashboard/requirements.txt
export DATABASE_URL=postgresql://admin:secret_password@localhost:5432/finance_platform
python services/tefas_worker/main.py      # Port 8001
python services/admin_dashboard/main.py   # Port 3000
```

## Ortam Degiskenleri

| Degisken | Varsayilan | Aciklama |
|----------|-----------|----------|
| DATABASE_URL | postgresql://admin:secret_password@postgres_db:5432/finance_platform | PostgreSQL URL |
| KAP_PIPELINE_DIR | /app/kap-pipeline | KAP pipeline kodu |
