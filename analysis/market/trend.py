"""
Module này dùng để tính trend kỹ thuật của index
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from analysis.technical import TechnicalEngine

class TrendModule:
    def __init__(self, db_engine):
        self.engine = db_engine
        self.tech = TechnicalEngine()

    def get_market_regime(self, symbol="VNINDEX"):
        """Tính toán Xu hướng, Regime, Ngày phân phối"""
        query = text("""
            SELECT time, open, high, low, close, volume, trading_value as value
            FROM fact_daily_bars WHERE symbol = :symbol ORDER BY time ASC
        """)
        try:
            df = pd.read_sql(query, self.engine, params={"symbol": symbol})
            if len(df) < 250: return None
            
            # Indicators
            df['SMA_50'] = df['close'].rolling(50).mean()
            df['SMA_200'] = df['close'].rolling(200).mean()
            df['VOL_SMA_20'] = df['volume'].rolling(20).mean()
            # Technical Engine (ADX, ATR...)
            df = self.tech.add_all_indicators(df)
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            c = last['close']
            
            # 1. Market Regime & Trend
            e20 = last.get('EMA_20', last['close'])
            e50 = last.get('EMA_50', last['SMA_50'])
            adx = last.get('ADX', 0)
            
            is_long_uptrend = c > last['SMA_200']
            regime_label = "SIDEWAY"
            regime_color = "#FFD700"
            regime_score = 50
            
            if c > e20 and e20 > e50:
                if adx > 25:
                    regime_label = "UPTREND MẠNH"
                    regime_color = "#00CC96"
                    regime_score = 90
                else:
                    regime_label = "UPTREND YẾU"
                    regime_color = "#90EE90"
                    regime_score = 75
            elif c < e20 and e20 < e50:
                regime_label = "DOWNTREND"
                regime_color = "#EF553B"
                regime_score = 30
            
            # 2. Distribution Days (Logic O'Neil chuẩn)
            pct_chg = df['close'].pct_change()
            dist_mask = (
                (pct_chg < -0.002) & 
                (df['volume'] > df['VOL_SMA_20']) & 
                (df['close'] < df['open'])
            )
            dist_days = int(dist_mask.tail(25).sum())
            
            # Volatility Description
            atr_pct = (last.get('ATR_20', c*0.01) / c) * 100
            regime_desc = f"ATR: {atr_pct:.1f}%"

            return {
                "symbol": symbol,
                "close": c,
                "change_pct": (c - prev['close']) / prev['close'] * 100,
                "volume": last['volume'],
                "avg_volume": last['VOL_SMA_20'],
                "vol_str": f"{last['volume']/1000000:.1f}M",
                "regime": regime_label,
                "regime_color": regime_color,
                "regime_desc": regime_desc,
                "health_score": regime_score,
                "color": regime_color, # Legacy support
                "dist_days": dist_days,
                # Metadata để dùng ở module khác nếu cần
                "adx": adx,
                "is_bull_long": is_long_uptrend
            }
        except Exception as e:
            print(f"[TrendModule] Error: {e}")
            return None