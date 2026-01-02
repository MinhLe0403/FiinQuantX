# analysis/backtester.py
import pandas as pd
import numpy as np

class SignalBacktester:
    def __init__(self, recommender_engine):
        self.recommender = recommender_engine

    def check_signal_at_row(self, row, health_scores):
        """
        Tách logic kiểm tra tín hiệu ra để chạy nhanh hơn (Vector hóa logic).
        Logic này PHẢI khớp với recommendation.py.
        """
        c = row['close']
        ema20 = row.get('EMA_20', 0)
        ema50 = row.get('EMA_50', 0)
        vol_spike = row.get('VOL_SPIKE', False)
        
        # Lấy điểm số giả định (đã tính sẵn ở core)
        s_flow = row.get('score_flow', 0)
        s_tech = row.get('score_tech', 0)
        
        # 1. BREAKOUT
        if (c > ema20) and vol_spike and (s_flow >= 5.0 or s_tech >= 6.0):
            return "BREAKOUT"
            
        # 2. PULLBACK
        dist = (c - ema20) / c if c > 0 else 0
        has_trend = row.get('ADX', 0) > 18
        if (ema20 > ema50) and has_trend and (-0.025 <= dist <= 0.04) and (row.get('RSI_14', 50) < 70):
             return "PULLBACK"
             
        # 3. EARLY TREND
        vol_strong = row['volume'] > row.get('VOL_SMA_20', 1) * 1.1
        if (c > ema20) and (ema20 >= ema50 * 0.99) and vol_strong and s_flow >= 4.0:
            return "EARLY TREND"
            
        return None

    def scan_recent_30_days(self, df_scored):
        """
        Quét 30 ngày gần nhất của 1 mã.
        Trả về danh sách các tín hiệu đã phát ra.
        """
        signals_found = []
        if df_scored.empty or len(df_scored) < 35: return []

        # Chỉ quét 30 phiên cuối
        lookback_window = df_scored.iloc[-30:]
        
        for idx, row in lookback_window.iterrows():
            # Kiểm tra xem ngày này có tín hiệu không
            strategy = self.check_signal_at_row(row, None)
            
            if strategy:
                # Tính hiệu suất thực tế từ ngày đó đến nay (T+Current)
                # Lưu ý: idx là index của ngày phát tín hiệu (T0)
                # Giá mua = Close T0 (giả định)
                buy_price = row['close']
                
                # Lấy dữ liệu từ T+1 đến hiện tại
                # loc[idx:] bao gồm cả idx, ta cần dữ liệu sau đó
                future_data = df_scored.loc[idx+1:] 
                
                if future_data.empty:
                    current_pnl = 0.0
                    days_held = 0
                else:
                    current_price = future_data.iloc[-1]['close']
                    current_pnl = (current_price - buy_price) / buy_price
                    days_held = len(future_data)

                signals_found.append({
                    "date": row['time'],
                    "symbol": row['symbol'],
                    "strategy": strategy,
                    "buy_price": buy_price,
                    "current_price": row['close'] if future_data.empty else future_data.iloc[-1]['close'],
                    "pnl_pct": current_pnl,
                    "days_held": days_held,
                    "row_idx": idx # Để dùng cho Deep Backtest
                })
        
        return signals_found

    def deep_backtest_strategy(self, df_full, strategy_name):
        """
        Kiểm tra thống kê lịch sử của strategy này trên mã này (Quy tắc T+2 -> T+30)
        """
        history_signals = []
        
        # Quét toàn bộ lịch sử (trừ 30 ngày cuối để tránh trùng lặp report)
        search_range = df_full.iloc[:-30]
        
        for idx, row in search_range.iterrows():
            if self.check_signal_at_row(row, None) == strategy_name:
                history_signals.append(idx)
        
        if not history_signals: return None
        
        # Tính toán thống kê (Reuse logic cũ)
        results = []
        horizon = 30
        t_plus_start = 2 # T+2
        
        for idx in history_signals:
            if idx + horizon + t_plus_start >= len(df_full): continue
            
            entry_price = df_full.iloc[idx]['close']
            
            # Cửa sổ T+2 -> T+30
            window = df_full.iloc[idx + t_plus_start : idx + t_plus_start + horizon]
            if window.empty: continue
            
            max_price = window['high'].max()
            end_price = window.iloc[-1]['close']
            
            max_return = (max_price - entry_price) / entry_price
            end_return = (end_price - entry_price) / entry_price
            
            results.append(max_return)

        if not results: return None
        
        res_series = pd.Series(results)
        return {
            "sample_size": len(results),
            "win_rate": (res_series > 0.05).mean() * 100, # % số lần lãi > 5%
            "avg_max_return": res_series.mean(),
            "best_return": res_series.max()
        }