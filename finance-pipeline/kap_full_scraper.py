#!/usr/bin/env python3
"""
KAP Full Scraper - Playwright ile tum sirketlerin finansal/ortak/yonetim verisini cek
Yeni URL yapisi: /tr/sirket-finansal-bilgileri/{mkk_id}-{slug}
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
import json
import sqlite3
import re
import time
import random

DB_PATH = 'finance.db'

async def build_url_map():
    """BIST sirketler sayfasindan mkk_id -> slug eslesmesi olustur"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='tr-TR'
        )
        page = await context.new_page()
        
        print('BIST sirketlerinden URL map olusturuluyor...')
        await page.goto('https://kap.org.tr/tr/bist-sirketler', timeout=30000)
        await asyncio.sleep(8)
        
        # Extract all company links
        links = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href,
                text: a.textContent.trim()
            })).filter(l => l.href.includes('sirket-bilgileri/ozet/'))
        }''')
        
        url_map = {}
        for link in links:
            # Parse: /tr/sirket-bilgileri/ozet/1107-turk-hava-yollari-a-o
            m = re.search(r'/ozet/(\d+)-(.+)$', link['href'])
            if m:
                mkk_id = m.group(1)
                slug = m.group(2)
                ticker = link['text'].strip()
                url_map[ticker] = {'mkk_id': mkk_id, 'slug': slug}
        
        print(f'  {len(url_map)} sirket URL map olusturuldu')
        await browser.close()
        return url_map


async def scrape_financial_page(page, mkk_id, slug):
    """Tek bir sirketin finansal bilgiler sayfasini cek"""
    url = f'https://kap.org.tr/tr/sirket-finansal-bilgileri/{mkk_id}-{slug}'
    try:
        await page.goto(url, timeout=25000)
        await asyncio.sleep(5)
        text = await page.inner_text('body')
        
        if '404' in text[:500]:
            return None
        
        data = {}
        
        # Parse FİNANSAL DURUM TABLOSU (Balance Sheet)
        # Format: "Dönen Varlıklar\t253.043\t341.910\t436.412\t512.191"
        bs_keywords = {
            'Dönen Varlıklar': 'current_assets',
            'Duran Varlıklar': 'non_current_assets',
            'Toplam Varlıklar': 'total_assets',
            'Kısa Vadeli Yükümlülükler': 'short_term_debt',
            'Uzun Vadeli Yükümlülükler': 'long_term_debt',
            'Toplam Yükümlülükler': 'total_debt',
            'Ana Ortaklığa Ait Özkaynaklar': 'equity',
            'Ödenmiş Sermaye': 'paid_capital',
            # total_equity maps to equity
        }
        
        for line in text.split('\n'):
            for keyword, field in bs_keywords.items():
                if line.startswith(keyword):
                    # Extract last numeric value (most recent period)
                    nums = re.findall(r'[\d.,]+', line)
                    nums = [n for n in nums if len(n) > 1]  # Skip single digits
                    if nums:
                        val = nums[-1].replace('.', '').replace(',', '.')
                        try:
                            data[field] = float(val) * 1000000  # x1000000 TL
                        except:
                            pass
        
        # Parse KAR VEYA ZARAR (Income Statement)
        is_keywords = {
            'Hasılat': 'revenue',
            'Brüt Kâr': 'gross_profit',
            'Esas Faaliyet Kârı': 'ebit',
            'Net Dönem Kârı': 'net_profit',
        }
        
        for line in text.split('\n'):
            for keyword, field in is_keywords.items():
                if line.startswith(keyword):
                    nums = re.findall(r'[\d.,]+', line)
                    nums = [n for n in nums if len(n) > 1]
                    if nums:
                        val = nums[-1].replace('.', '').replace(',', '.')
                        try:
                            data[field] = float(val) * 1000000
                        except:
                            pass
        
        return data
    except Exception as e:
        return None


async def scrape_general_page(page, mkk_id, slug):
    """Tek bir sirketin genel bilgiler sayfasini cek"""
    url = f'https://kap.org.tr/tr/sirket-bilgileri/genel/{mkk_id}-{slug}'
    try:
        await page.goto(url, timeout=25000)
        await asyncio.sleep(5)
        text = await page.inner_text('body')
        
        if '404' in text[:500]:
            return None
        
        data = {'management': [], 'shareholders': [], 'subsidiaries': [], 'sector': None, 'index_group': None}
        
        # Parse YÖNETİM KURULU
        in_yk = False
        for line in text.split('\n'):
            if 'Yönetim Kurulu Üyeleri' in line:
                in_yk = True
                continue
            if in_yk:
                if 'Yönetimde Söz Sahibi' in line:
                    in_yk = False
                    continue
                # Skip header line
                if 'Adı-Soyadı' in line and 'Görevi' in line:
                    continue
                # Lines like: MURAT ŞEKER\t\tErkek\tYönetim Kurulu Başkanı\tEkonomist\t...
                parts = line.split('\t')
                if len(parts) >= 4 and parts[0].strip():
                    name = parts[0].strip()
                    # Validate: name should be all caps letters/spaces (Turkish name format)
                    if name and len(name) > 3 and not name.startswith('(') and not name.startswith('*') and name.isupper():
                        gender = parts[2].strip() if len(parts) > 2 else ''
                        title = parts[3].strip() if len(parts) > 3 else ''
                        profession = parts[4].strip() if len(parts) > 4 else ''
                        data['management'].append({
                            'name': name,
                            'gender': gender,
                            'title': title,
                            'profession': profession
                        })
        
        # Parse ORTAKLIK YAPISI
        in_shareholders = False
        for line in text.split('\n'):
            if 'Paya veya Oy Hakkına Sahip' in line:
                in_shareholders = True
                continue
            if in_shareholders:
                if 'Son Durum' in line or 'Fiili Dolaşım' in line:
                    in_shareholders = False
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    name = parts[0].strip()
                    pct_str = parts[2].strip() if len(parts) > 2 else '0'
                    if name and not name.startswith('(') and not name.startswith('*') and name != 'Ortağın Adı-Soyadı/Ticaret Ünvanı':
                        data['shareholders'].append({
                            'name': name,
                            'percent': pct_str
                        })
        
        # Parse BAĞLI ORTAKLIKLAR
        in_bo = False
        for line in text.split('\n'):
            if 'Bağlı Ortaklıklar, Finansal Duran' in line:
                in_bo = True
                continue
            if in_bo:
                if 'DİĞER HUSUSLAR' in line:
                    in_bo = False
                    continue
                parts = line.split('\t')
                if len(parts) >= 5 and parts[0].strip():
                    name = parts[0].strip()
                    if name and not name.startswith('(') and not name.startswith('*'):
                        data['subsidiaries'].append({
                            'name': name,
                            'activity': parts[1].strip() if len(parts) > 1 else '',
                            'capital': parts[2].strip() if len(parts) > 2 else '',
                            'share_pct': parts[4].strip() if len(parts) > 4 else '',
                        })
        
        # Parse Sektör
        for line in text.split('\n'):
            if 'Şirketin Sektörü' in line:
                idx = text.split('\n').index(line)
                lines = text.split('\n')
                if idx + 1 < len(lines):
                    data['sector'] = lines[idx + 1].strip()
            if 'Şirketin Dahil Olduğu Endeksler' in line:
                idx = text.split('\n').index(line)
                lines = text.split('\n')
                if idx + 1 < len(lines):
                    data['index_group'] = lines[idx + 1].strip()[:200]
        
        return data
    except Exception as e:
        return None


async def run_scraper():
    """Ana scraper fonksiyonu"""
    from playwright.async_api import async_playwright
    
    # Build URL map
    url_map = await build_url_map()
    
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=5000')
    c = db.cursor()
    
    # Get existing companies
    companies = c.execute('SELECT id, ticker, mkk_id, company_name FROM companies WHERE mkk_id IS NOT NULL').fetchall()
    print(f'\n{len(companies)} sirket icin scraping basliyor...')
    
    # Create mapping: ticker -> {mkk_id, slug}
    ticker_to_url = {}
    for ticker, info in url_map.items():
        ticker_to_url[ticker.upper()] = info
    
    # Also map by mkk_id
    mkk_to_url = {}
    for ticker, info in url_map.items():
        mkk_to_url[info['mkk_id']] = info
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='tr-TR'
        )
        
        stats = {'financial': 0, 'general': 0, 'errors': 0, 'skipped': 0}
        
        for idx, (comp_id, ticker, mkk_id, name) in enumerate(companies):
            # Find URL
            url_info = ticker_to_url.get(ticker.upper()) or mkk_to_url.get(str(mkk_id))
            if not url_info:
                stats['skipped'] += 1
                continue
            
            if idx % 50 == 0:
                print(f'\n  [{idx}/{len(companies)}] {ticker} ({name})...')
            
            page = await context.new_page()
            
            # 1. Finansal veri
            fin_data = await scrape_financial_page(page, url_info['mkk_id'], url_info['slug'])
            if fin_data:
                # Update only the MOST RECENT period for this company
                c.execute('''SELECT id FROM financials WHERE company_id = ? 
                    ORDER BY year DESC, period DESC LIMIT 1''', (comp_id,))
                row = c.fetchone()
                if row:
                    fin_id = row[0]
                    for field, value in fin_data.items():
                        if value and value != 0:
                            c.execute(f'''UPDATE financials SET {field} = ? WHERE id = ?''',
                                (value, fin_id))
                stats['financial'] += 1
            
            # Anti-ban gecikme
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # 2. Genel bilgi
            gen_data = await scrape_general_page(page, url_info['mkk_id'], url_info['slug'])
            if gen_data:
                # Save management
                if gen_data.get('management'):
                    for mgmt in gen_data['management']:
                        try:
                            c.execute('''INSERT OR IGNORE INTO management_members 
                                (company_id, name, title, member_type)
                                VALUES (?, ?, ?, ?)''',
                                (comp_id, mgmt['name'], mgmt['title'], 'YK'))
                        except sqlite3.OperationalError:
                            db.rollback()
                            time.sleep(2)
                
                # Save shareholders
                if gen_data.get('shareholders'):
                    for sh in gen_data['shareholders']:
                        pct = sh.get('percent', '0').replace('%', '').replace(',', '.').strip()
                        try:
                            pct_val = float(pct)
                        except:
                            pct_val = 0
                        try:
                            c.execute('''INSERT OR IGNORE INTO shareholders
                                (company_id, holder_name, share_ratio_percent, holder_type)
                                VALUES (?, ?, ?, ?)''',
                                (comp_id, sh['name'], pct_val, 'BILDIRIMEN'))
                        except sqlite3.OperationalError:
                            db.rollback()
                            time.sleep(2)
                
                # Save subsidiaries
                if gen_data.get('subsidiaries'):
                    for sub in gen_data['subsidiaries']:
                        pct_str = sub.get('share_pct', '0').replace('%', '').replace(',', '.').strip()
                        try:
                            pct_val = float(pct_str)
                        except:
                            pct_val = 0
                        try:
                            rel = 'BAGLI_ORTAKLIK' if float(pct_val) > 50 else 'ISTIRAK'
                            c.execute('''INSERT OR IGNORE INTO subsidiaries
                                (company_id, name, activity, share_percent, relation_type)
                                VALUES (?, ?, ?, ?, ?)''',
                                (comp_id, sub['name'], sub['activity'], pct_val, rel))
                        except sqlite3.OperationalError:
                            db.rollback()
                            time.sleep(2)
                
                # Update sector
                if gen_data.get('sector'):
                    c.execute('UPDATE companies SET sector = ? WHERE id = ? AND (sector IS NULL OR sector = "")',
                        (gen_data['sector'], comp_id))
                
                # Update index_group
                if gen_data.get('index_group'):
                    c.execute('UPDATE companies SET index_group = ? WHERE id = ?',
                        (gen_data['index_group'], comp_id))
                
                stats['general'] += 1
            
            await page.close()
            
            # Anti-ban
            await asyncio.sleep(random.uniform(3.0, 6.0))
            
            # Commit every 20 companies
            if idx % 20 == 0:
                db.commit()
        
        await browser.close()
    
    db.commit()
    db.close()
    
    print(f'\n{"="*70}')
    print(f'SCRAPING TAMAMLANDI')
    print(f'  Finansal: {stats["financial"]} sirket')
    print(f'  Genel: {stats["general"]} sirket')
    print(f'  Hata: {stats["errors"]}')
    print(f'  Atlanan: {stats["skipped"]}')
    print(f'{"="*70}')

if __name__ == '__main__':
    asyncio.run(run_scraper())
