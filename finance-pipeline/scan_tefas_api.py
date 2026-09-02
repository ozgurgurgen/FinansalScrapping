"""Discover TEFAS API endpoints by scraping the website JS files"""
import requests, re, time, json

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Referer': 'https://www.tefas.gov.tr/',
})

BASE = 'https://www.tefas.gov.tr'

# Step 1: Get main HTML to find JS files
r = s.get(BASE, timeout=15)
html = r.text
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
print(f"Found {len(scripts)} script files\n")

# Step 2: Search all JS for API endpoint names
all_endpoints = set()
for script_url in scripts:
    full_url = script_url if script_url.startswith('http') else f'{BASE}{script_url}'
    try:
        jr = s.get(full_url, timeout=15)
        # Find all API patterns
        found = re.findall(r'["\']api/funds/([A-Za-z0-9]+)["\']', jr.text)
        found2 = re.findall(r'api/funds/([A-Za-z0-9]+)', jr.text)
        endpoints = set(found + found2)
        if endpoints:
            all_endpoints.update(endpoints)
            print(f"  {script_url.split('/')[-1]}: {sorted(endpoints)}")
    except:
        pass
    time.sleep(0.5)

print(f"\nAll discovered endpoints ({len(all_endpoints)}):")
for ep in sorted(all_endpoints):
    print(f"  /api/funds/{ep}")
