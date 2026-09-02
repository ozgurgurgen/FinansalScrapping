#!/usr/bin/env python3
"""
KAP Deep Extract - Daha uzun bekleme ve icerik tespiti
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
import json

async def deep_extract():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR',
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        # Capture ALL network requests
        all_requests = []
        def on_response(response):
            url = response.url
            if 'kap.org.tr' in url and response.status == 200:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type or 'text' in content_type:
                    all_requests.append({
                        'url': url, 
                        'status': response.status,
                        'content_type': content_type
                    })
        page.on('response', on_response)
        
        print('='*70)
        print('KAP DEEP EXTRACTION')
        print('='*70)
        
        # 1. Company page - wait longer
        print('\n1. THYAO - 10sn bekleme ile...')
        all_requests.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao', timeout=30000)
            # Wait for content
            await asyncio.sleep(10)
            
            # Check what's on the page
            html = await page.content()
            print(f'   HTML boyutu: {len(html)} bytes')
            
            # Find all text content
            text = await page.inner_text('body')
            print(f'   Text boyutu: {len(text)} chars')
            
            # Print first 2000 chars of text
            print(f'   Sayfa icerigi (ilk 2000):')
            for line in text.split('\n')[:30]:
                if line.strip():
                    print(f'     {line.strip()[:120]}')
            
            print(f'\n   Network istekleri: {len(all_requests)}')
            for r in all_requests:
                print(f'     {r["url"][:120]} ({r["content_type"][:30]})')
                
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 2. Try bilanço with explicit wait
        print('\n2. THYAO bilanço - explicit wait...')
        all_requests.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/mali-tablolar', timeout=30000)
            
            # Try to wait for table or any financial data
            try:
                await page.wait_for_selector('table', timeout=15000)
                print('   Tablo bulundu!')
            except:
                print('   Tablo 15sn icinde yuklenmedi')
            
            # Wait even more
            await asyncio.sleep(10)
            
            text = await page.inner_text('body')
            print(f'   Text boyutu: {len(text)} chars')
            
            # Print content
            print(f'   Sayfa icerigi (ilk 2000):')
            for line in text.split('\n')[:30]:
                if line.strip():
                    print(f'     {line.strip()[:120]}')
            
            # Check for tables again
            tables = await page.query_selector_all('table')
            print(f'\n   Tablo sayisi: {len(tables)}')
            
            # Check for divs with financial data
            divs = await page.query_selector_all('div')
            print(f'   Div sayisi: {len(divs)}')
            
            # Look for specific patterns
            all_text = text.lower()
            patterns = ['dönen', 'duran', 'nakit', 'borç', 'özkaynak', 'hisse', 'pay', 
                       'admin', 'yönetim', 'temettü', 'geri alım', 'ihale']
            print('\n   Icerik taramasi:')
            for pat in patterns:
                if pat in all_text:
                    # Find the line
                    for line in text.split('\n'):
                        if pat in line.lower() and len(line.strip()) > 3:
                            print(f'     ✓ {pat}: {line.strip()[:100]}')
                            break
                else:
                    print(f'     ✗ {pat}: yok')
            
            print(f'\n   Network: {len(all_requests)} istek')
            for r in all_requests[:10]:
                print(f'     {r["url"][:120]}')
                
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 3. Try ortaklar
        print('\n3. THYAO ortaklar - explicit wait...')
        all_requests.clear()
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/ortaklar', timeout=30000)
            await asyncio.sleep(10)
            
            text = await page.inner_text('body')
            print(f'   Text boyutu: {len(text)} chars')
            print(f'   Sayfa icerigi (ilk 1500):')
            for line in text.split('\n')[:20]:
                if line.strip():
                    print(f'     {line.strip()[:120]}')
                    
        except Exception as e:
            print(f'   Hata: {e}')
        
        await browser.close()
    
    print('\n' + '='*70)
    print('TAMAMLANDI')
    print('='*70)

asyncio.run(deep_extract())
