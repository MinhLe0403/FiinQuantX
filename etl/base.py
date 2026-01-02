import time
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from config import DATABASE_URL, FIIN_USER, FIIN_PASS

try:
    from FiinQuantX import FiinSession
except ImportError:
    class FiinSession: pass

class BaseETL:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.client = None
        self._connect_api()

    def _connect_api(self):
        try:
            self.client = FiinSession(username=FIIN_USER, password=FIIN_PASS).login()
            print("✅ [API] Connected to FiinQuant")
        except Exception as e:
            print(f"❌ [API] Connection Failed: {e}")

    def sleep(self, seconds=0.2):
        """Rate limiting"""
        time.sleep(seconds)

    def get_last_updated_date(self, table_name, symbol):
        """Lấy ngày dữ liệu mới nhất trong DB của một mã"""
        try:
            query = text(f"SELECT MAX(time) FROM {table_name} WHERE symbol = :symbol")
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                return pd.to_datetime(res[0]).date() if res and res[0] else None
        except:
            return None

    def upsert_data(self, df, table_name, pk_cols):
        """Hàm lưu dữ liệu vào DB (Cơ chế Update-Insert)"""
        if df is None or df.empty: return
        try:
            # Clean data
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.drop_duplicates(subset=pk_cols)
            
            with self.engine.begin() as conn:
                temp_table = f"temp_{table_name}_{datetime.now().strftime('%M%S%f')}"
                df.to_sql(temp_table, conn, index=False, if_exists='replace')
                
                # Ép kiểu cho Financials nếu cần
                if table_name == 'fact_financial_ratios':
                    cols = [c for c in df.columns if c not in pk_cols]
                    for c in cols:
                        conn.execute(text(f"ALTER TABLE {temp_table} ALTER COLUMN {c} TYPE NUMERIC USING {c}::numeric"))

                # Xóa cũ -> Chèn mới
                where_clause = " AND ".join([f"{table_name}.{c} = {temp_table}.{c}" for c in pk_cols])
                conn.execute(text(f"DELETE FROM {table_name} USING {temp_table} WHERE {where_clause}"))
                
                cols = ",".join([f'"{c}"' for c in df.columns])
                conn.execute(text(f"INSERT INTO {table_name} ({cols}) SELECT {cols} FROM {temp_table}"))
                conn.execute(text(f"DROP TABLE {temp_table}"))
        except Exception as e:
            print(f"   ⚠️ Upsert Error {table_name}: {str(e)[:100]}")

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
    
    def get_row_count(self, table_name, symbol):
        """Đếm số lượng bản ghi của 1 mã trong bảng"""
        try:
            query = text(f"SELECT COUNT(*) FROM {table_name} WHERE symbol = :symbol")
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                return res[0] if res else 0
        except:
            return 0