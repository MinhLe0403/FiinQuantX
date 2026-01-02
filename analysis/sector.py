# analysis/sector.py

import pandas as pd
from sqlalchemy import text

class SectorAnalysis:
    def __init__(self, db_engine):
        self.engine = db_engine

    def get_sector_ranking(self, limit_days=10):
        """
        Xếp hạng toàn bộ nhóm ngành dựa trên:
        1. Hiệu suất tăng giá (Gia quyền theo thanh khoản)
        2. Tổng dòng tiền (GTGD)
        3. Dòng tiền khối ngoại (Foreign Net Val)
        """
        query = text(f"""
            WITH recent_data AS (
                SELECT 
                    d.sector, f.symbol, f.time, 
                    f.close, 
                    LAG(f.close, 1) OVER (PARTITION BY f.symbol ORDER BY f.time) as prev_close,
                    f.trading_value,
                    COALESCE(i.foreign_net_val, 0) as foreign_net_val
                FROM fact_daily_bars f
                JOIN dim_stocks d ON f.symbol = d.symbol
                LEFT JOIN fact_investor_flows_daily i ON f.time = i.time AND f.symbol = i.symbol
                WHERE d.sector IS NOT NULL AND d.sector <> '' 
                AND d.type = 'STOCK'
                AND f.time >= CURRENT_DATE - INTERVAL '14 days'
            ),
            daily_calc AS (
                SELECT 
                    sector, symbol, time, trading_value, foreign_net_val,
                    (close - prev_close)/prev_close as pct_change
                FROM recent_data
                WHERE prev_close > 0
                AND time = (SELECT MAX(time) FROM fact_daily_bars) -- Lấy ngày mới nhất
            ),
            sector_agg AS (
                SELECT 
                    sector,
                    COUNT(symbol) as stock_count,
                    SUM(trading_value) as total_value,
                    SUM(foreign_net_val) as foreign_flow,
                    
                    -- Weighted Return: (Mã to ảnh hưởng nhiều hơn mã nhỏ)
                    SUM(pct_change * trading_value) / NULLIF(SUM(trading_value), 0) * 100 as weighted_change,
                    
                    -- Độ rộng ngành
                    SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) as adv,
                    SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) as dec
                FROM daily_calc
                GROUP BY sector
            )
            SELECT *,
                -- Scoring đơn giản để ranking (60% Giá + 40% Tiền)
                (RANK() OVER (ORDER BY weighted_change ASC)) * 0.6 + 
                (RANK() OVER (ORDER BY total_value ASC)) * 0.4 as composite_score
            FROM sector_agg
            ORDER BY weighted_change DESC
        """)
        
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            print(f"Sector Analysis Error: {e}")
            return pd.DataFrame()

    def get_top_stocks_in_sector(self, sector_name):
        """Lấy các cổ phiếu mạnh nhất trong 1 ngành cụ thể"""
        query = text("""
            SELECT f.symbol, f.close, f.trading_value
            FROM fact_daily_bars f
            JOIN dim_stocks d ON f.symbol = d.symbol
            WHERE d.sector = :sector
            AND f.time = (SELECT MAX(time) FROM fact_daily_bars)
            ORDER BY f.trading_value DESC
            LIMIT 5
        """)
        try:
            return pd.read_sql(query, self.engine, params={"sector": sector_name})
        except: return pd.DataFrame()