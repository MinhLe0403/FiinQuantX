import pandas as pd
import numpy as np
from .base import BaseETL

class PriceLoader(BaseETL):
    def sync(self, symbol, start_date, end_date):
        """
        Tải dữ liệu Giá, Raw Close và Overview để tính VWAP/TradingValue chính xác.
        """
        # 1. Fetch Adjusted Price (OHLCV)
        task_p = lambda: self.client.Fetch_Trading_Data(
            realtime=False, tickers=[symbol], 
            fields=['open', 'high', 'low', 'close', 'volume', 'bu', 'sd'], 
            adjusted=True, by='1d', from_date=start_date, to_date=end_date
        ).get_data()
        
        df_p = self.safe_api_call(task_p)
        if df_p is None or df_p.empty: return

        # 2. Fetch Raw Price (Để lấy giá đóng cửa chưa điều chỉnh)
        task_r = lambda: self.client.Fetch_Trading_Data(
            realtime=False, tickers=[symbol], fields=['close'], 
            adjusted=False, by='1d', from_date=start_date, to_date=end_date
        ).get_data()
        df_r = self.safe_api_call(task_r)

        # 3. Fetch Overview (QUAN TRỌNG: Để lấy totalMatchValue thực tế)
        task_o = lambda: self.client.PriceStatistics().get_overview(
            tickers=[symbol], time_filter="Daily", from_date=start_date, to_date=end_date
        )
        df_o = self.safe_api_call(task_o)

        # 4. Xử lý và Lưu
        self._process_and_save(df_p, df_r, df_o, symbol)
        self.sleep()

    def _process_and_save(self, df, df_raw, df_overview, symbol):
        # --- A. Chuẩn hóa Dataframe chính (OHLCV) ---
        time_col = next((c for c in df.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
        if time_col: df.rename(columns={time_col: 'time'}, inplace=True)
        
        df.rename(columns={"ticker": "symbol", "bu": "buy_active_vol", "sd": "sell_active_vol"}, inplace=True)
        df['time'] = pd.to_datetime(df['time'])
        df['symbol'] = symbol

        # --- B. Merge Raw Close ---
        if df_raw is not None and not df_raw.empty:
            time_col_r = next((c for c in df_raw.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
            if time_col_r: 
                df_raw.rename(columns={time_col_r: 'time'}, inplace=True)
                # Đổi tên ticker thành symbol nếu có để merge
                if 'ticker' in df_raw.columns: df_raw.rename(columns={'ticker': 'symbol'}, inplace=True)
                
                df_raw['time'] = pd.to_datetime(df_raw['time'])
                
                # Merge
                df = pd.merge(df, df_raw[['time', 'symbol', 'close']], on=['time', 'symbol'], how='left', suffixes=('', '_raw'))
                df.rename(columns={'close_raw': 'close_raw'}, inplace=True)
        
        if 'close_raw' not in df.columns: df['close_raw'] = df['close']

        # --- C. Merge Overview & Tính Trading Value ---
        # Mặc định Trading Value là NaN
        df['trading_value'] = np.nan

        if df_overview is not None and not df_overview.empty:
            time_col_o = next((c for c in df_overview.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
            if time_col_o:
                df_overview.rename(columns={time_col_o: 'time'}, inplace=True)
                if 'ticker' in df_overview.columns: df_overview.rename(columns={'ticker': 'symbol'}, inplace=True)
                df_overview['time'] = pd.to_datetime(df_overview['time'])
                
                # Merge totalMatchValue vào df chính
                # Lưu ý: totalMatchValue là Giá trị khớp lệnh (không bao gồm thỏa thuận) -> Chính xác để tính VWAP
                if 'totalMatchValue' in df_overview.columns:
                    df = pd.merge(df, df_overview[['time', 'symbol', 'totalMatchValue']], on=['time', 'symbol'], how='left')
                    df['trading_value'] = df['totalMatchValue']

        # --- D. Logic Fallback & Tính VWAP ---
        
        # 1. Fallback Trading Value: Nếu API Overview lỗi hoặc trả về 0/NaN
        # Dùng công thức Typical Price * Volume
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df['trading_value'] = df['trading_value'].fillna(0)
        
        mask_missing = df['trading_value'] == 0
        if mask_missing.any():
            df.loc[mask_missing, 'trading_value'] = typical_price.loc[mask_missing] * df.loc[mask_missing, 'volume']

        # 2. Tính VWAP (Volume Weighted Average Price)
        # VWAP = Sum(Price * Vol) / Sum(Vol)
        # Sử dụng Rolling 14 ngày để làm mượt dữ liệu (theo chuẩn FiinQuant logic)
        window = 14
        
        # Nhóm theo symbol để tính rolling chính xác (phòng trường hợp batch có nhiều mã, dù ở đây thường là 1)
        pv_rolling = df.groupby('symbol')['trading_value'].transform(lambda x: x.rolling(window=window, min_periods=1).sum())
        vol_rolling = df.groupby('symbol')['volume'].transform(lambda x: x.rolling(window=window, min_periods=1).sum())
        
        df['vwap'] = pv_rolling / vol_rolling.replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(df['close']) # Fallback cuối cùng là giá đóng cửa

        # --- E. Lưu vào DB ---
        cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'close_raw', 'volume', 
                'trading_value', 'vwap', 'buy_active_vol', 'sell_active_vol']
        
        valid_cols = [c for c in cols if c in df.columns]
        self.upsert_data(df[valid_cols], "fact_daily_bars", ['time', 'symbol'])

    def sync_batch(self, tickers_list, start_date, end_date):
        """
        Tải dữ liệu cho danh sách nhiều mã cùng lúc (Tối ưu API)
        """
        if not tickers_list: return

        # 1. Fetch Adjusted OHLCV (Batch)
        task_p = lambda: self.client.Fetch_Trading_Data(
            realtime=False, tickers=tickers_list, 
            fields=['open', 'high', 'low', 'close', 'volume', 'bu', 'sd'], 
            adjusted=True, by='1d', from_date=start_date, to_date=end_date
        ).get_data()
        df_p = self.safe_api_call(task_p)
        
        if df_p is None or df_p.empty: return

        # 2. Fetch Raw Close (Batch)
        task_r = lambda: self.client.Fetch_Trading_Data(
            realtime=False, tickers=tickers_list, fields=['close'], 
            adjusted=False, by='1d', from_date=start_date, to_date=end_date
        ).get_data()
        df_r = self.safe_api_call(task_r)

        # 3. Fetch Overview (Batch) - Để lấy Trading Value chuẩn
        task_o = lambda: self.client.PriceStatistics().get_overview(
            tickers=tickers_list, time_filter="Daily", from_date=start_date, to_date=end_date
        )
        df_o = self.safe_api_call(task_o)

        # 4. Xử lý & Lưu
        self._process_and_save_batch(df_p, df_r, df_o)
        self.sleep()

    def _process_and_save_batch(self, df, df_raw, df_overview):
        # A. Chuẩn hóa DF Chính
        if 'timestamp' in df.columns: df.rename(columns={'timestamp': 'time'}, inplace=True)
        if 'ticker' in df.columns: df.rename(columns={'ticker': 'symbol'}, inplace=True) # QUAN TRỌNG
        
        df.rename(columns={"bu": "buy_active_vol", "sd": "sell_active_vol"}, inplace=True)
        df['time'] = pd.to_datetime(df['time'])

        # B. Merge Raw Close
        if df_raw is not None and not df_raw.empty:
            if 'timestamp' in df_raw.columns: df_raw.rename(columns={'timestamp': 'time'}, inplace=True)
            if 'ticker' in df_raw.columns: df_raw.rename(columns={'ticker': 'symbol'}, inplace=True)
            df_raw['time'] = pd.to_datetime(df_raw['time'])
            
            # Merge theo cả Time và Symbol
            df = pd.merge(df, df_raw[['time', 'symbol', 'close']], on=['time', 'symbol'], how='left', suffixes=('', '_raw'))
            df.rename(columns={'close_raw': 'close_raw'}, inplace=True)
        
        if 'close_raw' not in df.columns: df['close_raw'] = df['close']

        # C. Merge Overview (Trading Value)
        df['trading_value'] = np.nan
        if df_overview is not None and not df_overview.empty:
            if 'timestamp' in df_overview.columns: df_overview.rename(columns={'timestamp': 'time'}, inplace=True)
            if 'ticker' in df_overview.columns: df_overview.rename(columns={'ticker': 'symbol'}, inplace=True)
            df_overview['time'] = pd.to_datetime(df_overview['time'])
            
            if 'totalMatchValue' in df_overview.columns:
                df = pd.merge(df, df_overview[['time', 'symbol', 'totalMatchValue']], on=['time', 'symbol'], how='left')
                df['trading_value'] = df['totalMatchValue']

        # D. Fallback & VWAP Calculation (Vectorized with GroupBy)
        # Fallback Trading Value
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df['trading_value'] = df['trading_value'].fillna(0)
        
        mask_missing = df['trading_value'] == 0
        if mask_missing.any():
            df.loc[mask_missing, 'trading_value'] = typical_price.loc[mask_missing] * df.loc[mask_missing, 'volume']

        # Tính VWAP (Rolling theo từng Symbol)
        window = 14
        # Group by Symbol để rolling không bị lẫn lộn giữa các mã
        grouped = df.groupby('symbol')
        pv_rolling = grouped['trading_value'].transform(lambda x: x.rolling(window, min_periods=1).sum())
        vol_rolling = grouped['volume'].transform(lambda x: x.rolling(window, min_periods=1).sum())
        
        df['vwap'] = pv_rolling / vol_rolling.replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(df['close'])

        # E. Save
        cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'close_raw', 'volume', 
                'trading_value', 'vwap', 'buy_active_vol', 'sell_active_vol']
        valid_cols = [c for c in cols if c in df.columns]
        
        # Upsert Batch (pk_cols gồm time và symbol)
        self.upsert_data(df[valid_cols], "fact_daily_bars", ['time', 'symbol'])
