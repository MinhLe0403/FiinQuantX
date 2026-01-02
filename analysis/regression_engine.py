# analysis/regression_engine.py
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import r2_score, mean_absolute_error

class RegressionBot:
    def __init__(self):
        # ĐỊNH NGHĨA CÁC BIẾN NGUYÊN NHÂN (FEATURES)
        # Bạn có thể thêm bất kỳ cột nào có trong df_scored
        self.features = [
            'score_tech',    # Điểm kỹ thuật tổng hợp
            'score_flow',    # Điểm dòng tiền
            'score_fund',    # Điểm cơ bản
            'score_val',     # Điểm định giá
            'RSI_14',        # Momentum
            'ADX',           # Trend Strength
            'smart_net_val'  # Giá trị mua ròng (cần xử lý trong prepare)
        ]

    def prepare_data(self, df, horizon=5):
        data = df.copy()
        
        # 1. Tạo biến Target
        data[f'return_t{horizon}'] = data['close'].shift(-horizon) / data['close'] - 1
        
        # 2. Xử lý smart_net_val
        if 'foreign_net_val' in data.columns:
            data['smart_net_val'] = (data['foreign_net_val'].fillna(0) + data.get('prop_net_val', 0).fillna(0)) / 1e9
        
        # 3. CHỌN FEATURES LINH HOẠT (Quan trọng)
        # Chỉ giữ lại các feature có ít nhất 50% dữ liệu (tránh cột toàn NaN)
        available_features = []
        for f in self.features:
            if f in data.columns:
                # Nếu cột đó có quá nhiều NaN (>50%), ta bỏ qua cột đó, chứ không bỏ dòng
                if data[f].isna().mean() < 0.5:
                    available_features.append(f)
                    # Fill NaN của cột feature bằng trung vị (median) để không mất dữ liệu
                    data[f] = data[f].fillna(data[f].median())
        
        # Nếu không còn feature nào -> Trả về rỗng
        if not available_features:
            return pd.DataFrame(), []

        # 4. Chỉ drop những dòng thiếu Target (Return) hoặc dữ liệu quá nát
        data = data.dropna(subset=[f'return_t{horizon}'] + available_features)
        
        return data, available_features

    def train_and_predict(self, df, horizon_list=[2, 5, 10, 20]):
        """
        Hàm cốt lõi: 
        Duyệt qua các khung thời gian, huấn luyện mô hình và dự báo.
        """
        results = {}
        
        for h in horizon_list:
            # A. Chuẩn bị dữ liệu
            train_df, valid_feats = self.prepare_data(df, horizon=h)
            
            # Cần ít nhất 60 phiên để hồi quy có ý nghĩa
            if len(train_df) < 60: 
                continue

            X = train_df[valid_feats]
            y = train_df[f'return_t{h}']

            # B. Train Model (Hồi quy tuyến tính)
            # Dùng Ridge Regression để giảm nhẹ vấn đề đa cộng tuyến (nếu các score tương đồng nhau)
            model = Ridge(alpha=1.0) 
            model.fit(X, y)
            
            # C. Đánh giá Model (In-sample Backtest)
            y_pred = model.predict(X)
            r2 = r2_score(y, y_pred) # Độ phù hợp của mô hình
            mae = mean_absolute_error(y, y_pred) # Sai số trung bình
            
            # D. Dự báo cho hiện tại (Real-time Prediction)
            # Lấy dòng dữ liệu mới nhất (chưa có target thực tế) để dự báo tương lai
            last_row = df.iloc[-1:][valid_feats].fillna(0)
            predicted_return = model.predict(last_row)[0]
            
            # Lưu lại Beta (Hệ số tác động của từng biến)
            betas = dict(zip(valid_feats, model.coef_))
            
            results[f'T+{h}'] = {
                'predicted_return': predicted_return, # Dự báo lợi nhuận %
                'r2_score': r2,                       # Độ tin cậy của mô hình
                'mae_error': mae,                     # Sai số biên
                'betas': betas,                       # Trọng số (Biến nào quan trọng nhất?)
                'sample_size': len(train_df)
            }
            
        return results