import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def check_investor_flow_table():
    print(f"\n🕵️ KIỂM TRA BẢNG DÒNG TIỀN (FACT_INVESTOR_FLOWS_DAILY)")
    print("="*80)
    
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
    except Exception as e:
        print(f"❌ Lỗi kết nối DB: {e}")
        return

    # 1. THỐNG KÊ TỔNG QUAN
    print("\n1️⃣  THỐNG KÊ TỔNG QUAN")
    try:
        query_overview = text("""
            SELECT 
                COUNT(*) as total_rows,
                MIN(time)::date as first_date,
                MAX(time)::date as last_date,
                COUNT(DISTINCT symbol) as total_symbols
            FROM fact_investor_flows_daily
        """)
        df_overview = pd.read_sql(query_overview, conn)
        print(df_overview.to_string(index=False))
    except Exception as e:
        print(f"Lỗi: {e}")

    # 2. KIỂM TRA DỮ LIỆU CÁC CỘT QUAN TRỌNG
    print("\n2️⃣  CHẤT LƯỢNG DỮ LIỆU (DATA QUALITY)")
    try:
        # Kiểm tra xem các cột mới có dữ liệu không (Khác 0 và Khác Null)
        query_quality = text("""
            SELECT 
                SUM(CASE WHEN share_issue > 0 THEN 1 ELSE 0 END) as has_share_issue,
                
                -- Kiểm tra dòng tiền chi tiết (Mới thêm)
                SUM(CASE WHEN foreign_ind_buy_val > 0 OR foreign_ind_sell_val > 0 THEN 1 ELSE 0 END) as has_foreign_ind,
                SUM(CASE WHEN foreign_inst_buy_val > 0 OR foreign_inst_sell_val > 0 THEN 1 ELSE 0 END) as has_foreign_inst,
                
                -- Kiểm tra dòng tiền cơ bản (Cũ)
                SUM(CASE WHEN foreign_buy_val > 0 OR foreign_sell_val > 0 THEN 1 ELSE 0 END) as has_foreign_total,
                SUM(CASE WHEN prop_buy_val > 0 OR prop_sell_val > 0 THEN 1 ELSE 0 END) as has_prop
            FROM fact_investor_flows_daily
        """)
        df_qual = pd.read_sql(query_quality, conn)
        print(df_qual.to_string(index=False))
        
        # Đánh giá
        total = df_overview.iloc[0]['total_rows']
        has_new = df_qual.iloc[0]['has_foreign_inst']
        print(f"\n>> Đánh giá: Có {has_new}/{total} dòng ({has_new/total*100:.1f}%) đã có dữ liệu chi tiết Nước ngoài (Ind/Inst).")
        
    except Exception as e:
        print(f"Lỗi (Có thể do chưa chạy upgrade DB để thêm cột mới): {e}")

    # 3. SOI DỮ LIỆU CHI TIẾT (SAMPLE)
    print("\n3️⃣  MẪU DỮ LIỆU CHI TIẾT (TOP 5 DÒNG MỚI NHẤT)")
    ticker = input("Nhập mã muốn soi (Enter để lấy VN30): ").upper().strip()
    if not ticker: ticker = "VN30"
    
    try:
        # Lấy các cột quan trọng để hiển thị
        query_sample = text(f"""
            SELECT 
                time::date, symbol, 
                share_issue,
                -- Chia tỷ cho gọn
                ROUND(foreign_buy_val / 1000000000, 2) as F_Buy,
                ROUND(foreign_sell_val / 1000000000, 2) as F_Sell,
                
                -- Cột mới
                ROUND(foreign_inst_buy_val / 1000000000, 2) as Inst_Buy,
                ROUND(foreign_ind_buy_val / 1000000000, 2) as Ind_Buy,
                
                ROUND(prop_net_val / 1000000000, 2) as Prop_Net
            FROM fact_investor_flows_daily
            WHERE symbol = '{ticker}'
            ORDER BY time DESC
            LIMIT 10
        """)
        df_sample = pd.read_sql(query_sample, conn)
        if df_sample.empty:
            print(f"❌ Không có dữ liệu cho {ticker}")
        else:
            print(f"Đơn vị: Tỷ VNĐ")
            print(df_sample.to_string(index=False))
            
    except Exception as e:
        print(f"Lỗi hiển thị mẫu: {e}")

    conn.close()
    print("\n" + "="*80)

if __name__ == "__main__":
    check_investor_flow_table()