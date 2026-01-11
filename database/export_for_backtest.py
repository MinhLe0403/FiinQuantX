import sys
import os
import pandas as pd
import argparse
from sqlalchemy import create_engine, text
from datetime import datetime

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL
# Thử import list VN30 để hỗ trợ export theo nhóm
try:
    from etl.market import MarketLoader
    has_market_loader = True
except ImportError:
    has_market_loader = False

def export_backtest_data(symbols, start_date='2020-01-01', output_format='csv'):
    """
    Xuất dữ liệu hợp nhất (Price + Flow + Valuation) ra file để Backtest.
    """
    if not symbols:
        print("❌ Vui lòng cung cấp danh sách mã cổ phiếu.")
        return

    print(f"🚀 Đang chuẩn bị dữ liệu cho {len(symbols)} mã...")
    print(f"📅 Từ ngày: {start_date}")
    
    engine = create_engine(DATABASE_URL)
    
    # Tạo thư mục output nếu chưa có
    output_dir = os.path.join(project_root, 'data_exports')
    os.makedirs(output_dir, exist_ok=True)

    # Query hợp nhất dữ liệu (JOIN 3 bảng quan trọng nhất)
    # Chúng ta lấy các trường quan trọng nhất cho Backtest
    query = text("""
        SELECT 
            p.time, 
            p.symbol, 
            p.open, p.high, p.low, p.close,
            COALESCE(p.close_raw, p.close) AS close_raw,
            p.volume,
            p.trading_value,
            p.buy_active_vol, 
            p.sell_active_vol,
            p.vwap,

            f.share_issue,

            -- =======================
            -- Investor Value Flows
            -- =======================
            -- Foreign
            COALESCE(f.foreign_buy_val, 0) AS foreign_buy_val,
            COALESCE(f.foreign_sell_val, 0) AS foreign_sell_val,
                     
            -- FOREIGN DETAILED (Mới)
            COALESCE(f.foreign_ind_buy_val, 0) AS foreign_ind_buy_val,
            COALESCE(f.foreign_ind_sell_val, 0) AS foreign_ind_sell_val,
                     
            COALESCE(f.foreign_inst_buy_val, 0) AS foreign_inst_buy_val,
            COALESCE(f.foreign_inst_sell_val, 0) AS foreign_inst_sell_val,

            -- Proprietary (Prop)
            COALESCE(f.prop_buy_val, 0) AS prop_buy_val,
            COALESCE(f.prop_sell_val, 0) AS prop_sell_val,

            -- Local Individual
            COALESCE(f.local_ind_buy_val, 0) AS local_ind_buy_val,
            COALESCE(f.local_ind_sell_val, 0) AS local_ind_sell_val,

            -- Local Institution
            COALESCE(f.local_inst_buy_val, 0) AS local_inst_buy_val,
            COALESCE(f.local_inst_sell_val, 0) AS local_inst_sell_val,

            -- =======================
            -- Investor Volume Flows
            -- =======================
            -- Foreign
            COALESCE(f.foreign_buy_vol, 0) AS foreign_buy_vol,
            COALESCE(f.foreign_sell_vol, 0) AS foreign_sell_vol,

            -- FOREIGN DETAILED (Mới)
            COALESCE(f.foreign_ind_buy_vol, 0) AS foreign_ind_buy_vol,
            COALESCE(f.foreign_ind_sell_vol, 0) AS foreign_ind_sell_vol,
                     
            COALESCE(f.foreign_inst_buy_vol, 0) AS foreign_inst_buy_vol,
            COALESCE(f.foreign_inst_sell_vol, 0) AS foreign_inst_sell_vol,

            -- Proprietary (Prop)
            COALESCE(f.prop_buy_vol, 0) AS prop_buy_vol,
            COALESCE(f.prop_sell_vol, 0) AS prop_sell_vol,

            -- Local Individual
            COALESCE(f.local_ind_buy_vol, 0) AS local_ind_buy_vol,
            COALESCE(f.local_ind_sell_vol, 0) AS local_ind_sell_vol,

            -- Local Institution
            COALESCE(f.local_inst_buy_vol, 0) AS local_inst_buy_vol,
            COALESCE(f.local_inst_sell_vol, 0) AS local_inst_sell_vol,
                    
            -- =======================
            -- Net Value (Buy - Sell)
            -- =======================
            (COALESCE(f.foreign_buy_val, 0)     - COALESCE(f.foreign_sell_val, 0))     AS foreign_net_val,
            (COALESCE(f.foreign_ind_buy_val, 0) - COALESCE(f.foreign_ind_sell_val, 0)) AS foreign_ind_net_val,
            (COALESCE(f.foreign_inst_buy_val, 0) - COALESCE(f.foreign_inst_sell_val, 0)) AS foreign_inst_net_val,
            (COALESCE(f.prop_buy_val, 0)        - COALESCE(f.prop_sell_val, 0))        AS prop_net_val,
            (COALESCE(f.local_inst_buy_val, 0)  - COALESCE(f.local_inst_sell_val, 0))  AS local_inst_net_val,
            (COALESCE(f.local_ind_buy_val, 0)   - COALESCE(f.local_ind_sell_val, 0))   AS local_ind_net_val,

            -- =======================
            -- Net Volume (BuyVol - SellVol)
            -- =======================
            (COALESCE(f.foreign_buy_vol, 0)     - COALESCE(f.foreign_sell_vol, 0))     AS foreign_net_vol,
            (COALESCE(f.foreign_ind_buy_vol, 0) - COALESCE(f.foreign_ind_sell_vol, 0)) AS foreign_ind_net_vol,
            (COALESCE(f.foreign_inst_buy_vol, 0) - COALESCE(f.foreign_inst_sell_vol, 0)) AS foreign_inst_net_vol,
            (COALESCE(f.prop_buy_vol, 0)        - COALESCE(f.prop_sell_vol, 0))        AS prop_net_vol,
            (COALESCE(f.local_inst_buy_vol, 0)  - COALESCE(f.local_inst_sell_vol, 0))  AS local_inst_net_vol,
            (COALESCE(f.local_ind_buy_vol, 0)   - COALESCE(f.local_ind_sell_vol, 0))   AS local_ind_net_vol,

            -- =======================
            -- Total Volume (BuyVol + SellVol)
            -- =======================
            (COALESCE(f.foreign_buy_vol, 0) + COALESCE(f.foreign_sell_vol, 0)) AS foreign_total_vol,
            (COALESCE(f.foreign_ind_buy_vol, 0) + COALESCE(f.foreign_ind_sell_vol, 0)) AS foreign_ind_total_vol,
            (COALESCE(f.foreign_inst_buy_vol, 0) + COALESCE(f.foreign_inst_sell_vol, 0)) AS foreign_inst_total_vol,
            (COALESCE(f.prop_buy_vol, 0)    + COALESCE(f.prop_sell_vol, 0))    AS prop_total_vol,
            (COALESCE(f.local_inst_buy_vol, 0) + COALESCE(f.local_inst_sell_vol, 0)) AS local_inst_total_vol,
            (COALESCE(f.local_ind_buy_vol, 0) + COALESCE(f.local_ind_sell_vol, 0)) AS local_ind_total_vol,

            -- =======================
            -- Total Value (Buy + Sell)
            -- =======================
            (COALESCE(f.foreign_buy_val, 0) + COALESCE(f.foreign_sell_val, 0)) AS foreign_total_val,
            (COALESCE(f.foreign_ind_buy_val, 0) + COALESCE(f.foreign_ind_sell_val, 0)) AS foreign_ind_total_val,
            (COALESCE(f.foreign_inst_buy_val, 0) + COALESCE(f.foreign_inst_sell_val, 0)) AS foreign_inst_total_val,
            (COALESCE(f.prop_buy_val, 0)    + COALESCE(f.prop_sell_val, 0))    AS prop_total_val,
            (COALESCE(f.local_inst_buy_val, 0) + COALESCE(f.local_inst_sell_val, 0)) AS local_inst_total_val,
            (COALESCE(f.local_ind_buy_val, 0) + COALESCE(f.local_ind_sell_val, 0)) AS local_ind_total_val,

            -- =======================
            -- Valuations
            -- =======================
            v.pe, 
            v.pb,
            v.market_cap

        FROM fact_daily_bars p
        LEFT JOIN fact_investor_flows_daily f ON p.time = f.time AND p.symbol = f.symbol
        LEFT JOIN fact_valuation_daily v ON p.time = v.time AND p.symbol = v.symbol
        
        WHERE p.symbol IN :symbols
          AND p.time >= :start_date
        ORDER BY p.symbol, p.time ASC
    """)

    try:
        # Chuyển list symbols thành tuple để SQL hiểu
        df = pd.read_sql(query, engine, params={"symbols": tuple(symbols), "start_date": start_date})
        
        if df.empty:
            print("⚠️ Không tìm thấy dữ liệu nào.")
            return

        # Xử lý làm sạch cơ bản cho Backtest
        df.fillna(0, inplace=True) # Fill 0 cho các giá trị flow bị thiếu
        df['time'] = pd.to_datetime(df['time'])

        # Xuất ra file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if len(symbols) == 1:
            file_name = f"{symbols[0]}_backtest_{timestamp}"
        else:
            file_name = f"MultiStocks_{len(symbols)}_backtest_{timestamp}"

        file_path = os.path.join(output_dir, f"{file_name}.{output_format}")

        if output_format == 'csv':
            df.to_csv(file_path, index=False)
        elif output_format == 'parquet':
            df.to_parquet(file_path, index=False)
        elif output_format == 'excel':
            df.to_excel(file_path + ".xlsx", index=False)

        print(f"✅ Xuất thành công: {file_path}")
        print(f"📊 Tổng số dòng: {len(df)}")
        print("💡 Gợi ý: Dùng thư viện 'Backtrader' hoặc 'VectorBT' để load file này.")

    except Exception as e:
        print(f"❌ Lỗi xuất dữ liệu: {e}")

if __name__ == "__main__":
    # --- GIAO DIỆN DÒNG LỆNH ĐƠN GIẢN ---
    print("--- CÔNG CỤ XUẤT DỮ LIỆU BACKTEST ---")
    print("1. Xuất 1 mã cụ thể")
    print("2. Xuất rổ VN30")
    print("3. Xuất toàn bộ thị trường (Cẩn thận file lớn)")
    
    choice = input("Chọn (1/2/3): ").strip()
    
    symbols = []
    
    if choice == '1':
        s = input("Nhập mã (VD: FPT): ").upper().strip()
        symbols = [s]
    elif choice == '2':
        if has_market_loader:
            loader = MarketLoader()
            symbols = loader.get_tickers_from_group("VN30")
            # Thêm chính chỉ số VN30 vào để so sánh (Benchmark)
            symbols.append("VN30") 
        else:
            print("⚠️ Chưa có module MarketLoader, dùng danh sách mẫu.")
            symbols = ["FPT", "MWG", "HPG", "TCB", "VPB"] # Ví dụ
    elif choice == '3':
        print("⚠️ Cảnh báo: File sẽ rất nặng (>500MB).")
        confirm = input("Tiếp tục? (y/n): ")
        if confirm.lower() == 'y':
            # Lấy tất cả mã trong bảng daily_bars
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                symbols = pd.read_sql("SELECT DISTINCT symbol FROM fact_daily_bars", conn)['symbol'].tolist()

    if symbols:
        fmt = input("Định dạng (csv/parquet): ").lower().strip() or 'csv'
        start = input("Từ ngày (YYYY-MM-DD) [Enter lấy từ 2020]: ").strip() or '2020-01-01'
        export_backtest_data(symbols, start_date=start, output_format=fmt)