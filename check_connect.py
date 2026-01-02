import sqlalchemy
from sqlalchemy import create_engine, text

# Cấu hình kết nối
# Thay 'password' bằng mật khẩu bạn đặt lúc cài PostgreSQL
DB_URI = "postgresql://postgres:minhle0403@localhost:5432/stock_db"

try:
    # 1. Thử kết nối
    print("Dang ket noi den Database...")
    engine = create_engine(DB_URI)
    connection = engine.connect()
    print("✅ KET NOI THANH CONG!")

    # 2. Thử tạo một bảng dữ liệu mẫu
    print("Dang tao bang mau...")
    create_table_sql = text("""
    CREATE TABLE IF NOT EXISTS test_connect (
        id SERIAL PRIMARY KEY,
        message VARCHAR(50)
    );
    """)
    connection.execute(create_table_sql)
    connection.commit() # Xác nhận thay đổi
    print("✅ Tao bang thanh cong!")
    
    connection.close()
    print("Chuc mung! Moi truong cua ban da san sang cho Buoc 1.")

except Exception as e:
    print("❌ KET NOI THAT BAI!")
    print("Loi chi tiet:", e)
    print("\nGoi y sua loi:")
    print("- Kiem tra lai mat khau trong bien DB_URI.")
    print("- Kiem tra xem PostgreSQL da chay chua (Mo pgAdmin xem co vao duoc khong).")
    print("- Kiem tra xem da tao database ten la 'stock_db' chua.")