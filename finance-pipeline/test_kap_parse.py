#!/usr/bin/env python3
"""Test parsing KAP Next.js RSC payload for disclosure content"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import re

def fetch_and_parse(disclosure_index):
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Referer': 'https://kap.org.tr',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    })
    r = s.get(f'https://kap.org.tr/tr/Bildirim/{disclosure_index}', timeout=20)
    if r.status_code != 200:
        print(f'Status: {r.status_code}')
        return
    
    raw = r.text
    print(f'Size: {len(raw)}')
    
    # The RSC payload has < encoded as \u003c (literal string)
    # In Python, the raw HTML string contains the literal chars: \ u 0 0 3 c
    # Which in Python repr looks like: \\u003c
    # Let's find the actual pattern
    
    # Write first 200 chars of sendData section to file
    idx = raw.find('sendData')
    if idx >= 0:
        chunk = raw[idx:idx+200]
        print(f'sendData found at {idx}')
        print(f'  repr: {repr(chunk[:150])}')
    
    # Find the explanationText field in the RSC payload
    # It's inside the sendData JSON as: explanationText\\\":\\\"value\\\"
    # In Python string: 'explanationText\\":\\"value\\"'
    # This is actually the literal chars: explanationText" : " value "
    # Wait no - the JSON itself is escaped inside a JS string
    
    # Let's find ALL occurrences of 'explanationText' in the raw HTML
    idx = 0
    while True:
        pos = raw.find('explanationText', idx)
        if pos < 0:
            break
        print(f'explanationText at position {pos}')
        # Show the raw context
        ctx = raw[pos:pos+300]
        print(f'  context: {repr(ctx[:200])}')
        idx = pos + 1
    
    # Let me also try a completely different approach: 
    # Find the whole RSC push content, extract the JSON, parse it
    push_pattern = re.compile(r'self\.__next_f\.push\(\[1,(.*?)\]\)', re.DOTALL)
    for i, m in enumerate(push_pattern.finditer(raw)):
        content = m.group(1)
        if 'sendData' in content:
            print(f'\n=== RSC Push {i} with sendData ===')
            # This is a JSON string like "1d:{...}"
            # Let's find the disclosure body content
            # The actual table HTML is in a later RSC push that starts with a number like "35:"
            pass
    
    # Find the push that contains the actual table content (explanationText)
    for i, m in enumerate(push_pattern.finditer(raw)):
        content = m.group(1)
        # Check if this contains the table HTML
        if 'financial-table' in content and len(content) > 1000:
            print(f'\n=== RSC Push {i} with financial-table (len={len(content)}) ===')
            # Decode the content
            # Remove the leading "XX:" prefix
            colon_idx = content.find(':')
            if colon_idx > 0:
                payload = content[colon_idx+1:]
                # Unescape the JSON string
                payload = payload.replace('\\\\u003c', '<')
                payload = payload.replace('\\\\u003e', '>')
                payload = payload.replace('\\\\u0026', '&')
                payload = payload.replace('\\\\n', '\n')
                payload = payload.replace('\\\\r', '')
                payload = payload.replace('\\\\t', '')
                payload = payload.replace('\\\\"', '"')
                payload = payload.replace("\\'", "'")
                
                # Now parse the table
                # Find gwt-Label content
                labels = re.findall(r'gwt-Label multi-language-content content-tr[^>]*>([^<]+)', payload)
                print(f'TR Labels: {len(labels)}')
                for l in labels:
                    print(f'  {l[:100]}')
                
                # Find all td content
                tds = re.findall(r'<td[^>]*>(.*?)</td>', payload, re.DOTALL)
                print(f'\nTD cells: {len(tds)}')
                for td in tds:
                    clean = re.sub(r'<[^>]+>', '', td).strip()
                    if clean:
                        print(f'  TD: {clean[:120]}')
                
                # Write to file for inspection
                with open('test_kap_content.html', 'w', encoding='utf-8') as f:
                    f.write(payload)
                print(f'\nWrote decoded HTML to test_kap_content.html')
            break

# Test with buyback page that has known data
fetch_and_parse(1655982)
