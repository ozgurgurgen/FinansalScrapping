#!/usr/bin/env python3
"""
Technical Analysis Module — RSI, MACD, Bollinger Bands, Supertrend, Pivot Points
Uses yfinance for historical data and computes indicators locally.
"""
import numpy as np
import yfinance as yf


def compute_rsi(closes, period=14):
    """Relative Strength Index."""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    rs_values = []
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rs_values.append(100)
        else:
            rs = avg_gain / avg_loss
            rs_values.append(100 - (100 / (1 + rs)))
    
    # Pad beginning
    return [None] * (period + 1) + rs_values


def compute_macd(closes, fast=12, slow=26, signal=9):
    """MACD line, signal line, histogram."""
    def ema(data, span):
        multiplier = 2 / (span + 1)
        ema_values = [data[0]]
        for i in range(1, len(data)):
            ema_values.append((data[i] - ema_values[-1]) * multiplier + ema_values[-1])
        return np.array(ema_values)
    
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line.tolist(), signal_line.tolist(), histogram.tolist()


def compute_bollinger_bands(closes, period=20, std_dev=2):
    """Bollinger Bands: upper, middle, lower."""
    closes_arr = np.array(closes)
    middle = []
    upper = []
    lower = []
    
    for i in range(len(closes)):
        if i < period - 1:
            middle.append(None)
            upper.append(None)
            lower.append(None)
        else:
            window = closes_arr[i - period + 1:i + 1]
            m = np.mean(window)
            s = np.std(window, ddof=0)
            middle.append(float(m))
            upper.append(float(m + std_dev * s))
            lower.append(float(m - std_dev * s))
    
    return upper, middle, lower


def compute_supertrend(closes, highs, lows, period=10, multiplier=3):
    """Supertrend indicator: direction and values."""
    atr = []
    for i in range(1, len(closes)):
        if i < period:
            atr.append(None)
            continue
        tr_list = []
        for j in range(max(1, i - period + 1), i + 1):
            tr = max(
                highs[j] - lows[j],
                abs(highs[j] - closes[j - 1]),
                abs(lows[j] - closes[j - 1])
            )
            tr_list.append(tr)
        atr.append(np.mean(tr_list))
    
    atr = [None] + atr
    
    upper_band = []
    lower_band = []
    direction = []  # 1 = bullish, -1 = bearish
    supertrend_val = []
    
    for i in range(len(closes)):
        if atr[i] is None or i < period:
            upper_band.append(None)
            lower_band.append(None)
            direction.append(None)
            supertrend_val.append(None)
            continue
        
        hl2 = (highs[i] + lows[i]) / 2
        ub = hl2 + multiplier * atr[i]
        lb = hl2 - multiplier * atr[i]
        
        upper_band.append(ub)
        lower_band.append(lb)
        
        if i == period:
            direction.append(1)
            supertrend_val.append(lb)
            continue
        
        prev_close = closes[i - 1]
        
        # Adjust bands
        if lb > (lower_band[i - 1] or lb) or prev_close < (lower_band[i - 1] or lb):
            lb_adj = lb
        else:
            lb_adj = lower_band[i - 1]
        
        if ub < (upper_band[i - 1] or ub) or prev_close > (upper_band[i - 1] or ub):
            ub_adj = ub
        else:
            ub_adj = upper_band[i - 1]
        
        lower_band[i] = lb_adj
        upper_band[i] = ub_adj
        
        if direction[i - 1] == 1:
            if closes[i] < lower_band[i]:
                direction.append(-1)
                supertrend_val.append(upper_band[i])
            else:
                direction.append(1)
                supertrend_val.append(lower_band[i])
        else:
            if closes[i] > upper_band[i]:
                direction.append(1)
                supertrend_val.append(lower_band[i])
            else:
                direction.append(-1)
                supertrend_val.append(upper_band[i])
    
    return direction, supertrend_val


def compute_pivot_points(high, low, close):
    """Classic Pivot Points: PP, R1-R3, S1-S3."""
    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    
    return {
        'PP': round(pp, 2),
        'R1': round(r1, 2), 'R2': round(r2, 2), 'R3': round(r3, 2),
        'S1': round(s1, 2), 'S2': round(s2, 2), 'S3': round(s3, 2),
    }


def compute_sma(closes, period):
    """Simple Moving Average."""
    result = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        result.append(float(np.mean(closes[i - period + 1:i + 1])))
    return result


def compute_ema(closes, period):
    """Exponential Moving Average."""
    multiplier = 2 / (period + 1)
    ema_values = [closes[0]]
    for i in range(1, len(closes)):
        ema_values.append((closes[i] - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def get_technical_analysis(ticker, period='6mo'):
    """
    Full technical analysis for a BIST stock.
    Returns dict with all indicators and signals.
    """
    try:
        t = yf.Ticker(f'{ticker}.IS')
        df = t.history(period=period)
        
        if df.empty:
            return {'error': f'{ticker} icin veri bulunamadi'}
        
        closes = df['Close'].values.tolist()
        highs = df['High'].values.tolist()
        lows = df['Low'].values.tolist()
        volumes = df['Volume'].values.tolist()
        
        # Current values
        current_price = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        current_close = closes[-1]
        
        # RSI
        rsi_values = compute_rsi(closes)
        current_rsi = rsi_values[-1]
        
        # MACD
        macd_line, signal_line, histogram = compute_macd(closes)
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        current_hist = histogram[-1]
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(closes)
        current_bb_upper = bb_upper[-1]
        current_bb_middle = bb_middle[-1]
        current_bb_lower = bb_lower[-1]
        
        # Supertrend
        st_direction, st_value = compute_supertrend(closes, highs, lows)
        current_st_direction = st_direction[-1]
        current_st_value = st_value[-1]
        
        # Pivot Points (based on last candle)
        pivots = compute_pivot_points(current_high, current_low, current_close)
        
        # Moving Averages
        sma_5 = compute_sma(closes, 5)
        sma_10 = compute_sma(closes, 10)
        sma_20 = compute_sma(closes, 20)
        sma_50 = compute_sma(closes, 50)
        sma_200 = compute_sma(closes, min(200, len(closes)))
        ema_12 = compute_ema(closes, 12)
        ema_26 = compute_ema(closes, 26)
        
        # Trend signals
        rsi_signal = 'Asiri Alim' if current_rsi and current_rsi > 70 else ('Asiri Satim' if current_rsi and current_rsi < 30 else 'Notr')
        macd_signal = 'AL' if current_hist and current_hist > 0 and histogram[-2] <= 0 else ('SAT' if current_hist and current_hist < 0 and histogram[-2] >= 0 else 'Notr')
        
        bb_position = 'UST BANT' if current_price > current_bb_upper else ('ALT BANT' if current_price < current_bb_lower else 'ORTA')
        
        trend = 'Yukselis' if current_st_direction == 1 else 'Dusus' if current_st_direction == -1 else 'Belirsiz'
        
        # Overall signal
        buy_signals = sum([
            1 if current_rsi and current_rsi < 30 else 0,
            1 if current_price > current_bb_lower and current_price < current_bb_middle else 0,
            1 if current_st_direction == 1 else 0,
            1 if current_hist and current_hist > 0 else 0,
        ])
        
        sell_signals = sum([
            1 if current_rsi and current_rsi > 70 else 0,
            1 if current_price > current_bb_upper else 0,
            1 if current_st_direction == -1 else 0,
            1 if current_hist and current_hist < 0 else 0,
        ])
        
        if buy_signals >= 3:
            overall = 'GUCLU AL'
        elif buy_signals >= 2:
            overall = 'AL'
        elif sell_signals >= 3:
            overall = 'GUCLU SAT'
        elif sell_signals >= 2:
            overall = 'SAT'
        else:
            overall = 'NOTR'
        
        # Chart data (last 60 candles)
        chart_len = min(60, len(df))
        chart_data = {
            'dates': [d.strftime('%Y-%m-%d') for d in df.index[-chart_len:]],
            'closes': [round(c, 2) for c in closes[-chart_len:]],
            'volumes': [int(v) for v in volumes[-chart_len:]],
            'bb_upper': [round(v, 2) if v else None for v in bb_upper[-chart_len:]],
            'bb_middle': [round(v, 2) if v else None for v in bb_middle[-chart_len:]],
            'bb_lower': [round(v, 2) if v else None for v in bb_lower[-chart_len:]],
        }
        
        return {
            'ticker': ticker,
            'price': round(current_price, 2),
            'period': period,
            
            'rsi': {'value': round(current_rsi, 2) if current_rsi else None, 'signal': rsi_signal, 'period': 14},
            'macd': {
                'macd': round(current_macd, 4) if current_macd else None,
                'signal': round(current_signal, 4) if current_signal else None,
                'histogram': round(current_hist, 4) if current_hist else None,
                'signal_text': macd_signal
            },
            'bollinger': {
                'upper': round(current_bb_upper, 2) if current_bb_upper else None,
                'middle': round(current_bb_middle, 2) if current_bb_middle else None,
                'lower': round(current_bb_lower, 2) if current_bb_lower else None,
                'position': bb_position
            },
            'supertrend': {
                'direction': 'Yukselis' if current_st_direction == 1 else 'Dusus',
                'value': round(current_st_value, 2) if current_st_value else None
            },
            'pivots': pivots,
            'moving_averages': {
                'sma_5': round(sma_5[-1], 2) if sma_5[-1] else None,
                'sma_10': round(sma_10[-1], 2) if sma_10[-1] else None,
                'sma_20': round(sma_20[-1], 2) if sma_20[-1] else None,
                'sma_50': round(sma_50[-1], 2) if sma_50[-1] else None,
                'sma_200': round(sma_200[-1], 2) if sma_200[-1] else None,
                'ema_12': round(ema_12[-1], 2),
                'ema_26': round(ema_26[-1], 2),
            },
            'trend': trend,
            'overall_signal': overall,
            'chart_data': chart_data,
        }
    
    except Exception as e:
        return {'error': str(e)}


def scan_stocks_by_condition(tickers, condition_func, condition_name=''):
    """Scan a list of tickers with a custom condition function. Uses batch download for speed."""
    import pandas as pd
    
    results = []
    # Use yfinance batch download for speed
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            # Download all at once
            symbols = [f'{t}.IS' for t in batch]
            data = yf.download(symbols, period='3mo', group_by='ticker', progress=False, threads=True)
            
            for ticker in batch:
                try:
                    sym = f'{ticker}.IS'
                    if len(batch) == 1:
                        df = data
                    else:
                        df = data[sym] if sym in data.columns.get_level_values(0) else None
                    
                    if df is None or df.empty or len(df) < 30:
                        continue
                    
                    closes = df['Close'].dropna().values.tolist()
                    if len(closes) < 30:
                        continue
                    
                    volumes = df['Volume'].dropna().values.tolist()
                    rsi_values = compute_rsi(closes)
                    _, _, histogram = compute_macd(closes)
                    
                    current = {
                        'ticker': ticker,
                        'price': closes[-1],
                        'change_pct': round((closes[-1] - closes[-2]) / closes[-2] * 100, 2),
                        'volume': volumes[-1] if volumes else 0,
                        'rsi': round(rsi_values[-1], 2) if rsi_values[-1] else None,
                        'macd': round(histogram[-1], 4) if histogram[-1] else None,
                    }
                    
                    if condition_func(current):
                        results.append(current)
                except Exception:
                    pass
        except Exception:
            pass
    
    return results


# Preset conditions for screener
SCANNER_PRESETS = {
    'oversold': {
        'name': 'Asiri Satim (RSI<30)',
        'condition': lambda x: x.get('rsi') and x['rsi'] < 30,
        'category': 'reversal'
    },
    'overbought': {
        'name': 'Asiri Alim (RSI>70)',
        'condition': lambda x: x.get('rsi') and x['rsi'] > 70,
        'category': 'reversal'
    },
    'bullish_momentum': {
        'name': 'Yukselis Momentumu',
        'condition': lambda x: x.get('rsi') and x['rsi'] > 50 and x.get('macd') and x['macd'] > 0,
        'category': 'momentum'
    },
    'bearish_momentum': {
        'name': 'Dusus Momentumu',
        'condition': lambda x: x.get('rsi') and x['rsi'] < 50 and x.get('macd') and x['macd'] < 0,
        'category': 'momentum'
    },
    'high_volume': {
        'name': 'Yuksek Hacim',
        'condition': lambda x: x.get('volume') and x['volume'] > 10_000_000,
        'category': 'volume'
    },
    'big_gainers': {
        'name': 'Gunun Kazananlari (>%3)',
        'condition': lambda x: x.get('change_pct') and x['change_pct'] > 3,
        'category': 'momentum'
    },
    'big_losers': {
        'name': 'Gunun Kaybedenleri (<%-3)',
        'condition': lambda x: x.get('change_pct') and x['change_pct'] < -3,
        'category': 'momentum'
    },
    'macd_bullish': {
        'name': 'MACD AL Sinyali',
        'condition': lambda x: x.get('macd') and x['macd'] > 0,
        'category': 'trend'
    },
}
