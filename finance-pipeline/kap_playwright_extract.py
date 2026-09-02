#!/usr/bin/env python3
"""
KAP Playwright ile DOM extraction - bilanço, ortaklar, buyback
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
import json
import re

async def extract_kap_data():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='tr-TR'
        )
        
        page = await context.new_page()
        
        print('='*70)
        print('KAP PLAYWRIGHT DOM EXTRACTION')
        print('='*70)
        
        # 1. BİLANÇO SAYFASI - current_assets, cash, capex
        print('\n1. THYAO BİLANÇO...')
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/mali-tablolar', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)
            
            # Try to click on bilanço tab if exists
            try:
                bilanco_tab = page.locator('text=Bilanço').first
                if await bilanco_tab.is_visible():
                    await bilanco_tab.click()
                    await asyncio.sleep(3)
                    print('   Bilanço sekmesine tıklandı')
            except:
                pass
            
            # Get all table data
            tables = await page.evaluate('''() => {
                const tables = document.querySelectorAll('table');
                const results = [];
                tables.forEach((table, idx) => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('td, th').forEach(cell => {
                            cells.push(cell.textContent.trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length > 0) results.push({idx, rows});
                });
                return results;
            }''')
            
            print(f'   Tablo sayısı: {len(tables)}')
            for t in tables:
                print(f'\n   Tablo {t["idx"]}: {len(t["rows"])} satır')
                for row in t["rows"][:10]:
                    print(f'     {row[:6]}')
            
            # Also get the full page text to find bilanço data
            page_text = await page.evaluate('() => document.body.innerText')
            
            # Look for financial keywords
            keywords = ['Dönen Varlıklar', 'Duran Varlıklar', 'Nakit', 'Finansal Borç', 
                       'Kısa Vadeli', 'Uzun Vadeli', 'Özkaynaklar', 'Toplam Borçlar']
            print('\n   Anahtar kelime araması:')
            for kw in keywords:
                if kw.lower() in page_text.lower():
                    # Find the line with this keyword
                    for line in page_text.split('\n'):
                        if kw.lower() in line.lower() and len(line.strip()) > 5:
                            print(f'     ✓ {line.strip()[:100]}')
                            break
                else:
                    print(f'     ✗ {kw}: BULUNAMADI')
                    
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 2. ORTAKLAR SAYFASI
        print('\n2. THYAO ORTAKLAR...')
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/ortaklar', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)
            
            tables = await page.evaluate('''() => {
                const tables = document.querySelectorAll('table');
                const results = [];
                tables.forEach((table, idx) => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('td, th').forEach(cell => {
                            cells.push(cell.textContent.trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length > 0) results.push({idx, rows});
                });
                return results;
            }''')
            
            print(f'   Tablo sayısı: {len(tables)}')
            for t in tables:
                print(f'\n   Tablo {t["idx"]}: {len(t["rows"])} satır')
                for row in t["rows"][:10]:
                    print(f'     {row[:6]}')
            
            # Page text for shareholder data
            page_text = await page.evaluate('() => document.body.innerText')
            ortak_keywords = ['Pay Oranı', 'Hisse', 'Ortak', 'Pay Sahipleri', 'Nitelikli']
            print('\n   Anahtar kelime araması:')
            for kw in ortak_keywords:
                for line in page_text.split('\n'):
                    if kw.lower() in line.lower() and len(line.strip()) > 5:
                        print(f'     ✓ {line.strip()[:100]}')
                        break
                        
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 3. GERİ ALIM SAYFASI
        print('\n3. THYAO GERİ ALIM...')
        try:
            await page.goto('https://kap.org.tr/tr/sirket-bilgileri/thyao/geri-alim', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)
            
            tables = await page.evaluate('''() => {
                const tables = document.querySelectorAll('table');
                const results = [];
                tables.forEach((table, idx) => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('td, th').forEach(cell => {
                            cells.push(cell.textContent.trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length > 0) results.push({idx, rows});
                });
                return results;
            }''')
            
            print(f'   Tablo sayısı: {len(tables)}')
            for t in tables:
                print(f'\n   Tablo {t["idx"]}: {len(t["rows"])} satır')
                for row in t["rows"][:10]:
                    print(f'     {row[:6]}')
                    
        except Exception as e:
            print(f'   Hata: {e}')
        
        # 4. BİLDİRİM DETAY SAYFASI
        print('\n4. BİLDİRİM DETAY (ihale/blok satış)...')
        try:
            await page.goto('https://kap.org.tr/tr/bildirim/1632898', 
                          wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)
            
            tables = await page.evaluate('''() => {
                const tables = document.querySelectorAll('table');
                const results = [];
                tables.forEach((table, idx) => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('td, th').forEach(cell => {
                            cells.push(cell.textContent.trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length > 0) results.push({idx, rows});
                });
                return results;
            }''')
            
            print(f'   Tablo sayısı: {len(tables)}')
            for t in tables:
                print(f'\n   Tablo {t["idx"]}: {len(t["rows"])} satır')
                for row in t["rows"][:5]:
                    print(f'     {row[:8]}')
                    
        except Exception as e:
            print(f'   Hata: {e}')
        
        await browser.close()
    
    print('\n' + '='*70)
    print('DOM EXTRACTION TAMAMLANDI')
    print('='*70)

asyncio.run(extract_kap_data())
