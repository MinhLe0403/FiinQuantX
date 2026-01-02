import pandas as pd
from datetime import datetime
from .base import BaseETL

class FundamentalLoader(BaseETL):
    # --- 1. VALUATION (Định giá PE/PB) ---
    def sync_valuation(self, symbol, start_date, end_date):
        self.sync_valuation_batch([symbol], start_date, end_date)

    def sync_valuation_batch(self, tickers_list, start_date, end_date):
        if not tickers_list: return
        
        # API Valuation
        task = lambda: self.client.MarketDepth().get_stock_valuation(
            tickers=tickers_list, from_date=start_date, to_date=end_date
        )
        df = self.safe_api_call(task)
        
        if df is not None and not df.empty:
            df.rename(columns={"ticker": "symbol", "timestamp": "time", "pe": "pe", "pb": "pb"}, inplace=True)
            df['time'] = pd.to_datetime(df['time'])
            
            # --- [FIX QUAN TRỌNG TẠI ĐÂY] ---
            # Ép kiểu dữ liệu sang số (Numeric). 
            # errors='coerce' sẽ biến lỗi (text, empty string) thành NaN
            df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
            df['pb'] = pd.to_numeric(df['pb'], errors='coerce')
            # --------------------------------
            
            cols = ['time', 'symbol', 'pe', 'pb']
            
            # Xử lý Market Cap
            if 'marketCap' in df.columns:
                df['market_cap'] = pd.to_numeric(df['marketCap'], errors='coerce')
                cols.append('market_cap')
            elif 'market_cap' in df.columns: # Trường hợp tên cột đã rename
                 df['market_cap'] = pd.to_numeric(df['market_cap'], errors='coerce')
                 cols.append('market_cap')
            
            # Upsert vào DB
            # Chỉ lấy các dòng có ít nhất PE hoặc PB hoặc MarketCap (tránh lưu dòng rỗng)
            # df_final = df.dropna(subset=['pe', 'pb', 'market_cap'], how='all') 
            # (Tùy chọn: có thể không cần drop nếu muốn giữ history)
            
            self.upsert_data(df[cols], "fact_valuation_daily", ['time', 'symbol'])
        
        self.sleep()

    # --- 2. FINANCIALS (Báo cáo tài chính) ---
    
    def sync_financials(self, symbol):
        """Lấy BCTC cho 1 mã"""
        self.sync_financials_batch([symbol])

    def sync_financials_batch(self, tickers_list):
        """
        Lấy BCTC cho một danh sách mã.
        Logic: Lấy dữ liệu 2 năm gần nhất.
        """
        if not tickers_list: return

        current_year = datetime.now().year
        years = [current_year, current_year - 1]
        
        # API get_ratios hỗ trợ list tickers
        task = lambda: self.client.FundamentalAnalysis().get_ratios(
            tickers=tickers_list, years=years, quarters=[1, 2, 3, 4], type="consolidated"
        )
        raw_data = self.safe_api_call(task)
        
        if raw_data:
            # Khi gọi nhiều mã, API thường trả về Dict {'SYM': [list data], ...}
            # Cần xử lý để đưa vào hàm process chung
            self._process_financials(raw_data)
        
        self.sleep()

    def _process_financials(self, raw_data, specific_symbol=None):
        """
        Xử lý dữ liệu thô từ API (List hoặc Dict) và lưu vào DB.
        """
        all_records = []

        # 1. Chuẩn hóa dữ liệu đầu vào thành 1 list phẳng
        if isinstance(raw_data, dict):
            # Trường hợp API trả về Dict: {'FPT': [...], 'VNM': [...]}
            for ticker, items in raw_data.items():
                if items and isinstance(items, list):
                    all_records.extend(items)
        elif isinstance(raw_data, list):
            # Trường hợp API trả về List (thường khi gọi 1 mã)
            all_records = raw_data
        
        if not all_records: return

        # 2. Parse dữ liệu
        parsed_recs = []
        for item in all_records:
            ticker = item.get('ticker')
            
            # Nếu chỉ định specific_symbol thì lọc, không thì lấy hết
            if specific_symbol and ticker != specific_symbol:
                continue
            
            if not ticker: continue

            # Helper lấy dữ liệu an toàn
            r = item.get('ratios', {})
            def g(cat, key): 
                # Thử tìm trong category, nếu không có trả về None
                return r.get(cat, {}).get(key)

            # Mapping dữ liệu
            rec = {
                "symbol": ticker,
                "year": item.get('year'),
                "quarter": item.get('quarter'),
                
                # Hiệu quả hoạt động
                "roe": g('ProfitabilityRatio', 'ROE') or g('ProfitabilityComponent', 'ROE'),
                "roa": g('ProfitabilityRatio', 'ROA') or g('ProfitabilityComponent', 'ROA'),
                "roic": g('ProfitabilityRatio', 'ROIC'),
                "ebit_margin": g('ProfitabilityRatio', 'EBITMargin'),
                
                # Định giá cơ bản
                "eps": g('ValuationRatios', 'BasicEPS'),
                "book_value_per_share": g('ValuationRatios', 'BookValuePerShare'),
                
                # Sức khỏe tài chính (Doanh nghiệp)
                "current_ratio": g('SolvencyRatio', 'CurrentRatio'),
                "debt_to_equity": g('SolvencyRatio', 'LiabilitiesToEquityRatio'),
                
                # Ngân hàng (Bank Specific)
                "nim": g('ProfitabilityComponent', 'NIM'),
                "ldr": g('LiquidityAndAssetsComponent', 'LDRPercentage'),
                "bad_debt_ratio": g('AssetQualityComponent', 'ProblemLoansAndLeasesCalculatedAsPercentageOfGrossLoans'),
                "loan_loss_reserves_to_npls": g('AssetQualityComponent', 'LoanLossReservesToNPLs'),
                
                # Tăng trưởng
                "loans_growth_yoy": g('GrowthComponent', 'AverageLoansGrowthPercentageYoY'),
                "deposits_growth_yoy": g('GrowthComponent', 'AverageDepositGrowthPercentageYoY'),
                "interest_income_growth_yoy": g('GrowthComponent', 'InterestincomeGrowthPercentageYoY'),
                "revenue_growth_yoy": g('Growth', 'NetRevenueGrowthYoY'),
                "ebt_growth_yoy": g('Growth', 'EBTgrowthYoY')
            }
            parsed_recs.append(rec)
        
        # 3. Lưu vào DB
        if parsed_recs:
            df = pd.DataFrame(parsed_recs)
            # Upsert vào bảng fact_financial_ratios với PK là (symbol, year, quarter)
            self.upsert_data(df, "fact_financial_ratios", ['symbol', 'year', 'quarter'])