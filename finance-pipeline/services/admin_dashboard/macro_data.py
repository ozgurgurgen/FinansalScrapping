#!/usr/bin/env python3
"""
Macro Data Module — TCMB EVDS, Economic Calendar, Bond Yields
"""
import re
import time
import random
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8',
        'Referer': 'https://www.tcmb.gov.tr',
    })
    return s


# ══════════════════════════════════════════════════════════════════
# TCMB ENFLASYON VERILERI
# ══════════════════════════════════════════════════════════════════

def get_tcmb_inflation(inflation_type='tufe', limit=24):
    """
    TCMB resmi web sitesinden enflasyon verilerini ceker.
    inflation_type: 'tufe' (TUFE) veya 'ufe' (UFE)
    """
    session = create_session()
    
    urls = {
        'tufe': 'https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb+tr/main+menu/istatistikler/enflasyon+verileri',
        'ufe': 'https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/Enflasyon+Verileri/Uretici+Fiyatlari',
    }
    
    url = urls.get(inflation_type, urls['tufe'])
    
    try:
        r = session.get(url, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        data = []
        tables = soup.find_all('table')
        
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all(['th', 'td'])]
            header_text = ' '.join(headers)
            
            if any(kw in header_text for kw in ['enflasyon', 'yillik', 'aylik', '%']):
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if len(cells) >= 3:
                        date_str = cells[0]
                        yearly = cells[1] if len(cells) > 1 else ''
                        monthly = cells[2] if len(cells) > 2 else ''
                        
                        # Parse
                        year_match = re.search(r'(\d{4})', date_str)
                        month_match = re.search(r'(\d{1,2})', date_str)
                        
                        if year_match and month_match:
                            y = float(yearly.replace(',', '.').replace('%', '').strip()) if yearly.strip() else None
                            m = float(monthly.replace(',', '.').replace('%', '').strip()) if monthly.strip() else None
                            data.append({
                                'date': f"{year_match.group(1)}-{month_match.group(1).zfill(2)}",
                                'yearly': y,
                                'monthly': m,
                            })
                break
        
        data.sort(key=lambda x: x['date'], reverse=True)
        
        return {
            'type': inflation_type.upper(),
            'data': data[:limit],
            'latest_yearly': data[0]['yearly'] if data else None,
            'latest_monthly': data[0]['monthly'] if data else None,
            'source': 'TCMB',
            'timestamp': datetime.now().isoformat(),
        }
    
    except Exception as e:
        return {'error': str(e), 'data': []}


# ══════════════════════════════════════════════════════════════════
# EKONOMIK TAKVIM
# ══════════════════════════════════════════════════════════════════

DOVIZ_CALENDAR_URL = 'https://www.doviz.com/ekonomik-takvim'

COUNTRY_MAP = {
    'Türkiye': 'TR', 'ABD': 'US', 'Euro Bölgesi': 'EU',
    'Almanya': 'DE', 'İngiltere': 'GB', 'Japonya': 'JP', 'Çin': 'CN',
}

TURKISH_MONTHS = {
    'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6,
    'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12,
}


def get_economic_calendar(countries=None, period='this_week'):
    """
    doviz.com ekonomik takviminden olaylari ceker.
    countries: ['TR', 'US', 'EU', ...] veya None (tumu)
    period: 'today', 'this_week', 'this_month'
    """
    if countries is None:
        countries = ['TR', 'US', 'EU', 'DE', 'GB', 'JP', 'CN']
    
    session = create_session()
    
    try:
        r = session.get(DOVIZ_CALENDAR_URL, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        events = []
        seen = set()
        
        # Parse all tab containers
        for container_id in ['calendar-content-0', 'calendar-content-1', 'calendar-content-2', 'calendar-content-3']:
            container = soup.find(id=container_id)
            if not container:
                continue
            
            current_date = None
            for child in container.find_all(['div'], recursive=False):
                classes = child.get('class', [])
                
                if 'text-bold' in classes:
                    # Parse date heading
                    text = child.get_text(strip=True)
                    m = re.match(r'(\d{1,2})\s+(\S+)\s+(\d{4})', text)
                    if m:
                        day, month_name, year = m.groups()
                        month = TURKISH_MONTHS.get(month_name.lower())
                        if month:
                            current_date = datetime(int(year), month, int(day))
                    continue
                
                table = child.find('table')
                if not table or not current_date:
                    continue
                
                for tr in table.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) < 7:
                        continue
                    
                    marker = tr.find('span', class_='importance')
                    marker_classes = marker.get('class', []) if marker else []
                    importance = 'high' if 'high' in marker_classes else ('medium' if 'mid' in marker_classes else 'low')
                    
                    time_text = tds[0].get_text(strip=True)
                    country_name = tds[1].get_text(strip=True)
                    event_name = ' '.join(tds[3].get_text(strip=True).split())
                    
                    if not event_name:
                        continue
                    
                    event_dt = current_date
                    tm = re.match(r'(\d{1,2}):(\d{2})', time_text)
                    if tm:
                        event_dt = current_date.replace(hour=int(tm.group(1)), minute=int(tm.group(2)))
                    
                    country_code = COUNTRY_MAP.get(country_name)
                    
                    if country_code not in countries:
                        continue
                    
                    # Filter by period
                    now = datetime.now()
                    if period == 'today' and event_dt.date() != now.date():
                        continue
                    elif period == 'this_week' and (event_dt.date() - now.date()).days > 7:
                        continue
                    
                    actual = tds[4].get_text(strip=True) or None
                    forecast = tds[5].get_text(strip=True) or None
                    previous = tds[6].get_text(strip=True) or None
                    
                    key = (event_dt.isoformat(), country_name, event_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    events.append({
                        'date': event_dt.strftime('%Y-%m-%d'),
                        'time': time_text,
                        'country_code': country_code,
                        'country_name': country_name,
                        'event_name': event_name,
                        'importance': importance,
                        'actual': actual,
                        'forecast': forecast,
                        'previous': previous,
                    })
        
        # Sort by date
        events.sort(key=lambda x: (x['date'], x.get('time', '')))
        
        return {
            'events': events,
            'total': len(events),
            'countries': countries,
            'period': period,
            'source': 'doviz.com',
            'timestamp': datetime.now().isoformat(),
        }
    
    except Exception as e:
        return {'error': str(e), 'events': []}


# ══════════════════════════════════════════════════════════════════
# DEVLET TAHVIL FAIZLERI
# ══════════════════════════════════════════════════════════════════

def get_bond_yields():
    """TCMB'den tahvil faiz oranlarini ceker."""
    session = create_session()
    
    try:
        url = 'https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb+tr/main+menu/istatistikler/veri-setleri/tahvil-faiz-oranlari'
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        yields_data = []
        
        # Try to find yield data in tables
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cells) >= 2:
                    name = cells[0]
                    value = cells[1]
                    try:
                        v = float(value.replace(',', '.').replace('%', '').strip())
                        yields_data.append({'name': name, 'value': v})
                    except:
                        pass
        
        return {'yields': yields_data, 'source': 'TCMB', 'timestamp': datetime.now().isoformat()}
    
    except Exception as e:
        return {'error': str(e), 'yields': []}


# ══════════════════════════════════════════════════════════════════
# DÖVİZ KURLARI
# ══════════════════════════════════════════════════════════════════

def get_fx_rates():
    """Güncel doviz kurlarini ceker."""
    session = create_session()
    
    try:
        # TCMB official rates
        url = 'https://www.tcmb.gov.tr/kurlar/today.xml'
        r = session.get(url, timeout=10)
        
        if r.status_code == 200 and '<?xml' in r.text[:100]:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(r.text)
            
            rates = []
            for currency in root.findall('.//Currency'):
                code = currency.get('CurrencyCode', '')
                name = currency.get('CurrencyName', '')
                forexbuy = currency.find('ForexBuying')
                forexsell = currency.find('ForexSelling')
                
                if forexbuy is not None and forexbuy.text:
                    rates.append({
                        'code': code,
                        'name': name,
                        'buy': float(forexbuy.text.replace(',', '.')),
                        'sell': float(forexsell.text.replace(',', '.')) if forexsell is not None and forexsell.text else None,
                    })
            
            return {'rates': rates, 'source': 'TCMB', 'timestamp': datetime.now().isoformat()}
    
    except:
        pass
    
    # Fallback: doviz.com
    try:
        r = session.get('https://www.doviz.com/', timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        rates = []
        for row in soup.select('table.data-table tr'):
            cells = row.find_all('td')
            if len(cells) >= 3:
                name = cells[0].get_text(strip=True)
                buy = cells[1].get_text(strip=True)
                sell = cells[2].get_text(strip=True)
                try:
                    rates.append({
                        'code': name[:3].upper(),
                        'name': name,
                        'buy': float(buy.replace(',', '.')),
                        'sell': float(sell.replace(',', '.')),
                    })
                except:
                    pass
        
        return {'rates': rates[:20], 'source': 'doviz.com', 'timestamp': datetime.now().isoformat()}
    
    except Exception as e:
        return {'error': str(e), 'rates': []}


if __name__ == '__main__':
    # Quick test
    print('=== TCMB ENFLASYON ===')
    r = get_tcmb_inflation('tufe', 6)
    for d in r.get('data', []):
        print(f"  {d['date']}: Yillik={d['yearly']}%, Aylik={d['monthly']}%")
    
    print('\n=== EKONOMIK TAKVIM ===')
    cal = get_economic_calendar(['TR', 'US'], 'this_week')
    for e in cal.get('events', [])[:10]:
        print(f"  {e['date']} {e['time']} | {e['country_code']} | {e['event_name']} | {e['importance']}")
