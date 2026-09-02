"""Test ALL TEFAS endpoints discovered from JS analysis"""
import requests, json, time

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.tefas.gov.tr/',
    'Origin': 'https://www.tefas.gov.tr',
    'Content-Type': 'application/json',
})

BASE = 'https://www.tefas.gov.tr'

# All endpoints discovered from JS
tests = [
    # Known working
    ("fonBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonFiyatBilgiGetir", {"fonKodu": "YAC", "dil": "TR", "periyod": 6}),

    # From JS .post calls (common chunk)
    ("fonDetayGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonBuyuklukBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonGetiriBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonYonetimBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonGnlBlgSiraliGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("dagilimSiraliGetirT", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonAlSatEkranValorHesapla", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonGrupGetir", {"dil": "TR"}),
    ("fonKurucuGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonProfilDtyGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonTipiGetir", {"dil": "TR"}),
    ("fonTurDnmGetiriGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonTurGetir", {"dil": "TR"}),
    ("fonUnvanGetir", {"fonKodu": "YAC", "dil": "TR"}),
    ("fonUnvanAra", {"fonKodu": "YAC", "dil": "TR"}),

    # Trading volume / market data (tefas/ prefix)
    ("tefas/getFplFonList", {"dil": "TR"}),
    ("tefas/getFplFonBazliIslemHacmi", {"dil": "TR"}),
    ("tefas/getFplFonTurBazliIslemHacmi", {"dil": "TR"}),
    ("tefas/getFplFonTuruBazindaFonSayisi", {"dil": "TR"}),
    ("tefas/getFplHaftaList", {"dil": "TR"}),
    ("tefas/getFplIslemYapanKurumAdet", {"dil": "TR"}),
    ("tefas/getFplMkkStokBakiye", {"fonKodu": "YAC", "dil": "TR"}),
    ("tefas/getFplToplamIslemHacmi", {"dil": "TR"}),
    ("tefas/getFplUyeBazliIslemHacmi", {"dil": "TR"}),
    ("tefas/getFplUyeTipiBazliIslemHacmi", {"dil": "TR"}),
    ("tefas/getFplDovizList/v2", {"dil": "TR"}),

    # Home page
    ("fonTefasDuyuruGetir", {"dil": "TR"}),
    ("fonDonemGetir", {"dil": "TR"}),
]

print(f"Testing {len(tests)} TEFAS API endpoints...\n")

for name, payload in tests:
    # Try both with and without /api/funds prefix
    for prefix in ["/api/funds", "/api", ""]:
        path = f"{prefix}/{name}"
        try:
            r = s.post(f"{BASE}{path}", json=payload, timeout=10)
            if r.status_code == 200:
                d = r.json()
                count = len(d.get("resultList", [])) if isinstance(d.get("resultList"), list) else -1
                if count > 0:
                    keys = list(d["resultList"][0].keys()) if isinstance(d["resultList"][0], dict) else ["non-dict"]
                    print(f"  OK {path}: {count} records | keys={keys[:12]}")
                    break
                elif count == -1:
                    # Result might be a dict, not a list
                    top_keys = list(d.keys())
                    print(f"  OK {path}: dict response | keys={top_keys}")
                    break
                else:
                    if prefix == "":  # Only print empty on last attempt
                        raw = json.dumps(d, ensure_ascii=False)[:200]
                        print(f"  EMPTY {name}: {raw}")
                    continue
            elif r.status_code == 404:
                continue  # Try next prefix
            else:
                continue
        except Exception as e:
            continue
        break
    time.sleep(1)
