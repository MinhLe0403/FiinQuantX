# etl/market.py
import pandas as pd
from .base import BaseETL

class MarketLoader(BaseETL):
    def get_tickers_from_group(self, code):
        if not self.client: return []
        try:
            resp = self.client.TickerList(ticker=code)
            tickers = list(resp)
            # SỬA: Cho phép lấy cả mã dài (Index) nếu nó không phải là rác
            # Chỉ lọc bỏ rỗng hoặc không phải string
            clean_tickers = [str(t) for t in tickers if isinstance(t, str) and len(t) >= 3]
            return clean_tickers
        except: return []

    def map_stock_to_index(self, index_code, tickers_list):
        """Lưu danh sách mã thuộc Index vào DB"""
        if not tickers_list: return
        
        # Tạo DataFrame mapping
        data = [{"symbol": t, "index_code": index_code} for t in tickers_list]
        df = pd.DataFrame(data)
        
        # Upsert vào bảng map_stock_index
        # PK là (symbol, index_code)
        self.upsert_data(df, "map_stock_index", ["symbol", "index_code"])
        # print(f"   + Mapped {len(df)} stocks to {index_code}")

    def sync_basic_info_batch(self, tickers_list):
        """
        Lấy thông tin cơ bản cho 1 danh sách mã (Tối ưu API)
        """
        if not tickers_list: return
        
        # Chia chunk 50 mã/lần gọi
        chunk_size = 50
        for i in range(0, len(tickers_list), chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            try:
                df = self.client.BasicInfor(tickers=chunk).get()
                if df is not None and not df.empty:
                    if 'sector' not in df.columns: df['sector'] = None
                    # Rename columns
                    df.rename(columns={"ticker": "symbol", "companyName": "company_name", 
                                       "exchange": "exchange", "sector": "sector"}, inplace=True)
                    
                    df['type'] = 'STOCK'
                    cols = ['symbol', 'company_name', 'exchange', 'sector', 'type']
                    
                    self.upsert_data(df[cols], "dim_stocks", ['symbol'])
                    print(f"   -> Updated Info: {len(df)} stocks")
                self.sleep(0.2)
            except Exception as e:
                print(f"   ⚠️ Error Info Batch: {e}")