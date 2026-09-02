"""Find exact date format used near basTarih in TEFAS JS"""
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

# Find the first occurrence of basTarih and show 800 chars before it
idx = text.find('basTarih')
chunk = text[max(0,idx-800):idx+200]
print("=== Context around first basTarih ===")
print(chunk)

# Find h function near the first basTarih
# Look backward from basTarih for "h=" or "function h"
# Actually let's look at the whole block
start = max(0, idx-2000)
end = min(len(text), idx+500)
block = text[start:end]

# Find all variable assignments like "e=...", "h=...", "l=..."
date_assigns = re.findall(r'(?:let|var|const)\s+([a-z])\s*=\s*[^;]{1,100}(?:Date|date|format|tarih)[^;]*', block)
print(f"\n=== Date variable assignments near basTarih ===")
for d in date_assigns:
    print(f"  {d}")

# Also look at the h() call
h_calls = re.findall(r'h\([^)]{0,100}\)', block)
print(f"\n=== h() calls near basTarih ===")
for h in h_calls:
    print(f"  {h}")
