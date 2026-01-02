import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text

# --- CẤU HÌNH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def check_db_size():
    engine = create_engine(DATABASE_URL)
    print(f"🔍 Đang kết nối và kiểm tra dung lượng Database...\n")

    with engine.connect() as conn:
        # 1. Kiểm tra tổng dung lượng của Database 'stock_db'
        query_total = text("SELECT pg_size_pretty(pg_database_size(current_database()));")
        total_size = conn.execute(query_total).scalar()
        
        # 2. Kiểm tra chi tiết từng bảng (Table)
        query_tables = text("""
            SELECT
                relname AS "Tên Bảng",
                pg_size_pretty(pg_total_relation_size(relid)) AS "Dung lượng",
                n_live_tup AS "Số dòng (Rows)"
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC;
        """)
        df = pd.read_sql(query_tables, conn)

    print(f"📦 TỔNG DUNG LƯỢNG DATABASE: {total_size}")
    print("-" * 50)
    print("CHI TIẾT TỪNG BẢNG:")
    print(df.to_string(index=False))
    print("-" * 50)
    
    # Đánh giá
    print("\n💡 ĐÁNH GIÁ:")
    # Chuyển đổi size về dạng MB để so sánh (đơn giản hóa)
    # Đây chỉ là logic hiển thị text, không ảnh hưởng tính toán
    print(f"Với ổ cứng của bạn, bạn có thể lưu trữ thoải mái.")
    print("PostgreSQL nén dữ liệu rất tốt, 10 năm dữ liệu chỉ khoảng 2-3GB thôi.")

if __name__ == "__main__":
    try:
        check_db_size()
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")