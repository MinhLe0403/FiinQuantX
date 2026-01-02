import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

class StockView:
    @staticmethod
    def render_analysis(data):
        if not data: return
        if "error" in data:
            st.error(data["error"])
            return

        # 1. HEADER
        c1, c2 = st.columns([2.5, 1.5])
        with c1:
            st.title(f"{data['symbol']} - {data['price_fmt']}")
            st.caption(f"Cập nhật: {data['date_str']}")
            # Delta color logic
            clr_chg = "green" if data['change_pct'] >= 0 else "red"
            st.markdown(f"**Biến động:** :{clr_chg}[{data['change_pct']:+.2f}%]")
            
            st.markdown(f"<h3 style='color:{data['rec_color']}'>{data['rec']}</h3>", unsafe_allow_html=True)
            
        with c2:
            clr = data['score_color']
            st.markdown(f"<div style='font-size:60px; font-weight:800; text-align:center; color:{clr}; line-height:1'>{data['score']:.1f}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center; color:{clr}'>TỔNG ĐIỂM</div>", unsafe_allow_html=True)

        # 2. 5 PILLARS (Render native cards)
        cols = st.columns(5)
        for i, p in enumerate(data['pillars']):
            with cols[i]:
                # Hack viền màu bằng html container
                st.markdown(f"""
                <div style="background-color:#1e1e1e; padding:10px; border-radius:10px; border-left:5px solid {p['color']}; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.3)">
                    <div style="font-size:12px; color:#aaa; text-transform:uppercase">{p['label']}</div>
                    <div style="font-size:22px; font-weight:bold; color:{p['color']}">{p['val']:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

        # 3. KEY METRICS
        st.markdown("---")
        m = data['metrics']
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Biến động giá", f"{data['change_pct']:+.2f}%")
        m2.metric("P/E TTM", f"{m['pe']:.1f}")
        m3.metric("Smart Money", f"{m['smart_money']:+.1f} tỷ")
        m4.metric("Dòng tiền/Vol", f"{m['participation']:+.1f}%")
        rs_clr = "normal" if m['rs_rating']>0 else "inverse"
        m5.metric("Sức mạnh RS", f"{m['rs_rating']:+.1f}%", f"{'Khỏe' if m['rs_rating']>0 else 'Yếu'} hơn TT", delta_color=rs_clr)

        # 4. INSIGHTS
        with st.expander("📝 Luận điểm & Cảnh báo", expanded=False):
            c_p, c_w = st.columns(2)
            with c_p:
                st.success("TÍCH CỰC")
                for x in data['insights']['pros']: st.write(f"• {x}")
            with c_w:
                st.error("RỦI RO")
                for x in data['insights']['cons']: st.write(f"• {x}")

        # 5. TRADE PLAN
        plan = data['trade_plan']
        if plan['has_plan']:
            st.markdown("---")
            st.subheader("🎯 KẾ HOẠCH GIAO DỊCH")
            tc, ic = st.columns(2)
            
            # Helper render card plan
            def card_plan(area, p_data):
                clr = p_data['color']
                act = p_data['action']
                # Streamlit native styling
                st.markdown(f"#### :{clr}[{act}]")
                st.caption(f"_{p_data['reason']}_")
                if "Trading" in area:
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Vùng Mua", p_data['entry'])
                    c2.metric("Mục tiêu", p_data['target'])
                    c3.metric("Cắt lỗ", p_data['stop'])
                else:
                    st.info(f"**Gom giá:** {p_data['entry']}")

            with tc: 
                with st.container(border=True): 
                    st.caption("TRADING NGẮN HẠN")
                    card_plan("Trading", plan['trading'])
                    # Key levels inside trading
                    with st.expander("Các mốc KT"):
                        kl = plan['key_levels']
                        k1, k2 = st.columns(2)
                        with k1: 
                            st.caption("Hỗ trợ")
                            for k,v in kl.get('supports',[]): st.write(f"{k}: {v:,.0f}")
                        with k2:
                            st.caption("Kháng cự")
                            for k,v in kl.get('resistances',[]): st.write(f"{k}: {v:,.0f}")

            with ic: 
                with st.container(border=True):
                    st.caption("TÍCH SẢN DÀI HẠN")
                    card_plan("Investing", plan['investing'])

        # 6. TABS CHI TIẾT
        st.markdown("---")
        StockView._render_detail_tabs(data)

    @staticmethod
    def _render_detail_tabs(data):
        t1, t2, t3, t4, t5 = st.tabs(["🌊 DÒNG TIỀN", "📈 KỸ THUẬT", "🏢 CƠ BẢN", "💰 ĐỊNH GIÁ", "🛡️ RỦI RO"])
        df = data['chart_df']
        
        # TAB 1: FLOW
        with t1:
            st.subheader("Dòng tiền Thông minh & DNA")
            # Logic vẽ VWAP & DNA (Nếu có data DNA từ bước trước)
            dna = data.get('flow_dna', {}).get('profile')
            if dna:
                # Hiển thị Lead Lag
                st.info("DNA Insight: " + str(dna.get('lead_lag_stats', 'Updating...')))
            else:
                st.write("Đang cập nhật DNA Flow...")
            
            # Simple Flow Chart (Lấy history scores)
            hs = pd.DataFrame(data.get('hist_scores', []))
            if not hs.empty:
                hs['time'] = pd.to_datetime(hs['time'])
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hs['time'], y=hs['close'], name='Giá'), secondary_y=False)
                fig.add_trace(go.Scatter(x=hs['time'], y=hs['score_flow'], name='Điểm Flow'), secondary_y=True)
                st.plotly_chart(fig, use_container_width=True)

        # TAB 2: TECHNICAL (Basic Chart)
        with t2:
            if not df.empty and 'EMA_20' in df.columns:
                fig = go.Figure(go.Candlestick(x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'))
                fig.add_trace(go.Scatter(x=df['time'], y=df['EMA_20'], line=dict(color='orange'), name='EMA 20'))
                if 'ICHI_SPAN_A' in df.columns:
                    fig.add_trace(go.Scatter(x=df['time'], y=df['ICHI_SPAN_A'], line=dict(width=0), showlegend=False))
                    fig.add_trace(go.Scatter(x=df['time'], y=df['ICHI_SPAN_B'], line=dict(width=0), fill='tonexty', fillcolor='rgba(0,250,250,0.1)', name='Cloud'))
                st.plotly_chart(fig, use_container_width=True)
                
        # TAB 3: FUNDAMENTAL
        with t3:
            f = data['fund_data']
            if f['type'] != 'Unknown':
                st.subheader(f"Loại hình: {f['type']}")
                st.json(f['raw'])
            else: st.info("Thiếu BCTC")
            
        # TAB 4 & 5 (Tương tự...)
        # Bạn có thể copy logic vẽ P/E Chart và ATR từ code cũ vào đây dễ dàng