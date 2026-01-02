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
        self.sleep()

    def _process_and_save(self, df, symbol):
        df.fillna(0, inplace=True)
        
        time_col = next((c for c in df.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
        if not time_col: return
        
        df.rename(columns={time_col: 'time', "code": "symbol", "shareIssue": "share_issue"}, inplace=True)
        df['time'] = pd.to_datetime(df['time'])
        df['symbol'] = symbol # Gán symbol vì API trả về có thể thiếu nếu gọi lẻ

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
        time_col = next((c for c in df.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
        if not time_col: return
        
        df.rename(columns={time_col: 'time', "code": "symbol", "shareIssue": "share_issue"}, inplace=True)
        df['time'] = pd.to_datetime(df['time'])
        
        # Không gán df['symbol'] cứng, vì batch có nhiều mã, API đã có cột symbol/code rồi

        self._map_columns_and_save(df)

    # --- HÀM MAPPING CHUNG (DRY Principle) ---
    def _map_columns_and_save(self, df):
        """Logic mapping cột dùng chung cho cả Single và Batch"""
        
        # 1. MAPPING CHI TIẾT (FOREIGN DETAILED)
        # A. Foreign Individual
        df['foreign_ind_buy_val'] = df.get('foreignIndividualBuyTradingMatchValue', 0)
        df['foreign_ind_sell_val'] = df.get('foreignIndividualSellTradingMatchValue', 0)
        df['foreign_ind_buy_vol'] = df.get('foreignIndividualBuyTradingMatchVolume', 0)
        df['foreign_ind_sell_vol'] = df.get('foreignIndividualSellTradingMatchVolume', 0)
        
        # B. Foreign Institutional
        df['foreign_inst_buy_val'] = df.get('foreignInstitutionalBuyTradingMatchValue', 0)
        df['foreign_inst_sell_val'] = df.get('foreignInstitutionalSellTradingMatchValue', 0)
        df['foreign_inst_buy_vol'] = df.get('foreignInstitutionalBuyTradingMatchVolume', 0)
        df['foreign_inst_sell_vol'] = df.get('foreignInstitutionalSellTradingMatchVolume', 0)

        # 2. TÍNH TOÁN DỮ LIỆU TỔNG HỢP (FOREIGN TOTAL)
        # Cộng dồn từ chi tiết để đảm bảo khớp số liệu
        df['foreign_buy_val'] = df['foreign_ind_buy_val'] + df['foreign_inst_buy_val']
        df['foreign_sell_val'] = df['foreign_ind_sell_val'] + df['foreign_inst_sell_val']
        df['foreign_buy_vol'] = df['foreign_ind_buy_vol'] + df['foreign_inst_buy_vol']
        df['foreign_sell_vol'] = df['foreign_ind_sell_vol'] + df['foreign_inst_sell_vol']
        
        # 3. CÁC NHÓM KHÁC (PROP, LOCAL IND, LOCAL INST)
        # Prop
        df['prop_buy_val'] = df.get('proprietaryTotalMatchBuyTradeValue', 0)
        df['prop_sell_val'] = df.get('proprietaryTotalMatchSellTradeValue', 0)
        df['prop_buy_vol'] = df.get('proprietaryTotalMatchBuyTradeVolume', 0)
        df['prop_sell_vol'] = df.get('proprietaryTotalMatchSellTradeVolume', 0)

        # Local Ind
        df['local_ind_buy_val'] = df.get('localIndividualBuyMatchValue', 0)
        df['local_ind_sell_val'] = df.get('localIndividualSellMatchValue', 0)
        df['local_ind_buy_vol'] = df.get('localIndividualBuyMatchVolume', 0)
        df['local_ind_sell_vol'] = df.get('localIndividualSellMatchVolume', 0)
        
        # Local Inst
        df['local_inst_buy_val'] = df.get('localInstitutionalBuyMatchValue', 0)
        df['local_inst_sell_val'] = df.get('localInstitutionalSellMatchValue', 0)
        df['local_inst_buy_vol'] = df.get('localInstitutionalBuyMatchVolume', 0)
        df['local_inst_sell_vol'] = df.get('localInstitutionalSellMatchVolume', 0)

        # 4. TÍNH NET VALUE/VOLUME
        groups = ['foreign', 'prop', 'local_ind', 'local_inst']
        for g in groups:
            df[f'{g}_net_val'] = df[f'{g}_buy_val'] - df[f'{g}_sell_val']
            df[f'{g}_net_vol'] = df[f'{g}_buy_vol'] - df[f'{g}_sell_vol']

        # 5. CHỌN CỘT ĐỂ LƯU
        cols = ['time', 'symbol', 'share_issue']
        
        # Cột tổng hợp
        for g in groups:
            cols.extend([f'{g}_buy_val', f'{g}_sell_val', f'{g}_net_val', f'{g}_buy_vol', f'{g}_sell_vol', f'{g}_net_vol'])
            
        # Cột chi tiết mới
        cols.extend([
            'foreign_ind_buy_val', 'foreign_ind_sell_val', 'foreign_ind_buy_vol', 'foreign_ind_sell_vol',
            'foreign_inst_buy_val', 'foreign_inst_sell_val', 'foreign_inst_buy_vol', 'foreign_inst_sell_vol'
        ])
        
        # Lọc cột hợp lệ & Upsert
        valid_cols = [c for c in cols if c in df.columns]
        self.upsert_data(df[valid_cols], "fact_investor_flows_daily", ['time', 'symbol'])