"""Test TEFAS sorted endpoints with Turkish date format DD.MM.YYYY"""
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

def test(name, payload, label=""):
    url = f"{BASE}/api/funds/{name}"
    try:
        r = s.post(url, json=payload, timeout=15)
        d = r.json()
        err = d.get('errorMessage')
        result = d.get('resultList') or d.get('result')
        count = len(result) if isinstance(result, list) else -1
        print(f"\n{'='*60}")
        print(f"POST {name} {label}")
        if err:
            print(f"Error: {err}")
        if count > 0:
            print(f"Records: {count}")
            if isinstance(result, list):
                print(json.dumps(result[0], ensure_ascii=False, indent=2)[:800])
        elif count == 0:
            print("Empty result")
        else:
            print(json.dumps(d, ensure_ascii=False, indent=2)[:800])
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(2)

# Try Turkish date format DD.MM.YYYY
test("dagilimSiraliGetirT", {
    "fonKodu": "YAC", "dil": "TR",
    "basTarih": "01.08.2026", "bitTarih": "28.08.2026",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "DD.MM.YYYY format")

test("dagilimSiraliGetirT", {
    "fonKodu": "YAC", "dil": "TR",
    "fonTur": 100,
    "basTarih": "01.08.2026", "bitTarih": "28.08.2026",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "with fonTur")

test("fonGnlBlgSiraliGetir", {
    "fonKodu": "YAC", "dil": "TR",
    "basTarih": "01.08.2026", "bitTarih": "28.08.2026",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "DD.MM.YYYY format")

test("fonGnlBlgSiraliGetir", {
    "fonKodu": "", "dil": "TR",
    "fonTur": 100,
    "basTarih": "01.08.2026", "bitTarih": "28.08.2026",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "all funds")

# Test fonDetayGetir with more params
test("fonDetayGetir", {
    "fonKodu": "YAC", "dil": "TR",
    "basTarih": "01.01.2020", "bitTarih": "28.08.2026"
}, "with date range")

# Test fonAlSatEkranValorHesapla
test("fonAlSatEkranValorHesapla", {
    "fonKodu": "YAC", "dil": "TR",
    "islemTutar": 1000
}, "tutar")

test("fonAlSatEkranValorHesapla", {
    "fonKodu": "YAC", "dil": "TR",
    "tutar": 1000
}, "tutar field")

# Try fonBuyuklukBazliBilgiGetir with fonTur
test("fonBuyuklukBazliBilgiGetir", {
    "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "with fonTur")

# Try fonGetiriBazliBilgiGetir with fonTur
test("fonGetiriBazliBilgiGetir", {
    "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "with fonTur")

# Try fonYonetimBazliBilgiGetir with fonTur
test("fonYonetimBazliBilgiGetir", {
    "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "with fonTur")
