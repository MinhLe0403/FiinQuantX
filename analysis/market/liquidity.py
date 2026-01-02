import pandas as pd
import numpy as np
from sqlalchemy import text

class LiquidityModule:
    def __init__(self, db_engine):
        self.engine = db_engine

    def get_cashflow_rotation(self):
        """
        Phân tích dòng tiền luân chuyển (Rotation) - Phiên bản "Bất tử" (Robust)
        Tự động lấy Share Issue gần nhất nếu dữ liệu hôm nay bị thiếu.
        """
        query = text("""
            WITH latest_trading_day AS (
                SELECT MAX(time) as t_max FROM fact_daily_bars
            ),
            
            -- 1. KỸ THUẬT FILL-FORWARD: Lấy số lượng cổ phiếu lưu hành MỚI NHẤT hiện có trong DB
            latest_shares AS (
                SELECT DISTINCT ON (symbol) 
                    symbol, 
                    share_issue 
                FROM fact_investor_flows_daily 
                WHERE share_issue IS NOT NULL AND share_issue > 0
                ORDER BY symbol, time DESC
            ),
            
            -- 2. Lấy dữ liệu giao dịch phiên gần nhất
            stock_snapshot AS (
                SELECT 
                    f.symbol, 
                    f.trading_value, 
                    f.close,
                    -- Join với bảng shares đã fill
                    COALESCE(s.share_issue, 0) as shares
                FROM fact_daily_bars f
                LEFT JOIN latest_shares s ON f.symbol = s.symbol
                WHERE f.time = (SELECT t_max FROM latest_trading_day)
                AND f.trading_value > 0 -- Chỉ xét mã có thanh khoản
            ),
            
            -- 3. Tính toán Vốn hóa (Market Cap) ước tính
            calc_cap AS (
                SELECT 
                    symbol, 
                    trading_value,
                    (close * shares) as raw_market_cap
                FROM stock_snapshot
            ),
            
            -- 4. Phân nhóm (Large, Mid, Small) dựa trên phân vị (Percentile)
            ranked_stocks AS (
                SELECT 
                    symbol, 
                    trading_value,
                    raw_market_cap,
                    PERCENT_RANK() OVER (ORDER BY raw_market_cap DESC) as pct_rank
                FROM calc_cap
                WHERE raw_market_cap > 0 -- Chỉ phân nhóm những mã tính được vốn hóa
            ),
            grouped AS (
                SELECT 
                    symbol, 
                    trading_value,
                    CASE 
                        WHEN pct_rank <= 0.10 THEN 'Large Cap (Vốn hóa lớn)' -- Top 10%
                        WHEN pct_rank <= 0.40 THEN 'Mid Cap (Vừa)'           -- Next 30%
                        ELSE 'Small Cap (Nhỏ)'                               -- Rest 60%
                    END as cap_group
                FROM ranked_stocks
            )
            
            -- 5. Tổng hợp dòng tiền
            SELECT 
                cap_group, 
                SUM(trading_value) as total_val,
                COUNT(*) as count
            FROM grouped
            GROUP BY cap_group
            ORDER BY total_val DESC
        """)
        
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            print(f"Cashflow Rotation Error: {e}")
            return pd.DataFrame()
        
    def get_quant_metrics(self, symbol="VNINDEX", days=100):
        """
        🔥 MODULE ULTRA-QUANT: Tính toán các chỉ số vi mô & dòng tiền chuyên sâu
        Đáp ứng tiêu chuẩn: Liquidity Dyn, Microstructure, Volatility Joint.
        """
        # 1. Fetch Data (Cần lấy cả Buy/Sell Active và VWAP)
        query = text(f"""
            SELECT 
                time, open, high, low, close, volume, 
                trading_value, 
                buy_active_vol, sell_active_vol, 
                vwap
            FROM fact_daily_bars
            WHERE symbol = :symbol
            ORDER BY time ASC
        """)
        
        try:
            df = pd.read_sql(query, self.engine, params={"symbol": symbol})
            if df.empty or len(df) < 50: return None
            
            # --- PRE-CALCULATION (Chuẩn bị dữ liệu) ---
            window_short = 5
            window_med = 20
            
            # Tính Volatility (ATR)
            df['tr'] = np.maximum(df['high'] - df['low'], 
                       np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                  abs(df['low'] - df['close'].shift(1))))
            df['atr'] = df['tr'].rolling(window_med).mean()
            df['atr_pct'] = df['atr'] / df['close']
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # ==============================================================
            # KHỐI 1: LIQUIDITY DYNAMICS (Động lực thanh khoản)
            # ==============================================================
            # 1.1. Liquidity Shock (Z-Score của Value)
            val_mean = df['trading_value'].rolling(window_med).mean()
            val_std = df['trading_value'].rolling(window_med).std()
            liquidity_z = (last['trading_value'] - val_mean.iloc[-1]) / val_std.iloc[-1]
            
            # 1.2. Liquidity Expansion Rate (Tốc độ mở rộng tiền)
            liq_expansion = last['trading_value'] / val_mean.iloc[-1]
            
            # Trạng thái Thanh khoản
            liq_status = "Bình thường"
            if liquidity_z > 2.0: liq_status = "ĐỘT BIẾN (SHOCK)"
            elif liquidity_z < -1.5: liq_status = "CẠN KIỆT (DROUGHT)"
            elif liq_expansion > 1.2: liq_status = "Đang mở rộng"

            # ==============================================================
            # KHỐI 2: MICROSTRUCTURE (Cấu trúc Vi mô - Cực quan trọng)
            # ==============================================================
            # 2.1. Buying/Selling Pressure (Lực Mua/Bán Chủ động)
            # Nếu DB chưa có Active Vol, ta dùng xấp xỉ: (Close-Low)/(High-Low)
            buy_vol = last['buy_active_vol'] if last['buy_active_vol'] else 0
            sell_vol = last['sell_active_vol'] if last['sell_active_vol'] else 0
            
            # Order Imbalance (Mất cân bằng cung cầu)
            # Dương = Phe Mua thắng thế, Âm = Phe Bán thắng
            total_active = buy_vol + sell_vol
            order_imbalance = (buy_vol - sell_vol) / total_active if total_active > 0 else 0
            
            # 2.2. Market Pressure (Áp lực so với giá vốn VWAP)
            # VWAP Deviation: Giá đang bị kéo xa khỏi giá vốn bao nhiêu lần ATR?
            # > +2 ATR: Quá mua (Over-extended) -> Dễ chỉnh
            # < -2 ATR: Quá bán (Deep discount) -> Dễ hồi
            vwap_dev = (last['close'] - last['vwap']) / last['atr'] if last['vwap'] else 0
            
            
            # ==============================================================
            # KHỐI 3: SHORT-TERM FLOW MOMENTUM (Gia tốc dòng tiền)
            # ==============================================================
            # Money Flow Index (Simplified): Value * (1 nếu tăng, -1 nếu giảm)
            df['money_flow'] = df['trading_value'] * np.where(df['close'] > df['close'].shift(1), 1, -1)
            
            # Flow Acceleration (Gia tốc): Flow 3 ngày / Flow 10 ngày
            flow_3d = df['money_flow'].rolling(3).sum().iloc[-1]
            flow_10d = df['money_flow'].rolling(10).sum().iloc[-1]
            
            flow_accel = flow_3d / abs(flow_10d) if flow_10d != 0 else 0
            
            
            # ==============================================================
            # KHỐI 4: VOLATILITY REGIME (Chế độ biến động)
            # ==============================================================
            # Dùng Percentile của ATR% trong 1 năm qua
            atr_history = df['atr_pct'].tail(250)
            atr_rank = atr_history.rank(pct=True).iloc[-1]
            
            vol_regime = "NEUTRAL"
            if atr_rank > 0.8: vol_regime = "HIGH VOLATILITY (Cẩn thận)" # Rủi ro cao
            elif atr_rank < 0.2: vol_regime = "LOW VOLATILITY (Nén)" # Sắp có biến
            
            
            # --- TỔNG HỢP KẾT QUẢ ---
            return {
                # Liquidity
                "liq_z_score": round(liquidity_z, 2),
                "liq_status": liq_status,
                
                # Microstructure
                "imbalance": round(order_imbalance * 100, 1), # %
                "vwap_dev": round(vwap_dev, 2), # Đơn vị ATR
                
                # Momentum
                "flow_accel": round(flow_accel, 2),
                
                # Volatility
                "vol_rank": round(atr_rank * 100, 0),
                "vol_regime": vol_regime,
                
                # Raw Values (để vẽ chart nếu cần)
                "buy_active": buy_vol,
                "sell_active": sell_vol
            }

        except Exception as e:
            print(f"Quant Metrics Error: {e}")
            return None
        
    def _normalize_score(self, value, min_v=-3, max_v=3):
        """Helper: Quy đổi Z-Score sang thang 0-100 (Sigmoid-like clamping)"""
        # Clamp giá trị trong khoảng [min, max]
        clamped = max(min(value, max_v), min_v)
        # Map linear sang 0-100
        return (clamped - min_v) / (max_v - min_v) * 100

    def analyze_market_flow_pro(self, index_symbol="VNINDEX"):
        """
        MARKET FLOW ENGINE (MFE) - Specific for Index Symbol
        Lấy trực tiếp dữ liệu Flow của chính Index đó (Foreign, Prop...) từ DB
        thay vì cộng gộp từ cổ phiếu thành phần.
        """
        # SQL JOIN thẳng thắn giữa Price và Flow của chính mã Index
        query = text("""
            SELECT 
                p.time, 
                p.open, p.high, p.low, p.close, p.volume, p.trading_value,
                -- Dòng tiền của chính Index (đã có trong bảng Flow)
                COALESCE(f.foreign_net_val, 0) as foreign_net,
                COALESCE(f.prop_net_val, 0) as prop_net,
                COALESCE(f.local_inst_net_val, 0) as inst_net,
                -- Tính tổng dòng tiền "Smart" (Ngoại + Tự doanh + Tổ chức)
                (COALESCE(f.foreign_net_val, 0) + COALESCE(f.prop_net_val, 0) + COALESCE(f.local_inst_net_val, 0)) as smart_net_total
            FROM fact_daily_bars p
            LEFT JOIN fact_investor_flows_daily f 
                ON p.time = f.time AND p.symbol = f.symbol
            WHERE p.symbol = :symbol
            AND p.time >= CURRENT_DATE - INTERVAL '120 days'
            ORDER BY p.time ASC
        """)
        
        try:
            df = pd.read_sql(query, self.engine, params={"symbol": index_symbol})
            if df.empty or len(df) < 30: return None
            
            # --- TÍNH TOÁN QUANT (GIỮ NGUYÊN LOGIC CŨ, CHỈ THAY ĐỔI ĐẦU VÀO) ---
            window = 20
            # Helper Z-Score
            calc_zscore = lambda s: (s - s.rolling(window).mean()) / s.rolling(window).std().replace(0, 1)

            # 1. SMF (Dựa trên dòng tiền của chính Index)
            df['z_foreign'] = calc_zscore(df['foreign_net'])
            df['z_prop'] = calc_zscore(df['prop_net'])
            df['z_inst'] = calc_zscore(df['inst_net'])
            df['smf_raw'] = df['z_foreign'] + df['z_prop'] + df['z_inst']
            
            # 2. FSI (Shock Index dựa trên GTGD của Index)
            df['fsi_raw'] = calc_zscore(df['trading_value'])
            
            # 3. Divergence (Correlation giữa %Change Index và Dòng tiền Smart của Index)
            df['pct_change'] = df['close'].pct_change()
            df['flow_divergence'] = df['pct_change'].rolling(window).corr(df['smart_net_total'])
            
            # 4. Fragility
            df['liquidity_gap'] = abs(df['close'] - df['open']) / df['volume'].replace(0, 1)
            
            is_down = df['close'] < df['close'].shift(1)
            down_vol = df['volume'] * is_down
            up_vol = df['volume'] * (~is_down)
            vol_fragility = down_vol.rolling(window).sum() / up_vol.rolling(window).sum().replace(0, 1)
            
            df['fragility_raw'] = calc_zscore(df['liquidity_gap']) + calc_zscore(vol_fragility)

            # --- KẾT QUẢ CUỐI CÙNG ---
            last = df.iloc[-1]
            
            # Normalize Scores
            score_smf = self._normalize_score(last['smf_raw'], -5, 5)
            score_fsi = self._normalize_score(last['fsi_raw'], -3, 3)
            score_div = (last['flow_divergence'] + 1) / 2 * 100 if pd.notna(last['flow_divergence']) else 50
            score_frag = 100 - self._normalize_score(last['fragility_raw'], -3, 3)
            
            # Tổng hợp MFE Score
            mfe_score = 0.35*score_smf + 0.25*score_fsi + 0.25*score_div + 0.15*score_frag
            
            fsi_label = "Bình thường"
            if last['fsi_raw'] > 2.0: fsi_label = "Đột biến (Vào)"
            elif last['fsi_raw'] < -2.0: fsi_label = "Đột biến (Rút)"

            return {
                "mfe_score": round(mfe_score, 1),
                "components": {
                    "smf": round(score_smf, 1),
                    "fsi": round(score_fsi, 1),
                    "div": round(score_div, 1),
                    "fragility": round(score_frag, 1)
                },
                "raw": {
                    "fsi_val": last['fsi_raw'],
                    "fsi_label": fsi_label,
                    "foreign_val": last['foreign_net'], # Net Val thực tế
                    "prop_val": last['prop_net']
                }
            }

        except Exception as e:
            print(f"MFE Error ({index_symbol}): {e}")
            return None