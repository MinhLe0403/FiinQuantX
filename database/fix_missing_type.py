import sys
import os
from sqlalchemy import create_engine, text

# Setup đường dẫn
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def fix_types():
    print("🛠️ ĐANG SỬA LỖI LOẠI CỔ PHIẾU (TYPE = N/A)...")
    
    engine = create_engine(DATABASE_URL)
    
    with engine.begin() as conn:
        # 1. Cập nhật mặc định STOCK cho tất cả các mã đang NULL
        print("-> Gán 'STOCK' cho các mã thiếu thông tin...")
        conn.execute(text("""
            UPDATE dim_stocks 
            SET type = 'STOCK' 
            WHERE type IS NULL OR type = '';
        """))
        
        # 2. Cập nhật INDEX cho các mã chỉ số thông dụng
        # Logic: Các mã Index thường là VNINDEX, VN30, HNX30...
        print("-> Chuẩn hóa lại các mã INDEX...")
        indices_list = [
            'VNINDEX', 'VN30', 'VN100', 'VNALL', 'VNXALL', 'VN50', 
            'VNFIN', 'VNFINSELECT', 'VNFINLEAD', 'VNSI', 'VNDIAMOND', 
            'VNMID', 'VNREAL', 'VNMAT', 'VNCONS', 'VNIND', 
            'VNSML', 'VNIT', 'VNCOND', 
            'HNXINDEX', 'HNX30', 'UPCOMINDEX'
        ]
        
        # Tạo chuỗi query an toàn
        indices_str = "', '".join(indices_list)
        query_fix_index = text(f"""
            UPDATE dim_stocks 
            SET type = 'INDEX' 
            WHERE symbol IN ('{indices_str}');
        """)
        conn.execute(query_fix_index)
        
    print("✅ HOÀN TẤT! Hãy chạy lại lệnh kiểm tra để xem kết quả.")

if __name__ == "__main__":
    fix_types()