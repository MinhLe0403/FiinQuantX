# controllers/market_controller.py
from analysis.market_trend import MarketTrendAnalysis
from analysis.sector import SectorAnalysis

class MarketController:
    def __init__(self, db_engine):
        # Khởi tạo Model
        self.market_model = MarketTrendAnalysis(db_engine)
        self.sector_model = SectorAnalysis(db_engine)

    def get_market_summary_data(self, indices=["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]):
        """
        Chuẩn bị dữ liệu cho Market Matrix (4 ô trên cùng)
        """
        result = []
        for symbol in indices:
            raw_data = self.market_model.analyze_index_pro(symbol)
            if not raw_data:
                continue
            
            # --- LOGIC XỬ LÝ GIAO DIỆN (Logic chuyển từ Model sang View) ---
            
            # 1. Map màu Xu hướng
            trend_map = {
                "UPTREND MẠNH": "#00CC96", # Green
                "UPTREND YẾU": "#90EE90",  # Light Green
                "DOWNTREND MẠNH": "#EF553B", # Red
                "DOWNTREND (Dò đáy)": "#FF4444", # Red
                "SIDEWAY": "#FFA15A"       # Orange
            }
            # Mặc định vàng nếu không khớp
            regime_color = next((v for k, v in trend_map.items() if k in raw_data['regime']), "#FFD700")

            # 2. Xử lý logic cảnh báo phân phối
            dist_d = raw_data['dist_days']
            dist_color = "#FF4B4B" if dist_d >= 4 else "#00CC96"
            dist_warning = dist_d >= 4 # Boolean cho View biết có hiện cảnh báo hay ko

            # 3. Format Dữ liệu hiển thị
            vol_pct = (raw_data['volume'] / raw_data['avg_volume']) * 100
            
            # Đóng gói dữ liệu sạch (ViewModel)
            view_item = {
                "symbol": symbol,
                "price": f"{raw_data['close']:,.2f}",
                "change_pct": raw_data['change_pct'],
                "change_fmt": f"{raw_data['change_pct']:+.2f}%",
                "is_positive": raw_data['change_pct'] >= 0,
                
                "regime_text": raw_data['regime'],
                "regime_color": regime_color,
                
                "vol_str": raw_data['vol_str'],
                "vol_pct_str": f"{vol_pct:.0f}%",
                
                "score": raw_data['health_score'],
                
                "dist_days": dist_d,
                "dist_color": dist_color,
                "is_dist_warning": dist_warning
            }
            result.append(view_item)
            
        return result

    def get_deep_dive_data(self, benchmark="VNINDEX"):
        """Chuẩn bị dữ liệu cho phần Biểu đồ chi tiết bên dưới"""
        # Gọi Model
        mk_main = self.market_model.analyze_index_pro(benchmark)
        breadth_real = self.market_model.get_market_breadth()
        rotation = self.market_model.get_cashflow_rotation()
        sectors = self.sector_model.get_sector_ranking(limit_days=5)
        
        # Đóng gói
        return {
            "breadth_stats": mk_main.get('breadth', {}) if mk_main else {},
            "breadth_real": breadth_real,
            "rotation": rotation,
            "sectors": sectors
        }
    
    def get_quant_lab_data(self, benchmark="VNINDEX"):
        """Lấy dữ liệu Quant"""
        return self.market_model.get_quant_metrics(benchmark)
    
        # --- THÊM HÀM MỚI NÀY VÀO CLASS MarketController ---
    def get_mfe_data(self, benchmark="VNINDEX"):
        """
        Lấy dữ liệu Market Flow Engine (MFE) và chuẩn hóa cho View
        """
        # Gọi Facade -> gọi LiquidityModule
        mfe_raw = self.market_model.analyze_market_flow_pro(benchmark)
        
        if not mfe_raw:
            return None
            
        score = mfe_raw['mfe_score']
        
        # Logic giao diện (View Logic)
        # Xác định màu sắc và nhãn trạng thái dựa trên điểm số
        if score >= 70:
            color = "#00CC96" # Xanh
            status_text = "TIỀN VÀO MẠNH"
        elif score <= 40:
            color = "#EF553B" # Đỏ
            status_text = "TIỀN RÚT / YẾU"
        else:
            color = "#FFD700" # Vàng
            status_text = "TRUNG TÍNH"
            
        # Kiểm tra FSI để tạo Alert text
        fsi_val = mfe_raw['raw']['fsi_val']
        fsi_alert = None
        if fsi_val > 2.0:
            fsi_alert = f"💡 Đột biến: {mfe_raw['raw']['fsi_label']} (Z={fsi_val:.1f})"
        elif fsi_val < -2.0:
            fsi_alert = f"⚠️ Cảnh báo: {mfe_raw['raw']['fsi_label']} (Z={fsi_val:.1f})"

        # Đóng gói dữ liệu cho View
        return {
            "score": score,
            "color": color,
            "status": status_text,
            "fsi_alert": fsi_alert,
            "components": mfe_raw['components'] # smf, fsi, div, fragility
        }
    
    def get_quant_lab_data(self, benchmark="VNINDEX"):
        """Lấy dữ liệu Quant theo Benchmark chỉ định"""
        # Chuyển tiếp benchmark xuống Model
        return self.market_model.get_quant_metrics(benchmark)
    
    def get_market_summary_data(self, indices=["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]):
        result = []
        for symbol in indices:
            raw_data = self.market_model.analyze_index_pro(symbol)
            if not raw_data: continue
            
            # --- LOGIC MỚI: TẠO KHUYẾN NGHỊ HÀNH ĐỘNG ---
            score = raw_data['health_score']
            trend = raw_data['regime']
            dist_d = raw_data['dist_days']
            
            action_text = "QUAN SÁT"
            action_color = "gray"
            
            # Quy tắc khuyến nghị đơn giản
            if dist_d >= 4:
                action_text = "HẠ TỶ TRỌNG / PHÒNG THỦ"
                action_color = "#FF4444" # Đỏ
            elif score >= 80:
                action_text = "MUA MẠNH / MARGIN OK"
                action_color = "#00CC96" # Xanh
            elif score >= 60 and "UPTREND" in trend:
                action_text = "CANH MUA (BUY DIP)"
                action_color = "#90EE90" # Xanh nhạt
            elif "DOWNTREND" in trend:
                action_text = "ĐỨNG NGOÀI / BÁN HỒI"
                action_color = "#EF553B"
            else:
                action_text = "GIAO DỊCH CHỌN LỌC"
                action_color = "#FFA15A"

            # --- Logic màu sắc Trend ---
            trend_map = {
                "UPTREND MẠNH": "#00CC96", "UPTREND YẾU": "#90EE90",
                "DOWNTREND MẠNH": "#EF553B", "DOWNTREND": "#FF4444", "SIDEWAY": "#FFA15A"
            }
            regime_color = next((v for k, v in trend_map.items() if k in trend), "#FFD700")

            # --- Đóng gói dữ liệu ---
            view_item = {
                "symbol": symbol,
                "price": f"{raw_data['close']:,.2f}",
                "change_fmt": f"{raw_data['change_pct']:+.2f}%",
                "vol_str": f"{raw_data['vol_str']} ({raw_data['volume']/raw_data['avg_volume']*100:.0f}% TB)",
                
                "regime_text": raw_data['regime'],
                "regime_color": regime_color,
                "score": raw_data['health_score'],
                "dist_days": dist_d,
                "dist_warning": dist_d >= 4,
                
                # Field Mới
                "action": action_text,
                "action_color": action_color
            }
            result.append(view_item)
            
        return result