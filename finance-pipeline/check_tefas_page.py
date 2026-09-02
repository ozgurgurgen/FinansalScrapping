"""Check TEFAS fund detail page for embedded data"""
import requests, re, json

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html',
    'Referer': 'https://www.tefas.gov.tr/',
})

# Fetch the fund detail page
urls = [
    'https://www.tefas.gov.tr/fon-detay/YAC',
    'https://www.tefas.gov.tr/fon/yac',
    'https://www.tefas.gov.tr/analiz/yac',
    'https://www.tefas.gov.tr/FonAnaliz.aspx?fon=YAC',
]

for url in urls:
    try:
        r = s.get(url, timeout=10, allow_redirects=True)
        print(f'\n=== {url} ===')
        print(f'  Status: {r.status_code}, Final: {r.url}')
        print(f'  Length: {len(r.text)}')
        
        # Look for embedded JSON data
        json_blocks = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if json_blocks:
            for i, block in enumerate(json_blocks):
                try:
                    data = json.loads(block)
                    print(f'  JSON block {i}: {json.dumps(data, ensure_ascii=False)[:500]}')
                except:
                    pass
        
        # Look for portfolio/allocation data in HTML
        tables = re.findall(r'<table[^>]*>(.*?)</table>', r.text, re.DOTALL)
        if tables:
            for i, t in enumerate(tables[:3]):
                # Extract table headers and first few rows
                ths = re.findall(r'<th[^>]*>(.*?)</th>', t)
                tds = re.findall(r'<td[^>]*>(.*?)</td>', t)
                print(f'  Table {i}: headers={ths[:8]}, cells={tds[:16]}')
                
    except Exception as e:
        print(f'  ERROR: {e}')
