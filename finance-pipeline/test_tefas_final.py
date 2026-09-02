"""Test TEFAS with calismaTipi and proper param names from JS analysis"""
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
        toplam = d.get('toplamSayi')
        toplam_sayfa = d.get('toplamSayfa')
        print(f"\n{'='*60}")
        print(f"POST {name} {label}")
        if err:
            print(f"Error: {err}")
        if count > 0:
            print(f"Records: {count} (toplamSayi={toplam}, toplamSayfa={toplam_sayfa})")
            print(json.dumps(result[0], ensure_ascii=False, indent=2)[:1000])
        elif count == 0:
            print(f"Empty (toplamSayi={toplam})")
        else:
            print(json.dumps(d, ensure_ascii=False, indent=2)[:800])
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(2)

# Key insight: use calismaTipi=2 (no dates) with fonTipi
# From JS: "dil:u.toUpperCase(),fonTipi:o,...islem:e"
# From JS: dagilimSiraliGetirT uses same structure

# Test 1: fonGnlBlgSiraliGetir with calismaTipi
test("fonGnlBlgSiraliGetir", {
    "dil": "TR",
    "fonTipi": "F",
    "fonTurKod": 101,
    "fonGrubu": 82,
    "calismaTipi": 2,
    "sayfaNo": 1,
    "sayfaBasinaKayit": 10
}, "fonTipi=F,calismaTipi=2")

# Test 2: dagilimSiraliGetirT with same structure
test("dagilimSiraliGetirT", {
    "dil": "TR",
    "fonTipi": "F",
    "fonTurKod": 101,
    "fonGrubu": 82,
    "calismaTipi": 2,
    "sayfaNo": 1,
    "sayfaBasinaKayit": 10
}, "fonTipi=F,calismaTipi=2")

# Test 3: Minimal - just fonTipi and dil
test("fonGnlBlgSiraliGetir", {
    "dil": "TR",
    "fonTipi": "F",
    "calismaTipi": 2,
    "sayfaNo": 1,
    "sayfaBasinaKayit": 10
}, "minimal")

# Test 4: Try different fonTipi values
for tip in ["F", "YAT", "EMK", "BYF", "Y", "1", "P"]:
    test("fonGnlBlgSiraliGetir", {
        "dil": "TR",
        "fonTipi": tip,
        "calismaTipi": 2,
        "sayfaNo": 1,
        "sayfaBasinaKayit": 5
    }, f"fonTipi={tip}")
