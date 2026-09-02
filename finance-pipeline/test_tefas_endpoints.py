"""Scan TEFAS for all available API endpoints"""
import requests, json, time, sys

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.tefas.gov.tr/',
    'Origin': 'https://www.tefas.gov.tr',
    'Content-Type': 'application/json'
})

BASE = 'https://www.tefas.gov.tr'

endpoints = [
    # Known working
    ('/api/funds/fonBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonFiyatBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR', 'periyod': 6}),

    # Fund list variants
    ('/api/funds/fonTumuGetir', {'dil': 'TR'}),
    ('/api/funds/fonListesiGetir', {'dil': 'TR'}),
    ('/api/funds/fonTumListeGetir', {'dil': 'TR'}),
    ('/api/funds/fonTumuGunlukGetir', {'dil': 'TR'}),
    ('/api/funds/fonTumBilgilerGetir', {'dil': 'TR'}),

    # Portfolio / Allocation
    ('/api/funds/fonDagitimGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonDagitimOraniGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonPortfoyGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonPortfoyBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonPortfoyDagitimGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonHisseDagitimGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonVarlikDagitimGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonToplamDagitimGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Performance / Return
    ('/api/funds/fonPerformansGetir', {'fonKodu': 'YAC', 'dil': 'TR', 'periyod': 6}),
    ('/api/funds/fonGetiriGetir', {'fonKodu': 'YAC', 'dil': 'TR', 'periyod': 6}),
    ('/api/funds/fonGetiriYuzdeGetir', {'fonKodu': 'YAC', 'dil': 'TR', 'periyod': 6}),

    # Daily
    ('/api/funds/fonGunlukKiyaslamaGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonGunlukYatirimciGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonGunlukOzetGetir', {'dil': 'TR'}),
    ('/api/funds/fonGunlukVeriGetir', {'fonKodu': 'YAC', 'dil': 'TR', 'periyod': 6}),
    ('/api/funds/fonGunlukFiyatGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Investors
    ('/api/funds/fonKisiSayisiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonKisiSayisiGunlukGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Size / Market
    ('/api/funds/fonToplamDegerGetir', {'dil': 'TR'}),
    ('/api/funds/fonBuyuklukGetir', {'dil': 'TR'}),

    # Risk / Benchmark
    ('/api/funds/fonRiskGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonBenchmarkGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Detail
    ('/api/funds/fonDetayGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonDetayBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonBilgiDetayGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Categories
    ('/api/funds/fonKategoriSiralamasiGetir', {'dil': 'TR'}),
    ('/api/funds/fonKategoriDetayGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),

    # Settlement / Order
    ('/api/funds/fonTertipBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonBaslangicBedelGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
    ('/api/funds/fonTanimBilgiGetir', {'fonKodu': 'YAC', 'dil': 'TR'}),
]

print(f"Testing {len(endpoints)} TEFAS API endpoints...\n")

for path, payload in endpoints:
    try:
        url = f'{BASE}{path}'
        r = s.post(url, json=payload, timeout=8)
        if r.status_code == 200:
            d = r.json()
            count = len(d.get('resultList', []))
            if count > 0:
                keys = list(d['resultList'][0].keys())
                print(f'  ✅ {path}: {count} records | keys={keys}')
            else:
                resp_str = json.dumps(d, ensure_ascii=False)[:150]
                print(f'  ⚠️  {path}: 200 but empty | {resp_str}')
        elif r.status_code == 404:
            pass  # skip 404s silently
        else:
            print(f'  ❓ {path}: {r.status_code}')
    except Exception as e:
        pass
    time.sleep(1.5)
