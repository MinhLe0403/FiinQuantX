import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def check_share_issue():
    print("🕵️ KIỂM TRA DỮ LIỆU SHARE ISSUE (KL LƯU HÀNH)...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. Thống kê chung
        query_summary = text("""
            SELECT 
                COUNT(*) as total_rows,
                SUM(CASE WHEN share_issue IS NULL OR share_issue = 0 THEN 1 ELSE 0 END) as missing_rows,
                MAX(time) as last_update
            FROM fact_investor_flows_daily
        """)
        summary = conn.execute(query_summary).fetchone()
        print(f"📊 Tổng số dòng Flow: {summary[0]}")
        print(f"⚠️ Số dòng thiếu Share Issue: {summary[1]}")
        print(f"🕒 Cập nhật lần cuối: {summary[2]}")

        # 2. Soi chi tiết các mã trong VN30 (Ví dụ)
        print("\n🔍 Kiểm tra mẫu VN30 (5 phiên gần nhất):")
        query_detail = text("""
            SELECT f.time, f.symbol, f.share_issue, p.close, 
                   (f.share_issue * p.close / 1000000000) as market_cap_ty
            FROM fact_investor_flows_daily f
            JOIN fact_daily_bars p ON f.symbol = p.symbol AND f.time = p.time
            WHERE f.symbol IN ('FPT', 'HPG', 'VNM', 'VIC')
            ORDER BY f.time DESC
            LIMIT 10
        """)
        df = pd.read_sql(query_detail, conn)
        if df.empty:
            print("❌ Không có dữ liệu mẫu. Hãy chạy cập nhật Batch cho VN30.")
        else:
            print(df.to_string(index=False))

if __name__ == "__main__":
    check_share_issue()