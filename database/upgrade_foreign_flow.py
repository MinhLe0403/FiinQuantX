import sys
import os
from sqlalchemy import create_engine, text

# Setup đường dẫn
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def upgrade_foreign_columns():
    print("🛠️ ĐANG CẬP NHẬT SCHEMA BẢNG FLOW (THÊM NĐTNN CHI TIẾT)...")
    
    engine = create_engine(DATABASE_URL)
    
    # Danh sách các cột cần thêm
    # Ind = Individual (Cá nhân), Inst = Institutional (Tổ chức)
    new_columns = [
        "foreign_ind_buy_vol BIGINT",
        "foreign_ind_sell_vol BIGINT",
        "foreign_ind_buy_val NUMERIC(25, 2)",
        "foreign_ind_sell_val NUMERIC(25, 2)",
        
        "foreign_inst_buy_vol BIGINT",
        "foreign_inst_sell_vol BIGINT",
        "foreign_inst_buy_val NUMERIC(25, 2)",
        "foreign_inst_sell_val NUMERIC(25, 2)"
    ]
    
    with engine.begin() as conn:
        for col_def in new_columns:
            try:
                # Cú pháp PostgreSQL: ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...
                col_name = col_def.split()[0]
                sql = f"ALTER TABLE fact_investor_flows_daily ADD COLUMN IF NOT EXISTS {col_def};"
                conn.execute(text(sql))
                print(f"   ✅ Đã thêm cột: {col_name}")
            except Exception as e:
                print(f"   ⚠️ Lỗi thêm cột {col_name}: {e}")

    print("🎉 NÂNG CẤP HOÀN TẤT!")

if __name__ == "__main__":
    upgrade_foreign_columns()