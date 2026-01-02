# analysis/market.py

import pandas as pd
import numpy as np
from sqlalchemy import text

class MarketEngine:
    def __init__(self, db_engine):
        self.engine = db_engine

    def get_index_series(self, symbol="VNINDEX", limit=365):
        """Lấy dữ liệu lịch sử của Index (VNINDEX, VN30, HNX...)"""
        # --- FIX LỖI Ở ĐÂY: đổi 'value' thành 'trading_value' ---
        query = text("""
            SELECT time, close, volume, trading_value as value
            FROM fact_daily_bars 
            WHERE symbol = :symbol
            ORDER BY time ASC
        """)
        try:
            df = pd.read_sql(query, self.engine, params={"symbol": symbol})
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'])
                # Tính % thay đổi hàng ngày
                df['change_percent'] = df['close'].pct_change()
            return df.tail(limit)
        except Exception as e:
            # Print lỗi ra nhưng không làm crash app, trả về empty df
            print(f"Market Engine Error (get_index_series): {e}")
            return pd.DataFrame()

    def get_sector_performance(self, limit=20):
        """
        Tính toán hiệu suất các Ngành
        """
        # Lưu ý: Cần chắc chắn bảng fact_daily_bars của bạn đã có dữ liệu và dim_stocks đã phân ngành
        query = text("""
            WITH last_dates AS (
                SELECT DISTINCT time 
                FROM fact_daily_bars 
                ORDER BY time DESC 
                LIMIT 2 -- Lấy 2 ngày giao dịch gần nhất
            ),
            target_data AS (
                SELECT 
                    f.symbol, d.sector, f.close, f.time,
                    LAG(f.close, 1) OVER (PARTITION BY f.symbol ORDER BY f.time) as prev_close
                FROM fact_daily_bars f
                JOIN dim_stocks d ON f.symbol = d.symbol
                WHERE f.time IN (SELECT time FROM last_dates)
                AND d.type = 'STOCK' AND d.sector IS NOT NULL
            ),
            daily_change AS (
                SELECT 
                    symbol, sector, time,
                    (close - prev_close) / prev_close as pct_change
                FROM target_data
                WHERE prev_close > 0
                AND time = (SELECT MAX(time) FROM last_dates)
            )
            SELECT 
                sector,
                COUNT(symbol) as stock_count,
                AVG(pct_change) * 100 as avg_change_pct,
                SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) as advance_count,
                SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) as decline_count
            FROM daily_change
            GROUP BY sector
            ORDER BY avg_change_pct DESC
        """)
        
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            # Lỗi thường gặp: chưa có data sector hoặc cấu trúc bảng chưa sync
            print(f"Market Engine Error (get_sector_performance): {e}")
            return pd.DataFrame()

    def calculate_rs_rating(self, stock_df, market_df):
        """
        Tính RS Rating (Relative Strength)
        """
        if stock_df.empty or market_df.empty or len(stock_df) < 20:
            return 0  # Not enough data
            
        try:
            # Chuẩn hóa index
            s_close = stock_df.set_index('time')['close'].sort_index().rename("stock_close")
            m_close = market_df.set_index('time')['close'].sort_index().rename("market_close")
            
            # Merge để đảm bảo cùng khung thời gian (xử lý ngày nghỉ lễ)
            df = pd.concat([s_close, m_close], axis=1).dropna()
            
            if len(df) < 50: return 0

            # Lấy window: 12 tháng (hoặc max dữ liệu có được)
            window = min(len(df) - 1, 250)
            
            # Hiệu suất Stock
            s_end = df['stock_close'].iloc[-1]
            s_start = df['stock_close'].iloc[-window]
            s_perf = (s_end - s_start) / s_start

            # Hiệu suất Market
            m_end = df['market_close'].iloc[-1]
            m_start = df['market_close'].iloc[-window]
            m_perf = (m_end - m_start) / m_start
            
            # Tính RS Relative (Đơn giản)
            rs_relative = (s_perf - m_perf) * 100
            
            return round(rs_relative, 2)
        except Exception as e:
            # print(f"RS Calc Error: {e}")
            return 0