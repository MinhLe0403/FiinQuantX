# analysis/recommendation.py
import pandas as pd
import numpy as np
from analysis.fundamental import FundamentalAnalysis 

class RecommenderEngine:
    def __init__(self):
        self.fund_checker = FundamentalAnalysis()

    def _find_key_levels(self, row, price):
        """Tìm hỗ trợ và kháng cự động dựa trên MA và BB"""
        levels_s = []
        levels_r = []
        
        # Support
        if row.get('LOW_20D', 0) > 0: levels_s.append(('Đáy 20P', row['LOW_20D']))
        if row.get('EMA_20', 0) > 0: levels_s.append(('EMA20', row['EMA_20']))
        if row.get('ICHI_KIJUN', 0) > 0: levels_s.append(('Kijun', row['ICHI_KIJUN']))
        if row.get('BB_LOWER', 0) > 0: levels_s.append(('BB_Low', row['BB_LOWER']))
        
        # Filter & Sort
        supports = sorted([l for l in levels_s if l[1] < price], key=lambda x: x[1], reverse=True)[:3]
        
        # Resistance (Logic cũ)
        if row.get('BB_UPPER', 0) > 0: levels_r.append(('BB High', row['BB_UPPER']))
        resistances = sorted([l for l in levels_r if l[1] > price], key=lambda x: x[1])[:3]
        
        return supports, resistances

# Trong class RecommenderEngine ...

    # Thêm dòng này vào đầu hàm generate_plan()
    def generate_plan(self, df_history, health_snapshot):
        if df_history.empty: 
            return {"trading": {"action": "QUAN SÁT"}, "investing": {"action": "QUAN SÁT"}}

        last_row = df_history.iloc[-1]
        atr = last_row.get('ATRr_14', last_row['close'] * 0.025)

        plan_trading = self._build_trading_plan(last_row, health_snapshot, atr)
        plan_investing = self._build_investing_plan(last_row, health_snapshot, atr)

        # ĐẢM BẢO LUÔN CÓ ACTION
        plan_trading.setdefault("action", "QUAN SÁT")
        plan_investing.setdefault("action", "QUAN SÁT")

        supports, resistances = self._find_key_levels(last_row, last_row['close'])

        return {
            "key_levels": {"supports": supports, "resistances": resistances},
            "trading": plan_trading,
            "investing": plan_investing
        }

    def _build_trading_plan(self, row, health, atr):
        """Logic Trading Tối ưu v2: Aggressive hơn, Bắt trend sớm (Early Trend)"""
        scores = health.get('scores', {})
        s_flow = scores.get('flow', 0)
        s_tech = scores.get('technical', 0)
        
        c = row['close']
        ema20 = row.get('EMA_20', 0)
        ema50 = row.get('EMA_50', 0)
        
        # --- BIẾN MẶC ĐỊNH (DEFAULT VALUES) ---
        action = "QUAN SÁT"
        reason = "Chưa có tín hiệu rõ ràng."
        strategy = ""
        entry_zone = "-"
        
        # Biến điều kiện
        is_uptrend_strong = row.get('TREND_STRONG', False)
        vol_spike = row.get('VOL_SPIKE', False)
        adx_val = row.get('ADX', 0)
        has_trend = adx_val > 18  
        
        vol_avg = row.get('VOL_SMA_20', 1)
        vol_strong = row['volume'] > vol_avg * 1.1
        
        # 1. BỘ LỌC SƠ CẤP (Early Exit)
        if s_tech < 4.0 and s_flow < 4.0 and not vol_spike:
            return {
                "action": "QUAN SÁT",
                "reason": "Cấu trúc giá và Dòng tiền đều yếu.",
                "entry_zone": "-", "stop_loss": "-", "target": "-"
            }

        # 2. XÁC ĐỊNH CHIẾN LƯỢC
        
        # --- STRATEGY 1: BREAKOUT ---
        if (c > ema20) and vol_spike and (s_flow >= 5.0 or s_tech >= 6.0):
            strategy = "BREAKOUT"
            action = "MUA GIA TĂNG"
            entry_zone = f"{c:,.0f} (MP)"
            reasons = ["Vol nổ mạnh"]
            if s_flow >= 6.0: reasons.append("Dòng tiền quyết liệt")
            elif s_tech >= 6.0: reasons.append("Tech đồng thuận")
            else: reasons.append("Giá vượt nền")
            reason = " + ".join(reasons)
            
        # --- STRATEGY 2: PULLBACK ---
        elif (ema20 > ema50) and has_trend:
            dist = (c - ema20) / c
            if -0.025 <= dist <= 0.04:
                if row.get('RSI_14', 50) < 70:
                    strategy = "PULLBACK"
                    action = "CANH MUA"
                    low_zone = ema20 * 0.98
                    high_zone = max(c, ema20 * 1.02)
                    entry_zone = f"{low_zone:,.0f} - {high_zone:,.0f}"
                    reason = f"Trend tăng (ADX={adx_val:.0f}), giá chỉnh về hỗ trợ."
            elif dist > 0.04:
                return {"action": "CHỜ CHỈNH", "reason": f"Giá đã chạy xa nền (+{dist*100:.1f}%), rủi ro.", "entry_zone": "-", "stop_loss": "-", "target": "-"}

        # --- STRATEGY 3: EARLY TREND ---
        elif (c > ema20) and (ema20 >= ema50 * 0.99) and vol_strong and s_flow >= 4.0:
            strategy = "EARLY TREND"
            action = "MUA THĂM DÒ"
            entry_zone = f"{c:,.0f}"
            reason = "Dấu hiệu chớm tăng: Vol tốt, Flow ổn định."
            
        # --- NẾU KHÔNG THỎA MÃN GÌ CẢ ---
        if strategy == "":
            return {
                "action": "QUAN SÁT", 
                "reason": "Sideway hoặc Trend yếu, kiên nhẫn chờ.",
                "entry_zone": "-", "stop_loss": "-", "target": "-"
            }

        # 3. QUẢN TRỊ RỦI RO (RISK MANAGEMENT)
        hard_support = row.get('LOW_20D', c * 0.85)
        ema_sup = ema20 if strategy == "BREAKOUT" else ema50
        
        potential_sl = max(hard_support, ema_sup * 0.97)
        sl_price = min(potential_sl, c - 2*atr)
        
        # Kiểm tra SL Max
        loss_pct = (c - sl_price) / c
        max_loss = min(0.15, (3.5 * atr) / c) # Max 15%
        
        if loss_pct > max_loss:
             sl_price = c * (1 - max_loss) # Ép SL về ngưỡng an toàn tối đa
             
        target = c + (c - sl_price) * 2.5
        
        return {
            "action": f"{action} ({strategy})",
            "reason": reason,
            "entry_zone": entry_zone,
            "stop_loss": f"{sl_price:,.0f} (-{(c-sl_price)/c*100:.1f}%)",
            "target": f"{target:,.0f}"
        }

    def _build_investing_plan(self, row, health, atr):
        scores = health.get('scores', {})
        fin = health.get('financials', {})
        s_val = scores.get('valuation', 0)
        c = row['close']
        
        # 1. SÀNG LỌC SỨC KHỎE TÀI CHÍNH (Tránh Value Trap)
        is_healthy, msg = self.fund_checker.check_financial_health(fin)
        
        if not is_healthy:
            return {
                "action": "KHÔNG KHUYẾN NGHỊ",
                "reason": f"Rủi ro Tài chính: {msg}",
                "buy_under": "-"
            }

        # 2. LOGIC TÍCH SẢN
        # Đk: Điểm định giá cao (>7 tức là Rẻ), Sức khỏe Tốt, Có dòng tiền tích lũy
        smart_score = scores.get('flow', 0)
        
        if s_val >= 7.5:
            action = "MUA TÍCH SẢN MẠNH"
            reason = "Định giá rất rẻ + Tài chính khỏe."
            # Mua under: Giá hiện tại + 5% biên độ
            buy_under = f"Dưới {c*1.05:,.0f}"
            
        elif s_val >= 6.0 and smart_score >= 6.0:
            action = "GOM DẦN"
            reason = "Định giá hợp lý và có Dòng tiền cá mập bảo kê."
            buy_under = f"Vùng {c:,.0f} - {c*0.95:,.0f}"
            
        else:
            action = "CHỜ ĐỊNH GIÁ TỐT HƠN"
            reason = "Doanh nghiệp tốt nhưng giá chưa đủ hấp dẫn."
            # Target Price cho P/E về 12 (VD)
            pe_curr = health.get('fund_metrics', {}).get('pe', 15)
            target_price = c * (12/pe_curr) if pe_curr > 0 else c*0.8
            buy_under = f"Chờ về {target_price:,.0f}"

        return {
            "action": action,
            "reason": reason,
            "buy_under": buy_under
        }