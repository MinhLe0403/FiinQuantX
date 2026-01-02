import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
import os

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from analysis.core import StockAnalyzer
    from etl.on_demand import OnDemandLoader
except ImportError as e:
    st.error(f"Lỗi module: {e}")
    st.stop()

st.set_page_config(page_title="FiinQuant Pro", layout="wide", page_icon="🦈")

# CSS ĐẸP HƠN, HIỆN ĐẠI HƠN
st.markdown("""
<style>
    .big-score {font-size: 68px !important; font-weight: bold; text-align: center;}
    .metric-card {
        background: #1e1e1e; padding: 15px; border-radius: 10px; 
        text-align: center; border-left: 6px solid #00AA00;
        margin-bottom: 10px;
    }
    .warning-card {border-left-color: #AA0000;}
    .stMetricValue {font-size: 20px !important;}
    .metric-contribution {font-size: 12px; color: #888; font-style: italic; margin-top: 5px;}
    .sub-metric-label {font-size: 14px; color: #aaa;}
    .sub-metric-value {font-size: 20px; font-weight: bold; color: white;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.header("CÔNG CỤ SĂN CÁ MẬP")
input_symbol = st.sidebar.text_input("Nhập Mã CP:", value="FPT").upper().strip()
days_lookback = st.sidebar.slider("Khung thời gian phân tích (Ngày):", 30, 365, 60)

if st.sidebar.button("Cập nhật Dữ liệu", type="primary"):
    if not input_symbol:
        st.stop()
    with st.sidebar.status(f"Đang tải {input_symbol}...", expanded=True) as status:
        try:
            loader = OnDemandLoader()
            success, msg = loader.check_and_update_ticker(input_symbol, years_back=5)
            if success:
                status.update(label="Hoàn tất!", state="complete")
                st.success("Cập nhật thành công!")
                st.cache_data.clear()
            else:
                status.update(label="Lỗi", state="error")
                st.sidebar.error(msg)
        except Exception as e:
            st.error(f"Lỗi cập nhật: {e}")

# --- HELPER FORMAT ---
def safe_fmt(val, fmt="{:,.0f}", default="-"):
    if pd.isna(val) or val is None:
        return default
    try:
        return fmt.format(val)
    except:
        return default

def card(label, value, color="#3366CC"):
    st.markdown(f"""
    <div class='metric-card' style='border-left-color:{color}'>
        <div class='sub-metric-label'>{label}</div>
        <div class='sub-metric-value'>{value}</div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN ---
analyzer = StockAnalyzer()

try:
    # Lấy dữ liệu
    df_chart = analyzer.get_full_data(input_symbol, limit=400)

    if hasattr(analyzer, 'get_investor_summary'):
        df_stats = analyzer.get_investor_summary(input_symbol, limit=days_lookback)
    else:
        df_stats = pd.DataFrame()

    if df_chart.empty:
        st.warning(f"Chưa có dữ liệu cho {input_symbol}. Hãy bấm 'Cập nhật Dữ liệu'.")
        st.stop()

    # PHÂN TÍCH MỚI
    health = analyzer.analyze_health(input_symbol)
    fin = health.get('financials') or {}
    scores = health.get('scores', {})
    details = health.get('details', {})
    hist_scores = health.get('history_scores', pd.DataFrame()) # Lấy lịch sử điểm

    # --- HEADER ĐẸP (GIỮ NGUYÊN) ---
    col1, col2 = st.columns([2.5, 1.5])
    with col1:
        st.markdown(f"# {input_symbol}")
        st.markdown(f"### {health['recommendation']}")
    with col2:
        score = health['total_score']
        color = "#00FF00" if score >= 7 else "#FFD700" if score >= 5 else "#FF4444"
        st.markdown(f"<div class='big-score' style='color:{color}'>{score:.1f}</div>", unsafe_allow_html=True)
        st.caption("<p style='text-align:center; margin-top:-10px'><strong>Tổng điểm / 10</strong></p>", unsafe_allow_html=True)

    # --- 5 ĐIỂM RIÊNG BIỆT (CÓ ĐÓNG GÓP) ---
    st.markdown("### Đánh giá chi tiết theo 5 yếu tố")
    cols = st.columns(5)
    
    metrics_config = [
        {"label": "Kỹ thuật", "key": "technical", "color": "#3366CC", "weight": 0.25},
        {"label": "Dòng tiền", "key": "flow", "color": "#00FF00", "weight": 0.35},
        {"label": "Cơ bản", "key": "fundamental", "color": "#FF8C00", "weight": 0.20},
        {"label": "Định giá", "key": "valuation", "color": "#9932CC", "weight": 0.15},
        {"label": "Rủi ro", "key": "risk", "color": "#FF4444", "weight": 0.0}
    ]

    for col, cfg in zip(cols, metrics_config):
        key = cfg['key']
        val = scores.get(key, 0)
        weight = cfg['weight']
        clr = cfg['color']
        contribution = val * weight
        contrib_text = f"Đóng góp: +{contribution:.2f}" if weight > 0 else "Hệ số phạt"
        
        with col:
            st.markdown(f"<div class='metric-card' style='border-left-color:{clr}'>", unsafe_allow_html=True)
            st.markdown(f"**{cfg['label']}**")
            st.markdown(f"<h2 style='color:{clr}; margin:5px'>{val:.1f}<small>/10</small></h2>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-contribution'>{contrib_text}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # --- SMART MONEY & CHỈ SỐ CHÍNH ---
    st.markdown("### Dòng tiền & Chỉ số quan trọng")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Giá hiện tại", safe_fmt(health['close'], "{:,.0f}"), f"{health.get('change_pct', 0):+.2f}%")
    m2.metric("P/E", safe_fmt(health.get('pe'), "{:.1f}"))
    m3.metric("Smart Money (10D)", f"{health.get('smart_net_billion_10d', 0):+.1f} tỷ")
    m4.metric("Tỷ trọng Smart Money", f"{health.get('smart_participation', 0):.1f}%")
    m5.metric("Thanh khoản TB 20 ngày", safe_fmt(health.get('volume_20d_avg', 0), "{:,.0f}"))

    # --- LUẬN ĐIỂM CHI TIẾT ---
    with st.expander("Luận điểm tích cực & Cảnh báo", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            st.success("**TÍCH CỰC**")
            # Gộp tất cả điểm tốt từ các mục
            all_pos = []
            for key in ['technical', 'flow', 'fundamental', 'valuation']:
                all_pos.extend(details.get(key, []))
            for item in all_pos:
                if item: st.write(f"✅ {item}")

        with cols[1]:
            # Cảnh báo
            warnings = details.get('warning', []) + details.get('risk', [])
            if warnings:
                st.error("**CẢNH BÁO**")
                for item in warnings:
                    st.write(f"⚠️ {item}")
            else:
                st.info("Chưa phát hiện rủi ro lớn.")

    # --- 5 TABS CHI TIẾT ---
    # (Sử dụng lại 5 Tabs của phiên bản cũ mà bạn thích)
    t1, t2, t3, t4, t5 = st.tabs([
        "🌊 1. DÒNG TIỀN (SÂU)", "📈 2. KỸ THUẬT", "🏢 3. CƠ BẢN", "💰 4. ĐỊNH GIÁ", "🛡️ 5. RỦI RO"
    ])

    # === TAB 1: DÒNG TIỀN (TÍCH HỢP ĐẦY ĐỦ) ===
    with t1:
        c_left, c_right = st.columns([2, 1])
        with c_left:
            # CHART 1: Lịch sử Điểm Dòng Tiền (Feature Mới)
            if not hist_scores.empty:
                fig_s = make_subplots(specs=[[{"secondary_y": True}]])
                fig_s.add_trace(go.Scatter(x=hist_scores['time'], y=hist_scores['close'], name="Giá", line=dict(color='gray', dash='dot')), secondary_y=False)
                fig_s.add_trace(go.Scatter(x=hist_scores['time'], y=hist_scores['score_flow'], name="Điểm Dòng Tiền", line=dict(color='#00FF00', width=2), fill='tozeroy'), secondary_y=True)
                fig_s.update_yaxes(title_text="Điểm (0-10)", range=[0, 10], secondary_y=True)
                fig_s.update_layout(title="Biến động Sức mạnh Dòng tiền", height=350, template="plotly_dark")
                st.plotly_chart(fig_s, use_container_width=True)
        
        with c_right:
            st.write("### Chỉ số đóng góp:")
            st.metric("Smart Money (10D)", f"{health.get('smart_net_billion_10d', 0):+.1f} tỷ")
            st.metric("Tỷ trọng Smart Money", f"{health.get('smart_participation', 0):.1f}%")
            # Thêm các chỉ số từ bảng thống kê hành vi (lấy dòng đầu tiên - Nước ngoài)
            if not df_stats.empty:
                foreign_row = df_stats[df_stats['Nhà Đầu Tư'] == 'Nước ngoài'].iloc[0]
                st.metric("Nước ngoài Gom/Xả", f"{foreign_row['KL Ròng Tổng']:,.0f}")

        st.divider()

        # Lấy thông tin Deep Dive
        f_health = health.get('flow_health', {})
        
        # 1. HIỂN THỊ TÍN HIỆU QUAN TRỌNG (Metric)
        st.subheader("🕵️‍♂️ Phân tích Hành vi Cá mập (Deep Dive)")
        col_d1, col_d2, col_d3 = st.columns(3)
        
        div_sig = f_health.get('divergence', 'Không rõ')
        div_color = "off"
        if "Bullish" in div_sig: div_color = "normal" # Xanh
        elif "Bearish" in div_sig: div_color = "inverse" # Đỏ

        col_d1.metric("Tín hiệu Phân kỳ", div_sig, delta_color=div_color)
        col_d2.metric("Vùng Gom Mạnh Nhất (60 phiên)", f_health.get('shark_zone', '-'))
        col_d3.metric("Giá trị Gom tại vùng này", f"{f_health.get('shark_in_zone_val', 0):.1f} tỷ")

        st.divider()

        # 3. Chart VWAP & Vị Thế (Logic Cũ + UI Mới)
        st.markdown("### 2. Phân tích Hành vi Giá & Khối lượng (Period VWAP)")
        
        col_sel, _ = st.columns([1, 3])
        with col_sel:
            target_investor = st.selectbox("Chọn nhóm NĐT:", 
                ["Nước ngoài (foreign)", "Tự doanh (prop)", "Cá nhân (local_ind)", "Tổ chức TN (local_inst)"], index=0)
        
        map_inv = {"Nước ngoài (foreign)": "foreign", "Tự doanh (prop)": "prop", "Cá nhân (local_ind)": "local_ind", "Tổ chức TN (local_inst)": "local_inst"}
        code = map_inv[target_investor]

        # Tính toán On-the-fly
        df_calc = df_chart.fillna(0).copy()
        # Cắt theo khung thời gian user chọn để tính VWAP đúng giai đoạn đó
        df_calc = df_calc.tail(days_lookback).reset_index(drop=True)

        c_buy_val = df_calc[f'{code}_buy_val'].cumsum()
        c_buy_vol = df_calc[f'{code}_buy_vol'].cumsum()
        c_sell_val = df_calc[f'{code}_sell_val'].cumsum()
        c_sell_vol = df_calc[f'{code}_sell_vol'].cumsum()
        
        # Tính VWAP
        df_calc['vwap_buy'] = c_buy_val / c_buy_vol.replace(0, 1)
        df_calc['vwap_sell'] = c_sell_val / c_sell_vol.replace(0, 1)
        # Fix đoạn đầu
        df_calc['vwap_buy'] = df_calc['vwap_buy'].mask(c_buy_vol == 0, df_calc['close'])
        df_calc['vwap_sell'] = df_calc['vwap_sell'].mask(c_sell_vol == 0, df_calc['close'])
        
        df_calc['net_vol_acc'] = c_buy_vol - c_sell_vol

        # Vẽ Chart VWAP
        fig_vwap = make_subplots(specs=[[{"secondary_y": True}]])
        fig_vwap.add_trace(go.Scatter(x=df_calc['time'], y=df_calc['close'], name="Giá TT", line=dict(color='gray', width=1, dash='dot'), opacity=0.5), secondary_y=False)
        fig_vwap.add_trace(go.Scatter(x=df_calc['time'], y=df_calc['vwap_buy'], name="VWAP Mua", line=dict(color='#00FF00', width=2)), secondary_y=False)
        fig_vwap.add_trace(go.Scatter(x=df_calc['time'], y=df_calc['vwap_sell'], name="VWAP Bán", line=dict(color='#FF4B4B', width=2)), secondary_y=False)
        
        colors = ['rgba(0, 255, 0, 0.15)' if v >= 0 else 'rgba(255, 0, 0, 0.15)' for v in df_calc['net_vol_acc']]
        fig_vwap.add_trace(go.Bar(x=df_calc['time'], y=df_calc['net_vol_acc'], name="Tích Lũy Ròng (Kỳ này)", marker_color=colors), secondary_y=True)

        fig_vwap.update_layout(template="plotly_dark", height=450, hovermode="x unified", title=f"Hành vi {target_investor} (Trong kỳ)")
        st.plotly_chart(fig_vwap, use_container_width=True)

        st.divider()

        # 4. Chart Xu hướng Dòng tiền Tích lũy Dài Hạn (CUSUM RAW - TOÀN LỊCH SỬ)
        st.markdown("### 3. Xu hướng Gom Ròng Tích Lũy (Toàn lịch sử)")
        st.info("Biểu đồ này cộng dồn khối lượng mua ròng từ quá khứ xa nhất có được. Dốc lên = Gom mạnh.")
        
        # Dùng df_chart (full history) thay vì df_calc (cắt ngắn)
        df_full = df_chart.fillna(0).copy()
        df_full['cum_net_foreign'] = df_full['foreign_net_vol'].cumsum()
        df_full['cum_net_prop'] = df_full['prop_net_vol'].cumsum()
        df_full['cum_net_ind'] = df_full['local_ind_net_vol'].cumsum()
        df_full['cum_net_inst'] = df_full['local_inst_net_vol'].cumsum()

        fig_cusum = make_subplots(specs=[[{"secondary_y": True}]])
        fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['close'], name="Giá CP", line=dict(color='gray', dash='dot')), secondary_y=False)
        fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['cum_net_foreign'], name="Nước ngoài", line=dict(color='yellow', width=2)), secondary_y=True)
        fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['cum_net_prop'], name="Tự doanh", line=dict(color='cyan', width=2)), secondary_y=True)
        fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['cum_net_ind'], name="Cá nhân", line=dict(color='red', width=2)), secondary_y=True)
        fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['cum_net_inst'], name="Tổ chức", line=dict(color='green', width=2)), secondary_y=True)
        
        fig_cusum.update_layout(title="Xu hướng Dòng tiền Tích lũy (Net Vol)", template="plotly_dark", height=500, hovermode="x unified")
        st.plotly_chart(fig_cusum, use_container_width=True)

        # 3. CHART ACTIVE PRESSURE (MUA CHỦ ĐỘNG vs BÁN CHỦ ĐỘNG)
        st.subheader("⚡ Áp lực Khớp lệnh Chủ động (Aggression)")
        st.info("💡 Mua Chủ Động (Xanh) thể hiện sự quyết liệt đẩy giá. Bán Chủ Động (Đỏ) thể hiện sự thoát hàng dứt khoát.")

        if 'buy_active_vol' in df_chart.columns:
            df_act = df_chart.tail(60)
            fig_act = go.Figure()
            
            # Vẽ dạng Bar chồng hoặc đối xứng
            fig_act.add_trace(go.Bar(x=df_act['time'], y=df_act['buy_active_vol'], name="Mua Chủ Động", marker_color='#00CC96'))
            fig_act.add_trace(go.Bar(x=df_act['time'], y=-df_act['sell_active_vol'], name="Bán Chủ Động", marker_color='#EF553B'))
            
            # Đường Net Active Tích lũy (Để xem phe nào đang thắng thế dài hạn)
            if 'active_pressure_cum' in df_act.columns:
                # Scale lại để vẽ chung trục (chỉ mang tính minh họa xu hướng)
                # Hoặc dùng secondary axis nếu muốn chính xác
                pass 

            fig_act.update_layout(title="Lực Mua/Bán Chủ Động (60 phiên)", barmode='overlay', height=350, template="plotly_dark")
            st.plotly_chart(fig_act, use_container_width=True)
            

        st.markdown(f"### 1. Bảng Chỉ Số Hành Vi (Trong {days_lookback} phiên gần nhất)")
        if not df_stats.empty:
            st.dataframe(
                df_stats.style.format({
                    "KL Mua TB": "{:,.0f}", "KL Bán TB": "{:,.0f}",
                    "VWAP Mua": "{:,.0f}", "VWAP Bán": "{:,.0f}",
                    "KL Ròng Tổng": "{:,.0f}", "Giá Trị Ròng": "{:,.0f}"
                })
                .applymap(lambda x: 'color: #00FF00' if x > 0 else 'color: #FF4B4B' if x < 0 else '', subset=['KL Ròng Tổng', 'Giá Trị Ròng'])
                .background_gradient(cmap='Blues', subset=['VWAP Mua', 'VWAP Bán']),
                use_container_width=True, hide_index=True
            )
            st.caption(f"Tips: Nếu VWAP Mua < Giá hiện tại ({health['close']:,.0f}) → nhóm này đang lãi")
        else:
            st.info("Không có dữ liệu thống kê hành vi.")

        st.divider()


    # === TAB 2: KỸ THUẬT CHUYÊN SÂU (ĐÃ UPDATE) ===
    with t2:
        # 1. Chart Lịch sử Điểm Tech (Giữ nguyên)
        if not hist_scores.empty:
            fig_t = make_subplots(specs=[[{"secondary_y": True}]])
            fig_t.add_trace(go.Scatter(x=hist_scores['time'], y=hist_scores['close'], name="Giá"), secondary_y=False)
            fig_t.add_trace(go.Scatter(x=hist_scores['time'], y=hist_scores['score_tech'], name="Điểm Tech", line=dict(color='#3366CC'), fill='tozeroy'), secondary_y=True)
            fig_t.update_yaxes(range=[0, 10], secondary_y=True)
            fig_t.update_layout(height=250, template="plotly_dark", margin=dict(l=0,r=0,t=30,b=0), title="Sức mạnh Kỹ thuật (Score)")
            st.plotly_chart(fig_t, use_container_width=True)

        st.divider()
        
        # Lấy dữ liệu Full Indicators từ core trả về
        df_full = health.get('full_df')
        
        if df_full is None or df_full.empty:
            st.warning("⚠️ Không có dữ liệu chỉ báo nâng cao. Vui lòng kiểm tra lại Core.")
        else:
            last = df_full.iloc[-1]

            # --- A. DASHBOARD CHỈ BÁO (RSI, ADX, STOCH, ICHIMOKU) ---
            st.subheader("🚦 Tín hiệu Kỹ thuật Đa chiều")
            c1, c2, c3, c4 = st.columns(4)
            
            # 1. RSI
            rsi = last.get('RSI_14', 50)
            c1.metric("RSI (14)", f"{rsi:.1f}", "Quá mua" if rsi > 70 else "Quá bán" if rsi < 30 else "Trung tính")
            
            # 2. ADX (Sức mạnh trend)
            adx = last.get('ADX', 0)
            trend_str = "Mạnh" if adx > 25 else "Yếu/Sideway"
            c2.metric("ADX (Trend)", f"{adx:.1f}", trend_str, delta_color="normal")

            # 3. Stochastic
            k, d = last.get('STOCH_K', 0), last.get('STOCH_D', 0)
            c3.metric("Stochastic %K", f"{k:.1f}", f"{k-d:.1f} (vs %D)")

            # 4. Ichimoku
            c_price = last['close']
            span_a = last.get('ICHI_SPAN_A', 0); span_b = last.get('ICHI_SPAN_B', 0)
            cloud_top = max(span_a, span_b)
            ichi_status = "Trên Mây ☁️" if c_price > cloud_top else "Dưới Mây 🔻" if c_price < min(span_a, span_b) else "Trong Mây ⚠️"
            c4.metric("Ichimoku", ichi_status)

            # --- B. CHART NÂNG CAO (ICHIMOKU + STOCH + MACD) ---
            st.subheader("📉 Biểu đồ Phân tích (Ichimoku + Stochastic)")
            
            # Checkbox tùy chọn hiển thị
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1: show_ichi = st.checkbox("Hiển thị Ichimoku Cloud", value=True)
            with col_opt2: show_ema = st.checkbox("Hiển thị EMA (20/50)", value=True)

            # Tạo Chart 3 dòng: Giá, Stochastic, MACD
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, 
                                row_heights=[0.6, 0.2, 0.2],
                                subplot_titles=("Price Action & Ichimoku", "Stochastic Oscillator", "MACD"))

            # --- ROW 1: GIÁ & ICHIMOKU ---
            fig.add_trace(go.Candlestick(x=df_full['time'], open=df_full['open'], high=df_full['high'], 
                                         low=df_full['low'], close=df_full['close'], name="Giá"), row=1, col=1)

            if show_ichi and 'ICHI_SPAN_A' in df_full.columns:
                # Vẽ Mây (Tô màu giữa Span A và Span B)
                # Mẹo: Vẽ Span A (ẩn), sau đó vẽ Span B và tô fill='tonexty'
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['ICHI_SPAN_A'], line=dict(width=0), 
                                         showlegend=False, hoverinfo='skip'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['ICHI_SPAN_B'], line=dict(width=0), 
                                         fill='tonexty', fillcolor='rgba(0, 250, 154, 0.15)', name="Cloud"), row=1, col=1)
                
                # Tenkan & Kijun
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['ICHI_TENKAN'], line=dict(color='#0496ff', width=1), name="Tenkan"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['ICHI_KIJUN'], line=dict(color='#a30000', width=1), name="Kijun"), row=1, col=1)

            if show_ema:
                if 'EMA_20' in df_full.columns: fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['EMA_20'], line=dict(color='yellow', width=1), name="EMA 20"), row=1, col=1)
                if 'EMA_50' in df_full.columns: fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['EMA_50'], line=dict(color='orange', width=1), name="EMA 50"), row=1, col=1)
                if 'BB_UPPER' in df_full.columns:
                    fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['BB_UPPER'], line=dict(color='gray', width=1, dash='dot'), name="BB Upper"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['BB_LOWER'], line=dict(color='gray', width=1, dash='dot'), name="BB Lower"), row=1, col=1)

            # --- ROW 2: STOCHASTIC ---
            if 'STOCH_K' in df_full.columns:
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['STOCH_K'], line=dict(color='#00FF00', width=1.5), name="Stoch %K"), row=2, col=1)
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['STOCH_D'], line=dict(color='red', width=1.5, dash='dot'), name="Stoch %D"), row=2, col=1)
                fig.add_hline(y=80, line_color="gray", line_dash="dot", row=2, col=1)
                fig.add_hline(y=20, line_color="gray", line_dash="dot", row=2, col=1)
                fig.update_yaxes(range=[0, 100], row=2, col=1)

            # --- ROW 3: MACD ---
            if 'MACD_HIST' in df_full.columns:
                colors_macd = ['green' if v >= 0 else 'red' for v in df_full['MACD_HIST']]
                fig.add_trace(go.Bar(x=df_full['time'], y=df_full['MACD_HIST'], marker_color=colors_macd, name="MACD Hist"), row=3, col=1)
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['MACD'], line=dict(color='#2962FF', width=1.5), name="MACD"), row=3, col=1)
                fig.add_trace(go.Scatter(x=df_full['time'], y=df_full['MACD_SIGNAL'], line=dict(color='#FF6D00', width=1.5), name="Signal"), row=3, col=1)

            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # --- C. DIỄN GIẢI CHI TIẾT ---
            st.info("💡 **Góc nhìn Chuyên gia:**")
            if details.get('technical'):
                for det in details['technical']:
                    st.write(f"• {det}")
            else:
                st.write("Chưa có tín hiệu kỹ thuật nổi bật.")
            
            st.divider()

            # --- D. BẢNG TỔNG HỢP CHỈ SỐ KỸ THUẬT (MỚI) ---
            with st.expander("📊 Xem Bảng Chi Tiết Giá Trị Các Chỉ Báo", expanded=False):
                
                # Hàm helper để đánh giá trạng thái nhanh
                def get_status(val, ref, type='bull'):
                    if type == 'bull': return "Tích cực" if val > ref else "Tiêu cực"
                    if type == 'bear': return "Tiêu cực" if val > ref else "Tích cực"
                    if type == 'rsi': 
                        if val > 70: return "Quá mua"
                        if val < 30: return "Quá bán"
                        return "Trung tính"
                    if type == 'adx': return "Mạnh" if val > 25 else "Yếu"
                    return ""

                # Chuẩn bị dữ liệu
                c = last['close']
                
                # 1. Nhóm Xu hướng (Moving Averages)
                trend_data = [
                    {"Chỉ báo": "Giá Đóng Cửa", "Giá trị": c, "Tín hiệu": "-"},
                    {"Chỉ báo": "EMA 20 (Ngắn hạn)", "Giá trị": last.get('EMA_20', 0), "Tín hiệu": get_status(c, last.get('EMA_20', 0))},
                    {"Chỉ báo": "EMA 50 (Trung hạn)", "Giá trị": last.get('EMA_50', 0), "Tín hiệu": get_status(c, last.get('EMA_50', 0))},
                    {"Chỉ báo": "EMA 200 (Dài hạn)", "Giá trị": last.get('EMA_200', 0), "Tín hiệu": get_status(c, last.get('EMA_200', 0))},
                    {"Chỉ báo": "ADX (Sức mạnh)", "Giá trị": last.get('ADX', 0), "Tín hiệu": get_status(last.get('ADX', 0), 25, 'adx')}
                ]
                
                # 2. Nhóm Động lượng (Oscillators)
                stoch_k = last.get('STOCH_K', 0); stoch_d = last.get('STOCH_D', 0)
                macd = last.get('MACD', 0); signal = last.get('MACD_SIGNAL', 0)
                
                osc_data = [
                    {"Chỉ báo": "RSI (14)", "Giá trị": last.get('RSI_14', 0), "Tín hiệu": get_status(last.get('RSI_14', 0), 0, 'rsi')},
                    {"Chỉ báo": "Stoch %K", "Giá trị": stoch_k, "Tín hiệu": "Cắt lên %D" if stoch_k > stoch_d else "Cắt xuống %D"},
                    {"Chỉ báo": "MACD", "Giá trị": macd, "Tín hiệu": "Trên Signal" if macd > signal else "Dưới Signal"},
                    {"Chỉ báo": "MACD Hist", "Giá trị": last.get('MACD_HIST', 0), "Tín hiệu": "Dương" if last.get('MACD_HIST', 0) > 0 else "Âm"},
                    {"Chỉ báo": "MFI (Dòng tiền)", "Giá trị": 0, "Tín hiệu": "N/A"} # Nếu sau này bạn thêm MFI
                ]

                # 3. Nhóm Ichimoku & Volatility
                tenkan = last.get('ICHI_TENKAN', 0); kijun = last.get('ICHI_KIJUN', 0)
                span_a = last.get('ICHI_SPAN_A', 0); span_b = last.get('ICHI_SPAN_B', 0)
                cloud_curr = max(span_a, span_b)
                
                ichi_data = [
                    {"Chỉ báo": "Tenkan-sen (9)", "Giá trị": tenkan, "Tín hiệu": "Trên Kijun" if tenkan > kijun else "Dưới Kijun"},
                    {"Chỉ báo": "Kijun-sen (26)", "Giá trị": kijun, "Tín hiệu": "-"},
                    {"Chỉ báo": "Span A", "Giá trị": span_a, "Tín hiệu": "Mây Xanh" if span_a > span_b else "Mây Đỏ"},
                    {"Chỉ báo": "Span B", "Giá trị": span_b, "Tín hiệu": "-"},
                    {"Chỉ báo": "Vị thế Mây", "Giá trị": c, "Tín hiệu": "Trên Mây" if c > cloud_curr else ("Dưới Mây" if c < min(span_a, span_b) else "Trong Mây")},
                    {"Chỉ báo": "BB Upper", "Giá trị": last.get('BB_UPPER', 0), "Tín hiệu": "Kháng cự"},
                    {"Chỉ báo": "BB Lower", "Giá trị": last.get('BB_LOWER', 0), "Tín hiệu": "Hỗ trợ"},
                    {"Chỉ báo": "ATR (Biến động)", "Giá trị": last.get('ATRr_14', 0), "Tín hiệu": f"{(last.get('ATRr_14', 0)/c*100):.1f}%"}
                ]

                # Hiển thị 3 cột
                col_t1, col_t2, col_t3 = st.columns(3)
                
                def make_df(data):
                    d = pd.DataFrame(data)
                    return d.style.format({"Giá trị": "{:,.2f}"})

                with col_t1:
                    st.markdown("**1. Xu hướng (Trend)**")
                    st.dataframe(make_df(trend_data), use_container_width=True, hide_index=True)

                with col_t2:
                    st.markdown("**2. Động lượng (Oscillators)**")
                    st.dataframe(make_df(osc_data), use_container_width=True, hide_index=True)
                    
                with col_t3:
                    st.markdown("**3. Ichimoku & Biến động**")
                    st.dataframe(make_df(ichi_data), use_container_width=True, hide_index=True)

    # === TAB 3: CƠ BẢN ===
    with t3:
        c_left, c_right = st.columns([1.2, 2.8])

        # -------------------------------------------------------
        # LEFT COLUMN
        # -------------------------------------------------------
        with c_left:

            # Chart lịch sử điểm cơ bản
            if not hist_scores.empty:
                fig_f = make_subplots(specs=[[{"secondary_y": True}]])
                fig_f.add_trace(
                    go.Scatter(
                        x=hist_scores['time'],
                        y=hist_scores['score_fund'],
                        name="Điểm Cơ bản",
                        line=dict(color='#FF8C00'),
                        fill='tozeroy'
                    ),
                    secondary_y=True
                )
                fig_f.update_yaxes(range=[0, 10], secondary_y=True)
                fig_f.update_layout(
                    height=250, template="plotly_dark",
                    title="Điểm Cơ bản",
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig_f, use_container_width=True)

            # Điểm tổng
            st.subheader(f"Điểm: {scores.get('fundamental')}/10")

            # --- Chỉ số quan trọng ---
            roe = fin.get('roe')
            roa = fin.get('roa')
            eps = fin.get('eps')

            st.metric("ROE", f"{roe*100:.1f}%" if roe else "-")
            st.metric("ROA", f"{roa*100:.1f}%" if roa else "-")
            st.metric("EPS", f"{eps:,.0f}" if eps else "-")

            # --- Đánh giá định tính ---
            st.write("**Đánh giá:**")
            for d in details.get('fundamental', []):
                st.success(f"🏢 {d}")

            # --- Chỉ số theo ngành ---
            if pd.notna(fin.get('nim')):  # Ngân hàng
                st.metric("NIM", safe_fmt(fin.get('nim', 0)*100, "{:.1f}%"))
                st.metric("Nợ xấu", safe_fmt(fin.get('bad_debt_ratio', 0)*100, "{:.1f}%"))
            else:  # Doanh nghiệp thường
                st.metric("Nợ/VCSH", safe_fmt(fin.get('debt_to_equity'), "{:.2f}"))

        # -------------------------------------------------------
        # RIGHT COLUMN
        # -------------------------------------------------------
        with c_right:
            if fin:
                st.markdown("#### Dữ liệu BCTC Quý gần nhất")
                fin_display = {
                    k: v for k, v in fin.items()
                    if k not in ['symbol', 'year', 'quarter']
                }
                st.json(fin_display)
            else:
                st.info("Chưa có dữ liệu.")

    # === TAB 4: ĐỊNH GIÁ ===
    with t4:

        if not hist_scores.empty:
            fig_v = make_subplots(specs=[[{"secondary_y": True}]])
            fig_v.add_trace(go.Scatter(x=hist_scores['time'], y=hist_scores['score_val'], name="Điểm Định giá", line=dict(color='#9932CC'), fill='tozeroy'), secondary_y=True)
            fig_v.update_yaxes(range=[0, 10], secondary_y=True)
            fig_v.update_layout(height=250, template="plotly_dark", title="Điểm Định giá", margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig_v, use_container_width=True)

        st.divider()

        c_left, c_right = st.columns([1.2, 2.8])
        with c_left:
            st.subheader(f"Điểm: {scores.get('valuation')}/10")
            pe = health.get('pe'); pb = health.get('pb')
            st.metric("P/E Hiện tại", f"{pe:.1f}" if pe else "-")
            st.metric("P/B Hiện tại", f"{pb:.1f}" if pb else "-")
            for d in details.get('valuation', []): st.info(f"💰 {d}")

        with c_right:
            c1, c2 = st.columns(2)
            c1.metric("P/E", safe_fmt(health.get('pe'), "{:.1f}"))
            c2.metric("P/B", safe_fmt(health.get('pb'), "{:.1f}"))

            if 'pe' in df_chart.columns:
                df_pe = df_chart[df_chart['pe'] > 0]
                fig_pe = go.Figure()
                fig_pe.add_trace(go.Scatter(x=df_pe['time'], y=df_pe['pe'], name="P/E Lịch sử", fill='tozeroy'))
                fig_pe.add_hline(y=df_pe['pe'].mean(), line_dash="dash", annotation_text="TB")
                fig_pe.update_layout(title="Lịch sử Định giá P/E (1 Năm)", template="plotly_dark", height=400)
                st.plotly_chart(fig_pe, use_container_width=True)

    # === TAB 5: RỦI RO ===
    with t5:
        c_left, c_right = st.columns([1.5, 2.5])
        with c_left:
            # if not hist_scores.empty:
            #     st.line_chart(hist_scores.set_index('time')['score_risk'])
            st.subheader(f"Điểm: {scores.get('risk')}/10")
            vol_avg = health.get('volume_20d_avg', 0)
            atr = df_chart.iloc[-1].get('ATRr_14', 0)
            atr_pct = (atr / health['close'] * 100) if health['close'] > 0 else 0
            
            st.metric("Thanh khoản TB", f"{vol_avg:,.0f}")
            st.metric("Biến động (ATR)", f"{atr_pct:.1f}%")
            
            st.write("**Cảnh báo:**")
            if not details.get('risk'): st.success("✅ An toàn")
            for r in details.get('risk', []): st.error(f"⚠️ {r}")

        with c_right:
            if 'ATRr_14' in df_chart.columns:
                fig_risk = make_subplots(rows=2, cols=1, shared_xaxes=True)
                fig_risk.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['close'], name="Giá"), row=1, col=1)
                fig_risk.add_trace(go.Scatter(x=df_chart['time'], y=df_chart['ATRr_14'], name="ATR (Rủi ro)", line=dict(color='red')), row=2, col=1)
                fig_risk.update_layout(title="Biến động giá & Rủi ro", template="plotly_dark", height=400)
                st.plotly_chart(fig_risk, use_container_width=True)

except Exception as e:
    st.error(f"Lỗi hiển thị: {e}")
    # import traceback; st.text(traceback.format_exc())