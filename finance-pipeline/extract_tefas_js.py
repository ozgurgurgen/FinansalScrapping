"""Extract date format and request patterns from TEFAS common JS"""
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

# Find date format patterns
date_patterns = re.findall(r'(date|tarih|basTarih|bitTarih|format)[^a-zA-Z].{0,80}', text, re.IGNORECASE)
print("=== DATE PATTERNS ===")
for p in date_patterns[:30]:
    print(f"  {p}")

# Find request body patterns near API calls
print("\n=== REQUEST BODY PATTERNS ===")
# Find content around dagilimSiraliGetir
idx = text.find('dagilimSiraliGetirT')
if idx >= 0:
    chunk = text[max(0,idx-300):idx+500]
    print(f"\ndagilimSiraliGetirT context:\n{chunk}")

# Find content around fonGnlBlgSiraliGetir
idx = text.find('fonGnlBlgSiraliGetir')
if idx >= 0:
    chunk = text[max(0,idx-300):idx+500]
    print(f"\nfonGnlBlgSiraliGetir context:\n{chunk}")

# Find format patterns
print("\n=== FORMAT PATTERNS ===")
formats = re.findall(r'(dayjs|moment|format|toDate|toString)\([^)]*\)', text)
for f in sorted(set(formats))[:20]:
    print(f"  {f}")

# Find all string literals that look like dates
print("\n=== DATE LITERALS ===")
literals = re.findall(r'"(\d{4}-\d{2}-\d{2}[^"]*)"', text)
for l in sorted(set(literals))[:20]:
    print(f"  {l}")

# Find ISO or long date formats
iso = re.findall(r'"(\\d{4}-\\d{2}-\\d{2}T[^"]*)"', text)
for i in sorted(set(iso))[:20]:
    print(f"  {i}")
