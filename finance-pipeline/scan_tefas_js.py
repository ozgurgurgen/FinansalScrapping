"""Deep scan TEFAS JS chunks for API endpoints"""
import requests, re, time

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Referer': 'https://www.tefas.gov.tr/',
})

BASE = 'https://www.tefas.gov.tr'

scripts = [
    '/_next/static/chunks/vendors-1d3a9093c2d211f8.js',
    '/_next/static/chunks/common-f00e5fba6a4ad2dc.js',
    '/_next/static/chunks/app/%5Blocale%5D/layout-9eeaafccd7685bde.js',
    '/_next/static/chunks/app/%5Blocale%5D/page-679795a63f78c9bd.js',
]

for script_path in scripts:
    url = f'{BASE}{script_path}'
    try:
        r = s.get(url, timeout=15)
        text = r.text
        print(f'\n=== {script_path.split("/")[-1]} ({len(text)} bytes) ===')
        
        # Find ALL API references
        apis = set(re.findall(r'/api/[A-Za-z/]+', text))
        funcs = set(re.findall(r'[a-zA-Z]+Getir', text))
        fund_refs = set(re.findall(r'["\']([^"\']*[Ff]on[^"\']*)["\']', text))
        
        if apis:
            print(f'  API paths: {sorted(apis)}')
        if funcs:
            print(f'  Getir functions: {sorted(funcs)}')
        if fund_refs:
            fund_short = [f for f in fund_refs if len(f) < 50]
            print(f'  Fund refs ({len(fund_short)}): {sorted(set(fund_short))[:30]}')
            
        # Also look for fetch/axios/post patterns
        fetches = re.findall(r'fetch\(["\']([^"\']+)["\']', text)
        posts = re.findall(r'\.post\(["\']([^"\']+)["\']', text)
        if fetches:
            print(f'  fetch: {sorted(set(fetches))}')
        if posts:
            print(f'  .post: {sorted(set(posts))}')
    except Exception as e:
        print(f'  ERROR: {e}')
    time.sleep(1)
