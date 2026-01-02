import pandas as pd
from analysis.core import StockAnalyzer

class StockController:
    def __init__(self):
        self.model = StockAnalyzer()

    def analyze_ticker(self, symbol, days_lookback=60):
        """Xử lý toàn bộ logic phân tích cổ phiếu và đóng gói ViewModel"""
        
        # 1. Fetch & Analyze (Model)
        health = self.model.analyze_health(symbol)
        
        # 2. Xử lý lỗi
        if "error" in health:
            return {"error": health["error"]}

        # 3. Chuẩn bị dữ liệu hiển thị (Format & Color Logic)
        
        # Header Info
        last_row = health.get('full_df').iloc[-1] if health.get('full_df') is not None else {}
        price = health['close']
        prev_close = health['full_df'].iloc[-2]['close'] if len(health['full_df']) > 1 else price
        pct_change = (price - prev_close) / prev_close * 100
        
        # Recommend Color
        rec = health['recommendation']
        rec_color = "green" if "MUA" in rec else "red" if "BÁN" in rec else "orange"
        
        # Score Color
        sc = health['total_score']
        score_color = "#00CC96" if sc >= 7 else "#EF553B" if sc < 5 else "#FFD700" # Xanh/Đỏ/Vàng

        # 5 Pillars
        scores = health.get('scores', {})
        pillars = [
            {"label": "Kỹ thuật", "key": "technical", "val": scores.get('technical',0), "color": "#3366CC", "w": 0.25},
            {"label": "Dòng tiền", "key": "flow", "val": scores.get('flow',0), "color": "#00FF00", "w": 0.35},
            {"label": "Cơ bản", "key": "fundamental", "val": scores.get('fundamental',0), "color": "#FF8C00", "w": 0.20},
            {"label": "Định giá", "key": "valuation", "val": scores.get('valuation',0), "color": "#9932CC", "w": 0.15},
            {"label": "Rủi ro", "key": "risk", "val": scores.get('risk',0), "color": "#FF4444", "w": 0.0}
        ]
        
        # Trade Plan Format
        plan_raw = health.get('trade_plan', {})
        trade_plan = {
            "has_plan": bool(plan_raw),
            "trading": self._fmt_plan(plan_raw.get('trading',{}), "Trading"),
            "investing": self._fmt_plan(plan_raw.get('investing',{}), "Investing"),
            "key_levels": plan_raw.get('key_levels', {})
        }

        # --- FIX: Lấy ngày từ cột 'time' an toàn hơn ---
        # last_row là pd.Series
        time_val = last_row.get('time')
        if pd.notnull(time_val):
            # Nếu đã là datetime object
            if hasattr(time_val, 'strftime'):
                date_str = time_val.strftime('%d/%m/%Y')
            # Nếu là string (ít khi xảy ra nếu db trả về chuẩn)
            else:
                date_str = str(time_val)
        else:
            date_str = '-'
        # ------------------------------------------------

        # 4. Return ViewModel Dictionary
        return {
            "symbol": symbol,
            "date_str": date_str, 
            "price_fmt": f"{price:,.0f}",
            "change_pct": pct_change,
            "rec": rec, "rec_color": rec_color,
            "score": sc, "score_color": score_color,
            
            # Metrics Row
            "metrics": {
                "pe": health.get('financials', {}).get('pe', 0),
                "smart_money": health.get('smart_net_billion_10d', 0),
                "participation": health.get('smart_participation', 0),
                "rs_rating": health.get('rs_rating', 0),
                "atr": last_row.get('ATRr_14', 0) / price * 100 if price > 0 else 0
            },
            
            # Cards
            "pillars": pillars,
            
            # Insights
            "insights": {
                "pros": health['details'].get('technical', []) + health['details'].get('flow', []) + health['details'].get('fundamental', []),
                "cons": health['details'].get('warning', [])
            },
            
            "trade_plan": trade_plan,
            
            # Raw Data cho Tabs
            "chart_df": health.get('full_df'),
            "hist_scores": health.get('history_scores'),
            "fund_data": {
                "raw": health.get('financials', {}),
                "metrics": health.get('fund_metrics', {}),
                "type": health.get('business_type', 'Unknown')
            },
            "flow_dna": health.get('flow_dna', {})
        }

    def _fmt_plan(self, p, mode):
        act = p.get('action', 'QUAN SÁT')
        color = "green" if "MUA" in act else "red" if "BÁN" in act else "gray"
        if mode == "Investing" and "MUA" in act: color = "orange"
        
        return {
            "action": act, "color": color, "reason": p.get('reason', ''),
            "entry": p.get('entry_zone') or p.get('buy_under', '-'),
            "target": p.get('target', '-'), "stop": p.get('stop_loss', '-')
        }