#!/usr/bin/env python3
"""Quick test of KAP RSC parser"""
import sys, os, time, random

# Fix encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrape_kap_rsc import fetch_kap_page, parse_disclosure_content

# Test buyback page
print('Testing buyback 1655982...')
html = fetch_kap_page(1655982)
if html:
    result = parse_disclosure_content(html)
    kv = result['kv']
    print(f'Tables: {result["tables_count"]}, KV: {len(kv)}')
    for k, v in list(kv.items())[:15]:
        print(f'  {k[:60]} = {v[:100]}')
else:
    print('FAILED to fetch')

time.sleep(4)

# Test tender page
print('\nTesting tender 1655938...')
html2 = fetch_kap_page(1655938)
if html2:
    result2 = parse_disclosure_content(html2)
    kv2 = result2['kv']
    print(f'Tables: {result2["tables_count"]}, KV: {len(kv2)}')
    for k, v in list(kv2.items())[:15]:
        print(f'  {k[:60]} = {v[:100]}')
else:
    print('FAILED')
