#!/usr/bin/env python3
"""
KAP Gizli API Keşfi - Playwright ile XHR/Fetch isteklerini yakalayarak
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
import json

async def discover_kap_apis():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR'
        )
        
        captured_apis = []
        
        def on_request(request):
            if request.resource_type in ('xhr', 'fetch'):
                url = request.url
                if 'kap.org.tr' in url and not url.endswith(('.js', '.css', '.png', '.jpg')):
                    captured_apis.append({
                        'url': url,
                        'method': request.method,
                        'post_data': request.post_data[:500] if request.post_data else None,
                        'headers': dict(request.headers)
                    })
        
        page = await context.new_page()
        page.on('request', on_request)
        
        print('='*70)
        print('KAP XHR/FETCH API KEŞİFİ')
        print('='*70)
        
        # 1. THYAO şirket sayfası
        print('\n1. THYAO şirket sayfası...')
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao', wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            print(f'   Yakalanan API: {len(captured_apis)}')
            for api in captured_apis:
                print(f'   {api["method"]} {api["url"][:120]}')
                if api["post_data"]:
                    print(f'     Body: {api["post_data"][:200]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 2. Sayfadaki JSON verilerini kontrol et
        print('\n2. Sayfa __NEXT_DATA__ kontrol...')
        try:
            next_data = await page.evaluate('''() => {
                const el = document.getElementById("__NEXT_DATA__");
                if (el) return el.textContent;
                return null;
            }''')
            if next_data:
                data = json.loads(next_data)
                print(f'   __NEXT_DATA__ bulundu! Keys: {list(data.keys())}')
                if 'props' in data:
                    print(f'   props keys: {list(data["props"].keys())}')
                    if 'pageProps' in data['props']:
                        pp = data['props']['pageProps']
                        print(f'   pageProps keys: {list(pp.keys())}')
                        for k, v in pp.items():
                            if isinstance(v, dict):
                                print(f'     {k}: dict ({len(v)} keys)')
                            elif isinstance(v, list):
                                print(f'     {k}: list ({len(v)} items)')
                            else:
                                print(f'     {k}: {type(v).__name__} = {str(v)[:100]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 3. Bilanço sayfası
        print('\n3. THYAO bilanço sayfası...')
        captured_apis.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/mali-tablolar', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            print(f'   Yakalanan API: {len(captured_apis)}')
            for api in captured_apis:
                print(f'   {api["method"]} {api["url"][:120]}')
                if api["post_data"]:
                    print(f'     Body: {api["post_data"][:300]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 4. __NEXT_DATA__ bilanço
        print('\n4. Bilanço __NEXT_DATA__...')
        try:
            next_data = await page.evaluate('''() => {
                const el = document.getElementById("__NEXT_DATA__");
                if (el) return el.textContent;
                return null;
            }''')
            if next_data:
                data = json.loads(next_data)
                if 'props' in data and 'pageProps' in data['props']:
                    pp = data['props']['pageProps']
                    print(f'   pageProps keys: {list(pp.keys())}')
                    for k, v in pp.items():
                        if isinstance(v, (dict, list)):
                            print(f'     {k}: {type(v).__name__} ({len(v)} items)')
                            if isinstance(v, list) and len(v) > 0:
                                if isinstance(v[0], dict):
                                    print(f'       Item keys: {list(v[0].keys())[:10]}')
                        else:
                            print(f'     {k}: {v}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 5. Ortaklık yapısı sayfası
        print('\n5. THYAO ortaklar sayfası...')
        captured_apis.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/ortaklar', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            print(f'   Yakalanan API: {len(captured_apis)}')
            for api in captured_apis:
                print(f'   {api["method"]} {api["url"][:120]}')
                if api["post_data"]:
                    print(f'     Body: {api["post_data"][:300]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 6. __NEXT_DATA__ ortaklar
        print('\n6. Ortaklar __NEXT_DATA__...')
        try:
            next_data = await page.evaluate('''() => {
                const el = document.getElementById("__NEXT_DATA__");
                if (el) return el.textContent;
                return null;
            }''')
            if next_data:
                data = json.loads(next_data)
                if 'props' in data and 'pageProps' in data['props']:
                    pp = data['props']['pageProps']
                    print(f'   pageProps keys: {list(pp.keys())}')
                    for k, v in pp.items():
                        if isinstance(v, list) and len(v) > 0:
                            print(f'     {k}: list ({len(v)} items)')
                            if isinstance(v[0], dict):
                                print(f'       Sample: {json.dumps(v[0], ensure_ascii=False)[:300]}')
                        elif isinstance(v, dict):
                            print(f'     {k}: dict ({len(v)} keys)')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 7. Geri alım sayfası
        print('\n7. THYAO buyback sayfası...')
        captured_apis.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/geri-alim', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            print(f'   Yakalanan API: {len(captured_apis)}')
            for api in captured_apis:
                print(f'   {api["method"]} {api["url"][:120]}')
                if api["post_data"]:
                    print(f'     Body: {api["post_data"][:300]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 8. __NEXT_DATA__ buyback
        print('\n8. Buyback __NEXT_DATA__...')
        try:
            next_data = await page.evaluate('''() => {
                const el = document.getElementById("__NEXT_DATA__");
                if (el) return el.textContent;
                return null;
            }''')
            if next_data:
                data = json.loads(next_data)
                if 'props' in data and 'pageProps' in data['props']:
                    pp = data['props']['pageProps']
                    print(f'   pageProps keys: {list(pp.keys())}')
                    for k, v in pp.items():
                        if isinstance(v, list) and len(v) > 0:
                            print(f'     {k}: list ({len(v)} items)')
                            if isinstance(v[0], dict):
                                print(f'       Keys: {list(v[0].keys())}')
                                print(f'       Sample: {json.dumps(v[0], ensure_ascii=False)[:300]}')
                        elif isinstance(v, dict):
                            print(f'     {k}: dict ({len(v)} keys)')
                            print(f'       Sample: {json.dumps(v, ensure_ascii=False)[:300]}')
        except Exception as e:
            print(f'   Hata: {e}')
        
        await browser.close()
    
    print('\n' + '='*70)
    print('KEŞİF TAMAMLANDI')
    print('='*70)

asyncio.run(discover_kap_apis())
