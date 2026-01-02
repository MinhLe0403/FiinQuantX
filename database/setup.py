import sys
import os
from sqlalchemy import create_engine, text

# --- TỰ ĐỘNG TÌM CONFIG ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

try:
    from config import DATABASE_URL
except ImportError:
    print("❌ Lỗi: Không tìm thấy file config.py!")
    sys.exit(1)

# --- 1. SCHEMA CHÍNH (Dành cho tạo mới) ---
SCHEMA_SQL = """
-- 1. Danh mục cổ phiếu
CREATE TABLE IF NOT EXISTS dim_stocks (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name VARCHAR(255),
    exchange VARCHAR(20),
    sector VARCHAR(100),
    industry VARCHAR(255),
    type VARCHAR(20) DEFAULT 'STOCK', -- Cột mới
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng Mapping Cổ phiếu - Chỉ số (MỚI)
CREATE TABLE IF NOT EXISTS map_stock_index (
    symbol VARCHAR(20) NOT NULL,
    index_code VARCHAR(20) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, index_code)
);

-- 3. Giá & Khối lượng
CREATE TABLE IF NOT EXISTS fact_daily_bars (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(15, 2), high NUMERIC(15, 2), low NUMERIC(15, 2), close NUMERIC(15, 2),
    close_raw NUMERIC(15, 2),
    volume BIGINT,
    trading_value NUMERIC(25, 2),
    vwap NUMERIC(15, 2),
    buy_active_vol BIGINT, sell_active_vol BIGINT,
    PRIMARY KEY (time, symbol)
);

-- 4. Dòng tiền Nhà đầu tư
CREATE TABLE IF NOT EXISTS fact_investor_flows_daily (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    share_issue NUMERIC(20, 2),
    
    foreign_buy_val NUMERIC(25, 2), foreign_sell_val NUMERIC(25, 2), foreign_net_val NUMERIC(25, 2),
    foreign_buy_vol BIGINT,         foreign_sell_vol BIGINT,         foreign_net_vol BIGINT,

    foreign_ind_buy_val NUMERIC(25, 2), foreign_ind_sell_val NUMERIC(25, 2), foreign_ind_net_val NUMERIC(25, 2),
    foreign_ind_buy_vol BIGINT, foreign_ind_sell_vol BIGINT, foreign_ind_net_vol BIGINT,
        
    foreign_inst_buy_vol BIGINT, foreign_inst_sell_vol BIGINT, foreign_inst_net_vol BIGINT,
    foreign_inst_buy_val NUMERIC(25, 2), foreign_inst_sell_val NUMERIC(25, 2), foreign_inst_net_val NUMERIC(25, 2),
    
    prop_buy_val NUMERIC(25, 2),    prop_sell_val NUMERIC(25, 2),    prop_net_val NUMERIC(25, 2),
    prop_buy_vol BIGINT,            prop_sell_vol BIGINT,            prop_net_vol BIGINT,
    
    local_ind_buy_val NUMERIC(25, 2), local_ind_sell_val NUMERIC(25, 2), local_ind_net_val NUMERIC(25, 2),
    local_ind_buy_vol BIGINT,         local_ind_sell_vol BIGINT,         local_ind_net_vol BIGINT,
    
    local_inst_buy_val NUMERIC(25, 2), local_inst_sell_val NUMERIC(25, 2), local_inst_net_val NUMERIC(25, 2),
    local_inst_buy_vol BIGINT,         local_inst_sell_vol BIGINT,         local_inst_net_vol BIGINT,
    
    PRIMARY KEY (time, symbol)
);

-- 5. Định giá & Vốn hóa
CREATE TABLE IF NOT EXISTS fact_valuation_daily (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    pe NUMERIC(10, 2), 
    pb NUMERIC(10, 2), 
    market_cap NUMERIC(25, 2),
    PRIMARY KEY (time, symbol)
);

-- 6. Chỉ số Tài chính
CREATE TABLE IF NOT EXISTS fact_financial_ratios (
    symbol VARCHAR(20) NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    
    roe NUMERIC(10, 4), roa NUMERIC(10, 4), eps NUMERIC(15, 2), book_value_per_share NUMERIC(15, 2),
    current_ratio NUMERIC(10, 4), debt_to_equity NUMERIC(10, 4), 
    ebit_margin NUMERIC(10, 4), roic NUMERIC(10, 4),
    revenue_growth_yoy NUMERIC(10, 4), ebt_growth_yoy NUMERIC(10, 4),
    nim NUMERIC(10, 4), ldr NUMERIC(10, 4), bad_debt_ratio NUMERIC(10, 4),
    loan_loss_reserves_to_npls NUMERIC(10, 4), loans_growth_yoy NUMERIC(10, 4), 
    deposits_growth_yoy NUMERIC(10, 4), interest_income_growth_yoy NUMERIC(10, 4),
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, year, quarter)
);
"""

# --- 2. HÀM MIGRATION (Nâng cấp cấu trúc cũ) ---
def upgrade_existing_db(conn):
    print("🔄 Kiểm tra và nâng cấp cấu trúc bảng cũ...")
    
    # 2.1 Thêm cột 'type' vào dim_stocks nếu chưa có
    try:
        conn.execute(text("ALTER TABLE dim_stocks ADD COLUMN IF NOT EXISTS type VARCHAR(20) DEFAULT 'STOCK';"))
        print("   ✅ Đã kiểm tra/thêm cột 'type' vào dim_stocks.")
    except Exception as e:
        print(f"   ⚠️ Lỗi update dim_stocks (có thể bỏ qua): {e}")

# --- 3. HÀM CHẠY CHÍNH ---
def run_setup(reset=False):
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Nếu muốn xóa sạch làm lại (Nguy hiểm - Cần confirm)
        if reset:
            print("⚠️ CHẾ ĐỘ RESET: Đang xóa toàn bộ dữ liệu...")
            conn.execute(text("DROP TABLE IF EXISTS map_stock_index CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS fact_investor_flows_daily CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS fact_daily_bars CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS fact_financial_ratios CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS fact_valuation_daily CASCADE;"))
            # Không drop dim_stocks để giữ danh mục nếu muốn, hoặc drop luôn tùy bạn
            conn.execute(text("DROP TABLE IF EXISTS dim_stocks CASCADE;"))
        
        # Tạo bảng (IF NOT EXISTS)
        print("🛠️ Đang khởi tạo cấu trúc bảng...")
        conn.execute(text(SCHEMA_SQL))
        
        # Chạy migration cho bảng cũ
        upgrade_existing_db(conn)
        
        conn.commit()
        print("✅ HOÀN TẤT SETUP DATABASE!")

if __name__ == "__main__":
    # Mặc định chạy chế độ an toàn (không xóa dữ liệu)
    # Muốn xóa sạch: run_setup(reset=True)
    run_setup(reset=False)