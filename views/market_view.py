# views/market_view.py
import streamlit as st
import plotly.graph_objects as go

class MarketView:
    @staticmethod
    def render_market_matrix(data_list):
        """Hiển thị 4 thẻ bài chỉ số (Kèm Khuyến nghị hành động)"""
        if not data_list: return

        # 1. Hướng dẫn đọc
        with st.expander("📖 Hướng dẫn đọc Bảng Tín Hiệu (Bấm để xem)", expanded=False):
            st.markdown("""
            - **Sức mạnh (0-100):** >80 là rất khỏe (Uptrend mạnh), <30 là rất yếu (Sập/Downtrend).
            - **Phân phối:** Số ngày thị trường bị bán mạnh trong 25 phiên gần nhất. Nếu **>=4 ngày** là dấu hiệu Đảo chiều (Tạo đỉnh).
            - **Khuyến nghị:** Dựa trên xu hướng và rủi ro để đưa ra hành động gợi ý.
            """)

        cols = st.columns(len(data_list))
        for i, item in enumerate(data_list):
            with cols[i]:
                # Sử dụng container native để layout đẹp
                with st.container(border=True):
                    # Header
                    c_name, c_price = st.columns([1, 2])
                    c_name.markdown(f"**{item['symbol']}**")
                    c_price.markdown(f"<div style='text-align:right; font-weight:bold;'>{item['price']} <span style='font-size:12px; color:{'green' if '+' in item['change_fmt'] else 'red'}'>{item['change_fmt']}</span></div>", unsafe_allow_html=True)
                    
                    st.caption(f"Vol: {item['vol_str']}")
                    
                    st.divider()
                    
                    # Trend Info (Có Tooltip giải thích)
                    st.markdown(f"Xu hướng: :{ 'green' if 'UP' in item['regime_text'] else 'red' }[{item['regime_text']}]", help="Xác định dựa trên EMA20, EMA50 và ADX.")
                    
                    # Recommendation (Điểm nhấn mới)
                    st.markdown(
                        f"<div style='background-color:{item['action_color']}33; border:1px solid {item['action_color']}; color:{item['action_color']}; padding:5px; border-radius:5px; text-align:center; font-weight:bold; font-size:14px; margin: 10px 0;'>{item['action']}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    # Footer Score
                    c1, c2 = st.columns(2)
                    c1.metric("Sức mạnh", f"{item['score']}/100", help="Tổng hợp điểm kỹ thuật và dòng tiền")
                    
                    # Dist Days Warning
                    dist_lbl = f"{item['dist_days']} ngày"
                    dist_delta = "Nguy hiểm" if item['dist_warning'] else "An toàn"
                    dist_col = "inverse" if item['dist_warning'] else "off"
                    c2.metric("Phân phối", dist_lbl, dist_delta, delta_color=dist_col, help="Số ngày giảm mạnh + Vol lớn. >=4 ngày là báo động đỏ.")

    @staticmethod
    def render_quant_lab(data):
        if not data: return
        st.subheader("🧪 PHÒNG LAB ĐỊNH LƯỢNG (Giải thích)")
        
        # Grid layout với caption giải nghĩa
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.metric(
                "Liquidity Z", f"{data['liq_z_score']:+.2f}", data['liq_status'],
                help="Đo lường dòng tiền vào so với trung bình 20 phiên. Z > 2.0 là tiền vào cực mạnh (Đột biến)."
            )
            
        with c2:
            st.metric(
                "Order Imbalance", f"{data['imbalance']:+.1f}%", 
                "Mua Chủ Động" if data['imbalance'] > 0 else "Bán Chủ Động",
                help="Sự chênh lệch giữa Khớp lệnh mua chủ động và bán chủ động. Dương là Tốt (Cầu > Cung)."
            )
            
        with c3:
            val = data['vwap_dev']
            lbl = "Quá Mua" if val > 2 else "Quá Bán" if val < -2 else "Cân bằng"
            st.metric(
                "VWAP Deviation", f"{val:+.2f} ATR", delta=lbl, delta_color="inverse",
                help="Giá lệch bao nhiêu so với Giá vốn trung bình trong ngày. Nếu lệch quá xa (>2 ATR) thường sẽ đảo chiều."
            )
            
        with c4:
            st.metric(
                "Volatility", f"{data['vol_rank']}/100", data['vol_regime'], delta_color="off",
                help="Mức độ biến động giá. Cao (High) = Rủi ro lớn, biên độ rộng. Thấp (Low) = Đang nén, chuẩn bị bung mạnh."
            )

    @staticmethod
    def render_mfe_dashboard(data):
        """MFE Dashboard với giải thích rõ ràng"""
        if not data: return

        st.markdown("---")
        st.subheader("🌊 ĐỘNG CƠ DÒNG TIỀN (MARKET FLOW ENGINE)")
        st.info("💡 **Góc nhìn:** Hệ thống chấm điểm dòng tiền dựa trên Big Data, không chỉ dựa vào giá xanh/đỏ.")

        c_main, c_comps = st.columns([1, 2])
        
        with c_main:
            score = data['score']
            color = data['color']
            st.markdown(f"""
            <div style="text-align: center; border: 4px solid {color}; border-radius: 50%; width: 160px; height: 160px; margin: 0 auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background-color: #1E1E1E;">
                <strong style="font-size: 42px; color: {color}; line-height: 1;">{score}</strong>
                <span style="color: {color}; font-size: 11px; font-weight: bold; margin-top:5px;">{data['status']}</span>
            </div>
            """, unsafe_allow_html=True)
            if data.get('fsi_alert'):
                st.warning(data['fsi_alert'])

        with c_comps:
            comps = data['components']
            
            # Sử dụng markdown để giải thích chi tiết
            def flow_bar(label, score, help_text):
                st.write(f"**{label}** ({score}/100)")
                st.progress(score/100)
                st.caption(f"ℹ️ {help_text}")
            
            flow_bar("1. Smart Money (Cá Mập)", comps['smf'], "Dòng tiền mua ròng thực tế của Khối ngoại & Tự doanh.")
            flow_bar("2. Đồng Thuận (Consensus)", comps['div'], "Sự đồng pha giữa Giá tăng và Tiền vào. Nếu Giá tăng mà Tiền ra (Phân kỳ) điểm sẽ thấp.")
            flow_bar("3. Cấu Trúc (Anti-Fragile)", comps['fragility'], "Độ bền vững. Nếu thanh khoản bị rút đột ngột (Liquidity Shock), chỉ số này sẽ báo động.")
            
    @staticmethod
    def render_deep_dive(data):
        """Hiển thị phần Breadth, Rotation, Sector"""
        c1, c2, c3 = st.columns([1.5, 1.5, 2.5])
        
        # 1. Breadth View
        with c1:
            with st.container(border=True):
                st.markdown("##### 🩺 Độ rộng (Market Breadth)", help="So sánh số lượng mã Tăng vs Giảm trên toàn thị trường.")
                br_real = data.get('breadth_real', {})
                br_stats = data.get('breadth_stats', {})
                
                if br_real:
                    g, r, y = br_real.get('green',0), br_real.get('red',0), br_real.get('yellow',0)
                    total = g+r+y
                    if total > 0:
                        fig = go.Figure(data=[go.Pie(
                            labels=['Tăng', 'Giảm', 'TC'], values=[g, r, y], 
                            hole=.6, marker_colors=['#00CC96', '#EF553B', '#FFD700'], textinfo='none'
                        )])
                        fig.update_layout(
                            annotations=[dict(text=f"{int(g/total*100)}%", x=0.5, y=0.5, font_size=20, showarrow=False, font_color="#00CC96")],
                            height=150, margin=dict(t=0,b=0,l=0,r=0), showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                st.caption(f"• >MA200: **{br_stats.get('pct_above_sma200',0)}%**")
                st.caption(f"• Vượt đỉnh 52W: **{br_stats.get('near_high_52w',0)} mã**")

        # 2. Rotation View
        with c2:
            with st.container(border=True):
                st.markdown("##### 💰 Dòng tiền Vốn hóa", help="Dòng tiền đang chảy vào Bluechip (Large) hay Penny (Small)?")
                df_rot = data.get('rotation', None)
                if df_rot is not None and not df_rot.empty:
                    fig = go.Figure(go.Bar(
                        x=df_rot['total_val'], y=df_rot['cap_group'], orientation='h',
                        marker_color=['#AB63FA', '#FFA15A', '#19D3F3'],
                        text=df_rot['total_val'].apply(lambda x: f"{x/1e9:.0f}"), textposition='auto'
                    ))
                    fig.update_layout(height=200, margin=dict(t=0,b=0,l=0,r=0), yaxis=dict(showticklabels=False), xaxis=dict(showticklabels=False), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                    st.info(f"Tập trung: {df_rot.iloc[0]['cap_group'].split('(')[0]}")
                else:
                    st.warning("Thiếu dữ liệu Vốn hóa.")

        with c3:
            with st.container(border=True):
                st.markdown("##### 🔥 Ngành Dẫn Sóng", help="Top các ngành có mức tăng giá và dòng tiền mạnh nhất.")
                df_sec = data.get('sectors')
                if df_sec is not None and not df_sec.empty:
                    # Rename cho dễ hiểu
                    disp_df = df_sec.head(5)[['sector', 'weighted_change', 'total_value']]
                    disp_df.columns = ["Ngành", "% Tăng", "Giá trị GD"]
                    st.dataframe(disp_df, use_container_width=True, hide_index=True)
    
    @staticmethod
    def render_quant_lab(data):
        if not data: return
        st.subheader("🧪 QUANT LAB")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Liquidity Z", f"{data['liq_z_score']:.2f}", data['liq_status'])
        c2.metric("Imbalance", f"{data['imbalance']:.1f}%")
        c3.metric("VWAP Dev", f"{data['vwap_dev']:.2f}")
        c4.metric("Volatility", f"{data['vol_rank']}/100", data['vol_regime'])

        # --- THÊM HÀM MỚI NÀY VÀO CLASS MarketView ---
    @staticmethod
    def render_mfe_dashboard(data):
        """Hiển thị Dashboard Động cơ dòng tiền (MFE)"""
        if not data:
            return

        st.subheader("🌊 ĐỘNG CƠ DÒNG TIỀN (MARKET FLOW ENGINE)")
        
        # Chia layout: 1 cột điểm tổng (tròn), 2 cột chi tiết thành phần
        c_main, c_comps = st.columns([1, 2])
        
        # 1. Vẽ vòng tròn điểm số bằng HTML/CSS
        with c_main:
            score = data['score']
            color = data['color']
            status = data['status']
            
            st.markdown(f"""
            <div style="
                text-align: center; 
                border: 4px solid {color}; 
                border-radius: 50%; 
                width: 170px; height: 170px; 
                margin: 0 auto; 
                display: flex; flex-direction: column; 
                justify-content: center; align-items: center; 
                background-color: #1E1E1E;
                box-shadow: 0 0 15px rgba(0,0,0,0.5);
            ">
                <span style="color: #aaa; font-size: 13px; font-weight: bold;">MFE SCORE</span>
                <strong style="font-size: 46px; color: {color}; line-height: 1;">{score}</strong>
                <span style="color: {color}; font-size: 11px; font-weight: bold; margin-top: 5px;">
                    {status}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            # Hiển thị FSI Alert (nếu có)
            if data['fsi_alert']:
                st.markdown(f"<div style='text-align: center; margin-top: 10px; font-size: 13px;'>{data['fsi_alert']}</div>", unsafe_allow_html=True)

        # 2. Vẽ các thanh thành phần
        with c_comps:
            comps = data['components']
            
            # Helper vẽ từng dòng
            def render_bar(label, value, desc):
                st.markdown(f"**{label}** <span style='float:right; font-size:12px; color:#aaa'>{value}/100</span>", unsafe_allow_html=True)
                st.progress(value / 100)
                st.caption(desc)
            
            # SMF
            render_bar("1. Dòng tiền Thông minh (Smart Money)", comps['smf'], 
                       "Sức mua ròng của Khối ngoại, Tự doanh và Tổ chức (Z-Score).")
            
            # Divergence
            render_bar("2. Sự đồng thuận (Price-Flow)", comps['div'], 
                       "Độ tương quan giữa Biến động giá và Dòng tiền tích lũy.")
            
            # Fragility
            render_bar("3. Độ Vững chãi (Market Structure)", comps['fragility'], 
                       "Khả năng chống chịu cú sốc thanh khoản (Thấp = Dễ vỡ).")