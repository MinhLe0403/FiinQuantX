"""
Chỉ để cập nhật dòng tiền
"""
import os
import sys
# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from etl.runner import ETLRunner
from etl.constants import ALL_INDICES, SECTOR_CODES_LIST
from datetime import datetime, timedelta

def run_fix():
    runner = ETLRunner()
    
    print("🚀 BẮT ĐẦU CẬP NHẬT RIÊNG DỮ LIỆU DÒNG TIỀN...")
    
    # 1. Chọn ngày muốn cập nhật (Ví dụ: Từ đầu năm 2024 đến nay)
    # Hoặc bạn có thể để None để script tự lấy 1 năm gần nhất
    start_date = "2024-01-01" 
    end_date = "2024-12-31" 
    
    # 2. Lấy danh sách mã cần fix
    # Cách A: Lấy toàn bộ mã trong VN30
    tickers = runner.get_tickers_by_group("VNINDEX")
    
    # Cách B: Lấy toàn bộ mã trong DB (nếu muốn chạy hết)
    # tickers = runner.get_tickers_by_group("VNINDEX") # Hoặc VNALL
    
    # Cách C: Chỉ định 1 vài mã
    # tickers = ['HPG', 'SSI', 'VND']

    if not tickers:
        print("❌ Không tìm thấy mã nào.")
        return

    print(f"📋 Danh sách: {len(tickers)} mã.")
    
    # 3. Chạy cập nhật (Batch)
    # Sử dụng hàm mới viết ở Bước 1
    runner.update_flow_batch_only(tickers, start_date, end_date)
    
    print("\n✅ HOÀN TẤT CẬP NHẬT DÒNG TIỀN!")

if __name__ == "__main__":
    run_fix()