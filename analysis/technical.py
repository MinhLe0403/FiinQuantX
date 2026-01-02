# analysis/technical.py
import pandas as pd
import numpy as np

class TechnicalEngine:
    def __init__(self):
        pass

    # --- INDICATORS CALCULATIONS (Giữ nguyên các hàm tính toán cơ bản) ---
    @staticmethod
    def _ema(series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()

    @staticmethod
    def _sma(series: pd.Series, length: int) -> pd.Series:
        return series.rolling(window=length, min_periods=1).mean()

    @staticmethod
    def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=length, min_periods=length).mean()
        avg_loss = loss.rolling(window=length, min_periods=length).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd(close: pd.Series, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return pd.DataFrame({"MACD": macd_line, "MACD_SIGNAL": signal_line, "MACD_HIST": hist})

    @staticmethod
    def _bbands(close: pd.Series, length=20, std_dev=2.0):
        sma = close.rolling(window=length).mean()
        std = close.rolling(window=length).std()
        return pd.DataFrame({
            "BB_MID": sma,
            "BB_UPPER": sma + std * std_dev,
            "BB_LOWER": sma - std * std_dev
        })

    @staticmethod
    def _atr(high, low, close, length=14):
        tr0 = abs(high - low)
        tr1 = abs(high - close.shift(1))
        tr2 = abs(low - close.shift(1))
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        return tr.rolling(window=length).mean()

    @staticmethod
    def _ichimoku(high, low, close):
        tenkan = (high.rolling(window=9).max() + low.rolling(window=9).min()) / 2
        kijun = (high.rolling(window=26).max() + low.rolling(window=26).min()) / 2
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = ((high.rolling(window=52).max() + low.rolling(window=52).min()) / 2).shift(26)
        chikou = close.shift(-26)
        return pd.DataFrame({
            "ICHI_TENKAN": tenkan, "ICHI_KIJUN": kijun,
            "ICHI_SPAN_A": span_a, "ICHI_SPAN_B": span_b, "ICHI_CHIKOU": chikou
        })

    @staticmethod
    def _stoch(high, low, close, k_window=14, d_window=3):
        low_min = low.rolling(window=k_window).min()
        high_max = high.rolling(window=k_window).max()
        k_percent = 100 * ((close - low_min) / (high_max - low_min + 1e-10))
        d_percent = k_percent.rolling(window=d_window).mean()
        return pd.DataFrame({"STOCH_K": k_percent, "STOCH_D": d_percent})

    @staticmethod
    def _adx(high, low, close, length=14):
        tr0 = abs(high - low)
        tr1 = abs(high - close.shift(1))
        tr2 = abs(low - close.shift(1))
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        
        up = high.diff(); down = -low.diff()
        plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
        
        tr_smooth = tr.ewm(alpha=1/length, adjust=False).mean().replace(0, 1e-10)
        plus_di = 100 * (plus_dm.ewm(alpha=1/length, adjust=False).mean() / tr_smooth)
        minus_di = 100 * (minus_dm.ewm(alpha=1/length, adjust=False).mean() / tr_smooth)
        
        sum_di = (plus_di + minus_di).replace(0, 1e-10)
        dx = 100 * abs(plus_di - minus_di) / sum_di
        adx = dx.ewm(alpha=1/length, adjust=False).mean()
        return pd.DataFrame({"ADX": adx, "PLUS_DI": plus_di, "MINUS_DI": minus_di})
    
    @staticmethod
    def _bollinger_bandwidth(close, length=20, std_dev=2.0):
        """Tính độ rộng dải Bollinger (để bắt Squeeze)"""
        sma = close.rolling(window=length).mean()
        std = close.rolling(window=length).std()
        upper = sma + std * std_dev
        lower = sma - std * std_dev
        
        # Bandwidth % = (Upper - Lower) / Middle
        # Tránh chia 0
        bandwidth = (upper - lower) / sma.replace(0, 1) * 100
        return bandwidth

    @staticmethod
    def _money_flow_index(high, low, close, volume, length=14):
        """Money Flow Index (MFI) - RSI kết hợp Volume"""
        tp = (high + low + close) / 3
        raw_money_flow = tp * volume
        
        flow_pos = np.where(tp > tp.shift(1), raw_money_flow, 0)
        flow_neg = np.where(tp < tp.shift(1), raw_money_flow, 0)
        
        flow_pos_s = pd.Series(flow_pos, index=close.index).rolling(length).sum()
        flow_neg_s = pd.Series(flow_neg, index=close.index).rolling(length).sum()
        
        mfi = 100 - (100 / (1 + flow_pos_s / flow_neg_s.replace(0, 1)))
        return mfi

    @staticmethod
    def _ad_line(high, low, close, volume):
        """Accumulation/Distribution Line (A/D Line)"""
        # CLV = [(C - L) - (H - C)] / (H - L)
        # AD = Previous AD + CLV * Volume
        
        # Tránh chia cho 0 nếu High == Low
        range_hl = (high - low).replace(0, 1e-5)
        clv = ((close - low) - (high - close)) / range_hl
        ad_vol = clv * volume
        ad_line = ad_vol.cumsum()
        return ad_line

    def add_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or len(df) < 52: return df
        df = df.copy().sort_values('time').reset_index(drop=True)
        for c in ['open','high','low','close','volume']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        c, h, l, v = df['close'], df['high'], df['low'], df['volume']

        df['EMA_20'] = self._ema(c, 20)
        df['EMA_50'] = self._ema(c, 50)
        df['EMA_200'] = self._ema(c, 200)
        df['RSI_14'] = self._rsi(c, 14)
        df = pd.concat([df, self._macd(c), self._bbands(c), self._ichimoku(h,l,c), self._stoch(h,l,c), self._adx(h,l,c)], axis=1)
        
        df['ATRr_14'] = self._atr(h, l, c, 14)
        df['VOL_SMA_20'] = v.rolling(20).mean()
        df['HIGH_52W'] = h.rolling(252, min_periods=1).max()
        df['BB_WIDTH'] = self._bollinger_bandwidth(c)
        df['MFI_14'] = self._money_flow_index(h, l, c, v)
        df['AD_LINE'] = self._ad_line(h, l, c, v)
        df['SMA_200'] = c.rolling(200).mean()
        
        # Fillna an toàn
        df.iloc[-1] = df.iloc[-1].ffill()
        
        # --- NEW: BỔ SUNG DATA CHO LOGIC MỚI ---
        # 1. Price Structure (Hard Support) - Donchian Channel Lower 20
        df['LOW_20D'] = df['low'].rolling(20).min()
        
        # 2. Volume Analysis
        # Vol Spike: Vol > 1.3 lần TB 20 phiên
        df['VOL_SPIKE'] = np.where(df['volume'] > df['VOL_SMA_20'] * 1.3, True, False)
        
        # 3. Trend Alignment Check
        # Uptrend mạnh: Giá > E20 > E50 > E200
        e20 = df['EMA_20']; e50 = df['EMA_50']; e200 = df['EMA_200']
        df['TREND_STRONG'] = np.where(
            (df['close'] > e20) & (e20 > e50) & (e50 > e200), True, False
        )
        
        return df

    # --- NEW: CALCULATE TECHNICAL SCORE ---
    def calculate_technical_score(self, df: pd.DataFrame) -> pd.Series:
        if df.empty: return pd.Series()
        
        score = pd.Series(0.0, index=df.index)
        c = df['close']
        
        # Helper để lấy column an toàn
        def get(col, default=0): return df[col] if col in df.columns else pd.Series(default, index=df.index)

        # 1. Trend EMA
        e20, e50, e200 = get('EMA_20'), get('EMA_50'), get('EMA_200')
        score += np.where((c > e20) & (e20 > e50) & (e50 > e200), 4.0, 
                 np.where((c > e20) & (e20 > e50), 3.0,
                 np.where(c > e20, 1.5, 0.0)))
        
        # 2. MACD
        score += np.where((get('MACD_HIST') > 0) & (get('MACD') > get('MACD_SIGNAL')), 2.0, 0.0)
        
        # 3. RSI
        rsi = get('RSI_14', 50)
        score += np.where((rsi > 40) & (rsi < 70), 1.0, np.where(rsi < 30, 1.5, 0.0))
        
        # 4. Ichimoku (Cloud Check)
        span_a = get('ICHI_SPAN_A', 99999999) # Default cực lớn để fail condition
        span_b = get('ICHI_SPAN_B', 99999999)
        cloud_top = np.maximum(span_a, span_b)
        score += np.where((span_a < 99999999) & (c > cloud_top), 1.5, 0.0)
        
        # 5. ADX
        score += np.where((get('ADX') > 25) & (get('PLUS_DI') > get('MINUS_DI')), 1.0, 0.0)

        # 6. Breakout / BBands
        high_52w = get('HIGH_52W', c * 1.5)
        score += np.where(c > high_52w * 0.95, 2.0, 0.0)
        
        bbu = get('BB_UPPER', c * 1.5)
        score += np.where(c > bbu * 0.98, 1.0, 0.0)

        return score.clip(0, 10)

    # --- NEW: CALCULATE RISK SCORE ---
    def calculate_risk_score(self, df: pd.DataFrame) -> pd.Series:
        if df.empty: return pd.Series()
        score = pd.Series(10.0, index=df.index)
        
        vol20 = df['volume'].rolling(20).mean().fillna(0)
        score -= np.where(vol20 < 300000, 4.0, np.where(vol20 < 800000, 1.5, 0.0))
        
        atr = df.get('ATRr_14', 0)
        c = df['close'].replace(0, 1)
        score -= np.where((c > 0) & ((atr / c * 100) > 7), 2.0, 0.0)
        
        return score.clip(0, 10)

    # --- NEW: GET SIGNALS FOR TEXT OUTPUT ---
    def get_signals(self, row: pd.Series):
        """
        Trả về signals (TỐT) và warnings (XẤU/RỦI RO)
        Dựa trên dữ liệu phiên cuối cùng.
        """
        signals = []
        warnings = []
        
        c = row['close']

        # 1. Ichimoku Cloud (Trend dài hạn)
        span_a, span_b = row.get('ICHI_SPAN_A', 0), row.get('ICHI_SPAN_B', 0)
        tenkan, kijun = row.get('ICHI_TENKAN', 0), row.get('ICHI_KIJUN', 0)
        
        if span_a > 0:
            cloud_top = max(span_a, span_b)
            cloud_bottom = min(span_a, span_b)
            
            # Tốt
            if c > cloud_top:
                signals.append("☁️ Giá nằm trên Mây (Uptrend dài hạn)")
                if tenkan > kijun: 
                    signals.append("⚔️ Tenkan cắt lên Kijun (Thế giá tăng mạnh)")
            # Xấu -> Đẩy vào warnings
            elif c < cloud_bottom:
                warnings.append("🔻 Giá nằm dưới Mây (Downtrend)")
                if tenkan < kijun:
                    warnings.append("⚔️ Tenkan cắt xuống Kijun (Thế giá giảm)")
            # Sideway -> Không đưa vào signals để tránh nhiễu (hoặc đưa vào warnings nếu muốn cảnh báo kẹt hàng)
            else:
                warnings.append("⚠️ Giá đang kẹt trong Mây (Sideway/Nhiễu)")

        # 2. ADX & DMI (Sức mạnh xu hướng)
        adx = row.get('ADX', 0)
        p_di = row.get('PLUS_DI', 0)
        m_di = row.get('MINUS_DI', 0)
        
        if adx > 25:
            if p_di > m_di:
                signals.append(f"💪 Xu hướng TĂNG rất mạnh (ADX={adx:.1f})")
            else:
                # Xấu -> Đẩy vào warnings
                warnings.append(f"🔪 Xu hướng GIẢM rất mạnh (ADX={adx:.1f})")
        else:
            # Sideway yếu
            pass 

        # 3. Moving Averages (EMA Structure)
        e20, e50, e200 = row.get('EMA_20', 0), row.get('EMA_50', 0), row.get('EMA_200', 0)
        
        # Tốt
        if c > e20 and e20 > e50:
            signals.append("✅ Thế mây EMA Tăng (Price > E20 > E50)")
        elif c > e20 and c < e50:
            signals.append("🎣 Giá phục hồi vượt E20 (Hồi phục ngắn hạn)")
            
        # Xấu -> Warnings
        if c < e20 and c < e50:
            warnings.append("📉 Giá gãy các đường EMA ngắn & trung hạn")
        if c < e200:
             warnings.append("☠️ Giá dưới EMA 200 (Downtrend dài hạn)")

        # 4. Stochastic & RSI (Động lượng)
        stoch_k = row.get('STOCH_K', 50)
        stoch_d = row.get('STOCH_D', 50)
        rsi = row.get('RSI_14', 50)
        
        # Stoch
        if stoch_k < 20 and stoch_k > stoch_d:
            signals.append("🎣 Stoch cắt lên vùng Quá bán (Điểm mua ngắn hạn)")
        elif stoch_k > 80 and stoch_k < stoch_d:
            warnings.append("🛑 Stoch cắt xuống vùng Quá mua (Tín hiệu chốt lời)")

        # RSI
        if rsi < 30:
            signals.append(f"❄️ RSI Quá bán ({rsi:.0f}) -> Dễ có nhịp hồi")
        elif rsi > 70:
            warnings.append(f"🔥 RSI Quá mua ({rsi:.0f}) -> Rủi ro chỉnh")
        elif rsi < 45 and c < e50:
             warnings.append("⚠️ Động lượng yếu (RSI < 45)")

        # 5. Price Action (Đỉnh/Đáy)
        high_52 = row.get('HIGH_52W', 999999)
        if c > high_52 * 0.95:
            signals.append("🚀 Giá tiệm cận Đỉnh 1 năm")
            
        return {"signals": signals, "warnings": warnings}