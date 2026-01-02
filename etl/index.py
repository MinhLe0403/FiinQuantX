import pandas as pd
import numpy as np
from .base import BaseETL
# Import FlowLoader để tái sử dụng logic lưu dòng tiền (tránh lặp code)
from .flow import FlowLoader 

class IndexLoader(BaseETL):
    
    # --- 1. HÀM SYNC ĐƠN LẺ (Sửa lỗi Attribute Error) ---
    def sync(self, symbol, start_date, end_date):
        """Đồng bộ dữ liệu cho 1 Index cụ thể"""
        # 1. Lấy giá và Active Volume
        self.sync_price_data([symbol], start_date, end_date)
        # 2. Lấy dòng tiền (Khối ngoại)
        self.sync_flow_data([symbol], start_date, end_date)

    # --- 2. HÀM SYNC BATCH (Cho cập nhật hàng loạt) ---
    def sync_batch(self, tickers_list, start_date, end_date):
        """Đồng bộ dữ liệu cho danh sách Index"""
        if not tickers_list: return
        # 1. Lấy giá batch
        self.sync_price_data(tickers_list, start_date, end_date)
        # 2. Lấy dòng tiền batch (nếu cần tách riêng, nhưng thường Index ít nên gọi chung cũng được)
        # Tuy nhiên để tối ưu, ta gọi hàm xử lý flow
        self.sync_flow_data(tickers_list, start_date, end_date)

    # --- 3. LOGIC XỬ LÝ CHI TIẾT ---
    
    def sync_price_data(self, tickers, start_date, end_date):
        """Hàm nội bộ lấy giá cho 1 hoặc nhiều mã"""
        # Fetch Price + Active Vol (bu, sd)
        # Index CÓ dữ liệu bu (buy active) và sd (sell active)
        task = lambda: self.client.Fetch_Trading_Data(
            realtime=False, tickers=tickers, 
            fields=['open', 'high', 'low', 'close', 'volume', 'bu', 'sd'], 
            adjusted=True, by='1d', from_date=start_date, to_date=end_date
        ).get_data()
        
        df = self.safe_api_call(task)
        if df is None or df.empty: return

        # Fetch Overview (Để lấy Trading Value chuẩn - totalMatchValue)
        task_o = lambda: self.client.PriceStatistics().get_overview(
            tickers=tickers, time_filter="Daily", from_date=start_date, to_date=end_date
        )
        df_o = self.safe_api_call(task_o)

        self._process_and_save_price(df, df_o)
        self.sleep()

    def sync_flow_data(self, tickers, start_date, end_date):
        """Hàm nội bộ lấy dòng tiền"""
        task = lambda: self.client.PriceStatistics().get_ceilingfloor(
            tickers=tickers, from_date=start_date, to_date=end_date
        )
        df = self.safe_api_call(task)
        
        if df is not None and not df.empty:
            # Tái sử dụng logic xử lý flow chuẩn từ module FlowLoader
            processor = FlowLoader()
            
            # Nếu df chứa nhiều mã, hàm _process_and_save_batch của FlowLoader (nếu được viết hỗ trợ batch) sẽ xử lý
            # Nếu FlowLoader chưa hỗ trợ batch xử lý (mà chỉ nhận 1 symbol), ta cần gọi hàm batch của nó
            # Tuy nhiên, ở bước tái cấu trúc trước, FlowLoader._process_and_save_batch đã được thiết kế để xử lý DataFrame tổng.
            # Chúng ta sẽ copy logic xử lý đó vào đây hoặc gọi nó nếu FlowLoader có method public.
            
            # Để an toàn và độc lập, ta gọi hàm xử lý batch của FlowLoader
            # Giả định flow.py đã có _process_and_save_batch (như đã cung cấp trước đó)
            processor._process_and_save_batch(df)
            
        self.sleep()

    def _process_and_save_price(self, df, df_o):
        # A. Chuẩn hóa tên cột
        if 'timestamp' in df.columns: df.rename(columns={'timestamp': 'time'}, inplace=True)
        if 'ticker' in df.columns: df.rename(columns={'ticker': 'symbol'}, inplace=True)
        
        # Đổi tên bu/sd
        df.rename(columns={"bu": "buy_active_vol", "sd": "sell_active_vol"}, inplace=True)
        
        df['time'] = pd.to_datetime(df['time'])
        df['close_raw'] = df['close'] # Index không điều chỉnh cổ tức

        # B. Merge Trading Value từ Overview
        df['trading_value'] = np.nan
        
        if df_o is not None and not df_o.empty:
            if 'timestamp' in df_o.columns: df_o.rename(columns={'timestamp': 'time'}, inplace=True)
            if 'ticker' in df_o.columns: df_o.rename(columns={'ticker': 'symbol'}, inplace=True)
            df_o['time'] = pd.to_datetime(df_o['time'])
            
            # Với Index, totalMatchValue là giá trị khớp lệnh
            if 'totalMatchValue' in df_o.columns:
                # Merge phải dựa trên cả time và symbol vì đây có thể là batch
                df = pd.merge(df, df_o[['time', 'symbol', 'totalMatchValue']], on=['time', 'symbol'], how='left')
                df['trading_value'] = df['totalMatchValue']

        # C. Fallback & Tính VWAP (Vectorized GroupBy)
        # Nếu không có trading_value, dùng Typical Price * Volume
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['trading_value'] = df['trading_value'].fillna(tp * df['volume'])
        
        # VWAP = Value / Volume
        # Tránh chia cho 0
        df['vwap'] = df['trading_value'] / df['volume'].replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(df['close'])

        # D. Lưu vào DB
        cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'close_raw', 'volume', 
                'trading_value', 'vwap', 'buy_active_vol', 'sell_active_vol']
        
        # Chỉ lấy các cột tồn tại
        valid_cols = [c for c in cols if c in df.columns]
        
        # Upsert Batch
        self.upsert_data(df[valid_cols], "fact_daily_bars", ['time', 'symbol'])
    
    # Hàm này giữ lại để tương thích nếu runner gọi (dù logic đã gộp vào sync_flow_data)
    def sync_flow_batch(self, tickers_list, start_date, end_date):
        self.sync_flow_data(tickers_list, start_date, end_date)