"""Try epoch timestamps and long date formats for TEFAS sorted endpoints"""
import requests, json, time
from datetime import datetime

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
            print(json.dumps(result[0], ensure_ascii=False, indent=2)[:800])
        elif count == 0:
            print("Empty result")
        else:
            print(json.dumps(d, ensure_ascii=False, indent=2)[:800])
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(2)

# Epoch timestamps (milliseconds)
now_ms = int(datetime.now().timestamp() * 1000)
month_ago_ms = int((datetime.now().timestamp() - 30*86400) * 1000)

test("dagilimSiraliGetirT", {
    "fonKodu": "YAC", "dil": "TR",
    "basTarih": month_ago_ms, "bitTarih": now_ms,
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "epoch ms")

# Long format
test("dagilimSiraliGetirT", {
    "fonKodu": "YAC", "dil": "TR",
    "basTarih": "2026-08-01T00:00:00", "bitTarih": "2026-08-28T23:59:59",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "ISO datetime")

# Try without dates but with fonGrubu
test("dagilimSiraliGetirT", {
    "fonGrubu": 82, "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "no dates with fonGrubu")

# Try fonGnlBlgSiraliGetir with fonGrubu + fonTur
test("fonGnlBlgSiraliGetir", {
    "fonGrubu": 82, "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "no dates with fonGrubu+fonTur")

# dagilimSiraliGetirDosya (file version)
test("dagilimSiraliGetirDosya", {
    "fonGrubu": 82, "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "no dates with fonGrubu+fonTur")

test("fonGnlBlgSiraliGetirDosya", {
    "fonGrubu": 82, "fonTur": 100, "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "no dates with fonGrubu+fonTur")

# Now try with fonTipi instead
test("dagilimSiraliGetirT", {
    "fonTipi": "YAT", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "fonTipi=YAT")

test("fonGnlBlgSiraliGetir", {
    "fonTipi": "YAT", "dil": "TR",
    "sayfaNo": 1, "sayfaBasinaKayit": 10
}, "fonTipi=YAT")
