# etl/runner.py (Đã sửa)
from datetime import datetime, timedelta
import pandas as pd

from .price import PriceLoader
from .flow import FlowLoader
from .fundamental import FundamentalLoader
from etl.market import MarketLoader
from .index import IndexLoader 
from .constants import ALL_INDICES 

class ETLRunner:
    def __init__(self):
        self.price = PriceLoader()
        self.flow = FlowLoader()
        self.fund = FundamentalLoader()
        self.market = MarketLoader()
        self.index = IndexLoader()

    def get_tickers_by_group(self, group_code):
        """Lấy danh sách mã để cập nhật (bao gồm cả chính Index nếu có)"""
        # 1. Lấy danh sách từ API
        tickers = self.market.get_tickers_from_group(group_code)
        
        # 2. Nếu group_code là 1 Index (VN30, VNINDEX...), hãy chắc chắn nó có trong list
        # Để Batch Job cập nhật cả chỉ số mẹ lẫn cổ phiếu con
        if group_code in ALL_INDICES:
            if group_code not in tickers:
                tickers.insert(0, group_code)
                
            # Lưu Mapping: Chỉ lưu các mã con (len=3) thuộc Index này
            stock_tickers = [t for t in tickers if len(t) == 3]
            self.market.map_stock_to_index(group_code, stock_tickers)
            
        return tickers

    def update_ticker(self, symbol, start_date=None, end_date=None, force_full=False):
        symbol = symbol.upper().strip()
        is_index = symbol in ALL_INDICES # Check kỹ từ constant
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not end_date: end_date = today

        if not start_date:
            # Check DB
            last_date = self.price.get_last_updated_date("fact_daily_bars", symbol)
            row_count = self.price.get_row_count("fact_daily_bars", symbol)
            
            # Logic tải lại: Nếu ít dữ liệu (<200) hoặc force -> Tải 5 năm
            if force_full or not last_date or row_count < 200:
                print(f"⚠️ {symbol}: Full load triggered.")
                start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
                # Chỉ sync basic info nếu là Stock, Index thường ko có basic info qua API này
                if not is_index: 
                    self.market.sync_basic_info_batch(symbol)
            else:
                if str(last_date) >= today: 
                    return True, f"{symbol} đã mới nhất."
                start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"🚀 Updating {symbol} ({'INDEX' if is_index else 'STOCK'}): {start_date} -> {end_date}")

        try:
            if is_index:
                # INDEX: Giá, Active Vol, Flow
                self.index.sync(symbol, start_date, end_date)
            else:
                # STOCK: Full
                self.price.sync(symbol, start_date, end_date)
                self.flow.sync(symbol, start_date, end_date)
                self.fund.sync_valuation(symbol, start_date, end_date)
                
                if force_full or (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days > 360:
                    self.fund.sync_financials(symbol)

            return True, f"Hoàn tất {symbol}"
        except Exception as e:
            return False, f"Lỗi {symbol}: {str(e)}"

    def update_batch_optimized(self, tickers_list, start_date=None, end_date=None, progress_callback=None):
        if not tickers_list: return 0, 0
        
        # Tách Index và Stock
        indices = [t for t in tickers_list if t in ALL_INDICES]
        stocks = [t for t in tickers_list if t not in ALL_INDICES]
        
        success = 0
        errors = 0
        total_steps = len(indices) + (len(stocks) // 20) + 1
        current_step = 0
        
        # 1. Chạy Indices (Loop từng mã)
        for idx_sym in indices:
            if progress_callback: progress_callback(current_step, total_steps, f"Index: {idx_sym}")
            ok, _ = self.update_ticker(idx_sym, start_date, end_date)
            if ok: success += 1
            else: errors += 1
            current_step += 1

        # 2. Chạy Stocks (Batch)
        chunk_size = 100
        for i in range(0, len(stocks), chunk_size):
            chunk = stocks[i:i + chunk_size]
            if progress_callback: progress_callback(current_step, total_steps, f"Batch Stock {i//20+1}")
            
            try:
                self.price.sync_batch(chunk, start_date, end_date)
                self.flow.sync_batch(chunk, start_date, end_date)
                self.fund.sync_valuation_batch(chunk, start_date, end_date)
                # Financials batch: Chỉ chạy nếu cần thiết (ví dụ update dài hạn)
                # Nếu update hàng ngày thì bỏ qua để nhanh
                if start_date and (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days > 300:
                     self.fund.sync_financials_batch(chunk)

                success += len(chunk)
            except: 
                errors += len(chunk)
            current_step += 1
            
        return success, errors
    
        # --- HÀM MỚI: CHỈ CẬP NHẬT DÒNG TIỀN (FLOW ONLY) ---
    def update_flow_only(self, symbol, start_date=None, end_date=None):
        """
        Chỉ chạy module Flow, bỏ qua Price, Fund, Market.
        """
        symbol = symbol.upper().strip()
        is_index = symbol in ALL_INDICES
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not end_date: end_date = today
        if not start_date: 
            # Mặc định lấy 1 năm nếu không chỉ định ngày
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        print(f"💰 Updating FLOW ONLY: {symbol} ({start_date} -> {end_date})")
        
        try:
            if is_index:
                # Index cũng dùng chung logic lấy flow qua PriceStatistics
                self.index.sync_flow_data([symbol], start_date, end_date)
            else:
                self.flow.sync(symbol, start_date, end_date)
            return True, "Done"
        except Exception as e:
            return False, str(e)

    def update_flow_batch_only(self, tickers_list, start_date=None, end_date=None):
        """
        Chạy Batch chỉ cho Dòng tiền (Tốc độ cao)
        """
        if not tickers_list: return
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not end_date: end_date = today
        if not start_date: 
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        print(f"💰 Batch Update Flow: {len(tickers_list)} mã ({start_date} -> {end_date})")
        
        # Chia chunk để gọi API hiệu quả
        chunk_size = 50
        total = len(tickers_list)
        
        for i in range(0, total, chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            print(f"   Processing Flow Batch {i//chunk_size + 1}...")
            try:
                # Gọi hàm sync_batch của module Flow
                self.flow.sync_batch(chunk, start_date, end_date)
            except Exception as e:
                print(f"   ❌ Lỗi batch: {e}")
