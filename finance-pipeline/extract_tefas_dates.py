"""Deep search for date format in TEFAS common JS chunk"""
import requests, re

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

url = 'https://www.tefas.gov.tr/_next/static/chunks/common-f00e5fba6a4ad2dc.js'
r = s.get(url, timeout=15)
text = r.text

# Find all patterns near basTarih / bitTarih / fonTipi
for keyword in ['basTarih', 'bitTarih', 'p_fontipi', 'fonTipi', 'sayfaNo', 'dagilimSirali', 'fonGnlBlgSirali']:
    indices = [m.start() for m in re.finditer(keyword, text)]
    if indices:
        print(f"\n=== '{keyword}' found {len(indices)} times ===")
        for idx in indices[:5]:
            start = max(0, idx - 200)
            end = min(len(text), idx + 200)
            chunk = text[start:end]
            print(f"  ...{chunk}...")
            print()
