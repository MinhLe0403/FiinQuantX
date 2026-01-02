# analysis/fundamental.py
import pandas as pd
import numpy as np
import re
from decimal import Decimal

class FundamentalAnalysis:
    def __init__(self):
        pass

    def _safe_float(self, val):
        """Chuyển đổi an toàn Decimal, String, None sang float"""
        if val is None:
            return None
        
        try:
            # Xử lý string dạng "Decimal('0.0068')" nếu dữ liệu trả về raw text
            if isinstance(val, str) and 'Decimal' in val:
                val = val.replace("Decimal('", "").replace("')", "")
            
            return float(val)
        except:
            return None

    def _get_metric(self, fin_data, key, default=None):
        """Helper lấy giá trị từ dict financial"""
        if not fin_data: return default
        val = self._safe_float(fin_data.get(key))
        return val if val is not None else default

    def analyze(self, df_history, fin_data):
        """
        Main method: Phân loại doanh nghiệp và tính điểm
        Output: Dict chứa điểm số và tín hiệu
        """
        if df_history.empty or not fin_data:
            return {
                "score_fund": 0, "score_val": 0,
                "signals": [], "warnings": [],
                "type": "Unknown"
            }
        
        last_price_row = df_history.iloc[-1]
        
        # 1. NHẬN DIỆN LOẠI DOANH NGHIỆP
        # Bank thường có NIM và không có hàng tồn kho/gross margin kiểu sx
        nim = self._get_metric(fin_data, 'nim')
        bad_debt = self._get_metric(fin_data, 'bad_debt_ratio')
        
        is_financial = (nim is not None) or (bad_debt is not None)
        
        if is_financial:
            return self._analyze_financial(last_price_row, fin_data)
        else:
            return self._analyze_general(last_price_row, fin_data)

    def _analyze_financial(self, price_row, fin):
        """Logic chấm điểm cho NGÂN HÀNG / TÀI CHÍNH"""
        score_fund = 0.0
        score_val = 0.0
        signals = []
        warnings = []
        
        # --- A. CƠ BẢN (Tối đa 10đ) ---
        # 1. Tăng trưởng Tín dụng & Thu nhập (Growth) - Trọng số 3.0
        credit_growth = self._get_metric(fin, 'loans_growth_yoy', 0)
        income_growth = self._get_metric(fin, 'interest_income_growth_yoy', 0)
        
        if credit_growth > 0.14: score_fund += 1.5
        elif credit_growth > 0.10: score_fund += 1.0
        
        if income_growth > 0.15: score_fund += 1.5
        elif income_growth > 0.10: score_fund += 1.0
        
        if credit_growth > 0.20: signals.append(f"🚀 Tăng trưởng tín dụng thần tốc ({credit_growth*100:.1f}%)")

        # 2. Chất lượng tài sản (Asset Quality) - Trọng số 4.0
        # Ưu tiên Nợ xấu (NPL) và Bao phủ nợ xấu
        npl = self._get_metric(fin, 'bad_debt_ratio')
        cover_ratio = self._get_metric(fin, 'loan_loss_reserves_to_npls')
        
        if npl is not None:
            if npl < 0.015: score_fund += 2.0; signals.append("✅ Tỷ lệ nợ xấu thấp (Top Tier)")
            elif npl < 0.025: score_fund += 1.0
            elif npl > 0.035: warnings.append(f"⚠️ Nợ xấu mức báo động ({npl*100:.2f}%)"); score_fund -= 1.0
        
        if cover_ratio is not None:
            if cover_ratio > 1.2: score_fund += 2.0; signals.append("🛡️ Bộ đệm bao phủ nợ xấu rất dày")
            elif cover_ratio > 0.8: score_fund += 1.0
            elif cover_ratio < 0.5: warnings.append("⚠️ Bao phủ nợ xấu mỏng")

        # 3. Hiệu quả sinh lời (NIM/LDR) - Trọng số 3.0
        nim = self._get_metric(fin, 'nim', 0)
        if nim > 0.035: score_fund += 2.0
        elif nim > 0.03: score_fund += 1.0
        else:
             # Nếu NIM thấp (ví dụ Bank bán buôn), check CASA hoặc LDR (Optional)
             pass 

        # --- B. ĐỊNH GIÁ (Tối đa 10đ) ---
        # Bank chủ yếu dùng P/B
        pb = price_row.get('pb', 0)
        if pb > 0:
            if pb < 1.0: score_val += 10.0; signals.append(f"💰 P/B {pb:.1f} - Định giá RẺ dưới giá trị sổ sách")
            elif pb < 1.3: score_val += 8.0; signals.append(f"⚖️ P/B {pb:.1f} - Vùng giá hợp lý")
            elif pb < 1.8: score_val += 5.0
            elif pb > 2.5: score_val += 0.0; warnings.append(f"💸 P/B {pb:.1f} - Đắt so với lịch sử")
            else: score_val += 2.0
        
        return {
            "type": "Financial",
            "score_fund": min(score_fund, 10),
            "score_val": min(score_val, 10),
            "signals": signals,
            "warnings": warnings,
            "metrics": {
                "growth": credit_growth, "npl": npl, "pb": pb, "nim": nim
            }
        }

    def _analyze_general(self, price_row, fin):
        """Logic chấm điểm cho DOANH NGHIỆP SẢN XUẤT / THƯƠNG MẠI"""
        score_fund = 0.0
        score_val = 0.0
        signals = []
        warnings = []
        
        # --- A. CƠ BẢN (10đ) ---
        # 1. Hiệu quả sinh lời (ROE/ROIC/Margin) - Trọng số 4.0
        roe = self._get_metric(fin, 'roe', 0)
        roic = self._get_metric(fin, 'roic', 0)
        ebit_margin = self._get_metric(fin, 'ebit_margin', 0)
        
        if roe > 0.20: score_fund += 2.5; signals.append(f"🔥 ROE rất cao ({roe*100:.1f}%)")
        elif roe > 0.15: score_fund += 1.5
        
        if ebit_margin > 0.15: score_fund += 1.5
        
        # 2. Sức khỏe tài chính (Debt/Equity) - Trọng số 3.0
        de = self._get_metric(fin, 'debt_to_equity')
        if de is not None:
            if de < 0.5: score_fund += 3.0; signals.append("✅ Nợ vay cực thấp (Tài chính an toàn)")
            elif de < 1.0: score_fund += 2.0
            elif de > 2.0: warnings.append(f"⚠️ Đòn bẩy tài chính cao (D/E={de:.1f})"); score_fund -= 1.0
        
        # 3. Tăng trưởng (Revenue/Profit Growth) - Trọng số 3.0
        rev_growth = self._get_metric(fin, 'revenue_growth_yoy', 0)
        ebt_growth = self._get_metric(fin, 'ebt_growth_yoy', 0)
        
        if rev_growth > 0.15 and ebt_growth > 0.15: 
            score_fund += 3.0; signals.append("🚀 Tăng trưởng kép doanh thu & lợi nhuận")
        elif ebt_growth > 0.10: score_fund += 1.5

        if rev_growth > 0.15:
            signals.append(f"🚀 Tăng trưởng doanh thu ấn tượng ({rev_growth*100:.1f}%)")
        elif rev_growth < -0.10:
            # Tăng trưởng âm sâu -> CẢNH BÁO
            warnings.append(f"📉 Doanh thu suy giảm mạnh ({rev_growth*100:.1f}%)")

        # --- B. ĐỊNH GIÁ (10đ) ---
        # Doanh nghiệp dùng kết hợp P/E (cho lợi nhuận) và P/B (cho tài sản)
        pe = price_row.get('pe', 0)
        
        # Check EPS, nếu âm thì không dùng PE
        eps = self._get_metric(fin, 'eps', 0)
        if eps > 0 and pe > 0:
            if pe < 10: 
                score_val += 8.0
                if roe > 0.15: signals.append("💎 Cổ phiếu Giá trị (PE thấp + ROE cao)")
            elif pe < 15: score_val += 6.0
            elif pe > 25: warnings.append("💸 P/E quá cao")
        
        # Bonus điểm nếu đang tăng trưởng mạnh mà PE chưa quá cao
        if ebt_growth > 0.20 and pe < 15: score_val += 2.0
        
        return {
            "type": "General",
            "score_fund": min(score_fund, 10),
            "score_val": min(score_val, 10),
            "signals": signals,
            "warnings": warnings,
            "metrics": {
                "roe": roe, "de": de, "pe": pe, "growth": ebt_growth
            }
        }
    
    def check_financial_health(self, fin):
        """
        Kiểm tra nhanh sức khỏe tài chính để tránh 'Value Trap'
        Trả về: (is_healthy: bool, reason: str)
        """
        if not fin: return False, "Thiếu dữ liệu BCTC"
        
        # 1. Check Đòn bẩy (Nợ/VCSH)
        de = self._safe_float(fin.get('debt_to_equity'))
        if de and de > 2.5: 
            return False, f"Đòn bẩy tài chính quá cao (D/E={de:.2f})"
        
        # 2. Check Tăng trưởng Doanh thu (Tránh DN đang teo tóp)
        rev_growth = self._safe_float(fin.get('revenue_growth_yoy'))
        if rev_growth and rev_growth < -0.10:
            return False, f"Doanh thu suy giảm mạnh ({rev_growth*100:.1f}%)"
            
        # 3. Check Lợi nhuận (Tránh DN thua lỗ)
        # Nếu có eps, check eps > 0
        eps = self._safe_float(fin.get('eps'))
        if eps is not None and eps < 0:
             return False, "Kinh doanh thua lỗ (EPS âm)"

        return True, "Sức khỏe tài chính ổn"