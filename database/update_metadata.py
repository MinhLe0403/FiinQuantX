# update_metadata.py
import sys
import os
import pandas as pd
from datetime import datetime

# Setup đường dẫn - Chỉnh lại để import từ root project
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))  # Lên 1 cấp từ etl/ → mle_stock/
sys.path.insert(0, project_root)

# Giờ import từ root
from etl.market import MarketLoader
from etl.constants import ALL_INDICES, SECTOR_CODES_LIST

def run_metadata_update():
    print(f"\n📋 [{datetime.now()}] BẮT ĐẦU CẬP NHẬT THÔNG TIN CƠ BẢN & MAPPING")
    
    loader = MarketLoader()
    all_stocks = set()

    # 1. QUÉT & MAP INDEX (QUAN TRỌNG)
    print("\n--- 1. CẬP NHẬT DANH MỤC CHỈ SỐ (Index Mapping) ---")
    for idx in ALL_INDICES:
        tickers = loader.get_tickers_from_group(idx)
        if tickers:
            print(f"   📌 {idx}: {len(tickers)} mã")
            # Lưu vào bảng map_stock_index
            loader.map_stock_to_index(idx, tickers)
            all_stocks.update(tickers)
    
    # 2. QUÉT NGÀNH (Để lấy thêm mã nếu có)
    print("\n--- 2. QUÉT MÃ TỪ CÁC NGÀNH (Sectors) ---")
    for sec in SECTOR_CODES_LIST:
        tickers = loader.get_tickers_from_group(sec)
        if tickers:
            all_stocks.update(tickers)
            
    final_list = sorted(list(all_stocks))
    print(f"\n📊 Tổng số mã cổ phiếu tìm thấy: {len(final_list)}")

    # 3. CẬP NHẬT DIM_STOCKS (Tên cty, Sàn, Ngành)
    print("\n--- 3. CẬP NHẬT THÔNG TIN CƠ BẢN (dim_stocks) ---")
    if final_list:
        loader.sync_basic_info_batch(final_list)
    
    print("\n✅ HOÀN TẤT! Database đã có đầy đủ danh sách mã và mapping.")

if __name__ == "__main__":
    run_metadata_update()