import pandas as pd
from sqlalchemy import text

class BreadthModule:
    def __init__(self, db_engine):
        self.engine = db_engine

    def get_advanced_breadth(self):
        """Tính % mã trên MA20, MA50, New Highs"""
        query = text("""
            WITH recent_price AS (
                SELECT symbol, time, close,
                    AVG(close) OVER (PARTITION BY symbol ORDER BY time ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma50,
                    AVG(close) OVER (PARTITION BY symbol ORDER BY time ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma200,
                    MAX(close) OVER (PARTITION BY symbol ORDER BY time ROWS BETWEEN 250 PRECEDING AND CURRENT ROW) as high52w
                FROM fact_daily_bars
                WHERE time >= CURRENT_DATE - INTERVAL '1 year'
            ),
            latest AS (SELECT * FROM recent_price WHERE time = (SELECT MAX(time) FROM fact_daily_bars))
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN close > sma50 THEN 1 ELSE 0 END) as above50,
                SUM(CASE WHEN close > sma200 THEN 1 ELSE 0 END) as above200,
                SUM(CASE WHEN close >= high52w * 0.98 THEN 1 ELSE 0 END) as new_high
            FROM latest
        """)
        try:
            df = pd.read_sql(query, self.engine)
            if df.empty: return {}
            r = df.iloc[0]
            tot = r['total'] if r['total'] > 0 else 1
            return {
                "pct_above_sma50": round(r['above50']/tot*100, 1),
                "pct_above_sma200": round(r['above200']/tot*100, 1),
                "near_high_52w": r['new_high']
            }
        except: return {}

    def get_market_breadth_basic(self):
        """Đếm Xanh/Đỏ/Vàng phiên gần nhất"""
        # (Logic SQL cũ đếm status)
        query = text("""
            WITH last_day AS (SELECT MAX(time) as t FROM fact_daily_bars)
            SELECT CASE WHEN close > open THEN 'Tang' WHEN close < open THEN 'Giam' ELSE 'ThamChieu' END as s,
            COUNT(*) as c FROM fact_daily_bars WHERE time = (SELECT t FROM last_day) GROUP BY 1
        """)
        try:
            df = pd.read_sql(query, self.engine)
            res = df.set_index('s')['c'].to_dict()
            return {"green": res.get('Tang', 0), "red": res.get('Giam', 0), "yellow": res.get('ThamChieu', 0)}
        except: return {}