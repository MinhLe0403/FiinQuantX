import sys
import os
from sqlalchemy import create_engine, text

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def fix_schema():
    engine = create_engine(DATABASE_URL)
    print("🛠️ Đang sửa lỗi Schema Database...")
    
    with engine.connect() as conn:
        # 1. Xóa bảng cũ bị sai cấu trúc
        print("   -> Đang xóa bảng 'fact_financial_ratios' cũ...")
        conn.execute(text("DROP TABLE IF EXISTS fact_financial_ratios"))
        conn.commit()
        print("   ✅ Đã xóa thành công.")

if __name__ == "__main__":
    fix_schema()