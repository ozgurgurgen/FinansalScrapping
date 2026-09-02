"""Fetch TEFAS Next.js page data to find embedded API data"""
import requests, re, json

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

# Check Next.js build manifest for routes
r = s.get('https://www.tefas.gov.tr/', timeout=15)
html = r.text

# Look for __NEXT_DATA__ or script[type=application/json]
next_data = re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if next_data:
    data = json.loads(next_data[0])
    print("=== __NEXT_DATA__ ===")
    print(json.dumps(data.get("props", {}).get("pageProps", {}), ensure_ascii=False, indent=2)[:3000])
else:
    print("No __NEXT_DATA__ found")
    
    # Check for buildManifest
    build = re.findall(r'/_next/static/[^/]+/_buildManifest\.js', html)
    print(f"\nBuild manifests: {build}")
    
    # Check all script tags
    scripts = re.findall(r'<script[^>]*src="([^"]*)"[^>]*>', html)
    print(f"\nAll script srcs:")
    for s_url in scripts:
        print(f"  {s_url}")
    
    # Try _buildManifest
    for s_url in scripts:
        if 'buildManifest' in s_url:
            full = s_url if s_url.startswith('http') else f'https://www.tefas.gov.tr{s_url}'
            try:
                jr = s.get(full, timeout=10)
                routes = re.findall(r'"/(fon[^"]*)"', jr.text)
                print(f"\nRoutes from manifest:")
                for rt in sorted(set(routes)):
                    print(f"  /{rt}")
            except:
                pass
