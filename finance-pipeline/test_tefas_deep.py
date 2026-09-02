"""Deep test of ALL working TEFAS endpoints - show full data"""
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

def test(name, payload):
    url = f"{BASE}/api/funds/{name}"
    try:
        r = s.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            d = r.json()
            print(f"\n{'='*60}")
            print(f"POST {name}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            print(json.dumps(d, ensure_ascii=False, indent=2)[:2000])
            return d
        else:
            print(f"  {name}: {r.status_code}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")
    return None

# 1. ALL fund list (full list for discovery)
d = test("fonUnvanAra", {"fonKodu": "", "dil": "TR"})
time.sleep(2)

# 2. Fund groups
d = test("fonGrupGetir", {"dil": "TR"})
time.sleep(2)

# 3. Fund types
d = test("fonTurGetir", {"dil": "TR"})
time.sleep(2)

# 4. Fund type detail
d = test("fonTipiGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 5. Allocation sorted (try with fonKodu)
d = test("dagilimSiraliGetirT", {"fonKodu": "YAC", "dil": "TR", "sayfaNo": 1, "sayfaBasinaKayit": 20})
time.sleep(2)

# 6. Daily info sorted
d = test("fonGnlBlgSiraliGetir", {"fonKodu": "YAC", "dil": "TR", "sayfaNo": 1, "sayfaBasinaKayit": 20})
time.sleep(2)

# 7. Fund detail
d = test("fonDetayGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 8. Fund founder/creator
d = test("fonKurucuGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 9. Fund profile detail
d = test("fonProfilDtyGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 10. Management based
d = test("fonYonetimBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 11. Return based
d = test("fonGetiriBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 12. Size based
d = test("fonBuyuklukBazliBilgiGetir", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 13. Valor calculation
d = test("fonAlSatEkranValorHesapla", {"fonKodu": "YAC", "dil": "TR", "islemTutari": 1000})
time.sleep(2)

# 14. MKK stock balance
d = test("tefas/getFplMkkStokBakiye", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 15. Total trading volume
d = test("tefas/getFplToplamIslemHacmi", {"dil": "TR"})
time.sleep(2)

# 16. Fund-based trading volume
d = test("tefas/getFplFonBazliIslemHacmi", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 17. Member-based trading volume
d = test("tefas/getFplUyeBazliIslemHacmi", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 18. Member type trading volume
d = test("tefas/getFplUyeTipiBazliIslemHacmi", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 19. Institution count
d = test("tefas/getFplIslemYapanKurumAdet", {"fonKodu": "YAC", "dil": "TR"})
time.sleep(2)

# 20. Currency list
d = test("tefas/getFplDovizList/v2", {"dil": "TR"})
time.sleep(2)

# 21. Week list
d = test("tefas/getFplHaftaList", {"dil": "TR"})
time.sleep(2)

# 22. Fund count by type
d = test("tefas/getFplFonTuruBazindaFonSayisi", {"dil": "TR"})
