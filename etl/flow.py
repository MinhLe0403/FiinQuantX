# etl/flow.py
import pandas as pd
from .base import BaseETL

class FlowLoader(BaseETL):
    # --- SYNC ĐƠN LẺ ---
    def sync(self, symbol, start_date, end_date):
        task = lambda: self.client.PriceStatistics().get_ceilingfloor(
            tickers=[symbol], from_date=start_date, to_date=end_date
        )
        df = self.safe_api_call(task)
        
        if df is not None and not df.empty:
            self._process_and_save(df, symbol)
        else:
            # Debug nếu không có dữ liệu
            pass 
        self.sleep()

    def _process_and_save(self, df, symbol):
        df.fillna(0, inplace=True)
        
        # 1. Tìm cột Time (Quan trọng)
        time_col = next((c for c in df.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
        if not time_col:
            print(f"❌ Flow Error: Không tìm thấy cột thời gian. Cols: {list(df.columns)}")
            return
        
        # 2. Rename chuẩn
        # Lưu ý: API thường trả về 'code', nhưng ta cần map về 'symbol'
        rename_map = {
            time_col: 'time',
            "shareIssue": "share_issue",
            "code": "symbol",   # Trường hợp API trả về 'code'
            "ticker": "symbol"  # Trường hợp API trả về 'ticker'
        }
        df.rename(columns=rename_map, inplace=True)
        
        df['time'] = pd.to_datetime(df['time'])
        
        # 3. Force gán symbol nếu update lẻ (Đề phòng API trả về thiếu cột symbol)
        if 'symbol' not in df.columns:
            df['symbol'] = symbol

        self._map_columns_and_save(df)

    # --- SYNC BATCH ---
    def sync_batch(self, tickers_list, start_date, end_date):
        task = lambda: self.client.PriceStatistics().get_ceilingfloor(
            tickers=tickers_list, from_date=start_date, to_date=end_date
        )
        df = self.safe_api_call(task)
        
        if df is not None and not df.empty:
            self._process_and_save_batch(df)
        self.sleep()

    def _process_and_save_batch(self, df):
        df.fillna(0, inplace=True)
        
        # 1. Tìm cột Time
        time_col = next((c for c in df.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
        if not time_col:
            print(f"❌ Batch Flow Error: Thiếu cột Time. Cols: {list(df.columns)}")
            return
        
        # 2. Rename chuẩn
        rename_map = {
            time_col: 'time',
            "shareIssue": "share_issue",
            "code": "symbol",
            "ticker": "symbol"
        }
        df.rename(columns=rename_map, inplace=True)
        
        df['time'] = pd.to_datetime(df['time'])
        
        # 3. Kiểm tra cột Symbol
        if 'symbol' not in df.columns:
            print(f"❌ Batch Flow Error: Thiếu cột 'symbol'. Cols gốc: {list(df.columns)}")
            return

        self._map_columns_and_save(df)

    # --- HÀM MAPPING CHUNG ---
    def _map_columns_and_save(self, df):
        # 1. Mapping Chi tiết
        df['foreign_ind_buy_val'] = df.get('foreignIndividualBuyTradingMatchValue', 0)
        df['foreign_ind_sell_val'] = df.get('foreignIndividualSellTradingMatchValue', 0)
        df['foreign_ind_buy_vol'] = df.get('foreignIndividualBuyTradingMatchVolume', 0)
        df['foreign_ind_sell_vol'] = df.get('foreignIndividualSellTradingMatchVolume', 0)
        
        df['foreign_inst_buy_val'] = df.get('foreignInstitutionalBuyTradingMatchValue', 0)
        df['foreign_inst_sell_val'] = df.get('foreignInstitutionalSellTradingMatchValue', 0)
        df['foreign_inst_buy_vol'] = df.get('foreignInstitutionalBuyTradingMatchVolume', 0)
        df['foreign_inst_sell_vol'] = df.get('foreignInstitutionalSellTradingMatchVolume', 0)

        # 2. Mapping Tổng hợp
        df['foreign_buy_val'] = df['foreign_ind_buy_val'] + df['foreign_inst_buy_val']
        df['foreign_sell_val'] = df['foreign_ind_sell_val'] + df['foreign_inst_sell_val']
        df['foreign_buy_vol'] = df['foreign_ind_buy_vol'] + df['foreign_inst_buy_vol']
        df['foreign_sell_vol'] = df['foreign_ind_sell_vol'] + df['foreign_inst_sell_vol']
        
        df['prop_buy_val'] = df.get('proprietaryTotalMatchBuyTradeValue', 0)
        df['prop_sell_val'] = df.get('proprietaryTotalMatchSellTradeValue', 0)
        df['prop_buy_vol'] = df.get('proprietaryTotalMatchBuyTradeVolume', 0)
        df['prop_sell_vol'] = df.get('proprietaryTotalMatchSellTradeVolume', 0)

        df['local_ind_buy_val'] = df.get('localIndividualBuyMatchValue', 0)
        df['local_ind_sell_val'] = df.get('localIndividualSellMatchValue', 0)
        df['local_ind_buy_vol'] = df.get('localIndividualBuyMatchVolume', 0)
        df['local_ind_sell_vol'] = df.get('localIndividualSellMatchVolume', 0)
        
        df['local_inst_buy_val'] = df.get('localInstitutionalBuyMatchValue', 0)
        df['local_inst_sell_val'] = df.get('localInstitutionalSellMatchValue', 0)
        df['local_inst_buy_vol'] = df.get('localInstitutionalBuyMatchVolume', 0)
        df['local_inst_sell_vol'] = df.get('localInstitutionalSellMatchVolume', 0)

        # 3. Tính Net
        groups = ['foreign', 'prop', 'local_ind', 'local_inst']
        for g in groups:
            df[f'{g}_net_val'] = df[f'{g}_buy_val'] - df[f'{g}_sell_val']
            df[f'{g}_net_vol'] = df[f'{g}_buy_vol'] - df[f'{g}_sell_vol']

        # 4. Chọn cột  và Upsert
        cols = ['time', 'symbol', 'share_issue']
        for g in groups:
            cols.extend([f'{g}_buy_val', f'{g}_sell_val', f'{g}_net_val', f'{g}_buy_vol', f'{g}_sell_vol', f'{g}_net_vol'])
        
        cols.extend([
            'foreign_ind_buy_val', 'foreign_ind_sell_val', 'foreign_ind_buy_vol', 'foreign_ind_sell_vol',
            'foreign_inst_buy_val', 'foreign_inst_sell_val', 'foreign_inst_buy_vol', 'foreign_inst_sell_vol'
        ])
        
        valid_cols = [c for c in cols if c in df.columns]
        self.upsert_data(df[valid_cols], "fact_investor_flows_daily", ['time', 'symbol'])