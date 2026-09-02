#!/usr/bin/env python3
"""
Advanced Analysis Module — Buffett, Sector Comparison, Analyst Data, Extended Indicators
Ported from borsa-mcp and enhanced for finance-pipeline.
"""
import numpy as np
import yfinance as yf
from datetime import datetime


# ══════════════════════════════════════════════════════════════════
# 1. BUFFETT VALUE ANALYSIS
# ══════════════════════════════════════════════════════════════════

def buffett_analysis(ticker):
    """
    Warren Buffett style value investing analysis.
    Owner Earnings, OE Yield, DCF Intrinsic Value, Safety Margin.
    """
    try:
        t = yf.Ticker(f'{ticker}.IS')
        info = t.info or {}
        
        # Get financial statements
        try:
            bs = t.balance_sheet
            is_ = t.income_stmt
            cf = t.cashflow
        except:
            bs = is_ = cf = None
        
        # Current price & market cap
        price = info.get('currentPrice') or info.get('lastPrice') or info.get('regularMarketPrice')
        market_cap = info.get('marketCap')
        
        if not price or not market_cap:
            return {'error': 'Fiyat veya piyasa degeri bulunamadi'}
        
        # ─── Owner Earnings (OE) ───
        # OE = Net Income + Depreciation - CapEx - ΔWorking Capital
        net_income = info.get('netIncomeToCommon', 0) or 0
        depreciation = info.get('depreciation', 0) or 0
        capex = info.get('capitalExpenditures', 0) or 0  # negative = outflow
        working_capital_change = 0  # Simplified: use 0 if not available
        
        owner_earnings = net_income + depreciation + capex + working_capital_change
        oe_annual = owner_earnings  # Already annual from yfinance
        
        # ─── OE Yield ───
        oe_yield = (oe_annual / market_cap * 100) if market_cap > 0 else 0
        
        # ─── DCF with Fisher Effect (simplified) ───
        # Fisher: r_real = (1 + r_nominal) / (1 + inflation) - 1
        nominal_rate = 0.30  # TR 10Y default (updated if available)
        expected_inflation = (info.get('inflationRate') or 0.32) / 100
        risk_premium = 0.10
        
        # Try to get real inflation from our macro data
        try:
            from services.admin_dashboard.macro_data import get_tcmb_inflation
            inf_data = get_tcmb_inflation('tufe', 1)
            if inf_data.get('data'):
                expected_inflation = inf_data['data'][0].get('yearly', 32) / 100
        except:
            pass
        
        # Try to get bond yield
        try:
            import yfinance as yf2
            tnx = yf2.Ticker('^TNX')
            h = tnx.history(period='1d')
            if not h.empty:
                # For BIST, use TR 10Y (higher)
                nominal_rate = 0.30  # Keep TR default
        except:
            pass
        
        r_real = (1 + nominal_rate) / (1 + expected_inflation) - 1 + risk_premium
        r_real = max(r_real, 0.05)  # Floor at 5%
        
        # Growth rate
        earnings_growth = info.get('earningsGrowth')
        if earnings_growth and earnings_growth > expected_inflation:
            growth_rate_real = (1 + earnings_growth) / (1 + expected_inflation) - 1
        else:
            growth_rate_real = min(0.03, 0.05)  # Conservative 3%
        
        terminal_growth_real = 0.02  # 2% terminal
        
        # DCF calculation
        forecast_years = 5
        total_pv = 0
        projected_oe = []
        for year in range(1, forecast_years + 1):
            projected = oe_annual * ((1 + growth_rate_real) ** year)
            pv = projected / ((1 + r_real) ** year)
            total_pv += pv
            projected_oe.append({'year': year, 'projected_oe': round(projected), 'pv': round(pv)})
        
        # Terminal value
        terminal_oe = projected_oe[-1]['projected_oe'] if projected_oe else oe_annual
        terminal_value = terminal_oe * (1 + terminal_growth_real) / (r_real - terminal_growth_real)
        terminal_pv = terminal_value / ((1 + r_real) ** forecast_years)
        
        intrinsic_value = total_pv + terminal_pv
        intrinsic_per_share = intrinsic_value / (info.get('sharesOutstanding', 1) or 1)
        
        # ─── Safety Margin ───
        safety_margin = ((intrinsic_per_share - price) / intrinsic_per_share * 100) if intrinsic_per_share > 0 else 0
        
        # ─── Buffett Score ───
        score = 0
        reasons = []
        
        # OE > 0
        if oe_annual > 0:
            score += 20
            reasons.append('Owner Earnings pozitif')
        
        # OE Yield > 10%
        if oe_yield > 10:
            score += 20
            reasons.append(f'OE Yield %{oe_yield:.1f} (>10%)')
        elif oe_yield > 5:
            score += 10
            reasons.append(f'OE Yield %{oe_yield:.1f} (orta)')
        
        # Safety margin > 0
        if safety_margin > 30:
            score += 30
            reasons.append(f'Guvenli Marj %{safety_margin:.1f} (>30%)')
        elif safety_margin > 10:
            score += 15
            reasons.append(f'Guvenli Marj %{safety_margin:.1f} (orta)')
        elif safety_margin > 0:
            score += 5
            reasons.append(f'Guvenli Marj %{safety_margin:.1f} (dusuk)')
        else:
            reasons.append(f'Guvenli Marj %{safety_margin:.1f} (negatif)')
        
        # ROE > 15%
        roe = (info.get('returnOnEquity') or 0) * 100
        if roe > 15:
            score += 15
            reasons.append(f'ROE %{roe:.1f} (>15%)')
        elif roe > 8:
            score += 8
            reasons.append(f'ROE %{roe:.1f}')
        
        # Low debt
        debt_equity = info.get('debtToEquity', 0) or 0
        if debt_equity < 50:
            score += 15
            reasons.append(f'Debt/Equity {debt_equity:.0f} (dusuk)')
        elif debt_equity < 100:
            score += 8
            reasons.append(f'Debt/Equity {debt_equity:.0f} (orta)')
        
        # Determine rating
        if score >= 70:
            rating = 'GUCLU AL'
        elif score >= 50:
            rating = 'AL'
        elif score >= 30:
            rating = 'NOTR'
        else:
            rating = 'SAT'
        
        return {
            'ticker': ticker,
            'price': round(price, 2),
            'market_cap': round(market_cap / 1e9, 2),
            
            'owner_earnings': {
                'value': round(oe_annual),
                'net_income': round(net_income),
                'depreciation': round(depreciation),
                'capex': round(capex),
                'unit': 'TL',
            },
            'oe_yield': round(oe_yield, 2),
            
            'dcf': {
                'nominal_rate': round(nominal_rate * 100, 1),
                'inflation': round(expected_inflation * 100, 1),
                'real_rate': round(r_real * 100, 2),
                'growth_rate': round(growth_rate_real * 100, 2),
                'terminal_growth': round(terminal_growth_real * 100, 1),
                'forecast_years': forecast_years,
                'intrinsic_value': round(intrinsic_value),
                'intrinsic_per_share': round(intrinsic_per_share, 2),
                'projected': projected_oe,
            },
            
            'safety_margin': round(safety_margin, 1),
            'buffett_score': score,
            'rating': rating,
            'reasons': reasons,
            
            'key_ratios': {
                'roe': round(roe, 1),
                'roa': round((info.get('returnOnAssets') or 0) * 100, 1),
                'debt_equity': round(debt_equity, 1),
                'current_ratio': info.get('currentRatio'),
                'profit_margins': round((info.get('profitMargins') or 0) * 100, 1),
                'operating_margins': round((info.get('operatingMargins') or 0) * 100, 1),
                'revenue_growth': round((info.get('revenueGrowth') or 0) * 100, 1),
                'earnings_growth': round((earnings_growth or 0) * 100, 1),
                'dividend_yield': round((info.get('dividendYield') or 0) * 100, 2),
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
            },
            
            'data_sources': {
                'nominal_rate': 'Default 30% (TR 10Y)',
                'inflation': 'TCMB TÜFE' if expected_inflation != 0.32 else 'Default',
                'growth': 'Yahoo Finance analyst' if earnings_growth else 'Default 3%',
            },
        }
    
    except Exception as e:
        return {'error': str(e)}





# ══════════════════════════════════════════════════════════════════
# 2. SECTOR COMPARISON
# ══════════════════════════════════════════════════════════════════

def sector_comparison(ticker):
    """
    Compare a stock against its sector peers.
    """
    try:
        t = yf.Ticker(f'{ticker}.IS')
        info = t.info or {}
        
        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')
        
        # Current stock metrics
        current = {
            'ticker': ticker,
            'name': info.get('shortName', ''),
            'sector': sector,
            'industry': industry,
            'pe': info.get('trailingPE'),
            'pb': info.get('priceToBook'),
            'roe': (info.get('returnOnEquity') or 0) * 100,
            'roa': (info.get('returnOnAssets') or 0) * 100,
            'profit_margin': (info.get('profitMargins') or 0) * 100,
            'revenue_growth': (info.get('revenueGrowth') or 0) * 100,
            'market_cap': info.get('marketCap', 0),
            'dividend_yield': (info.get('dividendYield') or 0) * 100,
        }
        
        # Find sector peers from our database
        import sqlite3, os
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'finance.db')
        db = sqlite3.connect(db_path)
        c = db.cursor()
        
        # Map yfinance sector to our DB sector names
        sector_map = {
            'Industrials': ['Imalat', 'Ulasim', 'Insaat'],
            'Financial Services': ['Bankacilik', 'Sigorta', 'Menkul Degerler'],
            'Technology': ['Teknoloji'],
            'Consumer Defensive': ['Gida', 'Perakende/Tuketim'],
            'Consumer Cyclical': ['Perakende/Tuketim', 'Otomotiv', 'Tekstil'],
            'Energy': ['Enerji', 'Petrol/Gaz'],
            'Basic Materials': ['Maden', 'Maden/Malzeme', 'Cimento/Cam'],
            'Healthcare': ['Saglik', 'Kimya'],
            'Communication Services': ['Iletisim'],
            'Real Estate': ['Gayrimenkul', 'GYO'],
            'Utilities': ['Altyapi'],
        }
        
        db_sectors = sector_map.get(sector, [sector])
        placeholders = ','.join(['?'] * len(db_sectors))
        c.execute(f'''
            SELECT ticker, company_name, sector FROM companies 
            WHERE sector IN ({placeholders}) AND ticker != ? AND ticker IS NOT NULL
            LIMIT 20
        ''', db_sectors + [ticker])
        peers_raw = c.fetchall()
        db.close()
        
        if not peers_raw:
            return {
                'ticker': ticker,
                'sector': sector,
                'industry': industry,
                'current': current,
                'peers': [],
                'sector_average': {'peer_count': 0},
                'position': {},
                'message': f'{sector} sektorunde eslesen sirket bulunamadi'
            }
        
        # Fetch peer data
        peers = []
        for peer_ticker, peer_name, peer_sector in peers_raw:
            try:
                pt = yf.Ticker(f'{peer_ticker}.IS')
                pi = pt.info or {}
                if pi.get('trailingPE') or pi.get('priceToBook'):
                    peers.append({
                        'ticker': peer_ticker,
                        'name': peer_name,
                        'pe': pi.get('trailingPE'),
                        'pb': pi.get('priceToBook'),
                        'roe': round((pi.get('returnOnEquity') or 0) * 100, 1),
                        'profit_margin': round((pi.get('profitMargins') or 0) * 100, 1),
                        'market_cap': pi.get('marketCap', 0),
                    })
            except:
                pass
        
        db.close()
        
        # Calculate sector averages
        if peers:
            pe_values = [p['pe'] for p in peers if p.get('pe')]
            pb_values = [p['pb'] for p in peers if p.get('pb')]
            roe_values = [p['roe'] for p in peers if p.get('roe')]
            
            sector_avg = {
                'pe': round(np.mean(pe_values), 1) if pe_values else None,
                'pb': round(np.mean(pb_values), 2) if pb_values else None,
                'roe': round(np.mean(roe_values), 1) if roe_values else None,
                'peer_count': len(peers),
            }
            
            # Position vs peers
            position = {}
            if current['pe'] and sector_avg['pe']:
                position['pe'] = 'Degerli' if current['pe'] < sector_avg['pe'] else 'Pahali'
            if current['roe'] and sector_avg['roe']:
                position['roe'] = 'Güclu' if current['roe'] > sector_avg['roe'] else 'Zayif'
        else:
            sector_avg = {'peer_count': 0}
            position = {}
        
        return {
            'ticker': ticker,
            'current': current,
            'sector_average': sector_avg,
            'position': position,
            'peers': peers[:10],  # Top 10 peers
        }
    
    except Exception as e:
        return {'error': str(e)}


# ══════════════════════════════════════════════════════════════════
# 3. ANALYST DATA & EARNINGS
# ══════════════════════════════════════════════════════════════════

def analyst_data(ticker):
    """
    Analyst ratings, price targets, earnings calendar.
    """
    try:
        t = yf.Ticker(f'{ticker}.IS')
        info = t.info or {}
        
        # Analyst recommendations
        recs = info.get('recommendationKey', 'N/A')
        target_mean = info.get('targetMeanPrice')
        target_high = info.get('targetHighPrice')
        target_low = info.get('targetLowPrice')
        current_price = info.get('currentPrice') or info.get('lastPrice') or 0
        
        upside = None
        if target_mean and current_price:
            upside = (target_mean - current_price) / current_price * 100
        
        # Earnings
        earnings_dates = None
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                earnings_dates = []
                for idx, row in ed.head(4).iterrows():
                    earnings_dates.append({
                        'date': str(idx.date()) if hasattr(idx, 'date') else str(idx),
                        'eps_estimate': float(row.get('EPS Estimate', 0)) if row.get('EPS Estimate') else None,
                        'eps_actual': float(row.get('Reported EPS', 0)) if row.get('Reported EPS') else None,
                    })
        except:
            pass
        
        # Growth estimates
        growth_estimates = {}
        try:
            ge = t.growth_estimates
            if ge is not None and not ge.empty:
                for col in ge.columns[:4]:
                    for idx in ge.index[:4]:
                        val = ge.loc[idx, col] if idx in ge.index else None
                        if val is not None:
                            growth_estimates[f'{col}_{idx}'] = round(float(val) * 100, 1)
        except:
            pass
        
        return {
            'ticker': ticker,
            'recommendation': recs,
            'price_target': {
                'mean': target_mean,
                'high': target_high,
                'low': target_low,
                'current': current_price,
                'upside': round(upside, 1) if upside else None,
            },
            'earnings': earnings_dates,
            'growth_estimates': growth_estimates,
        }
    
    except Exception as e:
        return {'error': str(e)}


# ══════════════════════════════════════════════════════════════════
# 4. EXTENDED TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════════

def compute_adx(highs, lows, closes, period=14):
    """Average Directional Index."""
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(closes)):
        h_diff = highs[i] - highs[i-1]
        l_diff = lows[i-1] - lows[i]
        
        plus_dm.append(max(h_diff, 0) if h_diff > l_diff else 0)
        minus_dm.append(max(l_diff, 0) if l_diff > h_diff else 0)
        
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)
    
    # Smooth
    atr = np.mean(tr_list[:period]) if len(tr_list) >= period else np.mean(tr_list)
    plus_di = np.mean(plus_dm[:period]) if len(plus_dm) >= period else np.mean(plus_dm)
    minus_di = np.mean(minus_dm[:period]) if len(minus_dm) >= period else np.mean(minus_dm)
    
    adx_values = [None] * (period + 1)
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_di = (plus_di * (period - 1) + plus_dm[i]) / period
        minus_di = (minus_di * (period - 1) + minus_dm[i]) / period
        
        if atr > 0:
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        else:
            dx = 0
        adx_values.append(dx)
    
    return adx_values


def compute_stochastic(closes, highs, lows, k_period=14, d_period=3):
    """Stochastic Oscillator: %K and %D."""
    k_values = [None] * (k_period - 1)
    
    for i in range(k_period - 1, len(closes)):
        window_high = max(highs[i - k_period + 1:i + 1])
        window_low = min(lows[i - k_period + 1:i + 1])
        
        if window_high == window_low:
            k_values.append(50)
        else:
            k_values.append((closes[i] - window_low) / (window_high - window_low) * 100)
    
    # %D = SMA of %K
    d_values = [None] * (k_period + d_period - 2)
    for i in range(k_period + d_period - 2, len(k_values)):
        valid_k = [v for v in k_values[i - d_period + 1:i + 1] if v is not None]
        d_values.append(np.mean(valid_k) if valid_k else None)
    
    return k_values, d_values


def compute_cci(highs, lows, closes, period=20):
    """Commodity Channel Index."""
    cci_values = [None] * (period - 1)
    
    for i in range(period - 1, len(closes)):
        tp = [(highs[j] + lows[j] + closes[j]) / 3 for j in range(i - period + 1, i + 1)]
        sma_tp = np.mean(tp)
        mad = np.mean([abs(x - sma_tp) for x in tp])
        
        if mad > 0:
            cci_values.append((tp[-1] - sma_tp) / (0.015 * mad))
        else:
            cci_values.append(0)
    
    return cci_values


def compute_williams_r(highs, lows, closes, period=14):
    """Williams %R."""
    wr_values = [None] * (period - 1)
    
    for i in range(period - 1, len(closes)):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        
        if hh == ll:
            wr_values.append(-50)
        else:
            wr_values.append((hh - closes[i]) / (hh - ll) * -100)
    
    return wr_values


def compute_aroon(highs, lows, period=25):
    """Aroon Up/Down."""
    aroon_up = [None] * (period - 1)
    aroon_down = [None] * (period - 1)
    
    for i in range(period - 1, len(highs)):
        high_window = highs[i - period + 1:i + 1]
        low_window = lows[i - period + 1:i + 1]
        
        days_since_high = period - 1 - high_window.index(max(high_window))
        days_since_low = period - 1 - low_window.index(min(low_window))
        
        aroon_up.append((period - days_since_high) / period * 100)
        aroon_down.append((period - days_since_low) / period * 100)
    
    return aroon_up, aroon_down


def extended_indicators(ticker, period='6mo'):
    """All technical indicators including extended ones."""
    from services.admin_dashboard.technical_analysis import compute_rsi, compute_macd, compute_bollinger_bands, compute_supertrend, compute_sma, compute_ema
    
    try:
        t = yf.Ticker(f'{ticker}.IS')
        df = t.history(period=period)
        
        if df.empty:
            return {'error': f'{ticker} icin veri bulunamadi'}
        
        closes = df['Close'].values.tolist()
        highs = df['High'].values.tolist()
        lows = df['Low'].values.tolist()
        volumes = df['Volume'].values.tolist()
        
        current = closes[-1]
        
        # Base indicators
        rsi_values = compute_rsi(closes)
        macd_line, signal_line, histogram = compute_macd(closes)
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(closes)
        st_direction, st_value = compute_supertrend(closes, highs, lows)
        
        # Extended indicators
        adx_values = compute_adx(highs, lows, closes)
        stoch_k, stoch_d = compute_stochastic(closes, highs, lows)
        cci_values = compute_cci(highs, lows, closes)
        wr_values = compute_williams_r(highs, lows, closes)
        aroon_up, aroon_down = compute_aroon(highs, lows)
        
        # Current values
        current_rsi = rsi_values[-1]
        current_macd = histogram[-1]
        current_adx = adx_values[-1] if adx_values[-1] is not None else None
        current_stoch_k = stoch_k[-1]
        current_stoch_d = stoch_d[-1]
        current_cci = cci_values[-1]
        current_wr = wr_values[-1]
        current_aroon_up = aroon_up[-1]
        current_aroon_down = aroon_down[-1]
        
        # Signal generation
        signals = {}
        buy_count = 0
        sell_count = 0
        
        # RSI
        if current_rsi and current_rsi < 30:
            signals['RSI'] = 'ASIRI SATIM (AL)'
            buy_count += 1
        elif current_rsi and current_rsi > 70:
            signals['RSI'] = 'ASIRI ALIM (SAT)'
            sell_count += 1
        else:
            signals['RSI'] = 'NOTR'
        
        # MACD
        if current_macd and current_macd > 0:
            signals['MACD'] = 'POZITIF (AL)'
            buy_count += 1
        elif current_macd and current_macd < 0:
            signals['MACD'] = 'NEGATIF (SAT)'
            sell_count += 1
        
        # ADX
        if current_adx:
            if current_adx > 25:
                signals['ADX'] = f'GUVCLU TREND ({current_adx:.0f})'
            else:
                signals['ADX'] = f'ZAYIF TREND ({current_adx:.0f})'
        
        # Stochastic
        if current_stoch_k and current_stoch_k < 20:
            signals['Stochastic'] = 'ASIRI SATIM (AL)'
            buy_count += 1
        elif current_stoch_k and current_stoch_k > 80:
            signals['Stochastic'] = 'ASIRI ALIM (SAT)'
            sell_count += 1
        
        # CCI
        if current_cci and current_cci < -100:
            signals['CCI'] = 'ASIRI SATIM (AL)'
            buy_count += 1
        elif current_cci and current_cci > 100:
            signals['CCI'] = 'ASIRI ALIM (SAT)'
            sell_count += 1
        
        # Williams %R
        if current_wr and current_wr < -80:
            signals['Williams'] = 'ASIRI SATIM (AL)'
            buy_count += 1
        elif current_wr and current_wr > -20:
            signals['Williams'] = 'ASIRI ALIM (SAT)'
            sell_count += 1
        
        # Aroon
        if current_aroon_up and current_aroon_down:
            if current_aroon_up > 70 and current_aroon_down < 30:
                signals['Aroon'] = 'YUKSELIS'
                buy_count += 1
            elif current_aroon_down > 70 and current_aroon_up < 30:
                signals['Aroon'] = 'DUSUS'
                sell_count += 1
        
        # Overall
        if buy_count >= 4:
            overall = 'GUCLU AL'
        elif buy_count >= 2:
            overall = 'AL'
        elif sell_count >= 4:
            overall = 'GUCLU SAT'
        elif sell_count >= 2:
            overall = 'SAT'
        else:
            overall = 'NOTR'
        
        return {
            'ticker': ticker,
            'price': round(current, 2),
            'period': period,
            
            'indicators': {
                'rsi': {'value': round(current_rsi, 2) if current_rsi else None, 'signal': signals.get('RSI')},
                'macd': {'histogram': round(current_macd, 4) if current_macd else None, 'signal': signals.get('MACD')},
                'adx': {'value': round(current_adx, 2) if current_adx else None, 'signal': signals.get('ADX')},
                'stochastic': {'k': round(current_stoch_k, 2) if current_stoch_k else None, 'd': round(current_stoch_d, 2) if current_stoch_d else None, 'signal': signals.get('Stochastic')},
                'cci': {'value': round(current_cci, 2) if current_cci else None, 'signal': signals.get('CCI')},
                'williams_r': {'value': round(current_wr, 2) if current_wr else None, 'signal': signals.get('Williams')},
                'aroon': {'up': round(current_aroon_up, 2) if current_aroon_up else None, 'down': round(current_aroon_down, 2) if current_aroon_down else None, 'signal': signals.get('Aroon')},
                'bollinger': {'upper': round(bb_upper[-1], 2) if bb_upper[-1] else None, 'middle': round(bb_middle[-1], 2) if bb_middle[-1] else None, 'lower': round(bb_lower[-1], 2) if bb_lower[-1] else None},
                'supertrend': {'direction': 'Yukselis' if st_direction[-1] == 1 else 'Dusus', 'value': round(st_value[-1], 2) if st_value[-1] else None},
            },
            
            'signal_summary': {
                'buy_count': buy_count,
                'sell_count': sell_count,
                'overall': overall,
            },
            
            'chart_data': {
                'dates': [d.strftime('%Y-%m-%d') for d in df.index[-60:]],
                'closes': [round(c, 2) for c in closes[-60:]],
                'volumes': [int(v) for v in volumes[-60:]],
            },
        }
    
    except Exception as e:
        return {'error': str(e)}


# ══════════════════════════════════════════════════════════════════
# 5. US STOCK SUPPORT
# ══════════════════════════════════════════════════════════════════

def us_stock_analysis(ticker):
    """Quick analysis for US stocks (NYSE/NASDAQ)."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        
        return {
            'ticker': ticker,
            'name': info.get('shortName') or info.get('longName'),
            'price': info.get('currentPrice') or info.get('lastPrice'),
            'currency': info.get('currency', 'USD'),
            'market_cap': info.get('marketCap'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'pe': info.get('trailingPE'),
            'pb': info.get('priceToBook'),
            'roe': (info.get('returnOnEquity') or 0) * 100,
            'dividend_yield': (info.get('dividendYield') or 0) * 100,
            '52w_high': info.get('fiftyTwoWeekHigh'),
            '52w_low': info.get('fiftyTwoWeekLow'),
            'beta': info.get('beta'),
        }
    except Exception as e:
        return {'error': str(e)}
