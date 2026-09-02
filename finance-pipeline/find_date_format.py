"""Find the date format function h() in TEFAS JS"""
import requests, re

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Referer': 'https://www.tefas.gov.tr/',
})

url = 'https://www.tefas.gov.tr/_next/static/chunks/common-f00e5fba6a4ad2dc.js'
r = s.get(url, timeout=15)
text = r.text

# Find the h() function definition near basTarih usage
# The JS has: "e=h(r),l=h(t)" where r and t are Date objects
# Let's find where h is defined in that scope

# Find the function that formats dates
# Look for toLocaleDateString or similar
patterns = [
    r'function\s+h\s*\(',
    r'h\s*=\s*\(',
    r'h\s*=\s*function',
    r'toLocaleDateString',
    r'toISOString',
    r'\.replace.*\d{4}',
    r'YYYY',
    r'yyyy',
    r'dd\.MM',
    r'MM\.dd',
]

for pat in patterns:
    matches = [(m.start(), text[max(0,m.start()-50):m.end()+100]) for m in re.finditer(pat, text)]
    if matches:
        print(f"\n=== Pattern: {pat} ===")
        for idx, ctx in matches[:3]:
            print(f"  @{idx}: ...{ctx}...")

# Also search for the /api/fund-returns/export to see what date format it uses
idx = text.find('api/fund-returns/export')
if idx >= 0:
    chunk = text[max(0,idx-500):idx+500]
    print(f"\n=== fund-returns/export context ===")
    print(chunk)
