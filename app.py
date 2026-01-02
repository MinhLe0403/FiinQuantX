import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine

# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- IMPORT MODULES ---
try:
    from analysis.core import StockAnalyzer
    from analysis.market.data_access import MarketEngine
    from mle_stock.analysis.sector import SectorAnalysis
    from analysis.market_trend import MarketTrendAnalysis
    from etl.runner import ETLRunner
    from etl.constants import VN_INDICES_OPTIONS, HNX_INDICES_OPTIONS, UPCOM_INDICES_OPTIONS
        
    from controllers.market_controller import MarketController
    from controllers.stock_controller import StockController  # Import mới
    from views.market_view import MarketView
    from views.stock_view import StockView                    # Import mới
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
# KHỞI TẠO ENGINE & HELPER FUNCTIONS
# ==============================================================================
analyzer = StockAnalyzer() # (Class core cũ của bạn)
sector_engine = SectorAnalysis(analyzer.engine)
market_engine = MarketTrendAnalysis(analyzer.engine)
from config import DATABASE_URL
engine = create_engine(DATABASE_URL)
market_ctrl = MarketController(engine)
stock_ctrl = StockController() # Khởi tạo Controller Stock
def safe_fmt(val, fmt="{:,.0f}", default="-"):
    if pd.isna(val) or val is None: return default
    try: return fmt.format(val)
    except: return default

# ==============================================================================
# 1. SIDEBAR (KHU VỰC ĐIỀU KHIỂN)
# ==============================================================================
st.sidebar.markdown("## 🦈 FiinQuant Pro")

# --- A. KHU VỰC PHÂN TÍCH (Luôn hiển thị) ---
st.sidebar.markdown("### 🔍 Phân Tích")
input_symbol = st.sidebar.text_input("Mã Cổ Phiếu:", value="FPT", help="Nhập mã CP cần soi (VD: FPT, HPG)").upper().strip()
days_lookback = st.sidebar.slider("Khung thời gian (Ngày):", 30, 365, 60)

# --- B. KHU VỰC QUẢN LÝ DỮ LIỆU ---
with st.sidebar.expander("⚙️ Quản lý & Cập nhật Dữ liệu", expanded=False):
    tab_single, tab_batch = st.tabs(["Một Mã", "Theo Lô"])
        
    # Tab 1: Cập nhật Mã đang xem
    with tab_single:
        st.caption(f"Cập nhật dữ liệu cho mã: **{input_symbol}**")
        force_update = st.checkbox("Tải lại toàn bộ (5 năm)", value=False)
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
                        st.cache_data.clear()
                    else:
                        status.update(label="Lỗi", state="error")
                        st.error(msg)

    # Tab 2: Cập nhật Hàng loạt
    with tab_batch:
        all_indices = VN_INDICES_OPTIONS + HNX_INDICES_OPTIONS + UPCOM_INDICES_OPTIONS
        selected_index = st.selectbox("Chọn Bộ Chỉ Số:", all_indices, index=0)
        
        today = datetime.now()
        start_d = st.date_input("Từ ngày:", value=today - timedelta(days=2))
        end_d = st.date_input("Đến ngày:", value=today)
        
        if st.button("🌊 Chạy Batch Update", use_container_width=True):
            runner = ETLRunner()
            with st.status("Đang xử lý...", expanded=True) as status:
                tickers = runner.get_tickers_by_group(selected_index)
                if not tickers:
                    st.error("Không tìm thấy mã.")
                else:
                    progress_bar = status.progress(0)
                    def update_progress(idx, total, ticker):
                        progress_bar.progress((idx + 1) / total, text=f"Đang xử lý: {ticker} ({idx+1}/{total})")
                    
                    s_str, e_str = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
                    s_count, e_count = runner.update_batch_optimized(tickers, s_str, e_str, update_progress)
                    
                    status.update(label="Xong!", state="complete")
                    st.success(f"Hoàn thành: {s_count} mã thành công.")
                    st.cache_data.clear()
        
        st.divider()
        if st.button("📥 Tải VNINDEX (Bắt buộc)", help="Cần để tính RS Rating"):
            with st.status("Tải Index...") as s:
                run = ETLRunner()
                run.update_ticker("VNINDEX", force_full=True)
                s.update(label="Xong!", state="complete")
                st.cache_data.clear()

# ==============================================================================
# 2. MAIN LAYOUT: TABS CHÍNH
# ==============================================================================
tab_market, tab_stock = st.tabs(["🌍 TỔNG QUAN THỊ TRƯỜNG", "🔍 PHÂN TÍCH CỔ PHIẾU"])

# ==============================================================================
# TAB 1: DASHBOARD THỊ TRƯỜNG (MARKET OVERVIEW) - NATIVE UI VERSION
# ==============================================================================

# --- RENDER TAB MARKET ---
with tab_market:
    # 1. Market Matrix
    matrix_data = market_ctrl.get_market_summary_data() # Lấy 4 chỉ số
    MarketView.render_market_matrix(matrix_data)
    
    # [Interactive] Chọn chỉ số soi Quant
    c_sel, _ = st.columns([1, 3])
    target_idx = c_sel.selectbox("🔎 Soi chi tiết:", ["VNINDEX", "VN30"], index=0)
    
    # 2. Quant Lab
    q_data = market_ctrl.get_quant_lab_data(target_idx)
    MarketView.render_quant_lab(q_data)
    
    # 3. MFE Dashboard
    mfe_data = market_ctrl.get_mfe_data(target_idx)
    MarketView.render_mfe_dashboard(mfe_data)
    
    # 4. Deep Dive (Lấy chung)
    dd_data = market_ctrl.get_deep_dive_data("VNINDEX") # Rotation/Breadth lấy toàn TT
    MarketView.render_deep_dive(dd_data)

    
# ==============================================================================
# TAB 2: PHÂN TÍCH CỔ PHIẾU (STOCK ANALYSIS) - TÍCH HỢP DIRECT
# ==============================================================================
with tab_stock:
    # A. Validate Input
    if not input_symbol:
        st.info("👈 Vui lòng nhập Mã Cổ phiếu ở Sidebar để bắt đầu phân tích.")
    else:
        # B. Fetch & Analyze
        df_chart = analyzer.get_full_data(input_symbol, limit=400)
        fin_data = analyzer.get_financials(input_symbol)
        
        if df_chart.empty:
            st.warning(f"Chưa có dữ liệu giá cho **{input_symbol}**. Vui lòng bấm 'Cập nhật Ngay'.")
        else:
            # 1. Gọi Core Logic
            health = analyzer.analyze_health(input_symbol)
            if "error" in health:
                st.error(health["error"])
            else:
                # 2. Unpack Data
                scores = health.get('scores', {})
                details = health.get('details', {})
                df_full = health.get('full_df') 
                hist_scores = pd.DataFrame(health.get('history_scores', []))
                if not hist_scores.empty: hist_scores['time'] = pd.to_datetime(hist_scores['time'])
                
                # Stats Summary (bảng thống kê cũ)
                df_stats = pd.DataFrame()
                if hasattr(analyzer, 'get_investor_summary'):
                    df_stats = analyzer.get_investor_summary(input_symbol, limit=days_lookback)

                last_row = df_full.iloc[-1]

                # --- 3. UI: HEADER ---
                c_head1, c_head2 = st.columns([2.5, 1.5])
                with c_head1:
                    st.title(f"{input_symbol} - Giá: {safe_fmt(health['close'])}")
                    st.caption(f"Ngày dữ liệu: {last_row['time'].strftime('%d/%m/%Y')}")
                    rec = health['recommendation']
                    r_col = "#00FF00" if "MUA" in rec else "#FF4444" if "BÁN" in rec else "#FFD700"
                    st.markdown(f"<h3 style='color:{r_col}; margin:0'>KHUYẾN NGHỊ: {rec}</h3>", unsafe_allow_html=True)
                with c_head2:
                    sc = health['total_score']
                    clr = "#00FF00" if sc >= 7 else "#FFD700" if sc >= 5 else "#FF4444"
                    st.markdown(f"<div class='big-score' style='color:{clr}'>{sc:.1f}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:center; color:{clr}'>TỔNG ĐIỂM</div>", unsafe_allow_html=True)

                # --- 4. UI: 5 PILLARS SCORE ---
                cols = st.columns(5)
                metrics_config = [
                    {"label": "Kỹ thuật", "key": "technical", "color": "#3366CC", "weight": 0.25},
                    {"label": "Dòng tiền", "key": "flow", "color": "#00FF00", "weight": 0.35},
                    {"label": "Cơ bản", "key": "fundamental", "color": "#FF8C00", "weight": 0.20},
                    {"label": "Định giá", "key": "valuation", "color": "#9932CC", "weight": 0.15},
                    {"label": "Rủi ro", "key": "risk", "color": "#FF4444", "weight": 0.0}
                ]
                for col, cfg in zip(cols, metrics_config):
                    val = scores.get(cfg['key'], 0)
                    contrib = f"Đóng góp: +{val * cfg['weight']:.2f}" if cfg['weight'] > 0 else "Hệ số Phạt"
                    with col:
                        st.markdown(f"""
                        <div class='metric-card' style='border-left-color:{cfg['color']}'>
                            <div class='sub-metric-label'>{cfg['label']}</div>
                            <div class='sub-metric-value' style='color:{cfg['color']}'>{val:.1f}</div>
                            <div style='font-size:11px; color:#888'>{contrib}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # --- 5. UI: KEY METRICS ---
                st.markdown("---")
                rs_rating = health.get('rs_rating', 0)
                m1, m2, m3, m4, m5 = st.columns(5)
                
                pct_chg = (last_row['close'] - df_full.iloc[-2]['close']) / df_full.iloc[-2]['close'] * 100
                m1.metric("Biến động giá", f"{pct_chg:+.2f}%")
                m2.metric("P/E TTM", safe_fmt(last_row.get('pe'), "{:.1f}"))
                m3.metric("Smart Net (10D)", f"{health.get('smart_net_billion_10d', 0):+.1f} tỷ")
                m4.metric("Dòng tiền / Vol", f"{health.get('smart_participation', 0):+.1f}%")
                
                rs_lbl = "Khỏe hơn TT" if rs_rating > 0 else "Yếu hơn TT"
                m5.metric("Sức mạnh RS", f"{rs_rating:+.1f}%", delta=rs_lbl, delta_color="normal" if rs_rating > 0 else "inverse")

                # --- 6. UI: INSIGHTS & WARNINGS ---
                with st.expander("📝 Luận điểm & Cảnh báo", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.success("✅ **ĐIỂM TÍCH CỰC**")
                        pros = details.get('technical', []) + details.get('flow', []) + details.get('fundamental', [])
                        if pros:
                            for p in pros: st.write(f"• {p}")
                        else: st.write("Không có điểm nhấn.")
                    with c2:
                        st.error("⚠️ **CẢNH BÁO RỦI RO**")
                        ws = details.get('warning', [])
                        if scores.get('risk', 10) < 5: ws.append(f"Điểm Rủi ro thấp ({scores.get('risk')}/10).")
                        if ws:
                            for w in ws: st.write(f"• {w}")
                        else: st.info("An toàn.")

                # --- 7. UI: TRADE PLAN ---
                plan = health.get('trade_plan', {})
                if plan:
                    st.markdown("---")
                    st.subheader("🎯 KẾ HOẠCH GIAO DỊCH")
                    ct, ci = st.columns(2)
                    
                    # Trading Plan Card
                    with ct:
                        tp = plan.get('trading', {})
                        act = tp.get('action', 'QUAN SÁT')
                        clr = "#00FF00" if "MUA" in act else "#FF4444" if "BÁN" in act else "gray"
                        
                        st.markdown(f"""
                        <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid {clr};">
                            <h4 style="color:{clr}; margin:0">⚡ TRADING NGẮN HẠN</h4>
                            <h2 style="color:white; margin:10px 0">{act}</h2>
                            <p style="color:#bbb; font-style:italic">"{tp.get('reason', '')}"</p>
                            <hr style="border-color:#444">
                            <div style="display:flex; justify-content:space-between">
                                <div><span style="color:#888; font-size:12px">Vùng Mua</span><br><strong style="color:#00CC96; font-size:16px">{tp.get('entry_zone','-')}</strong></div>
                                <div><span style="color:#888; font-size:12px">Mục Tiêu</span><br><strong style="color:#AB63FA; font-size:16px">{tp.get('target','-')}</strong></div>
                                <div><span style="color:#888; font-size:12px">Cắt Lỗ</span><br><strong style="color:#EF553B; font-size:16px">{tp.get('stop_loss','-')}</strong></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.expander("Các mốc Hỗ trợ/Kháng cự"):
                            kl = plan.get('key_levels', {})
                            s, r = st.columns(2)
                            with s:
                                st.caption("HỖ TRỢ")
                                for n, p in kl.get('supports', []): st.write(f"- {n}: **{p:,.0f}**")
                            with r:
                                st.caption("KHÁNG CỰ")
                                for n, p in kl.get('resistances', []): st.write(f"- {n}: **{p:,.0f}**")

                    # Investing Plan Card
                    with ci:
                        ip = plan.get('investing', {})
                        iact = ip.get('action', 'N/A')
                        iclr = "#FFA15A" if "MUA" in iact else "gray"
                        
                        st.markdown(f"""
                        <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid {iclr}; height: 100%">
                            <h4 style="color:{iclr}; margin:0">🐢 TÍCH SẢN DÀI HẠN</h4>
                            <h2 style="color:white; margin:10px 0">{iact}</h2>
                            <p style="color:#bbb; font-style:italic">"{ip.get('reason', '')}"</p>
                            <hr style="border-color:#444">
                            <div>
                                <span style="color:#888; font-size:12px">Vùng Giá Gom Khuyến Nghị:</span><br>
                                <strong style="color:white; font-size:18px">{ip.get('buy_under', '-')}</strong>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            
    # ==========================================
    #               DETAILED TABS
    # ==========================================
    t1, t2, t3, t4 = st.tabs([
        "🌊 1. DÒNG TIỀN (SÂU)", "📈 2. KỸ THUẬT", "🏢 3. CƠ BẢN", "🛡️ 4. RỦI RO"
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

        # ========================================================
        # [NEW] PHẦN HIỂN THỊ DNA & MÔ PHỎNG (Insert vào đây)
        # ========================================================
        dna = health.get('flow_dna', {})
        if dna:
            st.markdown("---")
            st.subheader("🧬 STOCK FLOW DNA (Phân tích Hành vi)")
            
            # 1. Trạng thái hiện tại
            st.info(f"📌 **Trạng thái:** {dna.get('current_state', 'N/A')}")
            
            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.metric("Smart Accu (5D)", f"{dna.get('smart_accu_5d',0):.2f}", help="Tích lũy ròng của Tay to trong 5 ngày/Avg Vol")
            col_d2.metric("Flow Z-Score", f"{dna.get('smart_z_score',0):.2f} σ", help="Độ đột biến dòng tiền (>2 là Breakout, <-2 là Panic)")
            
            # Hiển thị Lead-Lag
            corr_stats = dna.get('correlation_stats', {})
            lead_lag = corr_stats.get('lead_lag', {}) if corr_stats else {}
            if lead_lag:
                status = lead_lag.get('status', 'N/A')
                color = "normal" if "Tiền đi trước" in status else "off"
                col_d3.metric("Mối quan hệ", status, delta_color=color)

            # 2. Kết quả Mô phỏng Quá khứ (Simulation)
            st.markdown("##### 🎲 Mô phỏng Xác suất (Dựa trên 30 phiên tương tự nhất trong quá khứ)")
            sim = dna.get('simulation_stats', {})
            
            if sim:
                # Layout dạng thẻ
                sc1, sc2, sc3 = st.columns(3)
                
                win_rate = sim.get('win_rate_t5', 0)
                sc1.metric("Win Rate (T+5)", f"{win_rate}%", 
                           "Cao" if win_rate > 60 else "Thấp" if win_rate < 40 else "Trung bình")
                
                avg_ret = sim.get('avg_return_t5', 0)
                sc2.metric("Lợi nhuận TB", f"{avg_ret:+.1f}%")
                
                sc3.metric("Kịch bản Xấu nhất", f"{sim.get('worst_case', 0):+.1f}%")
                
                st.caption(f"*Hệ thống tìm thấy {sim.get('sample_size')} lần trong quá khứ cổ phiếu này có hành động dòng tiền (gom/xả/đột biến) giống hệt hôm nay.*")
            else:
                st.warning("Không đủ dữ liệu lịch sử tương đồng để chạy mô phỏng.")
                
        # ========================================================
        # (Kết thúc phần chèn thêm)
        
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

        # 3. Chart VWAP & Vị Thế & Giá Bán (Update)
        st.subheader("Phân tích Hành vi Cá mập (VWAP)")
        
        # 1. Selectbox chọn Nhóm NĐT (Đã thêm các nhóm mới)
        target_investor = st.selectbox(
            "Chọn Góc nhìn:", 
            [
                "Tổ chức Nước ngoài (foreign_inst)", # Ưu tiên
                "Cá nhân Nước ngoài (foreign_ind)",  # Mới
                "Tự doanh (prop)", 
                "Cá nhân Nội (local_ind)", 
                "Tổ chức Nội (local_inst)",
                "Khối Ngoại Tổng (foreign)" # Backup
            ],
            index=0
        )
        
        # Mapping Key từ selectbox sang tên cột dữ liệu
        # (Phải khớp với tên biến trong InvestorFlowAnalyzer)
        map_inv = {
            "Tổ chức Nước ngoài (foreign_inst)": "foreign_inst",
            "Cá nhân Nước ngoài (foreign_ind)": "foreign_ind",
            "Tự doanh (prop)": "prop",
            "Cá nhân Nội (local_ind)": "local_ind",
            "Tổ chức Nội (local_inst)": "local_inst",
            "Khối Ngoại Tổng (foreign)": "foreign"
        }
        code = map_inv[target_investor]
        
        # 2. Logic Vẽ VWAP (Copy từ logic chuẩn bạn đã gửi)
        # Lấy 60 ngày gần nhất
        # days_lookback = 60
        if not df_full.empty:
            df_calc = df_full.tail(days_lookback).copy().reset_index(drop=True)
            
            # ... (Đoạn code tính VWAP của bạn, CHÚ Ý thay 'code' vào đúng chỗ) ...
            
            # --- KHỞI TẠO BIẾN ---
            vwap_buy_series = []
            net_vol_series = [] 
            daily_sell_price_series = []
            
            current_vol = 0.0
            current_cost = 0.0 
            
            # Loop tính toán (Giống code bạn cung cấp)
            for i, row in df_calc.iterrows():
                # Lấy đúng cột theo 'code' đã chọn (VD: foreign_inst_buy_val)
                buy_val = row.get(f'{code}_buy_val', 0)
                buy_vol = row.get(f'{code}_buy_vol', 0)
                sell_val = row.get(f'{code}_sell_val', 0)
                sell_vol_amt = row.get(f'{code}_sell_vol', 0) # rename to avoid conflict
                price = row['close']
                
                # Fallback fill nếu thiếu Vol
                if buy_vol == 0 and buy_val > 0 and price > 0: buy_vol = buy_val / price
                if sell_vol_amt == 0 and sell_val > 0 and price > 0: sell_vol_amt = sell_val / price

                # Logic tính giá bán TB trong ngày
                daily_sell = (sell_val / sell_vol_amt) if sell_vol_amt > 0 else None
                daily_sell_price_series.append(daily_sell)

                # Logic VWAP Mua
                current_vwap = 0
                if buy_vol > 0:
                    current_cost += buy_val 
                    current_vol += buy_vol
                
                if current_vol > 0: 
                    current_vwap = current_cost / current_vol
                
                if sell_vol_amt > 0:
                    current_vol -= sell_vol_amt
                    current_cost = current_vol * current_vwap
                    if current_vol <= 0:
                        current_vol = 0; current_cost = 0; current_vwap = price # Reset
                
                vwap_buy_series.append(current_vwap if current_vol > 0 else None)
                net_vol_series.append(current_vol)

            # Gán & Vẽ
            df_calc['vwap_buy'] = pd.Series(vwap_buy_series).ffill() # Fix lỗi fillna method
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=df_calc['time'], y=df_calc['close'], name="Giá TT", line=dict(color='gray', dash='dot')), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_calc['time'], y=df_calc['vwap_buy'], name=f"Giá Vốn {code}", line=dict(color='#00FF00', width=2)), secondary_y=False)
            
            # Markers Giá Bán
            fig.add_trace(go.Scatter(x=df_calc['time'], y=daily_sell_price_series, mode='markers', name="Giá Bán", marker=dict(color='#FF4444', size=6, symbol='triangle-down')), secondary_y=False)
            
            # Inventory Bar
            fig.add_trace(go.Bar(x=df_calc['time'], y=net_vol_series, name="Tồn kho", marker_color='rgba(0, 204, 150, 0.15)'), secondary_y=True)
            
            fig.update_layout(title=f"Vị thế & Hành động: {target_investor}", height=450, hovermode="x unified", template="plotly_dark")
            fig.update_yaxes(showticklabels=False, secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

        # 4. Chart Xu hướng Dòng tiền Tích lũy Dài Hạn (CUSUM RAW - TOÀN LỊCH SỬ)
        st.markdown("### 3. Xu hướng tích lũy")
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
                'foreign_ind_net_vol': {'name': 'Cá nhân NN', 'color': 'orange'},
                'foreign_inst_net_vol': {'name': 'Tổ chức NN', 'color': 'purple'},
                'prop_net_vol': {'name': 'Tự doanh', 'color': 'cyan'},
                'local_ind_net_vol': {'name': 'Cá nhân', 'color': 'red'},
                'local_inst_net_vol': {'name': 'Tổ chức', 'color': 'green'}
            }
            
            for col_name, attrs in inv_map_cusum.items():
                if col_name in df_full.columns:
                    # Lũy kế từ đầu
                    y_vals = df_full[col_name].fillna(0).cumsum()
                    fig_cusum.add_trace(go.Scatter(x=df_full['time'], y=y_vals, name=attrs['name'], line=dict(color=attrs['color'], width=2)), secondary_y=True)

            fig_cusum.update_layout(title="Xu hướng khối lượng tích lũy", template="plotly_dark", height=500, hovermode="x unified")
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

    with t3:
        # ---------------- TAB 3: FUNDAMENTAL ----------------
        biz_type = health.get('business_type', 'Unknown')
        metrics = health.get('fund_metrics', {})

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

    # ---------------- TAB 5: RISK ----------------
    with t4:
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

# except Exception as e:
#     st.error(f"Đã xảy ra lỗi nghiêm trọng: {e}")
#     # st.exception(e)