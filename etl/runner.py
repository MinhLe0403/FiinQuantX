# etl/runner.py (Đã sửa)
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text

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
        is_index = symbol in ALL_INDICES
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not end_date: end_date = today

        # --- LOGIC TỰ ĐỘNG PHÁT HIỆN CHIA CỔ TỨC ---
        if not start_date:
            # 1. Lấy giá DB
            last_date_db, last_close_db = self.price.get_latest_price_check(symbol)
            row_count = self.price.get_row_count("fact_daily_bars", symbol)
            
            # Mặc định: Nếu chưa có dữ liệu -> Tải Full
            should_full_load = force_full or (last_date_db is None) or (row_count < 200)

            # 2. Nếu đã có dữ liệu, kiểm tra xem có bị lệch giá không (Detect Split)
            if not should_full_load and last_date_db:
                try:
                    # Gọi API lấy giá Adjusted của chính ngày last_date_db
                    check_date_str = last_date_db.strftime("%Y-%m-%d")
                    
                    # Chỉ lấy 1 dòng để check
                    df_check = self.price.client.Fetch_Trading_Data(
                        realtime=False, tickers=[symbol], fields=['close'], 
                        adjusted=True, by='1d', 
                        from_date=check_date_str, to_date=check_date_str
                    ).get_data()
                    
                    if df_check is not None and not df_check.empty:
                        api_close = float(df_check.iloc[0]['close'])
                        
                        # So sánh: Nếu lệch quá 2% (do làm tròn) -> Có chia tách
                        # Ví dụ: DB=50.0, API=45.0 -> Lệch -> Tải lại hết
                        if abs(api_close - last_close_db) / last_close_db > 0.02:
                            print(f"⚡ {symbol}: PHÁT HIỆN CHIA TÁCH/CỔ TỨC (DB: {last_close_db} != API: {api_close})")
                            print("   -> Kích hoạt tải lại toàn bộ lịch sử (Full Load).")
                            should_full_load = True
                        else:
                            # Giá khớp nhau -> Tải nối tiếp từ ngày hôm sau
                            pass
                except Exception as e:
                    print(f"   ⚠️ Không thể kiểm tra giá cũ {symbol}: {e}. Tiếp tục tải nối tiếp.")

            # 3. Thiết lập ngày bắt đầu dựa trên kết quả check
            if should_full_load:
                # Tải lại 5 năm
                start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
                # Nếu là Stock, cập nhật lại cả Basic Info (phòng trường hợp đổi tên/sàn)
                if not is_index: 
                    self.market.sync_basic_info_batch([symbol])
            else:
                if str(last_date_db) >= today: 
                    return True, f"{symbol} dữ liệu đã mới nhất ({last_date_db})."
                # Tải từ ngày tiếp theo
                start_date = (last_date_db + timedelta(days=1)).strftime("%Y-%m-%d")

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

    # --- HÀM MỚI: CHỈ CẬP NHẬT GIÁ (PRICE ONLY - BATCH) ---
    def update_price_batch_only(self, tickers_list, start_date=None, end_date=None, progress_callback=None):
        """
        Chạy Batch chỉ cho Dữ liệu Giá (OHLCV, VWAP, TradingValue).
        Bỏ qua Flow và Fundamental để tối ưu tốc độ.
        """
        if not tickers_list: return 0, 0
        
        # Tách Index và Stock (Vì Index xử lý khác một chút)
        indices = [t for t in tickers_list if t in ALL_INDICES]
        stocks = [t for t in tickers_list if t not in ALL_INDICES]
        
        success = 0
        errors = 0
        
        # 1. Cập nhật Index (Index luôn cần chạy riêng vì logic API khác)
        for idx_sym in indices:
            # IndexLoader đã có hàm sync (lấy cả giá và flow), 
            # nhưng ta chỉ muốn lấy giá. Ta gọi hàm con của nó.
            try:
                self.index.sync_price_data([idx_sym], start_date, end_date)
                success += 1
            except Exception as e:
                print(f"❌ Index Price Error {idx_sym}: {e}")
                errors += 1

        # 2. Cập nhật Stocks (Batch)
        chunk_size = 20 # Batch size an toàn
        total_stocks = len(stocks)
        
        for i in range(0, total_stocks, chunk_size):
            chunk = stocks[i:i + chunk_size]
            
            # Callback hiển thị tiến độ
            if progress_callback:
                current_idx = len(indices) + i
                total_steps = len(indices) + total_stocks
                progress_callback(current_idx, total_steps, f"Price Batch {i//chunk_size + 1}")
            
            print(f"📦 Price Batch {i//chunk_size + 1}: {chunk}")
            
            try:
                # CHỈ GỌI MODULE PRICE
                self.price.sync_batch(chunk, start_date, end_date)
                success += len(chunk)
            except Exception as e:
                print(f"❌ Batch Price Error: {e}")
                errors += len(chunk)
                
        return success, errors


    def check_price_integrity(self, symbol, lookback_days=100):
        """
        Kiểm tra tính toàn vẹn dữ liệu giá tại thời điểm quá khứ (lookback_days).
        Return: bool (True nếu lệch/sai, False nếu khớp/đúng)
        """
        # 1. Xác định khoảng thời gian kiểm tra (Khoảng 3 tháng + 10 ngày trước)
        # Để đảm bảo lấy được điểm dữ liệu nằm TRƯỚC đợt cập nhật gần đây của bạn
        target_date = datetime.now() - timedelta(days=lookback_days)
        target_date_str = target_date.strftime("%Y-%m-%d")

        # 2. Lấy giá đóng cửa tại ngày đó trong DB
        # Lấy bản ghi gần nhất trước hoặc bằng target_date
        try:
            query = text("""
                SELECT time, close 
                FROM fact_daily_bars 
                WHERE symbol = :symbol AND time <= :target_date 
                ORDER BY time DESC LIMIT 1
            """)
            with self.price.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol, "target_date": target_date_str}).fetchone()
                
            if not res:
                return False # Không có dữ liệu cũ để so sánh -> Bỏ qua hoặc coi là đúng
            
            db_date = pd.to_datetime(res[0]).strftime("%Y-%m-%d")
            db_close = float(res[1])

            # 3. Gọi API lấy giá Adjusted tại ĐÚNG ngày đó
            # API FiinQuant cho phép lấy lịch sử chính xác ngày đó
            df_api = self.price.client.Fetch_Trading_Data(
                realtime=False, tickers=[symbol], fields=['close'], 
                adjusted=True, by='1d', 
                from_date=db_date, to_date=db_date
            ).get_data()

            if df_api is None or df_api.empty:
                return False # Không check được -> Bỏ qua

            api_close = float(df_api.iloc[0]['close'])

            # 4. So sánh (Cho phép sai số nhỏ 1% do làm tròn)
            # Nếu lệch > 1% => Có chia tách => Cần tải lại
            if abs(db_close - api_close) / db_close > 0.01:
                print(f"⚠️ {symbol} LỆCH GIÁ ngày {db_date}: DB={db_close} != API={api_close}")
                return True
            
            return False # Khớp nhau -> Không cần làm gì

        except Exception as e:
            print(f"   Lỗi check {symbol}: {e}")
            return False

    def audit_and_fix_vnindex(self):
        """
        Quy trình: 
        1. Lấy mã VNINDEX.
        2. Soi từng mã tại thời điểm 100 ngày trước.
        3. Chỉ tải lại những mã bị lệch.
        """
        print(f"🕵️ BẮT ĐẦU KIỂM TRA DỮ LIỆU VNINDEX (Mốc: ~3 tháng trước)...")
        
        # 1. Lấy danh sách VNINDEX (bao gồm cả chỉ số và cổ phiếu con)
        # Lưu ý: get_tickers_by_group đã xử lý việc lấy mã con
        tickers = self.get_tickers_by_group("VNINDEX")
        # Lọc chỉ lấy cổ phiếu (bỏ qua mã index VNINDEX vì nó ít khi điều chỉnh giá quá khứ)
        stock_tickers = [t for t in tickers if len(t) == 3]
        print(f"📋 Danh sách kiểm tra: {len(stock_tickers)} mã.")
        
        re_download_list = []
        
        # 2. Vòng lặp kiểm tra
        for i, sym in enumerate(stock_tickers):
            print(f"   Checking {sym} ({i+1}/{len(stock_tickers)})...", end="\r")
            
            # Kiểm tra lệch giá tại mốc 100 ngày trước
            is_corrupted = self.check_price_integrity(sym, lookback_days=200)
            
            if is_corrupted:
                re_download_list.append(sym)

        print(f"\n\n📊 KẾT QUẢ KIỂM TRA:")
        print(f"   ✅ Khớp dữ liệu (Bỏ qua): {len(stock_tickers) - len(re_download_list)} mã")
        print(f"   ❌ Lệch dữ liệu (Cần tải lại): {len(re_download_list)} mã")
        
        if re_download_list:
            print(f"   -> Danh sách: {re_download_list}")
            print("\n🚀 ĐANG TẢI LẠI TOÀN BỘ (5 NĂM) CHO CÁC MÃ LỖI...")
            
            # 3. Chỉ chạy cập nhật cho danh sách lỗi
            today = datetime.now().strftime("%Y-%m-%d")
            start_5y = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
            
            # Gọi hàm update price batch (chỉ lấy giá để nhanh)
            s, e = self.update_price_batch_only(re_download_list, start_date=start_5y, end_date=today)
            
            print(f"✅ Đã sửa xong {s} mã.")
        else:
            print("\n🎉 Tuyệt vời! Không có mã nào bị lệch giá do chia cổ tức.")