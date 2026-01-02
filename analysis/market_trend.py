# analysis/market_trend.py

from analysis.market.trend import TrendModule
from analysis.market.liquidity import LiquidityModule
from analysis.market.breadth import BreadthModule

class MarketTrendAnalysis:
    def __init__(self, db_engine):
        self.engine = db_engine
        
        # Các module con
        self.trend_mod = TrendModule(db_engine)
        self.flow_mod = LiquidityModule(db_engine)
        self.breadth_mod = BreadthModule(db_engine)

    def analyze_index_pro(self, symbol="VN30"):
        # (Lưu ý: trong hàm này có gọi self.flow_mod.get_cashflow_rotation(), chỗ đó ok)
        t_data = self.trend_mod.get_market_regime(symbol)
        if not t_data: return None
        
        breadth_adv = self.breadth_mod.get_advanced_breadth()
        rotation = self.flow_mod.get_cashflow_rotation() # <-- Dòng này chạy nội bộ OK
        
        return {
            **t_data,
            "breadth": breadth_adv,
            "rotation_data": rotation,
        }

    def get_quant_metrics(self, symbol="VNINDEX"):
        """Proxy: Chuyển tiếp sang LiquidityModule"""
        return self.flow_mod.get_quant_metrics(symbol)

    def get_market_breadth(self):
        """Proxy: Chuyển tiếp sang BreadthModule"""
        return self.breadth_mod.get_market_breadth_basic()

    # --- 👇 BỔ SUNG THÊM HÀM NÀY ĐỂ KHẮC PHỤC LỖI ---
    def get_cashflow_rotation(self):
        """Proxy: Chuyển tiếp yêu cầu lấy Rotation sang LiquidityModule"""
        return self.flow_mod.get_cashflow_rotation()
    
    def analyze_market_flow_pro(self, index_symbol="VNINDEX"):
        """Proxy: Chuyển tiếp sang LiquidityModule"""
        return self.flow_mod.analyze_market_flow_pro(index_symbol)