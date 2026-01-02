import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text

# --- SETUP ĐƯỜNG DẪN ĐỂ IMPORT CONFIG ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL

def extract_ticker_data(symbol, limit=20, export_csv=False):
    symbol = symbol.upper().strip()
    print(f"\n🔍 ĐANG TRÍCH XUẤT DỮ LIỆU CỦA: {symbol}")
    print("="*60)
    
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
    except Exception as e:
        print(f"❌ Lỗi kết nối Database: {e}")
        return

    # 1. THÔNG TIN CƠ BẢN (DIM_STOCKS & MAPPING)
    print("\n1️⃣  THÔNG TIN CƠ BẢN & PHÂN LOẠI")
    try:
        # Lấy thông tin cơ bản
        query_info = text("SELECT * FROM dim_stocks WHERE symbol = :sym")
        df_info = pd.read_sql(query_info, conn, params={"sym": symbol})
        
        # Lấy thông tin Index (nếu có)
        query_idx = text("SELECT index_code FROM map_stock_index WHERE symbol = :sym")
        df_idx = pd.read_sql(query_idx, conn, params={"sym": symbol})
        
        if not df_info.empty:
            info = df_info.iloc[0]
            print(f"   - Tên: {info['company_name']}")
            print(f"   - Sàn: {info['exchange']} | Ngành: {info['sector']}")
            print(f"   - Loại: {info.get('type', 'N/A')}")
            
            if not df_idx.empty:
                indices = df_idx['index_code'].tolist()
                print(f"   - Thuộc các bộ chỉ số: {', '.join(indices)}")
            else:
                print("   - Chưa thuộc bộ chỉ số nào (hoặc chưa map).")
        else:
            print("   ⚠️ Không tìm thấy thông tin trong bảng dim_stocks.")
    except Exception as e: print(f"Lỗi Info: {e}")

    # 2. DỮ LIỆU GIÁ & KHỐI LƯỢNG (FACT_DAILY_BARS)
    print(f"\n2️⃣  DỮ LIỆU GIÁ (Top {limit} phiên gần nhất)")
    try:
        query_price = text("""
            SELECT time, close, volume, trading_value, vwap, buy_active_vol, sell_active_vol 
            FROM fact_daily_bars 
            WHERE symbol = :sym 
            ORDER BY time DESC 
            LIMIT :lim
        """)
        df_price = pd.read_sql(query_price, conn, params={"sym": symbol, "lim": limit})
        
        if not df_price.empty:
            # Format số cho dễ nhìn
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1000)
            print(df_price.to_string(index=False))
        else:
            print("   ❌ Không có dữ liệu giá.")
    except Exception as e: print(f"Lỗi Price: {e}")

    # 3. DỮ LIỆU DÒNG TIỀN (FACT_INVESTOR_FLOWS_DAILY)
    print(f"\n3️⃣  DỮ LIỆU DÒNG TIỀN (Top {limit} phiên gần nhất)")
    try:
        query_flow = text("""
            SELECT time, 
                   foreign_buy_val - foreign_sell_val as nn_net,
                   prop_buy_val - prop_sell_val as td_net,
                   local_ind_buy_val - local_ind_sell_val as cn_net,
                   local_inst_buy_val - local_inst_sell_val as tc_net, foreign_ind_buy_val - foreign_ind_sell_val as hihi_net,
            FROM fact_investor_flows_daily
            WHERE symbol = :sym 
            ORDER BY time DESC 
            LIMIT :lim
        """)
        df_flow = pd.read_sql(query_flow, conn, params={"sym": symbol, "lim": limit})
        
        if not df_flow.empty:
            # Chia cho 1 tỷ để dễ nhìn
            cols = ['nn_net', 'td_net', 'cn_net', 'tc_net']
            for c in cols: df_flow[c] = round(df_flow[c] / 1e9, 2)
            print(f"   (Đơn vị: Tỷ VNĐ)")
            print(df_flow.to_string(index=False))
        else:
            print("   ❌ Không có dữ liệu dòng tiền.")
    except Exception as e: print(f"Lỗi Flow: {e}")

    # 4. DỮ LIỆU TÀI CHÍNH & ĐỊNH GIÁ
    print(f"\n4️⃣  TÀI CHÍNH & ĐỊNH GIÁ")
    try:
        # Lấy Valuation gần nhất
        query_val = text("SELECT time, pe, pb, market_cap FROM fact_valuation_daily WHERE symbol = :sym ORDER BY time DESC LIMIT 1")
        df_val = pd.read_sql(query_val, conn, params={"sym": symbol})
        
        if not df_val.empty:
            val = df_val.iloc[0]
            mcap = val['market_cap'] / 1e9 if val['market_cap'] else 0
            print(f"   - Ngày cập nhật: {val['time']}")
            print(f"   - P/E: {val['pe']} | P/B: {val['pb']}")
            print(f"   - Vốn hóa: {mcap:,.0f} tỷ")
        
        # Lấy BCTC gần nhất
        query_fin = text("SELECT year, quarter, roe, roa, revenue_growth_yoy, ebt_growth_yoy FROM fact_financial_ratios WHERE symbol = :sym ORDER BY year DESC, quarter DESC LIMIT 1")
        df_fin = pd.read_sql(query_fin, conn, params={"sym": symbol})
        
        if not df_fin.empty:
            fin = df_fin.iloc[0]
            print(f"   - BCTC Quý {fin['quarter']}/{fin['year']}:")
            print(f"     + ROE: {fin['roe']*100:.1f}% | ROA: {fin['roa']*100:.1f}%")
            print(f"     + Tăng trưởng DT: {fin['revenue_growth_yoy']*100:.1f}%")
        else:
            print("   ⚠️ Chưa có dữ liệu BCTC.")

    except Exception as e: print(f"Lỗi Fin: {e}")

    # 5. XUẤT FILE CSV (TÙY CHỌN)
    if export_csv:
        print("\n📂 Đang xuất file CSV...")
        try:
            # Join Price & Flow để xuất file full
            query_full = text("""
                SELECT p.*, f.foreign_buy_val, f.foreign_sell_val, f.prop_buy_val, f.prop_sell_val
                FROM fact_daily_bars p
                LEFT JOIN fact_investor_flows_daily f ON p.time = f.time AND p.symbol = f.symbol
                WHERE p.symbol = :sym ORDER BY p.time DESC
            """)
            df_full = pd.read_sql(query_full, conn, params={"sym": symbol})
            filename = f"{symbol}_data_export.csv"
            df_full.to_csv(filename, index=False)
            print(f"✅ Đã xuất dữ liệu ra file: {filename}")
        except Exception as e:
            print(f"❌ Lỗi xuất CSV: {e}")

    conn.close()
    print("\n" + "="*60)

if __name__ == "__main__":
    ticker = input("Nhập mã cổ phiếu cần kiểm tra (VD: FPT): ")
    if ticker:
        # Tham số thứ 2 là export_csv=True nếu muốn xuất file
        extract_ticker_data(ticker, limit=10, export_csv=False)