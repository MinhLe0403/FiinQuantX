import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- IMPORT MODULES ---
try:
    from analysis.core import StockAnalyzer
    from etl.runner import ETLRunner
    from etl.constants import VN_INDICES_OPTIONS, HNX_INDICES_OPTIONS, UPCOM_INDICES_OPTIONS
    from mle_stock.analysis.market.data_access import MarketEngine
    from mle_stock.analysis.d import MarketOverviewAnalyzer
except ImportError as e:
    st.error(f"Lỗi module: {e}. Hãy đảm bảo bạn đang chạy từ thư mục gốc dự án.")
    st.stop()

st.set_page_config(page_title="FiinQuant Pro", layout="wide", page_icon="🦈")

# --- CSS: GIAO DIỆN DARK MODE HIỆN ĐẠI ---
st.markdown("""
<style>
    .big-score {font-size: 72px !important; font-weight: 800; text-align: center; line-height: 1.0;}
    .metric-card {
        background: #1e1e1e; padding: 15px; border-radius: 12px; 
        text-align: center; border-left: 5px solid #00AA00;
        margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .sub-metric-label {font-size: 13px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px;}
    .sub-metric-value {font-size: 22px; font-weight: bold; color: white;}
    
    /* Tùy chỉnh Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 4px; padding: 8px 16px; font-size: 14px; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #333; color: #00FF00; border: 1px solid #00FF00; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# MAIN LAYOUT
# ==============================================================================

# Khởi tạo
analyzer = StockAnalyzer()
market_analyzer = MarketOverviewAnalyzer(analyzer.engine)

# Tạo Tabs chính cho Ứng dụng
tab_market, tab_stock = st.tabs(["🌍 TỔNG QUAN THỊ TRƯỜNG", "🔍 PHÂN TÍCH CỔ PHIẾU"])

# ==============================================================================
# TAB 1: DASHBOARD THỊ TRƯỜNG
# ==============================================================================
with tab_market:
    st.header("NHỊP ĐẬP THỊ TRƯỜNG (MARKET PULSE)")
    
    # 1. VNINDEX HEALTH CHECK
    # Mặc định lấy VNINDEX, nút reload để cập nhật
    col_idx1, col_idx2 = st.columns([3, 1])
    
    with col_idx1:
        mk_status = market_analyzer.get_market_status("VNINDEX")
        
        if mk_status:
            # Hiển thị dạng Banner lớn
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VNINDEX", f"{mk_status['close']:,.2f}", f"{mk_status['change']:+.2f}%")
            
            vol_str = f"{(mk_status['volume']/1_000_000):.1f}M"
            vol_delta = f"{(mk_status['volume']/mk_status['avg_volume'] * 100):.0f}% TB"
            c2.metric("Thanh khoản", vol_str, vol_delta)
            
            # Trạng thái xu hướng
            st.markdown(f"""
            <div style="background-color: #222; padding: 10px; border-radius: 5px; border-left: 5px solid {mk_status['trend_color']}; text-align: center;">
                <span style="color: #aaa; font-size: 12px;">XU HƯỚNG CHỦ ĐẠO</span><br>
                <strong style="font-size: 20px; color: {mk_status['trend_color']}">{mk_status['trend']}</strong>
            </div>
            """, unsafe_allow_html=True)
            
            # Cảnh báo phân phối
            if mk_status['dist_days'] > 2:
                st.warning(f"⚠️ **Cẩn trọng:** Thị trường đã xuất hiện {mk_status['dist_days']} ngày phân phối lớn.")
            else:
                st.success(f"✅ Thị trường ổn định (Ít ngày phân phối: {mk_status['dist_days']})")
                
        else:
            st.error("Chưa có dữ liệu VNINDEX. Vui lòng vào Sidebar -> Cập nhật -> Tải VNINDEX.")

    with col_idx2:
        # Độ rộng thị trường (Market Breadth)
        breadth = market_analyzer.get_market_breadth()
        if breadth:
            labels = ['Tăng', 'Giảm', 'TC']
            values = [breadth.get('green', 0), breadth.get('red', 0), breadth.get('yellow', 0)]
            colors = ['#00CC96', '#EF553B', '#FFD700']
            
            fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=colors)])
            fig_pie.update_layout(title_text="Độ rộng (Số mã)", height=200, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # 2. DÒNG TIỀN NGÀNH (SECTOR ROTATION)
    st.subheader("🔥 DÒNG TIỀN THEO NHÓM NGÀNH")
    
    df_sector = market_analyzer.get_sector_ranking()
    
    if not df_sector.empty:
        # Lấy Top 5 Tăng & Top 5 Giảm
        c_lead, c_lag = st.columns(2)
        
        with c_lead:
            st.caption("🏆 TOP NGÀNH DẪN DẮT (Mạnh nhất)")
            st.dataframe(
                df_sector.head(8).style.format({"performance_score": "{:+.2f}%", "total_flow": "{:,.0f} tỷ"}),
                use_container_width=True
            )
            
        with c_lag:
            st.caption("🥀 TOP NGÀNH SUY YẾU")
            st.dataframe(
                df_sector.tail(8).sort_values("performance_score").style.format({"performance_score": "{:+.2f}%", "total_flow": "{:,.0f} tỷ"}),
                use_container_width=True
            )
            
        # Vẽ biểu đồ Bar Chart cho trực quan
        fig_sec = go.Figure()
        fig_sec.add_trace(go.Bar(
            x=df_sector['sector'], 
            y=df_sector['performance_score'],
            marker_color=['#00CC96' if x > 0 else '#EF553B' for x in df_sector['performance_score']]
        ))
        fig_sec.update_layout(title="Hiệu suất các Nhóm Ngành", height=350, template="plotly_dark")
        st.plotly_chart(fig_sec, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu Ngành. Hãy đảm bảo đã cập nhật dim_stocks và prices.")

# ==============================================================================
# 1. SIDEBAR: CẤU TRÚC LẠI
# ==============================================================================
st.sidebar.markdown("## 🦈 FiinQuant Pro")

# --- A. KHU VỰC PHÂN TÍCH (Luôn hiển thị) ---
st.sidebar.markdown("### 🔍 Phân Tích")
input_symbol = st.sidebar.text_input("Mã Cổ Phiếu:", value="FPT", help="Nhập mã CP cần soi (VD: FPT, HPG)").upper().strip()
days_lookback = st.sidebar.slider("Khung thời gian (Ngày):", 30, 365, 60)

# --- B. KHU VỰC QUẢN LÝ DỮ LIỆU (Ẩn trong Expander) ---
with st.sidebar.expander("⚙️ Quản lý & Cập nhật Dữ liệu", expanded=False):
    # Chia làm 2 Tabs: Đơn lẻ vs Hàng loạt
    tab_single, tab_batch = st.tabs(["Một Mã", "Theo Lô"])
        
    # --- Tab 1: Cập nhật Mã đang xem ---
    with tab_single:
        st.caption("Cập nhật dữ liệu cho mã hiện tại.")
        force_update = st.checkbox("Tải lại toàn bộ (5 năm)", value=False, help="Chọn nếu dữ liệu bị lỗi hoặc biểu đồ bị ngắt quãng.")
        
        if st.button("🚀 Cập nhật Ngay", use_container_width=True):
            if not input_symbol: 
                st.warning("Vui lòng nhập mã.")
            else:
                with st.status(f"Đang tải {input_symbol}...", expanded=True) as status:
                    runner = ETLRunner()
                    success, msg = runner.update_ticker(input_symbol, force_full=force_update)
                    
                    if success:
                        status.update(label="Hoàn tất!", state="complete")
                        st.toast(msg, icon="✅")
                        st.cache_data.clear() # Xóa cache để biểu đồ load lại dữ liệu mới
                    else:
                        status.update(label="Lỗi", state="error")
                        st.error(msg)

    # --- Tab 2: Cập nhật Hàng loạt (Batch) ---
    with tab_batch:
        st.caption("Quét dữ liệu theo Bộ chỉ số.")
        all_indices = VN_INDICES_OPTIONS + HNX_INDICES_OPTIONS + UPCOM_INDICES_OPTIONS
        selected_index = st.selectbox("Chọn Bộ Chỉ Số:", all_indices, index=0)
        
        # --- THÊM: CHỌN KHOẢNG THỜI GIAN ---
        c1, c2 = st.columns(2)
        today = datetime.now()
        # Mặc định lấy từ 2 ngày trước đến hôm nay (cập nhật ngắn hạn để nhanh)
        start_d = c1.date_input("Từ ngày:", value=today - timedelta(days=2))
        end_d = c2.date_input("Đến ngày:", value=today)
        
        if st.button("🌊 Chạy Batch Update", use_container_width=True):
            # Validate ngày
            if start_d > end_d:
                st.error("⚠️ Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
            else:
                runner = ETLRunner()
                with st.status("Đang khởi tạo tiến trình...", expanded=True) as status:
                    # 1. Lấy danh sách mã từ Index
                    tickers = runner.get_tickers_by_group(selected_index)
                    
                    if not tickers:
                        status.update(label="Lỗi", state="error")
                        st.error(f"Không tìm thấy mã nào trong {selected_index}")
                    else:
                        status.write(f"Tìm thấy {len(tickers)} mã. Bắt đầu cập nhật từ {start_d} đến {end_d}...")
                        
                        # 2. Chạy vòng lặp cập nhật
                        progress_bar = status.progress(0)
                        
                        s_str = start_d.strftime("%Y-%m-%d")
                        e_str = end_d.strftime("%Y-%m-%d")
                        
                        def update_progress(idx, total, ticker):
                            # Hiển thị progress dạng: "Đang xử lý: VNM (5/30)"
                            progress_bar.progress((idx + 1) / total, text=f"Đang xử lý: {ticker} ({idx+1}/{total})")
                        
                        # Gọi hàm update_batch_optimized
                        s_count, e_count = runner.update_batch_optimized(
                            tickers, 
                            start_date=s_str, 
                            end_date=e_str, 
                            progress_callback=update_progress
                        )
                        
                        status.update(label="Hoàn tất!", state="complete")
                        
                        if e_count > 0:
                            st.warning(f"Hoàn thành! Thành công: {s_count} mã. Lỗi: {e_count} mã.")
                        else:
                            st.success(f"Xuất sắc! Đã cập nhật thành công {s_count} mã.")
                        
                        st.cache_data.clear()

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def safe_fmt(val, fmt="{:,.0f}", default="-"):
    if pd.isna(val) or val is None: return default
    try: return fmt.format(val)
    except: return default

def card(label, value, color="#3366CC"):
    st.markdown(f"""
    <div class='metric-card' style='border-left-color:{color}'>
        <div class='sub-metric-label'>{label}</div>
        <div class='sub-metric-value'>{value}</div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 3. MAIN LOGIC (PHẦN HIỂN THỊ)
# ==============================================================================
analyzer = StockAnalyzer()

try:
    if not input_symbol:
        st.info("👋 Chào mừng! Hãy nhập mã cổ phiếu bên trái để bắt đầu.")
        st.stop()

    # 1. FETCH DATA (Raw)
    # Lấy 400 phiên để đủ tính toán các chỉ báo dài hạn (Ichimoku 52, MA200)
    df_chart = analyzer.get_full_data(input_symbol, limit=400)
    
    if df_chart.empty:
        st.warning(f"⚠️ Chưa có dữ liệu cho **{input_symbol}** trong Database.")
        st.info("👉 Hãy mở mục '⚙️ Quản lý Dữ liệu' bên trái và bấm 'Cập nhật Ngay'.")
        st.stop()
    
    # 2. FETCH FINANCIALS
    fin_data = analyzer.get_financials(input_symbol)

    # 3. ANALYZE HEALTH (Gọi Core mới)
    # Hàm này đã bao gồm: Calculate Scores, Deep Dive Flow, Generate Signals
    health = analyzer.analyze_health(input_symbol)
    
    if "error" in health:
        st.error(health["error"])
        st.stop()

    # 4. UNPACK DATA
    scores = health.get('scores', {})
    details = health.get('details', {})
    # Dataframe full chỉ báo để vẽ chart
    df_full = health.get('full_df') 
    # Dataframe lịch sử điểm số
    hist_scores = pd.DataFrame(health.get('history_scores', []))
    if not hist_scores.empty and 'time' in hist_scores.columns:
         hist_scores['time'] = pd.to_datetime(hist_scores['time'])
    
    # Metadata dòng tiền chuyên sâu
    f_health = health.get('flow_health', {})

    # Lấy thống kê hành vi dòng tiền (df_stats) cho bảng hiển thị
    if hasattr(analyzer, 'get_investor_summary'):
        df_stats = analyzer.get_investor_summary(input_symbol, limit=days_lookback)
    else:
        df_stats = pd.DataFrame()

    last_row = df_full.iloc[-1]

    # --- UI: HEADER ---
    col1, col2 = st.columns([2.5, 1.5])
    with col1:
        st.title(f"{input_symbol} - Giá: {safe_fmt(health['close'])}")
        st.caption(f"Ngày dữ liệu gần nhất: {last_row['time'].strftime('%d/%m/%Y')}")
        
        # Hiển thị Khuyến nghị
        rec = health['recommendation']
        if "MUA" in rec: rec_color = "#00FF00"
        elif "BÁN" in rec: rec_color = "#FF4444"
        else: rec_color = "#FFD700"
        
        st.markdown(f"<h3 style='color:{rec_color}; margin:0'>KHUYẾN NGHỊ: {rec}</h3>", unsafe_allow_html=True)
        
    with col2:
        score = health['total_score']
        color = "#00FF00" if score >= 7 else "#FFD700" if score >= 5 else "#FF4444"
        st.markdown(f"<div class='big-score' style='color:{color}'>{score:.1f}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; font-weight:bold; color:{color}'>TỔNG ĐIỂM / 10</div>", unsafe_allow_html=True)

    # --- UI: 5 PILLARS SCORE CARDS ---
    st.markdown("### 🧬 Đánh giá Sức khỏe")
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
        if weight > 0: contrib_text = f"Đóng góp: +{contribution:.2f}"
        else: contrib_text = "Hệ số Phạt"
        
        with col:
            st.markdown(f"""
            <div class='metric-card' style='border-left-color:{clr}'>
                <div class='sub-metric-label'>{cfg['label']}</div>
                <div class='sub-metric-value' style='color:{clr}'>{val:.1f}</div>
                <div style='font-size:11px; color:#888'>{contrib_text}</div>
            </div>
            """, unsafe_allow_html=True)

    # --- UI: KEY METRICS ROW ---
    st.markdown("---")

    # Lấy giá trị RS từ health
    rs_rating = health.get('rs_rating', 0)
    m1, m2, m3, m4, m5 = st.columns(5)
    
    prev_close = df_full.iloc[-2]['close'] if len(df_full) > 1 else last_row['close']
    pct_change = (last_row['close'] - prev_close) / prev_close * 100

    m1.metric("Biến động giá", f"{pct_change:+.2f}%", delta_color="normal")
    m2.metric("P/E TTM", safe_fmt(last_row.get('pe'), "{:.1f}"))
    m3.metric("Smart Net (10D)", f"{health.get('smart_net_billion_10d', 0):+.1f} tỷ")
    
    # Relative Ratio (% Thanh khoản)
    part_pct = health.get('smart_participation', 0)
    m4.metric("Sức mạnh Dòng tiền", f"{part_pct:+.1f}%", help="% Giá trị giao dịch ròng so với Thanh khoản")
    
    # SỬA CỘT M4: HIỂN THỊ SỨC MẠNH RS
    lbl_rs = "Khỏe hơn TT" if rs_rating > 0 else "Yếu hơn TT"
    color_rs = "normal" if rs_rating > 0 else "inverse" # Xanh nếu dương, Đỏ nếu âm
    
    m5.metric(
        label="Sức mạnh RS (vs VNINDEX)", 
        value=f"{rs_rating:+.1f}%", 
        delta=lbl_rs,
        delta_color=color_rs,
        help="RS > 0: Cổ phiếu tăng mạnh hơn (hoặc giảm ít hơn) VNINDEX. RS < 0: Yếu hơn thị trường."
    )

    # --- UI: INSIGHTS & WARNINGS ---
    with st.expander("📝 Luận điểm Đầu tư & Cảnh báo Chi tiết", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.success("✅ **ĐIỂM TÍCH CỰC**")
            all_pros = details.get('technical', []) + details.get('flow', []) + \
                       details.get('fundamental', []) + details.get('valuation', [])
            if all_pros:
                for p in all_pros: st.write(f"• {p}")
            else:
                st.write("Chưa có điểm nhấn tích cực.")
            
        with c2:
            st.error("⚠️ **CẢNH BÁO RỦI RO**")
            warnings = details.get('warning', [])
            
            if scores.get('risk', 10) < 5:
                warnings.append(f"Rủi ro biến động/Thanh khoản cao (Điểm Risk: {scores.get('risk')}/10)")
            
            if warnings:
                for w in warnings: st.write(f"• {w}")
            else:
                st.info("An toàn. Chưa phát hiện rủi ro lớn.")

    # =========================================================================
    # *** PHẦN MỚI: KẾ HOẠCH GIAO DỊCH TỪ MODULE RECOMMENDATION ***
    # =========================================================================
    plan = health.get('trade_plan', {})
    
    st.markdown("---")
    st.subheader("🎯 KẾ HOẠCH GIAO DỊCH (Gợi ý)")

    # Chia làm 2 cột: Ngắn hạn (Trader) và Dài hạn (Investor)
    c_trade, c_invest = st.columns(2)
    
    # === CỘT 1: TRADING (LƯỚT SÓNG) ===
    with c_trade:
        t_plan = plan.get('trading', {})
        action = t_plan.get('action', 'QUAN SÁT')
        
        # Màu sắc header
        color = "gray"
        if "MUA" in action: color = "#00FF00" # Green
        elif "BÁN" in action: color = "#FF4444" # Red
        
        # Dùng HTML để custom card đẹp
        st.markdown(f"""
        <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid {color}; min-height: 250px;">
            <h4 style="color: {color}; margin-top:0;">⚡ TRADING NGẮN HẠN</h4>
            <h2 style="color: white; margin: 10px 0;">{action}</h2>
            <p style="color: #bbb; font-style: italic; min-height: 40px;">"{t_plan.get('reason', '...')}"</p>
            <hr style="border-color: #444;">
            <div style="display: flex; justify-content: space-between; margin-top: 15px;">
                <div>
                    <span style="color: #888; font-size: 12px;">Vùng mua</span><br>
                    <strong style="font-size: 16px; color: #00CC96;">{t_plan.get('entry_zone', '-')}</strong>
                </div>
                <div>
                    <span style="color: #888; font-size: 12px;">Mục tiêu</span><br>
                    <strong style="font-size: 16px; color: #AB63FA;">{t_plan.get('target', '-')}</strong>
                </div>
                <div>
                    <span style="color: #888; font-size: 12px;">Cắt lỗ</span><br>
                    <strong style="font-size: 16px; color: #EF553B;">{t_plan.get('stop_loss', '-')}</strong>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Expander hiển thị Support/Resist
        with st.expander("Các mốc Kỹ thuật quan trọng"):
            kl = plan.get('key_levels', {})
            s_col, r_col = st.columns(2)
            with s_col:
                st.caption("HỖ TRỢ (Supports)")
                if kl.get('supports'):
                    for name, price in kl.get('supports'):
                        st.markdown(f"- {name}: **{price:,.0f}**")
                else: st.write("-")
            with r_col:
                st.caption("KHÁNG CỰ (Resistances)")
                if kl.get('resistances'):
                    for name, price in kl.get('resistances'):
                        st.markdown(f"- {name}: **{price:,.0f}**")
                else: st.write("-")

    # === CỘT 2: INVESTING (TÍCH SẢN) ===
    with c_invest:
        i_plan = plan.get('investing', {})
        i_action = i_plan.get('action', 'N/A')
        
        i_color = "gray"
        if "MUA" in i_action: i_color = "#FFA15A" # Orange for Investing
        
        st.markdown(f"""
        <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid {i_color}; min-height: 250px;">
            <h4 style="color: {i_color}; margin-top:0;">🐢 TÍCH SẢN GIÁ TRỊ</h4>
            <h2 style="color: white; margin: 10px 0;">{i_action}</h2>
            <p style="color: #bbb; font-style: italic; min-height: 40px;">"{i_plan.get('reason', '...')}"</p>
            <hr style="border-color: #444;">
            <div style="margin-top: 15px;">
                <span style="color: #888; font-size: 12px;">Vùng giá Gom Khuyến nghị:</span><br>
                <strong style="font-size: 20px; color: white;">{i_plan.get('buy_under', '-')}</strong>
            </div>
            <div style="margin-top: 10px;">
                <span style="color: #888; font-size: 12px;">Biên An Toàn (MOS):</span><br>
                <span style="color: {'#00FF00' if 'TÍCH SẢN' in i_action else '#FF4444'}; font-weight: bold;">
                    { "✅ Cao" if "TÍCH SẢN" in i_action else "⚠️ Thấp / Đã phản ánh vào giá" }
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Logic hiển thị dashboard NGÀNH
    with st.expander("📊 Bức tranh Toàn cảnh Thị trường (Sector Dashboard)", expanded=False):
        # Khởi tạo engine
        # (Tối ưu: Nên đưa ra ngoài để không init lại nhiều lần)
        m_engine = MarketEngine(analyzer.engine) 
        
        st.write("**Biến động các nhóm ngành (Phiên gần nhất):**")
        
        df_sector = m_engine.get_sector_performance()
        
        if not df_sector.empty:
            # Format lại bảng cho đẹp
            st.dataframe(
                df_sector.style.format({
                    "avg_change_pct": "{:+.2f}%",
                    "stock_count": "{:.0f}"
                })
                .background_gradient(subset=['avg_change_pct'], cmap='RdYlGn', vmin=-3, vmax=3)
                .bar(subset=['advance_count'], color='#00CC96')
                .bar(subset=['decline_count'], color='#EF553B'),
                use_container_width=True,
                column_config={
                    "sector": "Nhóm Ngành",
                    "stock_count": "Số lượng CP",
                    "avg_change_pct": "% Tăng giảm TB",
                    "advance_count": "Số mã Tăng",
                    "decline_count": "Số mã Giảm"
                }
            )
            
            # Lấy Top Ngành khỏe nhất
            top_sec = df_sector.iloc[0]
            st.info(f"🔥 Dòng tiền đang tập trung vào nhóm: **{top_sec['sector']}** (Tăng TB {top_sec['avg_change_pct']:.2f}%)")
        else:
            st.warning("Chưa có dữ liệu phân ngành. Hãy cập nhật 'dim_stocks' và chạy ETL giá.")


    # ==========================================
    #               DETAILED TABS
    # ==========================================
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
                # Tìm dòng Nước ngoài để hiển thị nhanh
                f_rows = df_stats[df_stats['Nhà Đầu Tư'].astype(str).str.contains('Nước ngoài')]
                if not f_rows.empty:
                    foreign_row = f_rows.iloc[0]
                    st.metric("Nước ngoài Gom/Xả", f"{foreign_row['KL Ròng Tổng']:,.0f}")

        st.divider()

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

        # Sử dụng cumsum trên cột của đối tượng đã chọn
        c_buy_val = df_calc.get(f'{code}_buy_val', pd.Series(0)).cumsum()
        c_buy_vol = df_calc.get(f'{code}_buy_vol', pd.Series(0)).cumsum()
        c_sell_val = df_calc.get(f'{code}_sell_val', pd.Series(0)).cumsum()
        c_sell_vol = df_calc.get(f'{code}_sell_vol', pd.Series(0)).cumsum()
        
        # Tính VWAP (Tránh chia cho 0)
        df_calc['vwap_buy'] = c_buy_val / c_buy_vol.replace(0, 1)
        df_calc['vwap_sell'] = c_sell_val / c_sell_vol.replace(0, 1)
        
        # Fix đoạn đầu khi chưa có vol -> gán bằng giá close
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
        
        # Tính toán tích lũy toàn lịch sử
        if 'foreign_net_val' in df_full.columns: # Kiểm tra cột tồn tại để tránh lỗi
            # Note: Core trả về foreign_net_val, ở đây dùng Volume để thấy rõ Gom/Xả slg
            # Chúng ta dùng net_vol đã có trong get_full_data ở Core
            fig_cusum = make_subplots(specs=[[{"secondary_y": True}]])
            fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=df_full['close'], name="Giá CP", line=dict(color='gray', dash='dot')), secondary_y=False)
            
            # CUSUM Lines
            inv_map_cusum = {
                'foreign_net_vol': {'name': 'Nước ngoài', 'color': 'yellow'},
                'prop_net_vol': {'name': 'Tự doanh', 'color': 'cyan'},
                'local_ind_net_vol': {'name': 'Cá nhân', 'color': 'red'},
                'local_inst_net_vol': {'name': 'Tổ chức', 'color': 'green'}
            }
            
            for col_name, attrs in inv_map_cusum.items():
                if col_name in df_full.columns:
                    # Lũy kế từ đầu
                    y_vals = df_full[col_name].fillna(0).cumsum()
                    fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=y_vals, name=attrs['name'], line=dict(color=attrs['color'], width=2)), secondary_y=True)

            fig_cusum.update_layout(title="Xu hướng Dòng tiền Tích lũy (Net Vol)", template="plotly_dark", height=500, hovermode="x unified")
            st.plotly_chart(fig_cusum, use_container_width=True)

        # 3. CHART ACTIVE PRESSURE
        st.subheader("4. Áp lực Khớp lệnh Chủ động (Aggression)")
        st.info("💡 Mua Chủ Động (Xanh) thể hiện sự quyết liệt đẩy giá. Bán Chủ Động (Đỏ) thể hiện sự thoát hàng dứt khoát.")

        if 'buy_active_vol' in df_chart.columns:
            df_act = df_chart.tail(60)
            fig_act = go.Figure()
            
            # Vẽ dạng Bar chồng hoặc đối xứng
            fig_act.add_trace(go.Bar(x=df_act['time'], y=df_act['buy_active_vol'], name="Mua Chủ Động", marker_color='#00CC96'))
            fig_act.add_trace(go.Bar(x=df_act['time'], y=-df_act['sell_active_vol'], name="Bán Chủ Động", marker_color='#EF553B'))
            
            fig_act.update_layout(title="Lực Mua/Bán Chủ Động (60 phiên)", barmode='overlay', height=350, template="plotly_dark")
            st.plotly_chart(fig_act, use_container_width=True)

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
        
        # Lấy dữ liệu Full Indicators (trong app mới này df_chart chính là full_df)
        df_full = health.get('full_df') # (Alias cho rõ nghĩa)
        
        if df_full is None or df_full.empty:
            st.warning("⚠️ Không có dữ liệu chỉ báo nâng cao.")
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

# ---------------- TAB 3: FUNDAMENTAL ----------------
    biz_type = health.get('business_type', 'Unknown')
    metrics = health.get('fund_metrics', {})

    with t3:
        st.subheader(f"Phân tích Cơ bản & Định giá ({'🏦 Ngân hàng/TC' if biz_type == 'Financial' else '🏭 Sản xuất/TM'})")
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.metric("Điểm Cơ bản", f"{scores.get('fundamental', 0):.1f}/10")
            st.metric("Điểm Định giá", f"{scores.get('valuation', 0):.1f}/10")
            
            st.divider()
            
            if biz_type == 'Financial':
                # HIỂN THỊ METRICS CHO BANK
                st.write("**Chỉ số quan trọng:**")
                st.write(f"📈 Tăng trưởng TD: `{metrics.get('growth', 0)*100:.1f}%`")
                st.write(f"☢️ Nợ xấu (NPL): `{metrics.get('npl', 0)*100:.2f}%`")
                st.write(f"💰 NIM: `{metrics.get('nim', 0)*100:.2f}%`")
                st.write(f"📊 P/B: `{metrics.get('pb', 0):.2f}`")
                
            else:
                # HIỂN THỊ METRICS CHO DOANH NGHIỆP THƯỜNG
                st.write("**Chỉ số quan trọng:**")
                st.write(f"🔥 ROE: `{metrics.get('roe', 0)*100:.1f}%`")
                st.write(f"⚖️ Nợ/VCSH (D/E): `{metrics.get('de', 0):.2f}`")
                st.write(f"🚀 Tăng trưởng EBT: `{metrics.get('growth', 0)*100:.1f}%`")
                st.write(f"📊 P/E: `{metrics.get('pe', 0):.1f}`")

        with c2:
            st.success("✅ **Đánh giá tích cực:**")
            for sig in details.get('fundamental', []):
                st.write(f"• {sig}")
            
            # Tách riêng warnings nếu có (đã gộp chung trong 'warning' ở core, 
            # nhưng nếu muốn lọc riêng warnings cơ bản thì cần sửa lại return struct ở Core chút xíu,
            # hoặc để chung ở mục Cảnh báo rủi ro global phía trên app)
            
            with st.expander("🔍 Xem dữ liệu BCTC thô", expanded=True):
                # Format JSON hiển thị đẹp hơn cho các số Decimal
                st.json(fin_data)

    # ---------------- TAB 4: VALUATION ----------------
    with t4:
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.metric("Điểm Định giá", f"{scores.get('valuation', 0):.1f}/10")
            st.metric("P/E hiện tại", f"{last_row.get('pe', 0):.1f}")
            st.metric("P/B hiện tại", f"{last_row.get('pb', 0):.1f}")
        
        with c_right:
            st.write("Biến động P/E 1 năm qua:")
            if 'pe' in df_chart.columns:
                df_pe = df_chart[df_chart['pe'] > 0]
                if not df_pe.empty:
                    fig_v = go.Figure()
                    fig_v.add_trace(go.Scatter(x=df_pe['time'], y=df_pe['pe'], fill='tozeroy', name="P/E"))
                    avg_pe = df_pe['pe'].mean()
                    fig_v.add_hline(y=avg_pe, line_dash='dash', annotation_text=f"TB: {avg_pe:.1f}")
                    fig_v.update_layout(template="plotly_dark", height=300, margin=dict(t=10,b=10))
                    st.plotly_chart(fig_v, use_container_width=True)

    # ---------------- TAB 5: RISK ----------------
    with t5:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Điểm Rủi ro", f"{scores.get('risk', 0):.1f}/10", help="Càng cao càng An toàn")
            
            st.metric("Thanh khoản TB", f"{last_row.get('VOL_SMA_20', 0):,.0f}")
            
            atr_pct = (last_row.get('ATRr_14', 0) / last_row['close'] * 100) if last_row['close'] else 0
            st.metric("Biến động (ATR%)", f"{atr_pct:.1f}%")

        with c2:
            st.warning("⚠️ **Vấn đề cần lưu ý:**")
            risk_msgs = details.get('warning', []) # Trong core mới, risk details nằm trong 'warning'
            
            for r in risk_msgs: st.write(f"- {r}")
            if scores.get('risk', 10) >= 8 and not risk_msgs:
                st.success("Cổ phiếu đang ở trạng thái ổn định/an toàn.")

except Exception as e:
    st.error(f"Đã xảy ra lỗi nghiêm trọng: {e}")
    # st.exception(e)