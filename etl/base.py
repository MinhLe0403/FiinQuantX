# etl/base.py
import sys
import os
import pandas as pd
import numpy as np
import time
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Config
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL, FIIN_USER, FIIN_PASS

try:
    from FiinQuantX import FiinSession
except ImportError:
    class FiinSession: pass

class BaseETL:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.client = None
        self._connect_client()

    def _connect_client(self):
        try:
            self.client = FiinSession(username=FIIN_USER, password=FIIN_PASS).login()
            # print("✅ [API] Connected")
        except Exception as e:
            print(f"❌ [API] Connection Failed: {e}")

    def sleep(self, seconds=0.2):
        time.sleep(seconds)

    def get_last_updated_date(self, table_name, symbol):
        try:
            query = text(f"SELECT MAX(time) FROM {table_name} WHERE symbol = :symbol")
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                return pd.to_datetime(res[0]).date() if res and res[0] else None
        except: return None

    def get_row_count(self, table_name, symbol):
        try:
            query = text(f"SELECT COUNT(*) FROM {table_name} WHERE symbol = :symbol")
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                return res[0] if res else 0
        except: return 0

    def safe_api_call(self, func, retries=3):
        for i in range(retries):
            try:
                return func()
            except Exception as e:
                if "Redis" in str(e) or "500" in str(e):
                    time.sleep(2)
                else:
                    return None
        return None
    
    def _backup_data_to_csv(self, table_name, symbol):
        """
        Lưu dữ liệu hiện tại ra file CSV trước khi ghi đè.
        File lưu tại: backups/table_name_symbol_timestamp.csv
        """
        try:
            # Tạo thư mục backup nếu chưa có
            backup_dir = os.path.join(project_root, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Query dữ liệu cũ
            query = text(f"SELECT * FROM {table_name} WHERE symbol = :sym")
            with self.engine.connect() as conn:
                df_old = pd.read_sql(query, conn, params={"sym": symbol})
            
            if not df_old.empty:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{table_name}_{symbol}_{timestamp}.csv"
                filepath = os.path.join(backup_dir, filename)
                df_old.to_csv(filepath, index=False)
                # print(f"   💾 Đã backup dữ liệu cũ: {filename}")
        except Exception as e:
            print(f"   ⚠️ Lỗi Backup: {e}")

    # --- HÀM UPSERT ĐÃ SỬA ĐỂ DEBUG ---
    def upsert_data(self, df, table_name, pk_cols):
        if df is None or df.empty: return
        
        # --- [BƯỚC MỚI] BACKUP TRƯỚC KHI GHI ---
        # Chỉ backup nếu cập nhật số lượng ít (để tránh chậm khi chạy Batch lớn)
        # Lấy symbol đại diện để backup
        if 'symbol' in df.columns:
            unique_symbols = df['symbol'].unique()
            if len(unique_symbols) == 1: # Chỉ backup khi update đơn lẻ
                self._backup_data_to_csv(table_name, unique_symbols[0])
        # ---------------------------------------

        try:
            # 1. DEBUG: Kiểm tra khóa chính
            missing_cols = [col for col in pk_cols if col not in df.columns]
            if missing_cols:
                print(f"❌ LỖI UPSERT [{table_name}]: Thiếu cột {missing_cols}")
                print(f"   👉 Các cột hiện có trong DF: {list(df.columns)}")
                return # Dừng ngay tại đây

            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.drop_duplicates(subset=pk_cols)
            
            with self.engine.begin() as conn:
                temp_table = f"temp_{table_name}_{datetime.now().strftime('%M%S%f')}"
                df.to_sql(temp_table, conn, index=False, if_exists='replace')
                
                # Fix lỗi kiểu dữ liệu cho bảng Financial
                if table_name == 'fact_financial_ratios':
                    cols = [c for c in df.columns if c not in pk_cols]
                    for c in cols:
                        conn.execute(text(f"ALTER TABLE {temp_table} ALTER COLUMN {c} TYPE NUMERIC USING {c}::numeric"))

                where_clause = " AND ".join([f"{table_name}.{c} = {temp_table}.{c}" for c in pk_cols])
                conn.execute(text(f"DELETE FROM {table_name} USING {temp_table} WHERE {where_clause}"))
                
                cols = ",".join([f'"{c}"' for c in df.columns])
                conn.execute(text(f"INSERT INTO {table_name} ({cols}) SELECT {cols} FROM {temp_table}"))
                conn.execute(text(f"DROP TABLE {temp_table}"))
                print(f"   -> Saved {len(df)} rows")
        except Exception as e:
            # In lỗi chi tiết ra màn hình thay vì giấu đi
            print(f"❌ CRITICAL DB ERROR [{table_name}]: {e}")

    def get_latest_price_check(self, symbol):
        """
        Lấy ngày và giá đóng cửa của dòng dữ liệu mới nhất trong DB.
        Để so sánh với API xem có bị điều chỉnh giá không.
        """
        try:
            # Lấy close_raw (giá gốc) hoặc close (giá đã điều chỉnh tại thời điểm lưu)
            # Ta nên so sánh 'close' (đã điều chỉnh) trong DB với 'close' (adjusted) hiện tại của API
            query = text("""
                SELECT time, close 
                FROM fact_daily_bars 
                WHERE symbol = :symbol 
                ORDER BY time DESC LIMIT 1
            """)
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                if res:
                    return pd.to_datetime(res[0]).date(), float(res[1])
                return None, None
        except Exception as e:
            # print(f"Error checking price: {e}")
            return None, None