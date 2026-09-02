#!/usr/bin/env python3
"""Quick test of borsa-mcp providers."""
import sys, asyncio
sys.path.insert(0, '.')
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def test():
    from providers.yfinance_provider import YahooFinanceProvider
    from providers.borsapy_provider import BorsapyProvider
    from providers.tefas_provider import TefasProvider
    from providers.btcturk_provider import BtcTurkProvider
    from providers.coinbase_provider import CoinbaseProvider
    from providers.borsapy_fx_provider import BorsapyFXProvider
    from providers.tcmb_provider import TcmbProvider
    import httpx
    
    client = httpx.AsyncClient(timeout=30, verify=False)
    
    print('='*60)
    print('BORSA MCP - KAPSAMLI TEST')
    print('='*60)
    
    # 1. Yahoo Finance - BIST
    yf = YahooFinanceProvider()
    print('\n1. BIST HISSELERI (Yahoo Finance)')
    for t in ['THYAO', 'GARAN', 'ASELS', 'BIMAS', 'KCHOL']:
        try:
            info = await yf.get_hizli_bilgi(t)
            b = info.get('bilgiler', '')
            print(f'\n  {t}:')
            print(f'    {str(b)[:250]}')
        except Exception as e:
            print(f'  {t}: HATA - {e}')
    
    # 2. Borsapy - BIST screener
    print('\n\n2. BIST TARAMA (Borsapy - Deger Yatirim)')
    bp = BorsapyProvider()
    try:
        result = await bp.deger_yatirim_taramasi()
        if result and hasattr(result, 'sonuclar'):
            print(f'  {len(result.sonuclar)} hisse bulundu')
            for s in result.sonuclar[:5]:
                print(f'    {s}')
    except Exception as e:
        print(f'  Hata: {e}')
    
    # 3. TEFAS
    print('\n\n3. TEFAS FONLARI')
    tefas = TefasProvider()
    methods = [m for m in dir(tefas) if not m.startswith('_') and callable(getattr(tefas, m))]
    print(f'  Mevcut methodlar: {methods}')
    try:
        result = await tefas.fon_arama('altin')
        if result:
            print(f'  Altin fonlari: {result}')
    except Exception as e:
        print(f'  TEFAS Hata: {e}')
    
    # 4. Kripto
    print('\n\n4. KRİPTO')
    btcturk = BtcTurkProvider(client)
    try:
        ticker = await btcturk.get_ticker('BTCTRY')
        if ticker and ticker.ticker_data:
            t = ticker.ticker_data[0]
            print(f'  BTCTRY: {t.last:,.0f} TL | 24s: %{t.daily_percent:.2f}')
    except Exception as e:
        print(f'  BtcTurk Hata: {e}')
    
    coinbase = CoinbaseProvider(client)
    try:
        ticker2 = await coinbase.get_ticker('BTC-USD')
        if ticker2 and ticker2.ticker_data:
            t = ticker2.ticker_data[0]
            print(f'  BTC-USD: ${t.last:,.0f} | 24s: {t.daily_percent:.2f}%')
    except Exception as e:
        print(f'  Coinbase Hata: {e}')
    
    # 5. Doviz/FX
    print('\n\n5. DÖVİZ/EMTIA')
    fx = BorsapyFXProvider(client)
    try:
        result = await fx.get_guncel_kurlar()
        if result:
            print(f'  {len(result)} kalem doviz/emtia')
            for r in result[:5]:
                print(f'    {r}')
    except Exception as e:
        print(f'  FX Hata: {e}')
    
    # 6. TCMB
    print('\n\n6. TCMB ENFLASYON')
    tcmb = TcmbProvider(client)
    try:
        result = await tcmb.get_enflasyon_verileri('tufe', 12)
        if result:
            print(f'  TUFE: {result}')
    except Exception as e:
        print(f'  TCMB Hata: {e}')
    
    await client.aclose()
    print('\n' + '='*60)
    print('TEST TAMAMLANDI')

if __name__ == '__main__':
    asyncio.run(test())
