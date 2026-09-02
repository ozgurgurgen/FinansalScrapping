"""Find what the h() date formatting function does in TEFAS"""
import requests, re

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

url = 'https://www.tefas.gov.tr/_next/static/chunks/common-f00e5fba6a4ad2dc.js'
r = s.get(url, timeout=15)
text = r.text

# Find the date format function. It takes a Date and returns a formatted string.
# The one at 7394: `return \`${t}.${r}.${l}\`` -- DD.MM.YYYY
# But we need the one that's used near basTarih

# Let's look at the exact function - extract around the first h() near basTarih
# The JS has: "r.setMonth(t.getMonth()-1),e=h(r),l=h(t)"
# This is inside a closure. The 'h' is from an outer scope.

# Let's look for ALL function definitions that return formatted date strings
# Pattern: function that takes a Date and returns a string with dots or slashes

# Look for the "formatDate" or similar
# The key is at position 7394: `return \`${t}.${r}.${l}\``
# But also look at the "w" function: "w(e,t,r='tr-TR',...)"
# And there might be another h()

# Let me search for all local variable 'h' definitions in the same closure
# where basTarih is used

# First, find the module/chunk that contains basTarih
idx = text.find('basTarih')
# Go backward to find the start of this function scope
# Look for the pattern: something like "r(56917)" near where basTarih is
scope_start = max(0, idx - 5000)
scope = text[scope_start:idx+1000]

# Find all function calls with 'h(' 
h_usages = [(m.start(), m.group()) for m in re.finditer(r'h\([^)]*\)', scope)]
print("=== h() usages near basTarih ===")
for pos, usage in h_usages:
    print(f"  @{pos}: {usage}")

# Now look for the h variable assignment near the scope
# Look for patterns like: ",h=" or "h=" near the top of the scope
h_defs = [(m.start(), scope[max(0,m.start()-20):m.end()+100]) for m in re.finditer(r',h=[^,;]+|h=function|function h', scope)]
print(f"\n=== h definitions near basTarih ===")
for pos, defn in h_defs:
    print(f"  @{pos}: {defn}")

# Look for the "d.ts" or "mm.dd" patterns
date_patterns = re.findall(r'["\']([^"\']*(?:\d+[./-]\d+[./-]\d+|dd|MM|yyyy|YYYY|toLocale)[^"\']*)["\']', text)
print(f"\n=== Date format strings in JS ===")
for p in sorted(set(date_patterns))[:20]:
    print(f"  {p}")

# Try searching for the /api/fund endpoint to understand API prefix
api_prefix = re.findall(r'baseURL["\s:]+["\']([^"\']+)["\']', text)
print(f"\n=== API base URLs ===")
for a in api_prefix:
    print(f"  {a}")

# Find the SB object which does the POST
sb_patterns = re.findall(r'SB[=:][^;]{0,200}', text)
for p in sb_patterns[:5]:
    if 'post' in p.lower() or 'axios' in p.lower() or 'fetch' in p.lower() or 'base' in p.lower():
        print(f"\n=== SB definition ===")
        print(f"  {p}")
