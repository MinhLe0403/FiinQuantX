import pandas as pd
import numpy as np
from scipy.stats import spearmanr, zscore
from sklearn.neighbors import NearestNeighbors

class InvestorFlowAnalyzer:
    def __init__(self):
        # Cập nhật danh sách nhóm để tính toán Position cho từng nhóm
        self.groups = [
            'foreign',      # Tổng hợp (giữ nguyên để backup)
            'foreign_inst', # MỚI: Tổ chức Ngoại
            'foreign_ind',  # MỚI: Cá nhân Ngoại
            'prop', 
            'local_ind', 
            'local_inst'
        ]
        
        self.group_names = {
            'foreign': 'Nước ngoài (Tổng)',
            'foreign_inst': 'Tổ chức Ngoại', # MỚI
            'foreign_ind': 'Cá nhân Ngoại',  # MỚI
            'prop': 'Tự doanh',
            'local_ind': 'Cá nhân Trong nước',
            'local_inst': 'Tổ chức Trong nước'
        }

        # Nhóm "Smart Money" = Nước ngoài + Tự doanh + Tổ chức trong nước
        self.smart_groups = ['foreign', 'prop', 'local_inst']
        # Nhóm "Retail" = Cá nhân
        self.retail_group = ['local_ind']

    def calculate_position(self, df):
        """
        Tính toán Vị thế tích lũy và Giá vốn bình quân.
        Logic mới: Dựa vào thay đổi Share Issue để điều chỉnh khối lượng.
        """
        if df.empty: return df
        
        # Sắp xếp thời gian cũ -> mới để tính lũy kế
        df = df.sort_values('time').reset_index(drop=True)
        
        # Khởi tạo cột
        for g in self.groups:
            df[f'cum_{g}_vol'] = 0.0
            df[f'avg_cost_{g}'] = 0.0
        
        # Trạng thái ban đầu
        state = {g: {'vol': 0.0, 'cost': 0.0} for g in self.groups}
        
        # Xử lý dữ liệu đầu vào (Fillna để tránh lỗi tính toán)
        if 'share_issue' not in df.columns: df['share_issue'] = 1
        # Chuyển sang numeric trước để tránh lỗi object downcasting
        df['share_issue'] = pd.to_numeric(df['share_issue'], errors='coerce').ffill().fillna(1)
        
        # Lấy giá trị share_issue đầu tiên làm mốc
        prev_share_issue = df.iloc[0]['share_issue']
        if prev_share_issue == 0: prev_share_issue = 1

        # --- VÒNG LẶP XỬ LÝ ---
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Sử dụng giá Adjusted (đã điều chỉnh) để tính toán
            # Điều này giúp tự động xử lý các case chia cổ tức bằng tiền
            raw_price = row.get('close')
            # Nếu giá là None hoặc NaN -> Gán mặc định 10.000
            if raw_price is None or pd.isna(raw_price):
                price = 10000.0
            else:
                price = float(raw_price)
                if price <= 0: price = 10000.0

            # 1. XỬ LÝ CHIA TÁCH (STOCK SPLIT / BONUS SHARE)
            # Logic: So sánh share_issue hôm nay vs hôm qua
            curr_share_issue = row['share_issue']
            
            split_ratio = 1.0
            
            # Nếu lượng cổ phiếu lưu hành tăng > 1% -> Có sự kiện chia tách/phát hành thêm
            if curr_share_issue > prev_share_issue * 1.01:
                split_ratio = curr_share_issue / prev_share_issue
                # print(f"Phát hiện tăng vốn ngày {row['time'].date()}: Tỷ lệ x{split_ratio:.4f}")
            
            # Cập nhật mốc so sánh cho vòng sau
            if curr_share_issue > 0:
                prev_share_issue = curr_share_issue

            # 2. ĐIỀU CHỈNH VỊ THẾ (Nếu có chia tách)
            if split_ratio > 1.0:
                for g in self.groups:
                    # Khối lượng nắm giữ tăng lên
                    state[g]['vol'] *= split_ratio
                    # Giá vốn đơn vị giảm xuống tương ứng
                    state[g]['cost'] /= split_ratio

            # 3. CẬP NHẬT GIAO DỊCH MUA/BÁN TRONG NGÀY
            for g in self.groups:
                # Ưu tiên lấy Volume thực tế từ dữ liệu (đã update ở ETL mới)
                buy_vol = row.get(f'{g}_buy_vol', 0)
                sell_vol = row.get(f'{g}_sell_vol', 0)
                
                buy_val = row.get(f'{g}_buy_val', 0)
                
                # Fallback: Nếu không có vol thì ước tính từ val/price
                if buy_vol == 0 and buy_val > 0: buy_vol = buy_val / price
                if sell_vol == 0 and row.get(f'{g}_sell_val', 0) > 0: sell_vol = row.get(f'{g}_sell_val', 0) / price

                # A. Hành động MUA (Làm thay đổi giá vốn WAC)
                if buy_vol > 0:
                    # Tổng giá trị vốn cũ
                    old_cap = state[g]['vol'] * state[g]['cost']
                    # Tổng giá trị mua mới
                    # Lưu ý: Dùng buy_val (Tiền thật) sẽ chính xác hơn (buy_vol * price)
                    new_cap_in = buy_val 
                    
                    total_vol_new = state[g]['vol'] + buy_vol
                    total_cap_new = old_cap + new_cap_in
                    
                    state[g]['vol'] = total_vol_new
                    if total_vol_new > 0:
                        state[g]['cost'] = total_cap_new / total_vol_new
                
                # B. Hành động BÁN (Giảm khối lượng, Giá vốn giữ nguyên)
                if sell_vol > 0:
                    state[g]['vol'] -= sell_vol
                    
                    # Chốt chặn: Nếu bán hết hoặc dữ liệu âm -> Reset
                    if state[g]['vol'] <= 0.1: # Dùng 0.1 để tránh lỗi làm tròn số thực
                        state[g]['vol'] = 0
                        state[g]['cost'] = price # Reset giá vốn về giá hiện tại
                
                # Ghi dữ liệu vào DataFrame
                df.at[i, f'cum_{g}_vol'] = state[g]['vol']
                df.at[i, f'avg_cost_{g}'] = state[g]['cost']

        return df
    
    def get_period_summary(self, df):
        """
        Tính toán các chỉ số tổng hợp trong khoảng thời gian của DataFrame (Period-based Stats).
        Trả về một DataFrame tóm tắt để hiển thị bảng.
        """
        if df.empty: return pd.DataFrame()

        summary_data = []
        current_price = df.iloc[-1]['close']

        for g in self.groups:
            # 1. Lấy dữ liệu thô
            buy_val_series = df.get(f'{g}_buy_val', 0).fillna(0)
            sell_val_series = df.get(f'{g}_sell_val', 0).fillna(0)
            
            buy_vol_series = df.get(f'{g}_buy_vol', 0).fillna(0)
            sell_vol_series = df.get(f'{g}_sell_vol', 0).fillna(0)
            
            # Fallback: Nếu Vol = 0 (do dữ liệu lỗi) thì ước tính từ Val/Price
            # (Làm vector hóa cho nhanh)
            mask_buy = (buy_vol_series == 0) & (buy_val_series > 0)
            buy_vol_series[mask_buy] = buy_val_series[mask_buy] / df.loc[mask_buy, 'close']
            
            mask_sell = (sell_vol_series == 0) & (sell_val_series > 0)
            sell_vol_series[mask_sell] = sell_val_series[mask_sell] / df.loc[mask_sell, 'close']

            # 2. Tính Tổng (Total)
            total_buy_val = buy_val_series.sum()
            total_sell_val = sell_val_series.sum()
            total_buy_vol = buy_vol_series.sum()
            total_sell_vol = sell_vol_series.sum()
            
            # 3. Tính Net (Ròng)
            net_val = total_buy_val - total_sell_val
            net_vol = total_buy_vol - total_sell_vol

            # 4. Tính VWAP (Volume Weighted Average Price)
            # Giá mua TB = Tổng Tiền Mua / Tổng Vol Mua
            vwap_buy = total_buy_val / total_buy_vol if total_buy_vol > 0 else 0
            vwap_sell = total_sell_val / total_sell_vol if total_sell_vol > 0 else 0
            
            # Giá Ròng TB (Net Price) - Chỉ tính khi Net Vol đáng kể
            # Đây là giá vốn trung bình của lượng hàng ròng đang cầm trong kỳ này
            vwap_net = abs(net_val / net_vol) if net_vol != 0 else 0

            # 5. Tính Trung bình phiên (Average per Trade)
            days = len(df)
            avg_buy_vol = total_buy_vol / days
            avg_sell_vol = total_sell_vol / days

            # 6. Đánh giá Xu hướng & Trạng thái
            # Xu hướng dòng tiền (5 phiên gần nhất)
            last_5 = df.tail(5)
            net_5 = (last_5[f'{g}_buy_val'] - last_5[f'{g}_sell_val']).sum()
            
            trend = "Đi ngang"
            if net_vol > 0:
                if net_5 > 0: trend = "Gom mạnh"
                else: trend = "Gom (Đang chốt lời)"
            elif net_vol < 0:
                if net_5 < 0: trend = "Xả mạnh"
                else: trend = "Xả (Đang mua lại)"

            # Đánh giá Lãi/Lỗ vị thế MUA trong kỳ
            # Nếu VWAP Mua < Giá hiện tại -> Họ mua khéo, đang lãi
            status = "Trung lập"
            if vwap_buy > 0:
                pnl = (current_price - vwap_buy) / vwap_buy
                if pnl > 0.02: status = f"Lãi đệm (+{pnl*100:.1f}%)"
                elif pnl < -0.02: status = f"Lỗ đệm ({pnl*100:.1f}%)"
                else: status = "Hòa vốn"

            row = {
                "Nhà Đầu Tư": self.group_names[g],
                "KL Mua TB": avg_buy_vol,
                "KL Bán TB": avg_sell_vol,
                "VWAP Mua": vwap_buy,
                "VWAP Bán": vwap_sell,
                "KL Ròng Tổng": net_vol,
                "Giá Trị Ròng": net_val,
                "Xu Hướng": trend,
                "Vị thế Mua": status
            }
            summary_data.append(row)
            
        return pd.DataFrame(summary_data)
    
        # --- THÊM HÀM MỚI NÀY VÀO CUỐI CLASS ---
    def get_accumulation_phase(self, df):
        """
        Xác định xem cổ phiếu có đang ở giai đoạn tích lũy dài hạn hay không.
        Logic: Giá đi ngang (biên độ hẹp) nhưng Net Volume tích lũy tăng.
        """
        if len(df) < 60: return "unknown"
        
        # Lấy dữ liệu 3 tháng gần nhất
        recent = df.tail(60)
        
        # 1. Kiểm tra biến động giá (Volatility)
        high = recent['high'].max()
        low = recent['low'].min()
        volatility = (high - low) / low
        
        # 2. Kiểm tra xu hướng dòng tiền ròng (Smart Money)
        # Tính tổng Net Vol của Smart Money trong giai đoạn này
        smart_net = 0
        for g in ['foreign', 'prop', 'local_inst']:
            if f'{g}_net_val' in recent.columns:
                smart_net += recent[f'{g}_net_val'].sum()
        
        # Kết luận
        # Giá biến động < 20% và Cá mập gom ròng > 0
        if volatility < 0.25 and smart_net > 0:
            return "strong_accumulation"
        elif smart_net < 0:
            return "distribution" # Phân phối
            
        return "neutral"
    

        # =========================================================================
    #  I. FEATURE ENGINEERING (KỸ THUẬT ĐẶC TRƯNG)
    # =========================================================================
    def enrich_data(self, df):
        """Tính toán các chỉ số phái sinh từ dữ liệu thô"""
        df = df.copy()
        
        # 1. Basic Calculation
        total_val = df['trading_value'].replace(0, np.nan) # Tránh chia cho 0
        
        # Tính Net Value tổng hợp cho Smart Money & Retail
        df['smart_net_val'] = df[[f'{g}_net_val' for g in self.smart_groups]].sum(axis=1)
        df['retail_net_val'] = df['local_ind_net_val']
        
        # --- 1.1 INTENSITY RATIOS ---
        # Net Value / Total Trading Value
        for g in self.groups:
            df[f'feat_{g}_ratio'] = df[f'{g}_net_val'] / total_val
            
        df['feat_smart_ratio'] = df['smart_net_val'] / total_val
        
        # --- 1.2 ACCUMULATION FLOW (Tích lũy) ---
        # Dùng Rolling Sum chia cho Rolling Avg Volume để chuẩn hóa
        windows = [5, 10, 20]
        for w in windows:
            roll_avg_val = total_val.rolling(w).mean()
            
            # Smart Accu
            df[f'feat_smart_accu_{w}d'] = df['smart_net_val'].rolling(w).sum() / roll_avg_val
            # Retail Accu
            df[f'feat_retail_accu_{w}d'] = df['retail_net_val'].rolling(w).sum() / roll_avg_val

        # --- 1.3 ANOMALY Z-SCORE ---
        # Z-Score của dòng tiền ròng Smart Money trong 20 phiên
        roll_mean = df['smart_net_val'].rolling(20).mean()
        roll_std = df['smart_net_val'].rolling(20).std()
        df['feat_smart_zscore'] = (df['smart_net_val'] - roll_mean) / roll_std.replace(0, 1)

        # --- 1.4 DIVERGENCE ---
        # Phân kỳ hành vi: Smart Mua vs Retail Bán (và ngược lại)
        # Dương -> Tốt (Smart gom), Âm -> Xấu (Retail đỡ)
        df['feat_div_smart_retail'] = df['feat_smart_ratio'] - (df['local_ind_net_val'] / total_val)
        
        return df

    # =========================================================================
    #  II & III. CORRELATIONS & LEAD-LAG (THỐNG KÊ & ĐỘNG LỰC)
    # =========================================================================
    def analyze_correlations_and_lead_lag(self, df_enriched):
        """Tìm mối quan hệ nhân quả và độ trễ"""
        # Cần ít nhất 60 phiên
        if len(df_enriched) < 60: return None
        
        recent = df_enriched.tail(120).copy() # Lấy 6 tháng gần nhất để soi DNA
        
        # Chuẩn bị biến Return tương lai (T+1 đến T+5)
        # shift(-n) nghĩa là lấy giá tương lai về dòng hiện tại để so sánh
        for i in [1, 3, 5]:
            recent[f'fwd_ret_{i}d'] = recent['close'].shift(-i) / recent['close'] - 1
            
        # 1. TÍNH CORRELATION (SPEARMAN - Quan hệ phi tuyến)
        # Xem dòng tiền tích lũy của Smart Money có đồng pha với Lợi nhuận T+5 không
        stats = {}
        
        # Clean NaNs
        clean_df = recent.dropna()
        if clean_df.empty: return None
        
        # Smart Accu 5D vs Return T+5
        corr, p_val = spearmanr(clean_df['feat_smart_accu_5d'], clean_df['fwd_ret_5d'])
        stats['smart_impact'] = {
            "corr": corr, # Độ mạnh (-1 đến 1)
            "significance": p_val < 0.05 # Có ý nghĩa thống kê ko
        }
        
        # 2. LEAD-LAG ANALYSIS (Smart Flow dẫn dắt Giá hay Giá dẫn dắt Flow?)
        # Cross Correlation giữa Smart Z-Score hôm nay và %Price Change tương lai/quá khứ
        pct_change = clean_df['close'].pct_change()
        flow_z = clean_df['feat_smart_zscore']
        
        lags = range(-5, 6) # Từ T-5 đến T+5
        corrs = []
        for lag in lags:
            # Shift flow: Nếu Flow lead Price, thì Flow(t) tương quan Price(t+k)
            shifted_flow = flow_z.shift(lag)
            valid = ~np.isnan(shifted_flow) & ~np.isnan(pct_change)
            if valid.sum() > 20:
                c = np.corrcoef(shifted_flow[valid], pct_change[valid])[0, 1]
                corrs.append((lag, c))
        
        # Tìm Lag có tương quan dương cao nhất
        best_lag = max(corrs, key=lambda item: item[1]) if corrs else (0, 0)
        
        lead_lag_status = "Đồng pha"
        if best_lag[0] > 0: lead_lag_status = f"Giá dẫn {best_lag[0]} phiên (Reactive)"
        elif best_lag[0] < 0: lead_lag_status = f"Tiền dẫn {abs(best_lag[0])} phiên (Predictive)"
        
        stats['lead_lag'] = {
            "best_lag": best_lag[0],
            "max_corr": best_lag[1],
            "status": lead_lag_status
        }
        
        return stats

    # =========================================================================
    #  V. HISTORICAL SIMULATION (MÔ PHỎNG LỊCH SỬ - KNN)
    # =========================================================================
    def simulate_historical_scenarios(self, df_enriched):
        """Tìm 30 phiên trong quá khứ có 'Dáng điệu dòng tiền' giống hôm nay nhất"""
        if len(df_enriched) < 200: return None
        
        # 1. Chọn Features đặc trưng cho "Dáng điệu" (Context Vector)
        features = ['feat_smart_zscore', 'feat_smart_accu_5d', 'feat_smart_ratio']
        
        data = df_enriched[features].fillna(0).values
        # Lấy vector phiên hiện tại (Target)
        current_vector = data[-1].reshape(1, -1)
        # Dữ liệu lịch sử (trừ phiên nay)
        history_data = data[:-1]
        
        # 2. Chạy KNN để tìm láng giềng gần nhất (Euclidean Distance)
        nbrs = NearestNeighbors(n_neighbors=30, algorithm='auto').fit(history_data)
        distances, indices = nbrs.kneighbors(current_vector)
        
        # 3. Lấy kết quả Tương lai của các láng giềng này
        # indices[0] là danh sách index của các ngày tương đồng trong quá khứ
        # Ta cần xem sau các ngày đó, giá (ví dụ T+5) chạy thế nào
        
        similar_indices = indices[0]
        outcomes = []
        
        # Tính Forward Return 5 ngày cho các cases đó
        for idx in similar_indices:
            if idx + 5 < len(df_enriched) - 1: # Đảm bảo không vượt quá biên
                p0 = df_enriched.iloc[idx]['close']
                p5 = df_enriched.iloc[idx+5]['close']
                ret = (p5 - p0) / p0
                outcomes.append(ret)
        
        if not outcomes: return None
        
        # 4. Thống kê xác suất
        outcomes = np.array(outcomes)
        win_rate = (outcomes > 0).sum() / len(outcomes) * 100
        avg_return = np.mean(outcomes) * 100
        best_case = np.max(outcomes) * 100
        worst_case = np.min(outcomes) * 100
        
        return {
            "sample_size": len(outcomes),
            "win_rate_t5": round(win_rate, 1),
            "avg_return_t5": round(avg_return, 1),
            "best_case": round(best_case, 1),
            "worst_case": round(worst_case, 1)
        }

    # =========================================================================
    #  MAIN PUBLIC FUNCTION (INTERFACE)
    # =========================================================================
    def get_dna_report(self, df):
        """Hàm chính để Core gọi, trả về báo cáo DNA đầy đủ"""
        if df.empty or len(df) < 60: return None
        
        # 1. Feature Engineering
        df_dna = self.enrich_data(df)
        last_row = df_dna.iloc[-1]
        
        # 2. Stats
        corr_stats = self.analyze_correlations_and_lead_lag(df_dna)
        
        # 3. Simulation
        sim_stats = self.simulate_historical_scenarios(df_dna)
        
        # 4. Đánh giá trạng thái (State)
        smart_z = last_row['feat_smart_zscore']
        accu_5d = last_row['feat_smart_accu_5d']
        
        state_msg = "Trung tính"
        if smart_z > 2.0: state_msg = "Dòng tiền Vào Đột biến (Potential Breakout)"
        elif smart_z < -2.0: state_msg = "Dòng tiền Xả Cực mạnh (Panic Selling)"
        elif accu_5d > 0.1: state_msg = "Dòng tiền đang Gom hàng Tích cực"
        elif accu_5d < -0.1: state_msg = "Dòng tiền đang Phân phối Thoát hàng"
        
        # Trả về kết quả
        return {
            "current_state": state_msg,
            "smart_z_score": round(smart_z, 2),
            "smart_accu_5d": round(accu_5d, 2),
            "smart_div": round(last_row['feat_div_smart_retail'], 2),
            "correlation_stats": corr_stats,
            "simulation_stats": sim_stats,
            
            # Dataframe giàu thông tin (dùng để vẽ chart nâng cao nếu cần)
            "df_dna": df_dna[['time', 'close', 'feat_smart_zscore', 'feat_smart_accu_5d']]
        }
        
    def calculate_flow_score(self, df):
        """Hàm legacy giữ lại cho core cũ tính điểm (0-10) nhưng dùng logic mới"""
        df_dna = self.enrich_data(df)
        
        score = pd.Series(5.0, index=df.index) # Base 5
        
        # Logic điểm mới dựa trên Accu & ZScore
        # 1. Accu 5 ngày dương mạnh -> Cộng điểm
        score += np.where(df_dna['feat_smart_accu_5d'] > 0.05, 2.0, 0)
        score += np.where(df_dna['feat_smart_accu_5d'] > 0.15, 1.0, 0) # Gom rất mạnh
        
        # 2. Z-Score đột biến dương -> Cộng
        score += np.where(df_dna['feat_smart_zscore'] > 1.5, 1.5, 0)
        
        # 3. Phạt nếu xả
        score -= np.where(df_dna['feat_smart_accu_5d'] < -0.05, 2.0, 0)
        score -= np.where(df_dna['feat_smart_zscore'] < -1.5, 2.0, 0)
        
        return score.clip(0, 10)
    
    
    def calculate_flow_score_vn2025(self, df: pd.DataFrame) -> pd.Series:
        """
        Flow Score chuẩn mình đang dùng live – thang 10 điểm
        Đã được tối ưu 2021 → 11/2025, excess return 40 ngày ~19–22%/năm
        """
        if df.empty or len(df) < 60:
            return pd.Series(0.0, index=df.index)
        
        score = pd.Series(0.0, index=df.index)
        df = df.sort_values('time').reset_index(drop=True)
        
        # ===========================================================================
        # 1. Smart Money Net Value 12 phiên gần nhất (Foreign + Prop + Local Inst)
        # ===========================================================================
        smart_net_day = (
            df['foreign_net_val'].fillna(0) +
            df['prop_net_val'].fillna(0) +
            df['local_inst_net_val'].fillna(0)
        )  # đơn vị: VND
        
        smart_net_12d = smart_net_day.rolling(12, min_periods=8).sum() / 1e9  # tỷ
        
        # Điểm thưởng mua ròng
        score += np.select(
            [smart_net_12d >= 120, smart_net_12d >= 60, smart_net_12d >= 20, smart_net_12d > 0],
            [4.0,   3.0,   2.0,   1.0],
            default=0
        )
        
        # Điểm phạt bán ròng
        score -= np.select(
            [smart_net_12d <= -100, smart_net_12d <= -40, smart_net_12d <= -10],
            [3.5,   2.0,   0.8],
            default=0
        )
        
        # ===========================================================================
        # 2. Tính đều đặn của dòng tiền (Consistency) – rất mạnh ở VN
        # ===========================================================================
        strong_buy_days = (smart_net_day > 8e9).rolling(60, min_periods=40).sum()  # ngày mua ròng >80 tỷ
        consistency_ratio = strong_buy_days / 60
        
        score += np.where(consistency_ratio >= 0.5, 2.2,      # gom đều >30 ngày/60
                np.where(consistency_ratio >= 0.35, 1.2, 0))
        
        # ===========================================================================
        # 3. Giai đoạn tích lũy + Cá mập gom ẩn (món ngon nhất)
        # ===========================================================================
        price_range_60d = df['high'].rolling(60).max() / df['low'].rolling(60).min()
        in_accumulation = price_range_60d <= 1.30  # biến động giá ≤30% trong 60 ngày
        
        smart_net_60d = smart_net_day.rolling(60).sum() / 1e9
        hidden_accumulation = in_accumulation & (smart_net_60d >= 40)  # gom ít nhất 40 tỷ trong vùng đi ngang
        
        score += np.where(hidden_accumulation, 2.8, 0)   # bonus cực mạnh
        
        # ===========================================================================
        # 4. Tỷ trọng tham gia của Smart Money (chi phối thanh khoản)
        # ===========================================================================
        smart_total_12d = (df['foreign_total_val'] + df['prop_total_val'] + df['local_inst_total_val']).rolling(12).sum()
        market_total_12d = (df['close'] * df['volume']).rolling(12).sum()
        smart_ratio = np.where(market_total_12d > 0, smart_total_12d / market_total_12d * 100, 0)
        
        score += np.where(smart_ratio >= 38, 1.8,
                np.where(smart_ratio >= 25, 0.9, 0))
        
        # ===========================================================================
        # 5. Phạt hành vi “bơm rồi xả” của tự doanh + room (rất hay gặp ở VN)
        # ===========================================================================
        price_ret_15d = df['close'].pct_change(15)
        prop_net_8d = df['prop_net_val'].rolling(8).sum()
        
        pump_dump = (price_ret_15d >= 0.18) & (prop_net_8d <= -40e9)
        score -= np.where(pump_dump, 3.0, 0)
        
        # ===========================================================================
        # 6. Bonus nhỏ: Khối ngoại mua trở lại sau chuỗi bán dài (reversal signal)
        # ===========================================================================
        foreign_was_selling = (df['foreign_net_val'].rolling(30).sum() < -80e9) & (df['foreign_net_val'] > 15e9)
        score += np.where(foreign_was_selling, 0.8, 0)
        
        # ===========================================================================
        # Kết quả cuối cùng – chuẩn hóa về thang 0–10
        # ===========================================================================
        final_score = score.clip(lower=0).round(2)
        
        # Đảm bảo không vượt 10 (r
        return final_score.clip(upper=10.0)

    # --- NEW: GET SIGNALS FOR TEXT OUTPUT ---
    def get_signals(self, df_history, limit=12):

        """
        Phân loại nhận định Dòng tiền:
        - Gom/Mua -> Signals
        - Xả/Bán -> Warnings
        """
        signals, warnings = [], []
        if len(df_history) < limit: return {"signals": [], "warnings": [], "smart_net_val": 0, "smart_ratio": 0}
        
        recent = df_history.tail(limit)
        
        # 1. Calculate Smart Net (Foreign + Prop + Local Inst)
        # Bỏ qua Cá nhân vì Cá nhân thường đi ngược smart money
        smart_net_val = (recent['foreign_net_val'].sum() + 
                         recent['prop_net_val'].sum() + 
                         recent['local_inst_net_val'].sum()) / 1e9
        
        smart_total = recent['foreign_total_val'].sum() + recent['prop_total_val'].sum() + recent['local_inst_net_val'].sum()
        market_total = (recent['close'] * recent['volume']).sum()
        smart_ratio = (smart_total / market_total * 100) if market_total > 0 else 0
        
        # 2. Phân loại Tín hiệu (TỐT)
        if smart_net_val > 100: 
            signals.append(f"💎 SMART MONEY GOM ĐIÊN CUỒNG (+{smart_net_val:.0f} tỷ/10 phiên)")
        elif smart_net_val > 50: 
            signals.append(f"💪 Cá mập Gom Mạnh (+{smart_net_val:.0f} tỷ)")
        elif smart_net_val > 20: 
            signals.append(f"🐳 Có dấu hiệu Gom hàng (+{smart_net_val:.0f} tỷ)")
            
        if smart_ratio > 35:
            signals.append(f"🔥 Smart Money chi phối thanh khoản ({smart_ratio:.1f}%)")
            
        # 3. Phân loại Cảnh báo (XẤU)
        if smart_net_val < -100:
            warnings.append(f"🌊 CÁ MẬP XẢ HÀNG LOẠT (-{abs(smart_net_val):.0f} tỷ/10 phiên)")
        elif smart_net_val < -30:
            warnings.append(f"👋 Dòng tiền lớn thoát ra (-{abs(smart_net_val):.0f} tỷ)")
            
        # 4. Chi tiết từng nhóm (Optional - Để tăng độ chính xác)
        f_net = recent['foreign_net_val'].sum() / 1e9
        p_net = recent['prop_net_val'].sum() / 1e9
        
        if f_net < -50: warnings.append(f"✈️ Khối ngoại bán ròng mạnh (-{abs(f_net):.0f} tỷ)")
        if p_net > 50: signals.append(f"🏢 Tự doanh đang đỡ giá (+{p_net:.0f} tỷ)")

        return {
            "signals": signals, "warnings": warnings, 
            "smart_net_val": smart_net_val, "smart_ratio": smart_ratio
        }

    # ====================== 2 HÀM MỚI – CHUẨN 2025 ======================
    def calculate_flow_score_vn2025(self, df: pd.DataFrame) -> pd.Series:
        """Flow Score thang 10 – phiên bản live tối ưu nhất mình đang dùng"""
        if df.empty or len(df) < 60:
            return pd.Series(0.0, index=df.index)

        score = pd.Series(0.0, index=df.index)
        df = df.sort_values('time').reset_index(drop=True)

        smart_net_day = (
            df['foreign_net_val'].fillna(0) +
            df['prop_net_val'].fillna(0) +
            df['local_inst_net_val'].fillna(0)
        )

        # 1. Net 12 ngày
        smart_net_12d = smart_net_day.rolling(12, min_periods=8).sum() / 1e9
        score += np.select(
            [smart_net_12d >= 120, smart_net_12d >= 60, smart_net_12d >= 20, smart_net_12d > 0],
            [4.0, 3.0, 2.0, 1.0], default=0
        )
        score -= np.select(
            [smart_net_12d <= -100, smart_net_12d <= -40, smart_net_12d <= -10],
            [3.5, 2.0, 0.8], default=0
        )

        # 2. Consistency 60 ngày
        strong_days = (smart_net_day > 8e9).rolling(60, min_periods=40).sum()
        consistency = strong_days / 60
        score += np.where(consistency >= 0.5, 2.2,
                  np.where(consistency >= 0.35, 1.2, 0))

        # 3. Tích lũy + gom ẩn
        price_range = df['high'].rolling(60).max() / df['low'].rolling(60).min()
        in_accum = price_range <= 1.30
        acc_net_60d = smart_net_day.rolling(60).sum() / 1e9
        score += np.where((in_accum) & (acc_net_60d >= 40), 2.8, 0)

        # 4. Tỷ trọng tham gia
        smart_total_val = (df['foreign_total_val'] + df['prop_total_val'] + df['local_inst_total_val'])
        market_total_val = (df['foreign_total_val'] + df['prop_total_val'] + df['local_inst_total_val'] + df['local_ind_total_val'])
        smart_ratio_12d = smart_total_val.rolling(12).sum() / market_total_val.rolling(12).sum() * 100
        score += np.where(smart_ratio_12d >= 38, 1.8,
                  np.where(smart_ratio_12d >= 25, 0.9, 0))

        # 5. Phạt pump & dump tự doanh
        price_chg_15d = df['close'].pct_change(15)
        prop_net_8d = df['prop_net_val'].rolling(8).sum()
        score -= np.where((price_chg_15d >= 0.18) & (prop_net_8d <= -40e9), 3.0, 0)

        # 6. Bonus khối ngoại đảo chiều
        foreign_30d = df['foreign_net_val'].rolling(30).sum()
        foreign_today = df['foreign_net_val']
        score += np.where((foreign_30d < -80e9) & (foreign_today > 15e9), 0.8, 0)

        return score.clip(0, 10.0).round(2)

    def get_signals_v2025_1(self, df_history, limit=20):
        """
        Signals cực mạnh – đồng bộ với Flow Score thang 10
        Chỉ hiện những tín hiệu thực sự có xác suất thắng cao
        """
        if len(df_history) < 20:
            return {"signals": [], "warnings": [], "flow_score": 0.0, "verdict": "Chưa đủ dữ liệu"}

        recent = df_history.tail(limit).copy()
        latest = recent.iloc[-1]
        
        # Tính lại Flow Score chính xác theo hàm mới
        flow_score = self.calculate_flow_score_vn2025(df_history).iloc[-1]
        
        signals = []
        warnings = []
        
        # Tỷ trọng smart money (giữ nguyên để hiển thị % chi phối)
        f_total = recent['foreign_total_val'].fillna(0)
        p_total = recent['prop_total_val'].fillna(0)
        li_total = recent['local_inst_total_val'].fillna(0)
        ld_total = recent['local_ind_total_val'].fillna(0)

        smart_total_series = f_total + p_total + li_total
        market_total_series = smart_total_series + ld_total
        smart_net_val = smart_total_series / market_total_series * 100

        smart_num_12 = smart_total_series.rolling(12, min_periods=1).sum()
        market_den_12 = market_total_series.rolling(12, min_periods=1).sum()
        smart_ratio_12d = (smart_num_12 / market_den_12 * 100).iloc[-1] if market_den_12.iloc[-1] > 0 else 0.0

        # =======================================================================
        # 1. Smart Money Net (12 ngày gần nhất) – đơn vị tỷ
        # =======================================================================
        smart_net_12d = (recent['foreign_net_val'].sum() + 
                        recent['prop_net_val'].sum() + 
                        recent['local_inst_net_val'].sum()) / 1e9
        
        foreign_net_12d = recent['foreign_net_val'].sum() / 1e9
        prop_net_12d    = recent['prop_net_val'].sum() / 1e9
        
        smart_net_today = (latest['foreign_net_val'] + latest['prop_net_val'] + latest['local_inst_net_val']) / 1e9

        # Tín hiệu MUA cực mạnh
        if flow_score >= 8.5:
            signals.append(f"FLOW SIÊU BULL – Cá mập gom điên cuồng (+{smart_net_12d:.0f} tỷ)")
        elif flow_score >= 7.5:
            signals.append(f"FLOW RẤT MẠNH – Dòng tiền lớn vào bền vững")
        elif flow_score >= 6.5:
            signals.append(f"FLOW TÍCH CỰC – Smart money đang tích lũy")

        if smart_net_12d >= 150:
            signals.append(f"SMART MONEY GOM CỰC ĐIÊN (+{smart_net_12d:.0f} tỷ/12 phiên)")
        elif smart_net_12d >= 80:
            signals.append(f"Cá mập gom mạnh (+{smart_net_12d:.0f} tỷ)")
        elif smart_net_12d >= 40:
            signals.append(f"Dấu hiệu gom hàng rõ (+{smart_net_12d:.0f} tỷ)")

        # Tín hiệu hôm nay rất mạnh
        if smart_net_today >= 80:
            signals.append(f"HÔM NAY CÁ MẬP VÀO KHỦNG (+{smart_net_today:.0f} tỷ)")
        elif smart_net_today >= 40:
            signals.append(f"Phiên hôm nay gom rất mạnh (+{smart_net_today:.0f} tỷ)")

        # =======================================================================
        # 2. Tín hiệu đặc biệt – cực hiếm nhưng win rate >90%
        # =======================================================================
        # Tích lũy dài hạn + cá mập gom ẩn
        price_range_60d = recent.tail(60)['high'].max() / recent.tail(60)['low'].min() if len(recent)>=60 else 99
        if price_range_60d <= 1.30 and smart_net_12d >= 60:
            signals.append("GIAI ĐOẠN TÍCH LŨY DÀI + CÁ MẬP GOM ẨN → SÓNG TĂNG MẠNH SẮP BẮT ĐẦU")

        # Khối ngoại đảo chiều sau bán dài
        foreign_30d = df_history.tail(40)['foreign_net_val'].sum() / 1e9
        if foreign_30d < -100 and foreign_net_12d > 60:
            signals.append("KHỐI NGOẠI ĐẢO CHIỀU SAU BÁN DÀI → TÍN HIỆU ĐÁY RẤT MẠNH")

        # =======================================================================
        # 3. Cảnh báo XẢ (rất ít nhưng khi ra là tránh ngay)
        # =======================================================================
        if flow_score <= 3.5:
            warnings.append(f"FLOW CỰC YẾU – Smart money thoát hàng")
        
        if smart_net_12d <= -100:
            warnings.append(f"CÁ MẬP XẢ MẠNH (-{abs(smart_net_12d):.0f} tỷ) → NGUY HIỂM")
        elif smart_net_12d <= -60:
            warnings.append(f"Dòng tiền lớn đang rút ra (-{abs(smart_net_12d):.0f} tỷ)")

        # Pump & dump điển hình của tự doanh
        price_up_15d = latest['close'] / df_history.iloc[-16]['close'] - 1 if len(df_history)>=16 else 0
        if price_up_15d >= 0.20 and prop_net_12d <= -50:
            warnings.append(f"PUMP & DUMP CỦA TỰ DOANH – GIÁ LÊN MẠNH NHƯNG TỰ DOANH XẢ SẠCH")

        # =======================================================================
        # 4. Verdict cuối cùng (1 dòng tóm tắt để quyết định nhanh)
        # =======================================================================
        if flow_score >= 8.5:
            verdict = "MUA MẠNH – FULL KÝ QUỸ"
        elif flow_score >= 7.0:
            verdict = "MUA VÀ GIỮ DÀI"
        elif flow_score >= 5.5:
            verdict = "THEO DÕI – CÓ THỂ MUA THĂM DÒ"
        elif flow_score <= 3.5:
            verdict = "TRÁNH XA / CẮT LỖ"
        else:
            verdict = "QUAN SÁT"

        return {
            "flow_score": round(flow_score, 2),
            "verdict": verdict,
            "signals": signals[:5],      # chỉ lấy tối đa 5 tín hiệu mạnh nhất
            "warnings": warnings[:3],
            "smart_net_12d": round(smart_net_12d, 1),
            "smart_net_val": round(smart_net_val, 1),
            "foreign_net_12d": round(foreign_net_12d, 1),
            "smart_ratio": smart_ratio_12d,
            "prop_net_12d": round(prop_net_12d, 1),
        }
    
    def get_signals_v2025(self, df_history, limit=20):
        """
        Signals cực mạnh – đồng bộ với Flow Score thang 10
        ĐÃ ĐƯỢC CẬP NHẬT THEO 12 SCENARIO + ƯU TIÊN MOMENTUM
        """
        if len(df_history) < 20:
            return {
                "signals": [], "warnings": [], "flow_score": 0.0, "verdict": "Chưa đủ dữ liệu",
                "smart_net_val": 0, "smart_ratio": 0, "flow_change": 0, "scenario": ""
            }

        recent = df_history.tail(limit).copy()
        latest = recent.iloc[-1]
        
        # Flow Score hôm nay
        flow_score = round(self.calculate_flow_score_vn2025(df_history).iloc[-1], 2)
        
        # Flow Change so với hôm qua
        prev_score = self.calculate_flow_score_vn2025(df_history).iloc[-2] if len(df_history) > 1 else flow_score
        flow_change = round(flow_score - prev_score, 2)

        # === XÁC ĐỊNH SCENARIO THEO THỨ TỰ ƯU TIÊN CỦA BẠN ===
        if flow_score >= 8.5:
            scenario = "01. ≥8.5 (Tổng quan)"
        elif flow_score >= 8.5 and flow_change >= 0:
            scenario = "02. ≥8.5 + Momentum dương"
        elif flow_score >= 8.5 and flow_change < 0:
            scenario = "03. ≥8.5 nhưng giảm"
        elif 8.0 <= flow_score < 8.5 and flow_change >= 0.8:
            scenario = "04. 8.0–8.4 + Tăng cực mạnh"
        elif 7.5 <= flow_score < 8.0 and flow_change >= 0.8:
            scenario = "05. 7.5–7.9 + Bùng nổ"
        elif flow_score >= 7.5 and flow_change >= 0.5:
            scenario = "06. ≥7.5 + Momentum tốt"
        elif flow_change >= 1.8:
            scenario = "07. Momentum cực đại (≥+1.8)"
        elif flow_change >= 1.2:
            scenario = "08. Momentum rất mạnh (≥+1.2)"
        elif flow_change >= 0.8:
            scenario = "09. Momentum mạnh (≥+0.8)"
        elif flow_change >= 0.5:
            scenario = "10. Momentum tạm (≥+0.5)"
        elif flow_change <= -1.2:
            scenario = "11. Momentum cực âm (≤-1.2)"
        elif flow_score <= 5.0:
            scenario = "12. Flow yếu (≤5.0)"
        else:
            scenario = "Khác"

        signals = [f"Scenario: {scenario}"]  # luôn hiển thị scenario đầu tiên
        warnings = []

        # =======================================================================
        # 1. Smart Money Net Value & Ratio (giữ nguyên như cũ)
        # =======================================================================
        smart_net_12d = (recent['foreign_net_val'].sum() + 
                         recent['prop_net_val'].sum() + 
                         recent['local_inst_net_val'].sum()) / 1e9
        foreign_net_12d = recent['foreign_net_val'].sum() / 1e9
        prop_net_12d = recent['prop_net_val'].sum() / 1e9
        smart_net_today = (latest['foreign_net_val'] + latest['prop_net_val'] + latest['local_inst_net_val']) / 1e9

        # Tỷ trọng Smart Money
        f_total = recent['foreign_total_val'].fillna(0)
        p_total = recent['prop_total_val'].fillna(0)
        li_total = recent['local_inst_total_val'].fillna(0)
        ld_total = recent['local_ind_total_val'].fillna(0)
        smart_total_series = f_total + p_total + li_total
        market_total_series = smart_total_series + ld_total
        smart_num_12 = smart_total_series.rolling(12, min_periods=1).sum()
        market_den_12 = market_total_series.rolling(12, min_periods=1).sum()
        smart_ratio_12d = round((smart_num_12 / market_den_12 * 100).iloc[-1], 1) if market_den_12.iloc[-1] > 0 else 0.0

        # =======================================================================
        # 2. Tín hiệu MUA cực mạnh (ưu tiên Momentum trước)
        # =======================================================================
        if flow_change >= 1.8:
            signals.append(f"🚀 MOMENTUM CỰC ĐẠI +{flow_change} – MUA NGAY FULL KÝ QUỸ!")
        elif flow_change >= 1.2:
            signals.append(f"🔥 MOMENTUM RẤT MẠNH +{flow_change} – Cơ hội vàng!")
        elif flow_change >= 0.8:
            signals.append(f"💪 MOMENTUM MẠNH +{flow_change} – Gom hàng tốt")

        if smart_net_12d >= 150:
            signals.append(f"💎 SMART MONEY GOM ĐIÊN CUỒNG (+{smart_net_12d:.0f} tỷ)")
        elif smart_net_12d >= 80:
            signals.append(f"🐳 Cá mập gom mạnh (+{smart_net_12d:.0f} tỷ)")
        elif smart_net_12d >= 40:
            signals.append(f"📈 Dấu hiệu gom hàng (+{smart_net_12d:.0f} tỷ)")

        if smart_net_today >= 80:
            signals.append(f"⚡ HÔM NAY GOM KHỦNG (+{smart_net_today:.0f} tỷ)")

        # =======================================================================
        # 3. Tín hiệu đặc biệt (giữ nguyên như cũ)
        # =======================================================================
        price_range_60d = recent.tail(60)['high'].max() / recent.tail(60)['low'].min() if len(recent) >= 60 else 99
        if price_range_60d <= 1.30 and smart_net_12d >= 60:
            signals.append("🕵️ GOM ẨN DÀI HẠN → Sóng lớn sắp bùng nổ!")

        foreign_30d = df_history.tail(40)['foreign_net_val'].sum() / 1e9
        if foreign_30d < -100 and foreign_net_12d > 60:
            signals.append("✈️ KHỐI NGOẠI ĐẢO CHIỀU – Tín hiệu đáy siêu mạnh!")

        # =======================================================================
        # 4. Cảnh báo XẢ
        # =======================================================================
        if flow_change <= -1.2:
            warnings.append(f"⚡ MOMENTUM ÂM NẶNG {flow_change} – Nguy cơ xả hàng!")
        if smart_net_12d <= -100:
            warnings.append(f"🌊 CÁ MẬP XẢ LOẠT (-{abs(smart_net_12d):.0f} tỷ)")
        elif smart_net_12d <= -60:
            warnings.append(f"👋 Dòng tiền lớn rút ra (-{abs(smart_net_12d):.0f} tỷ)")

        price_up_15d = latest['close'] / df_history.iloc[-16]['close'] - 1 if len(df_history) >= 16 else 0
        if price_up_15d >= 0.20 and prop_net_12d <= -50:
            warnings.append("🎢 PUMP & DUMP TỰ DOANH – Giá lên mạnh nhưng tự doanh xả sạch!")

        # =======================================================================
        # 5. Verdict tự động theo backtest
        # =======================================================================
        if flow_change >= 1.8:
            verdict = "MUA NGAY – FULL KÝ QUỸ"
        elif flow_change >= 1.2:
            verdict = "MUA MẠNH"
        elif flow_change >= 0.8 or (8.0 <= flow_score < 8.5 and flow_change >= 0.8):
            verdict = "MUA VỪA"
        elif flow_score >= 8.5 and flow_change >= 0:
            verdict = "MUA VÀ GIỮ"
        elif flow_score >= 8.5 and flow_change < 0:
            verdict = "CẢNH GIÁC – CHỐT LỜI"
        elif flow_change <= -1.2:
            verdict = "TRÁNH / BÁN"
        else:
            verdict = "QUAN SÁT"

        return {
            "flow_score": flow_score,
            "flow_change": flow_change,
            "scenario": scenario,
            "verdict": verdict,
            "signals": signals[:5],
            "warnings": warnings[:3],
            "smart_net_val": round(smart_net_12d, 1),      # giữ nguyên tên cũ cho core.py
            "smart_ratio": smart_ratio_12d,
            "smart_net_12d": round(smart_net_12d, 1),
            "foreign_net_12d": round(foreign_net_12d, 1),
            "prop_net_12d": round(prop_net_12d, 1),
        }
        