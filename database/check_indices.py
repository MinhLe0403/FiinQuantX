import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL
# Thử import danh sách index, nếu lỗi thì dùng list mặc định
try:
    from etl.constants import ALL_INDICES
except ImportError:
    ALL_INDICES = ["VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPCOMINDEX"]

def check_indices_status():
    print(f"\n📊 KIỂM TRA CHẤT LƯỢNG DỮ LIỆU CHỈ SỐ (DEEP CHECK)")
    print(f"🕒 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    engine = create_engine(DATABASE_URL)
    
    # 1. THỐNG KÊ TỔNG QUAN
    print("\n1️⃣  THỐNG KÊ TỔNG QUAN")
    indices_str = "', '".join(ALL_INDICES)
    
    # Query này đếm tổng số dòng, và đếm số dòng có dữ liệu thực (khác 0) của các trường quan trọng
    query_summary = text(f"""
        SELECT 
            symbol,
            MIN(time)::date as start_date,
            MAX(time)::date as end_date,
            COUNT(*) as total_rows,
            SUM(CASE WHEN trading_value > 0 THEN 1 ELSE 0 END) as rows_with_val,
            SUM(CASE WHEN buy_active_vol > 0 OR sell_active_vol > 0 THEN 1 ELSE 0 END) as rows_with_active
        FROM fact_daily_bars
        WHERE symbol IN ('{indices_str}')
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    try:
        with engine.connect() as conn:
            df_sum = pd.read_sql(query_summary, conn)
            
        if df_sum.empty:
            print("❌ Không tìm thấy dữ liệu chỉ số nào trong DB.")
        else:
            # Tính tỷ lệ % dữ liệu đầy đủ
            df_sum['val_coverage%'] = (df_sum['rows_with_val'] / df_sum['total_rows'] * 100).round(1)
            df_sum['active_coverage%'] = (df_sum['rows_with_active'] / df_sum['total_rows'] * 100).round(1)
            
            # Chọn cột hiển thị
            display_cols = ['symbol', 'end_date', 'total_rows', 'val_coverage%', 'active_coverage%']
            print(df_sum[display_cols].to_string(index=False))
            print("\n   (active_coverage% thấp là bình thường nếu dữ liệu lịch sử xa xưa không có Active Vol)")

            # 2. SOI CHI TIẾT 5 DÒNG MỚI NHẤT CỦA CÁC CHỈ SỐ CHÍNH
            print("\n" + "="*80)
            print("2️⃣  DỮ LIỆU CHI TIẾT (TOP 5 PHIÊN GẦN NHẤT)")
            
            target_indices = ['VNINDEX', 'VN30', 'HNXINDEX'] # Các chỉ số quan trọng nhất
            
            for idx in target_indices:
                print(f"\n📌 {idx}:")
                query_detail = text(f"""
                    SELECT 
                        time::date as date, 
                        close, 
                        volume, 
                        trading_value as value, 
                        vwap, 
                        buy_active_vol as buy_act, 
                        sell_active_vol as sell_act
                    FROM fact_daily_bars 
                    WHERE symbol = '{idx}' 
                    ORDER BY time DESC 
                    LIMIT 5
                """)
                with engine.connect() as conn:
                    df_detail = pd.read_sql(query_detail, conn)
                
                if not df_detail.empty:
                    # Format số tiền cho dễ nhìn (Chia tỷ)
                    df_detail['value'] = df_detail['value'].apply(lambda x: f"{x/1e9:.2f}B" if x else '-')
                    print(df_detail.to_string(index=False))
                else:
                    print("   (Chưa có dữ liệu)")

    except Exception as e:
        print(f"❌ Lỗi truy vấn: {e}")

if __name__ == "__main__":
    check_indices_status()