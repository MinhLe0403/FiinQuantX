# core.py
import sys, os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL
from analysis.investor_flow import InvestorFlowAnalyzer
from analysis.technical import TechnicalEngine
from analysis.fundamental import FundamentalAnalysis
from analysis.recommendation import RecommenderEngine
from analysis.market.data_access import MarketEngine 

class StockAnalyzer:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.flow_analyzer = InvestorFlowAnalyzer()
        self.tech_engine = TechnicalEngine()
        self.fund_analyzer = FundamentalAnalysis()
        self.recommender = RecommenderEngine()
        self.market_engine = MarketEngine(self.engine)

    def get_dim_stocks(self):
        """
        Lấy thông tin cổ phiếu từ bảng dim_stocks.
        Trả về DataFrame chứa tất cả dữ liệu (symbol, company_name, exchange, sector, industry, type, updated_at).
        """
        query = text("""
            SELECT symbol, company_name, exchange, sector, industry, type, updated_at
            FROM dim_stocks
            ORDER BY symbol ASC
        """)
        
        try:
            df = pd.read_sql(query, self.engine)
            print(f"✅ Đã lấy thông tin {len(df)} cổ phiếu từ bảng dim_stocks.")
            return df
        except Exception as e:
            print(f"❌ Lỗi khi lấy dữ liệu từ dim_stocks: {e}")
            return pd.DataFrame()
        

    def get_all_symbols(self):
        """
        Lấy danh sách mã trực tiếp từ bảng dữ liệu giá (fact_daily_bars)
        thay vì phụ thuộc vào bảng danh mục (dim_stocks).
        """
        # Query này sẽ quét bảng giá để tìm tất cả các mã có dữ liệu
        query = text("SELECT DISTINCT symbol FROM fact_daily_bars ORDER BY symbol ASC")
        
        try:
            with self.engine.connect() as conn:
                res = conn.execute(query).fetchall()
                symbols = [r[0] for r in res]
                print(f"📊 Debug: Tìm thấy {len(symbols)} mã từ dữ liệu giá (fact_daily_bars).")
                return symbols
        except Exception as e:
            print(f"❌ Error fetching symbols: {e}")
            return []

    # QUERY LẤY DATA, KHÔNG ĐƯỢC XÓA, CHỈ ĐƯỢC THÊM VÀ THAM CHIẾU
    def get_full_data(self, symbol, limit=365):
        # Query giữ nguyên như phiên bản chuẩn trước đó (Lấy đủ các cột Volume/Value)
        query = text(f"""
        SELECT 
            p.time, 
            p.symbol, 
            p.open, p.high, p.low, p.close,
            COALESCE(p.close_raw, p.close) AS close_raw,
            p.volume,
            p.trading_value,
            p.buy_active_vol, 
            p.sell_active_vol,
            p.vwap,

            f.share_issue,

            -- =======================
            -- Investor Value Flows
            -- =======================
            -- Foreign
            COALESCE(f.foreign_buy_val, 0) AS foreign_buy_val,
            COALESCE(f.foreign_sell_val, 0) AS foreign_sell_val,
                     
            -- FOREIGN DETAILED (Mới)
            COALESCE(f.foreign_ind_buy_val, 0) AS foreign_ind_buy_val,
            COALESCE(f.foreign_ind_sell_val, 0) AS foreign_ind_sell_val,
                     
            COALESCE(f.foreign_inst_buy_val, 0) AS foreign_inst_buy_val,
            COALESCE(f.foreign_inst_sell_val, 0) AS foreign_inst_sell_val,

            -- Proprietary (Prop)
            COALESCE(f.prop_buy_val, 0) AS prop_buy_val,
            COALESCE(f.prop_sell_val, 0) AS prop_sell_val,

            -- Local Individual
            COALESCE(f.local_ind_buy_val, 0) AS local_ind_buy_val,
            COALESCE(f.local_ind_sell_val, 0) AS local_ind_sell_val,

            -- Local Institution
            COALESCE(f.local_inst_buy_val, 0) AS local_inst_buy_val,
            COALESCE(f.local_inst_sell_val, 0) AS local_inst_sell_val,

            -- =======================
            -- Investor Volume Flows
            -- =======================
            -- Foreign
            COALESCE(f.foreign_buy_vol, 0) AS foreign_buy_vol,
            COALESCE(f.foreign_sell_vol, 0) AS foreign_sell_vol,

            -- FOREIGN DETAILED (Mới)
            COALESCE(f.foreign_ind_buy_vol, 0) AS foreign_ind_buy_vol,
            COALESCE(f.foreign_ind_sell_vol, 0) AS foreign_ind_sell_vol,
                     
            COALESCE(f.foreign_inst_buy_vol, 0) AS foreign_inst_buy_vol,
            COALESCE(f.foreign_inst_sell_vol, 0) AS foreign_inst_sell_vol,

            -- Proprietary (Prop)
            COALESCE(f.prop_buy_vol, 0) AS prop_buy_vol,
            COALESCE(f.prop_sell_vol, 0) AS prop_sell_vol,

            -- Local Individual
            COALESCE(f.local_ind_buy_vol, 0) AS local_ind_buy_vol,
            COALESCE(f.local_ind_sell_vol, 0) AS local_ind_sell_vol,

            -- Local Institution
            COALESCE(f.local_inst_buy_vol, 0) AS local_inst_buy_vol,
            COALESCE(f.local_inst_sell_vol, 0) AS local_inst_sell_vol,
                    
            -- =======================
            -- Net Value (Buy - Sell)
            -- =======================
            (COALESCE(f.foreign_buy_val, 0)     - COALESCE(f.foreign_sell_val, 0))     AS foreign_net_val,
            (COALESCE(f.foreign_ind_buy_val, 0) - COALESCE(f.foreign_ind_sell_val, 0)) AS foreign_ind_net_val,
            (COALESCE(f.foreign_inst_buy_val, 0) - COALESCE(f.foreign_inst_sell_val, 0)) AS foreign_inst_net_val,
            (COALESCE(f.prop_buy_val, 0)        - COALESCE(f.prop_sell_val, 0))        AS prop_net_val,
            (COALESCE(f.local_inst_buy_val, 0)  - COALESCE(f.local_inst_sell_val, 0))  AS local_inst_net_val,
            (COALESCE(f.local_ind_buy_val, 0)   - COALESCE(f.local_ind_sell_val, 0))   AS local_ind_net_val,

            -- =======================
            -- Net Volume (BuyVol - SellVol)
            -- =======================
            (COALESCE(f.foreign_buy_vol, 0)     - COALESCE(f.foreign_sell_vol, 0))     AS foreign_net_vol,
            (COALESCE(f.foreign_ind_buy_vol, 0) - COALESCE(f.foreign_ind_sell_vol, 0)) AS foreign_ind_net_vol,
            (COALESCE(f.foreign_inst_buy_vol, 0) - COALESCE(f.foreign_inst_sell_vol, 0)) AS foreign_inst_net_vol,
            (COALESCE(f.prop_buy_vol, 0)        - COALESCE(f.prop_sell_vol, 0))        AS prop_net_vol,
            (COALESCE(f.local_inst_buy_vol, 0)  - COALESCE(f.local_inst_sell_vol, 0))  AS local_inst_net_vol,
            (COALESCE(f.local_ind_buy_vol, 0)   - COALESCE(f.local_ind_sell_vol, 0))   AS local_ind_net_vol,

            -- =======================
            -- Total Volume (BuyVol + SellVol)
            -- =======================
            (COALESCE(f.foreign_buy_vol, 0) + COALESCE(f.foreign_sell_vol, 0)) AS foreign_total_vol,
            (COALESCE(f.foreign_ind_buy_vol, 0) + COALESCE(f.foreign_ind_sell_vol, 0)) AS foreign_ind_total_vol,
            (COALESCE(f.foreign_inst_buy_vol, 0) + COALESCE(f.foreign_inst_sell_vol, 0)) AS foreign_inst_total_vol,
            (COALESCE(f.prop_buy_vol, 0)    + COALESCE(f.prop_sell_vol, 0))    AS prop_total_vol,
            (COALESCE(f.local_inst_buy_vol, 0) + COALESCE(f.local_inst_sell_vol, 0)) AS local_inst_total_vol,
            (COALESCE(f.local_ind_buy_vol, 0) + COALESCE(f.local_ind_sell_vol, 0)) AS local_ind_total_vol,

            -- =======================
            -- Total Value (Buy + Sell)
            -- =======================
            (COALESCE(f.foreign_buy_val, 0) + COALESCE(f.foreign_sell_val, 0)) AS foreign_total_val,
            (COALESCE(f.foreign_ind_buy_val, 0) + COALESCE(f.foreign_ind_sell_val, 0)) AS foreign_ind_total_val,
            (COALESCE(f.foreign_inst_buy_val, 0) + COALESCE(f.foreign_inst_sell_val, 0)) AS foreign_inst_total_val,
            (COALESCE(f.prop_buy_val, 0)    + COALESCE(f.prop_sell_val, 0))    AS prop_total_val,
            (COALESCE(f.local_inst_buy_val, 0) + COALESCE(f.local_inst_sell_val, 0)) AS local_inst_total_val,
            (COALESCE(f.local_ind_buy_val, 0) + COALESCE(f.local_ind_sell_val, 0)) AS local_ind_total_val,

            -- =======================
            -- Valuations
            -- =======================
            v.pe, 
            v.pb

        FROM fact_daily_bars p
        LEFT JOIN fact_investor_flows_daily f 
            ON p.time::date = f.time::date 
            AND p.symbol = f.symbol
        LEFT JOIN fact_valuation_daily v 
            ON p.time::date = v.time::date 
            AND p.symbol = v.symbol

        WHERE p.symbol = :symbol
        ORDER BY p.time ASC;
        """)
        try:
            df = pd.read_sql(query, self.engine, params={"symbol": symbol})
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'])
                df = self.flow_analyzer.calculate_position(df)
                return df.tail(limit).reset_index(drop=True)
            return df
        except Exception as e:
            print(f"Core Error: {e}")
            return pd.DataFrame()

    def get_financials(self, symbol):
        try:
            query = text(f"""
            SELECT year, quarter, roe, roa, eps, book_value_per_share, 
                   debt_to_equity, current_ratio, nim, ldr, bad_debt_ratio,
                   loan_loss_reserves_to_npls, loans_growth_yoy, deposits_growth_yoy, interest_income_growth_yoy,
                   ebit_margin, roic, revenue_growth_yoy, ebt_growth_yoy
            FROM fact_financial_ratios
            WHERE symbol = :symbol ORDER BY year DESC, quarter DESC LIMIT 1
            """)
            with self.engine.connect() as conn:
                res = conn.execute(query, {"symbol": symbol}).fetchone()
                return dict(res._mapping) if res else None
        except: return None

    def get_investor_summary(self, symbol, limit=30):
        df = self.get_full_data(symbol, limit=limit)
        return self.flow_analyzer.get_period_summary(df)
    
    def calculate_historical_scores(self, df, fin):
        """
        Tính toán series điểm lịch sử.
        Lưu ý: Logic Fundamental cũ thường chỉ tính snapshot cho quý mới nhất.
        Nếu muốn time-series cho fundamental chính xác cần dữ liệu BCTC lịch sử theo quý.
        Ở đây ta dùng phương pháp 'Forward Fill' điểm cơ bản hiện tại cho chuỗi giá gần đây.
        """
        if df.empty: return df
        df = self.tech_engine.add_all_indicators(df)
        
        # 1. Tech & Flow Score
        df['score_tech'] = self.tech_engine.calculate_technical_score(df)
        df['score_risk'] = self.tech_engine.calculate_risk_score(df)
        df['score_flow'] = self.flow_analyzer.calculate_flow_score_vn2025(df)
        
        # 2. Fund & Val Score (Lấy từ module mới)
        # Vì Fundamental tính 1 lần (snapshot), ta apply giá trị đó cho các row gần nhất
        # Hoặc tính P/B P/E động cho valuation
        
        fund_result = self.fund_analyzer.analyze(df, fin)
        
        # Score Cơ bản là cố định trong kỳ báo cáo (snapshot)
        df['score_fund'] = fund_result['score_fund']
        
        # Score Định giá có thể biến động theo giá hàng ngày (nếu logic dùng PE/PB động)
        # Tuy nhiên để đơn giản và nhất quán với module tách biệt, ta dùng kết quả snapshot
        # Hoặc: bạn có thể viết lại hàm valuation động trong Fundamental nếu cần.
        df['score_val'] = fund_result['score_val'] 
        
        # 3. Tổng hợp
        df['score_total'] = (
            df['score_tech'] * 0.25 + 
            df['score_flow'] * 0.35 + 
            df['score_fund'] * 0.20 + 
            df['score_val'] * 0.15
        ) * (df['score_risk'] / 10.0)
        
        df['score_total'] = df['score_total'].clip(0, 10)
        return df
    
    def analyze_health(self, symbol, benchmark_symbol="VNINDEX"):
        """Hàm phân tích tổng hợp trả về KQ cho App"""
        
        # 1. Lấy dữ liệu
        df = self.get_full_data(symbol, limit=400)
        fin = self.get_financials(symbol) or {}
        
        # 1. Lấy dữ liệu thị trường để so sánh
        market_df = self.market_engine.get_index_series(benchmark_symbol, limit=400)

        if df.empty or len(df) < 60:
            return {
                "error": "Không đủ dữ liệu", "symbol": symbol, "close": 0, "total_score": 0,
                "recommendation": "NO DATA", "details": {}, "scores": {}, 
                "financials": {}, "trade_plan": {}
            }

        # 2. Tính toán điểm & Chỉ báo
        df_scored = self.calculate_historical_scores(df, fin)
        last_row = df_scored.iloc[-1]
        dna_report = self.flow_analyzer.get_dna_report(df) # Lấy báo cáo chi tiết
        
        # 3. Lấy Tín hiệu text từ các Engines
        tech_out = self.tech_engine.get_signals(last_row) # Return {signals, warnings}
        flow_out = self.flow_analyzer.get_signals_v2025(df_scored) # Return {signals, warnings, net_val...}
        fund_out = self.fund_analyzer.analyze(df_scored, fin) # Return {signals, warnings, metrics...}
        rs_rating = self.market_engine.calculate_rs_rating(df_scored, market_df)

        # Nếu RS âm nặng -> Yếu hơn thị trường -> Cảnh báo
        if rs_rating < -10:
            tech_out['warnings'].append(f"🐢 Cổ phiếu yếu hơn {benchmark_symbol} (-{abs(rs_rating)}%)")
        elif rs_rating > 10:
            tech_out['signals'].append(f"🐎 Khỏe hơn thị trường chung (+{rs_rating}%)")

        # Tổng hợp Warning từ 3 nguồn
        all_warnings = tech_out['warnings'] + flow_out['warnings'] + fund_out['warnings']
        # Tổng hợp Tích cực
        # Lưu ý: 'details' trong return dict bên dưới dùng để hiển thị text list trên App
        
        # 4. Tạo Object Health Tạm thời để đưa vào Recommender
        # Object này chứa đủ thông tin để Recommender ra quyết định
        health_snapshot = {
            'scores': {
                'technical': last_row['score_tech'],
                'flow': last_row['score_flow'],
                'fundamental': fund_out['score_fund'],
                'valuation': fund_out['score_val'],
                'risk': last_row['score_risk']
            },
            'fund_metrics': fund_out['metrics'],
            'business_type': fund_out['type']
        }
        
        # 5. GENERATE TRADE PLAN (KHUYẾN NGHỊ GIAO DỊCH) - NEW
        trade_plan = self.recommender.generate_plan(df_scored, health_snapshot)

        # 6. Recommendation Label (One word summary)
        # Logic đơn giản cho label chính
        total_score = last_row['score_total']
        main_action = "QUAN SÁT"
        if trade_plan.get('trading', {}).get('action', '').startswith("MUA"):
            main_action = "MUA NGẮN HẠN"
        elif trade_plan.get('investing', {}).get('action', '').startswith("MUA TÍCH SẢN"):
            main_action = "MUA TÍCH SẢN"
        elif total_score < 3 or trade_plan.get('trading', {}).get('action', '').startswith("BÁN"):
            main_action = "CẢNH BÁO BÁN"

        # 7. Final Return Dictionary Structure (Compatible with App.py)
        return {
            "symbol": symbol,
            "close": last_row['close'],
            "change_pct": (last_row['close'] - df_scored.iloc[-2]['close'])/df_scored.iloc[-2]['close']*100,
            
            "total_score": round(total_score, 1),
            "recommendation": main_action,
            "flow_dna": dna_report, # TRẢ VỀ DỮ LIỆU MỚI CHO APP
            
            "scores": {
                "technical": round(last_row['score_tech'], 1),
                "flow": round(last_row['score_flow'], 1),
                "fundamental": round(fund_out['score_fund'], 1),
                "valuation": round(fund_out['score_val'], 1),
                "risk": round(last_row['score_risk'], 1)
            },
            
            "details": {
                "technical": tech_out['signals'],
                "flow": flow_out['signals'],
                "fundamental": fund_out['signals'],
                "valuation": [], # Valuation đã gộp vào fundamental signals hoặc tách ra tùy nhu cầu
                "warning": all_warnings
            },
            
            # Data nâng cao cho Chart & Tab
            "financials": fin,
            "trade_plan": trade_plan,
            "business_type": fund_out['type'],
            "fund_metrics": fund_out['metrics'],
            
            "smart_net_billion_10d": round(flow_out['smart_net_val'], 1),
            "smart_participation": round(flow_out['smart_ratio'], 1),
            
            "full_df": df_scored, # Để app vẽ chart tech
            "history_scores": df_scored[['time','close','score_tech','score_flow','score_total', 'score_fund', 'score_val']].tail(360).to_dict(orient='records'),
            "rs_rating": rs_rating, # <--- TRƯỜNG MỚI
            "benchmark_symbol": benchmark_symbol,
        }
    
    def get_flow_momentum_ranking(self, top_n=50):
        """
        Trả về bảng xếp hạng Flow Momentum hôm nay (toàn thị trường)
        Dùng để hiển thị trong tab Market và gửi Discord
        """
        symbols = self.get_all_symbols()
        ranking = []

        for symbol in symbols:
            try:
                df = self.get_full_data(symbol, limit=60)
                if len(df) < 30:
                    continue

                # Tính Flow Score và Momentum
                scores = self.flow_analyzer.calculate_flow_score_vn2025(df)
                df['flow_score'] = scores
                df['flow_change'] = df['flow_score'].diff()

                latest = df.iloc[-1]
                prev = df.iloc[-2]

                score = latest['flow_score']
                change = latest['flow_change']

                # Chỉ lấy những mã có momentum tốt hoặc flow cao
                if change >= 0.5 or score >= 7.5:
                    ranking.append({
                        'symbol': symbol,
                        'close': latest['close'],
                        'change_pct': (latest['close'] / prev['close'] - 1) * 100,
                        'flow_score': round(score, 2),
                        'flow_change': round(change, 2),
                        'volume': latest['volume'],
                        'smart_net_today': (latest['foreign_net_val'] + latest['prop_net_val'] + latest['local_inst_net_val']) / 1e9,
                        'scenario': self._classify_scenario(score, change)
                    })
            except:
                continue

        # Sắp xếp theo Momentum → Flow Score → Volume
        ranking_df = pd.DataFrame(ranking)
        if ranking_df.empty:
            return pd.DataFrame()

        ranking_df = ranking_df.sort_values(
            by=['flow_change', 'flow_score', 'volume'],
            ascending=[False, False, False]
        ).head(top_n).reset_index(drop=True)

        ranking_df['rank'] = range(1, len(ranking_df) + 1)
        return ranking_df[['rank', 'symbol', 'close', 'change_pct', 'flow_score', 'flow_change', 'smart_net_today', 'scenario']]

    def _classify_scenario(self, score, change):
        """Phân loại scenario như trong backtest"""
        if change >= 1.8: return "07. Momentum cực đại"
        if change >= 1.2: return "08. Momentum rất mạnh"
        if change >= 0.8: return "09. Momentum mạnh"
        if 8.0 <= score < 8.5 and change >= 0.8: return "04. 8.0–8.4 + Tăng cực mạnh"
        if score >= 8.5 and change >= 0: return "02. ≥8.5 + Momentum dương"
        if score >= 8.5: return "01. ≥8.5 (Tổng quan)"
        return "Khác"