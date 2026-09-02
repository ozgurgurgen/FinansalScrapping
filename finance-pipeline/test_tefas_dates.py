"""Test sorted/paginated TEFAS endpoints with correct date params"""
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
        if r.status_code == 200:
            d = r.json()
            err = d.get('errorMessage')
            result = d.get('resultList') or d.get('result')
            count = len(result) if isinstance(result, list) else -1
            print(f"\n{'='*60}")
            print(f"POST {name} {label}")
            print(f"Payload: {json.dumps(payload)}")
            if err:
                print(f"Error: {err}")
            if count > 0:
                print(f"Records: {count}")
                print(json.dumps(result[0], ensure_ascii=False, indent=2)[:1000])
            elif count == 0:
                print("Empty result")
            else:
                print(json.dumps(d, ensure_ascii=False, indent=2)[:1000])
    except Exception as e:
        print(f"  {name}: ERROR {e}")
    time.sleep(2)

# Test sorted endpoints with date params
test("dagilimSiraliGetirT", {
    "fonKodu": "", "dil": "TR", "fonTur": 100,
    "fonGrubu": 82, "sayfaNo": 1, "sayfaBasinaKayit": 5,
    "basTarih": "2026-08-01", "bitTarih": "2026-08-28"
}, "with dates")

test("dagilimSiraliGetirT", {
    "dil": "TR", "fonTur": 100,
    "sayfaNo": 1, "sayfaBasinaKayit": 5
}, "no dates")

test("fonGnlBlgSiraliGetir", {
    "fonKodu": "", "dil": "TR", "fonTur": 100,
    "fonGrubu": 82, "sayfaNo": 1, "sayfaBasinaKayit": 5,
    "basTarih": "2026-08-01", "bitTarih": "2026-08-28"
}, "with dates")

test("fonGnlBlgSiraliGetir", {
    "dil": "TR", "fonTur": 100,
    "sayfaNo": 1, "sayfaBasinaKayit": 5
}, "no dates")

# Try fonBuyuklukBazliBilgiGetir with date
test("fonBuyuklukBazliBilgiGetir", {
    "fonKodu": "", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 5
}, "all funds")

test("fonGetiriBazliBilgiGetir", {
    "fonKodu": "", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 5
}, "all funds")

test("fonYonetimBazliBilgiGetir", {
    "fonKodu": "", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 5
}, "all funds")

# fonAlSatEkranValorHesapla with more params
test("fonAlSatEkranValorHesapla", {
    "fonKodu": "YAC", "dil": "TR",
    "islemTutar": 1000, "islemTipi": "ALIS"
}, "buy")

# FonUnvanGetir
test("fonUnvanGetir", {
    "fonKodu": "YAC", "dil": "TR"
}, "YAC")

# fonProfilDtyGetir with different params
test("fonProfilDtyGetir", {
    "fonKodu": "YAC", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 50
}, "with pagination")
