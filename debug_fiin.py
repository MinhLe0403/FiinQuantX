import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from config import FIIN_USER, FIIN_PASS

try:
    from FiinQuantX import FiinSession
    print("✅ Đã import thư viện FiinQuantX")
except ImportError:
    print("❌ Lỗi: Chưa cài thư viện FiinQuantX")
    sys.exit()

def debug_data():
    print("🔑 Đang đăng nhập FiinQuant...")
    client = FiinSession(username=FIIN_USER, password=FIIN_PASS).login()
    
    symbol = "HPG"
    today = datetime.now()
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    print(f"\n--- 1. KIỂM TRA DÒNG TIỀN (PriceStatistics) CHO {symbol} ---")
    try:
        # Lấy thử 5 ngày gần nhất
        df = client.PriceStatistics().get_ceilingfloor(
            tickers=[symbol], from_date=from_date, to_date=to_date
        )
        if df is not None and not df.empty:
            print("✅ Lấy được dữ liệu Dòng tiền!")
            print("👇 DANH SÁCH TÊN CỘT TRẢ VỀ (Copy cái này để so sánh):")
            print(df.columns.tolist())
            
            print("\n👇 DỮ LIỆU MẪU (2 dòng đầu):")
            # In ra các cột liên quan đến nước ngoài để xem có giá trị không
            cols_to_check = [c for c in df.columns if 'foreign' in c.lower() or 'buy' in c.lower()]
            print(df[cols_to_check].head(2).to_string())
        else:
            print("⚠️ API trả về DataFrame rỗng!")
    except Exception as e:
        print(f"❌ Lỗi gọi API Dòng tiền: {e}")

    print(f"\n--- 2. KIỂM TRA BÁO CÁO TÀI CHÍNH (FundamentalAnalysis) ---")
    try:
        # Lấy năm 2024
        raw_data = client.FundamentalAnalysis().get_ratios(
            tickers=[symbol], years=[2024], quarters=[1, 2, 3], type="consolidated"
        )
        
        print(f"Kiểu dữ liệu trả về: {type(raw_data)}")
        
        if isinstance(raw_data, list) and len(raw_data) > 0:
            print("✅ Lấy được dữ liệu BCTC!")
            first_item = raw_data[0]
            print("\n👇 CẤU TRÚC 1 PHẦN TỬ (JSON RAW):")
            # In đẹp JSON để dễ nhìn
            print(json.dumps(first_item, indent=4, ensure_ascii=False))
        else:
            print("⚠️ Dữ liệu BCTC rỗng hoặc không phải List.")
            print(f"Raw content: {raw_data}")

    except Exception as e:
        print(f"❌ Lỗi gọi API BCTC: {e}")

if __name__ == "__main__":
    debug_data()