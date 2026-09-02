"""Test TEFAS endpoints properly"""
import requests, json, time, sys

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.tefas.gov.tr/',
    'Origin': 'https://www.tefas.gov.tr',
    'Content-Type': 'application/json',
})

BASE = 'https://www.tefas.gov.tr'

tests = [
    ("fonBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonFiyatBilgiGetir", {"fonKodu": "YAC", "dil": "TR", "periyod": 6}),
    ("fonTumuGetir", {"dil": "TR"}),
    ("fonListesiGetir", {"dil": "TR"}),
    ("fonDagitimGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonDagitimOraniGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonPortfoyGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonPerformansGetir", {"fonKodu": "YAC", "dil": "TR", "periyod": 6}),
    ("fonGetiriGetir", {"fonKodu": "YAC", "dil": "TR", "periyod": 6}),
    ("fonGunlukKiyaslamaGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonKisiSayisiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonKisiSayisiGunlukGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonGunlukOzetGetir", {"dil": "TR"}),
    ("fonToplamDegerGetir", {"dil": "TR"}),
    ("fonBuyuklukGetir", {"dil": "TR"}),
    ("fonRiskGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonBenchmarkGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonDetayGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonKategoriSiralamasiGetir", {"dil": "TR"}),
    ("fonTumuGunlukGetir", {"dil": "TR"}),
    ("fonGunlukVeriGetir", {"fonKodu": "YAC", "dil": "TR", "periyod": 6}),
    ("fonGunlukYatirimciGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonHisseDagitimGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonVarlikDagitimGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonPortfoyDagitimGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonTertipBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonBaslangicBedelGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonTanimBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
]

print(f"Testing {len(tests)} TEFAS endpoints...\n")

for name, payload in tests:
    path = f"/api/funds/{name}"
    try:
        r = s.post(f"{BASE}{path}", json=payload, timeout=10)
        if r.status_code == 200:
            d = r.json()
            count = len(d.get("resultList", []))
            if count > 0:
                keys = list(d["resultList"][0].keys())
                print(f"  OK {name}: {count} records | keys={keys}")
                # Print first record for new endpoints
            else:
                raw = json.dumps(d, ensure_ascii=False)[:200]
                print(f"  EMPTY {name}: 200 but no data | {raw}")
        elif r.status_code == 404:
            print(f"  404 {name}")
        else:
            print(f"  {r.status_code} {name}")
    except Exception as e:
        print(f"  ERR {name}: {e}")
    time.sleep(1.5)
