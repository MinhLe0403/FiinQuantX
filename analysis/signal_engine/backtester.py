# analysis/signal_engine/backtester.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from .config import SignalConfig

cfg = SignalConfig()

def skip_weekends(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return dates[dates.weekday < 5]

def calculate_forward_returns(df: pd.DataFrame, signal_date: pd.Timestamp) -> Dict[int, float]:
    """Tính % return từ high sau T+2 đến T+N (ngày giao dịch)"""
    future = df[df['time'] > signal_date].copy()
    if future.empty:
        return {h: np.nan for h in cfg.HORIZONS}
    
    future = future.sort_values('time')
    trading_days = skip_weekends(future['time'])
    if len(trading_days) < 3:  # Không đủ T+2
        return {h: np.nan for h in cfg.HORIZONS}
    
    close_today = df[df['time'] == signal_date]['close'].iloc[0]
    highs = {}
    for h in cfg.HORIZONS:
        window = trading_days[:h+2]  # +2 vì T+0 là hôm nay, T+1 là mai, T+2 bắt đầu
        if len(window) >= 3:
            high_price = future[future['time'].isin(window)]['high'].max()
            highs[h] = (high_price / close_today) - 1
        else:
            highs[h] = np.nan
    return highs

def backtest_signal_history(symbol: str, analyzer: 'StockAnalyzer') -> pd.DataFrame:
    from analysis.core import StockAnalyzer
    sa = analyzer  # Dùng chính analyzer truyền vào
    
    df_full = sa.get_full_data(symbol, limit=1000)
    if len(df_full) < 200:
        return pd.DataFrame()
    
    df_full = analyzer.tech_engine.add_all_indicators(df_full)
    df_full = analyzer.flow_analyzer.calculate_position(df_full)
    df_full['smart_net_12d'] = (
        df_full['foreign_net_val'].rolling(12).sum() +
        df_full['prop_net_val'].rolling(12).sum() +
        df_full['local_inst_net_val'].rolling(12).sum()
    ) / 1e9

    signals = []
    for i in range(100, len(df_full)-40):  # Đảm bảo có đủ dữ liệu forward
        row = df_full.iloc[i]
        prev_row = df_full.iloc[i-1]
        date = row['time'].date()

        # Điều kiện chung
        if (row['volume'] < cfg.MIN_AVG_VOLUME * 0.8 or 
            row['close'] < cfg.MIN_PRICE or
            row.get('rs_rating', 0) < cfg.RS_RATING_MIN):
            continue

        # === NHÓM A: Breakout + Smart + Vol ===
        if (row['close'] > row['EMA_20'] and
            row['VOL_SPIKE'] and
            row['smart_net_12d'] > cfg.A_SMART_NET_12D_BILL and
            row['score_tech'] >= cfg.A_TECH_SCORE_MIN and
            cfg.A_FOREIGN_LOCAL_INST_BOTH_BUY and
            row['foreign_net_val'] > 0 and
            row['local_inst_net_val'] > 0):
            signals.append((date, "A_BREAKOUT"))

        # === NHÓM B: Pullback ===
        elif (row['EMA_20'] > row['EMA_50'] and
              row['ADX'] > cfg.B_ADX_MIN and
              abs((row['close'] - row['EMA_20']) / row['close']) <= cfg.B_PRICE_DISTANCE_EMA20 and
              row['score_flow'] >= cfg.B_FLOW_SCORE_MIN):
            signals.append((date, "B_PULLBACK"))

        # === NHÓM C: Accumulation ===
        elif (len(df_full) > i+60):
            recent60 = df_full.iloc[i-60:i]
            vola = (recent60['high'].max() - recent60['low'].min()) / recent60['low'].min()
            smart60 = recent60['foreign_net_val'].sum() + recent60['local_inst_net_val'].sum() + recent60['prop_net_val'].sum()
            if (vola < cfg.C_ACCUMULATION_VOLATILITY_MAX and
                smart60 > 0 and
                row['score_val'] >= cfg.C_VALUATION_SCORE_MIN):
                signals.append((date, "C_ACCUMULATION"))

    results = []
    for sig_date, sig_type in signals:
        rets = calculate_forward_returns(df_full, pd.Timestamp(sig_date))
        rets['signal_type'] = sig_type
        rets['signal_date'] = sig_date
        results.append(rets)
    
    return pd.DataFrame(results) if results else pd.DataFrame()