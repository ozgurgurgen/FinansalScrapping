#!/usr/bin/env python3
"""Test all borsa-mcp tools."""
import sys, asyncio, io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def test():
    from unified_mcp_server import app
    
    tests = [
        ('search_symbol', {'query': 'THYAO', 'market': 'bist', 'limit': 3}),
        ('get_quote', {'symbol': 'THYAO', 'market': 'bist'}),
        ('get_historical_data', {'symbol': 'THYAO', 'market': 'bist', 'period': '1mo'}),
        ('get_financial_statements', {'symbol': 'THYAO', 'market': 'bist', 'statement_type': 'all', 'period': 'annual'}),
        ('get_financial_ratios', {'symbol': 'THYAO', 'market': 'bist', 'ratio_set': 'valuation'}),
        ('get_crypto_market', {'symbol': 'BTCTRY', 'exchange': 'btcturk', 'data_type': 'ticker'}),
        ('get_fund_data', {'symbol': 'AAK', 'market': 'fund'}),
        ('get_index_data', {'symbol': 'XU100', 'market': 'bist'}),
        ('get_economic_calendar', {'country': 'TR', 'period': 'this_week'}),
        ('get_macro_data', {'data_type': 'tufe'}),
    ]
    
    for tool_name, params in tests:
        print(f'\n{"="*60}')
        print(f'TEST: {tool_name}({params})')
        print('='*60)
        try:
            r = await app.call_tool(tool_name, params)
            text = str(r)
            # Show first 500 chars
            print(text[:500])
            if len(text) > 500:
                print(f'... ({len(text)} chars total)')
        except Exception as e:
            print(f'HATA: {e}')

if __name__ == '__main__':
    asyncio.run(test())
