import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Setup đường dẫn
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from config import DATABASE_URL, FIIN_USER, FIIN_PASS

try:
    from FiinQuantX import FiinSession
except ImportError:
    class FiinSession: pass

class OnDemandLoader:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        try:
            self.client = FiinSession(username=FIIN_USER, password=FIIN_PASS).login()
            self.is_connected = True
        except:
            self.is_connected = False

    def _upsert_data(self, df, table_name, pk_cols):
        if df is None or df.empty: return
        try:
            with self.engine.begin() as conn:
                temp_table = f"temp_{table_name}_{datetime.now().strftime('%M%S%f')}"
                df.to_sql(temp_table, conn, index=False, if_exists='replace')
                
                # Ép kiểu số
                if table_name == 'fact_financial_ratios':
                    cols = ['roe', 'roa', 'eps', 'book_value_per_share', 'current_ratio', 'debt_to_equity', 'nim', 'ldr', 'bad_debt_ratio',
                            'loan_loss_reserves_to_npls', 'loans_growth_yoy', 'deposits_growth_yoy', 'interest_income_growth_yoy',
                            'ebit_margin', 'roic', 'revenue_growth_yoy', 'ebt_growth_yoy']
                    for c in cols:
                        if c in df.columns: conn.execute(text(f"ALTER TABLE {temp_table} ALTER COLUMN {c} TYPE NUMERIC USING {c}::numeric"))
                
                where_str = " AND ".join([f"{table_name}.{c} = {temp_table}.{c}" for c in pk_cols])
                conn.execute(text(f"DELETE FROM {table_name} USING {temp_table} WHERE {where_str}"))
                
                cols = ",".join(df.columns)
                conn.execute(text(f"INSERT INTO {table_name} ({cols}) SELECT {cols} FROM {temp_table}"))
                conn.execute(text(f"DROP TABLE {temp_table}"))
        except Exception as e:
            print(f"Upsert Error {table_name}: {e}")

    def check_and_update_ticker(self, symbol, years_back=5):
            symbol = symbol.upper().strip()
            if not self.is_connected: return False, "Lỗi kết nối."

            # 1. XÁC ĐỊNH KHOẢNG THỜI GIAN CẦN CẬP NHẬT
            try:
                with self.engine.connect() as conn:
                    last_p = conn.execute(text(f"SELECT MAX(time) FROM fact_daily_bars WHERE symbol = '{symbol}'")).fetchone()[0]
                    last_f = conn.execute(text(f"SELECT MAX(time) FROM fact_investor_flows_daily WHERE symbol = '{symbol}'")).fetchone()[0]
            except: last_p = None; last_f = None

            today = datetime.now().date()
            start_req = (datetime.now() - timedelta(days=365 * years_back)).date()
            fetch_from = start_req.strftime("%Y-%m-%d")
            
            d_p = pd.to_datetime(last_p).date() if last_p else None
            d_f = pd.to_datetime(last_f).date() if last_f else None
            
            # Lấy từ ngày cũ nhất bị thiếu
            if d_p and d_f:
                min_date = min(d_p, d_f)
                if min_date < today:
                    fetch_from = (min_date + timedelta(days=1)).strftime("%Y-%m-%d")
                elif min_date == today:
                    # Nếu đã có dữ liệu hôm nay, nhưng đang trong giờ giao dịch thì có thể cập nhật lại
                    # (Logic đơn giản: Nếu đã cập nhật hôm nay rồi thì báo xong)
                    return True, f"{symbol} dữ liệu đã mới nhất ({today})."

            # Biến tạm để truyền MarketCap từ phần Price sang phần Valuation
            df_market_cap_temp = pd.DataFrame()

            try:
                # A. BASIC INFO (Cập nhật thông tin cơ bản)
                if d_p is None:
                    try:
                        b_df = self.client.BasicInfor(tickers=[symbol]).get()
                        if not b_df.empty:
                            if 'sector' not in b_df.columns: b_df['sector'] = None
                            b_db = b_df.rename(columns={"ticker": "symbol", "companyName": "company_name", "exchange": "exchange", "sector": "sector"})
                            self._upsert_data(b_db[['symbol', 'company_name', 'exchange', 'sector']], "dim_stocks", ['symbol'])
                    except: pass

                # B. GIÁ, OVERVIEW (TRADING VALUE & VWAP)
                to_date = datetime.now().strftime("%Y-%m-%d")
                
                try:
                    # 1. Fetch OHLCV (Trading Data)
                    event = self.client.Fetch_Trading_Data(realtime=False, tickers=[symbol], 
                                                        fields=['open', 'high', 'low', 'close', 'volume', 'bu', 'sd'], 
                                                        adjusted=True, by='1d', from_date=fetch_from)
                    df_p = event.get_data()
                    
                    # Fetch Raw Close
                    try:
                        event_raw = self.client.Fetch_Trading_Data(realtime=False, tickers=[symbol], fields=['close'], adjusted=False, by='1d', from_date=fetch_from)
                        df_raw = event_raw.get_data()
                    except: df_raw = None

                    # 2. Fetch Overview (Để lấy totalMatchValue và marketCap chính xác)
                    try:
                        df_overview = self.client.PriceStatistics().get_overview(
                            tickers=[symbol], time_filter="Daily", from_date=fetch_from, to_date=to_date
                        )
                    except: df_overview = None

                    if df_p is not None and not df_p.empty:
                        # Chuẩn hóa cột thời gian df_p
                        time_col_p = next((c for c in df_p.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
                        if time_col_p: 
                            df_p.rename(columns={time_col_p: 'time'}, inplace=True)
                            df_p['time'] = pd.to_datetime(df_p['time'])

                        # Merge Raw Close
                        if df_raw is not None and not df_raw.empty:
                            time_col_r = next((c for c in df_raw.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
                            if time_col_r: 
                                df_raw.rename(columns={time_col_r: 'time'}, inplace=True)
                                df_raw['time'] = pd.to_datetime(df_raw['time'])
                                df_p = pd.merge(df_p, df_raw[['time', 'close']], on='time', how='left', suffixes=('', '_raw'))
                                df_p.rename(columns={'close_raw': 'close_raw'}, inplace=True)
                        else:
                            df_p['close_raw'] = df_p['close']

                        # Merge Overview (Trading Value & Market Cap)
                        if df_overview is not None and not df_overview.empty:
                            time_col_ov = next((c for c in df_overview.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
                            if time_col_ov:
                                df_overview.rename(columns={time_col_ov: 'time'}, inplace=True)
                                df_overview['time'] = pd.to_datetime(df_overview['time'])
                                
                                # Merge vào df_p
                                df_p = pd.merge(df_p, df_overview[['time', 'totalMatchValue', 'marketCap']], on='time', how='left')
                                
                                # Lưu MarketCap ra biến tạm để dùng cho phần Valuation bên dưới
                                df_market_cap_temp = df_p[['time', 'marketCap']].copy()
                                df_market_cap_temp.rename(columns={'marketCap': 'market_cap'}, inplace=True)
                                
                                # Gán Trading Value chính xác
                                df_p['trading_value'] = df_p['totalMatchValue']
                        else:
                            df_p['trading_value'] = np.nan

                        # === LOGIC TÍNH TOÁN QUAN TRỌNG ===
                        
                        # 1. Fill Trading Value (Fallback về Typical Price nếu API lỗi)
                        # Typical Price = (H+L+C)/3
                        typical_price = (df_p['high'] + df_p['low'] + df_p['close']) / 3
                        
                        # Nếu trading_value NaN hoặc 0 thì dùng công thức ước lượng
                        df_p['trading_value'] = df_p['trading_value'].fillna(0)
                        mask_missing = df_p['trading_value'] == 0
                        if mask_missing.any():
                            df_p.loc[mask_missing, 'trading_value'] = typical_price.loc[mask_missing] * df_p.loc[mask_missing, 'volume']

                        # 2. Tính VWAP (Volume Weighted Average Price) chuẩn xác
                        # VWAP = RollingSum(TradingValue) / RollingSum(Volume)
                        window = 14
                        roll_val = df_p['trading_value'].rolling(window=window, min_periods=1).sum()
                        roll_vol = df_p['volume'].rolling(window=window, min_periods=1).sum()
                        
                        df_p['vwap'] = roll_val / roll_vol.replace(0, np.nan)
                        df_p['vwap'] = df_p['vwap'].fillna(df_p['close']) # Fallback

                        # 3. Chuẩn bị dữ liệu để Upsert
                        df_p.rename(columns={"ticker": "symbol", "bu": "buy_active_vol", "sd": "sell_active_vol"}, inplace=True)
                        df_p['symbol'] = symbol
                        
                        c_p = ['time', 'symbol', 'open', 'high', 'low', 'close', 'close_raw', 'volume', 
                            'trading_value', 'vwap', 'buy_active_vol', 'sell_active_vol']
                        
                        # Chỉ lấy các cột có trong DataFrame
                        valid_cols = [c for c in c_p if c in df_p.columns]
                        self._upsert_data(df_p[valid_cols], "fact_daily_bars", ['time', 'symbol'])

                except Exception as e: print(f"Price/Overview err: {e}")

                # C. DÒNG TIỀN (INVESTOR FLOWS)
                try:
                    df_f = self.client.PriceStatistics().get_ceilingfloor(tickers=[symbol], from_date=fetch_from, to_date=to_date)
                    if df_f is not None and not df_f.empty:
                        df_f.fillna(0, inplace=True)
                        time_col = next((c for c in df_f.columns if c.lower() in ['timestamp', 'tradingdate', 'date', 'time']), None)
                        
                        if time_col:
                            df_f.rename(columns={time_col: 'time'}, inplace=True)
                            col_map = {"code": "symbol", "shareIssue": "share_issue"}
                            df_f.rename(columns=col_map, inplace=True)
                            
                            # Cộng gộp các cột
                            df_f['foreign_buy_val'] = df_f.get('foreignIndividualBuyTradingMatchValue', 0) + df_f.get('foreignInstitutionalBuyTradingMatchValue', 0)
                            df_f['foreign_sell_val'] = df_f.get('foreignIndividualSellTradingMatchValue', 0) + df_f.get('foreignInstitutionalSellTradingMatchValue', 0)
                            df_f['foreign_buy_vol'] = df_f.get('foreignIndividualBuyTradingMatchVolume', 0) + df_f.get('foreignInstitutionalBuyTradingMatchVolume', 0)
                            df_f['foreign_sell_vol'] = df_f.get('foreignIndividualSellTradingMatchVolume', 0) + df_f.get('foreignInstitutionalSellTradingMatchVolume', 0)
                            
                            df_f['prop_buy_val'] = df_f.get('proprietaryTotalMatchBuyTradeValue', 0)
                            df_f['prop_sell_val'] = df_f.get('proprietaryTotalMatchSellTradeValue', 0)
                            df_f['prop_buy_vol'] = df_f.get('proprietaryTotalMatchBuyTradeVolume', 0)
                            df_f['prop_sell_vol'] = df_f.get('proprietaryTotalMatchSellTradeVolume', 0)

                            df_f['local_ind_buy_val'] = df_f.get('localIndividualBuyMatchValue', 0)
                            df_f['local_ind_sell_val'] = df_f.get('localIndividualSellMatchValue', 0)
                            df_f['local_ind_buy_vol'] = df_f.get('localIndividualBuyMatchVolume', 0)
                            df_f['local_ind_sell_vol'] = df_f.get('localIndividualSellMatchVolume', 0)
                            
                            df_f['local_inst_buy_val'] = df_f.get('localInstitutionalBuyMatchValue', 0)
                            df_f['local_inst_sell_val'] = df_f.get('localInstitutionalSellMatchValue', 0)
                            df_f['local_inst_buy_vol'] = df_f.get('localInstitutionalBuyMatchVolume', 0)
                            df_f['local_inst_sell_vol'] = df_f.get('localInstitutionalSellMatchVolume', 0)

                            df_f['time'] = pd.to_datetime(df_f['time'])
                            
                            # Tính Net
                            for g in ['foreign', 'prop', 'local_ind', 'local_inst']:
                                df_f[f'{g}_net_val'] = df_f[f'{g}_buy_val'] - df_f[f'{g}_sell_val']
                                df_f[f'{g}_net_vol'] = df_f[f'{g}_buy_vol'] - df_f[f'{g}_sell_vol']
                            
                            cols_f = ['time', 'symbol', 'share_issue']
                            for g in ['foreign', 'prop', 'local_ind', 'local_inst']:
                                cols_f.extend([f'{g}_buy_val', f'{g}_sell_val', f'{g}_net_val', f'{g}_buy_vol', f'{g}_sell_vol', f'{g}_net_vol'])

                            valid_cols = [c for c in cols_f if c in df_f.columns]
                            self._upsert_data(df_f[valid_cols], "fact_investor_flows_daily", ['time', 'symbol'])
                except Exception as e: print(f"Flow err: {e}")

                # D. BCTC & ĐỊNH GIÁ
                if True:
                    u_from = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
                    
                    # 1. Valuation (PE, PB) + Merge MarketCap
                    try:
                        df_v = self.client.MarketDepth().get_stock_valuation(tickers=[symbol], from_date=u_from, to_date=to_date)
                        if df_v is not None and not df_v.empty:
                            df_v = df_v.rename(columns={"ticker": "symbol", "timestamp": "time", "pe": "pe", "pb": "pb"})
                            df_v['time'] = pd.to_datetime(df_v['time'])
                            df_v['pe'] = pd.to_numeric(df_v['pe'], errors='coerce')
                            df_v['pb'] = pd.to_numeric(df_v['pb'], errors='coerce')
                            
                            # Merge MarketCap từ bước (B) nếu có
                            if not df_market_cap_temp.empty:
                                # Merge dựa trên time
                                df_v = pd.merge(df_v, df_market_cap_temp, on='time', how='left')
                                # Những ngày không có MarketCap mới thì giữ nguyên (hoặc NaN)

                            cols_v = ['time', 'symbol', 'pe', 'pb']
                            if 'market_cap' in df_v.columns: 
                                cols_v.append('market_cap')
                                # Ép kiểu số cho market_cap
                                df_v['market_cap'] = pd.to_numeric(df_v['market_cap'], errors='coerce')
                            
                            self._upsert_data(df_v[cols_v], "fact_valuation_daily", ['time', 'symbol'])
                    except Exception as e: print(f"Valuation err: {e}")

                    # 2. Financial Ratios (Giữ nguyên)
                    try:
                        yrs = [datetime.now().year, datetime.now().year - 1]
                        raw = self.client.FundamentalAnalysis().get_ratios(tickers=[symbol], years=yrs, quarters=[1, 2, 3, 4], type="consolidated")
                        recs = []
                        if isinstance(raw, list):
                            for item in raw:
                                if item.get('ticker') != symbol: continue
                                r = item.get('ratios', {})
                                def g(c, k): return r.get(c, {}).get(k)
                                rec = {
                                    "symbol": symbol, "year": item.get('year'), "quarter": item.get('quarter'),
                                    "roe": g('ProfitabilityRatio', 'ROE') or g('ProfitabilityComponent', 'ROE'),
                                    "roa": g('ProfitabilityRatio', 'ROA') or g('ProfitabilityComponent', 'ROA'),
                                    "eps": g('ValuationRatios', 'BasicEPS'),
                                    "book_value_per_share": g('ValuationRatios', 'BookValuePerShare'),
                                    "current_ratio": g('SolvencyRatio', 'CurrentRatio'),
                                    "debt_to_equity": g('SolvencyRatio', 'LiabilitiesToEquityRatio'),
                                    "nim": g('ProfitabilityComponent', 'NIM'),
                                    "ldr": g('LiquidityAndAssetsComponent', 'LDRPercentage'),
                                    "bad_debt_ratio": g('AssetQualityComponent', 'ProblemLoansAndLeasesCalculatedAsPercentageOfGrossLoans'),
                                    "loan_loss_reserves_to_npls": g('AssetQualityComponent', 'LoanLossReservesToNPLs'),
                                    "loans_growth_yoy": g('GrowthComponent', 'AverageLoansGrowthPercentageYoY'),
                                    "deposits_growth_yoy": g('GrowthComponent', 'AverageDepositGrowthPercentageYoY'),
                                    "interest_income_growth_yoy": g('GrowthComponent', 'InterestincomeGrowthPercentageYoY'),
                                    "ebit_margin": g('ProfitabilityRatio', 'EBITMargin'),
                                    "roic": g('ProfitabilityRatio', 'ROIC'),
                                    "revenue_growth_yoy": g('Growth', 'NetRevenueGrowthYoY'),
                                    "ebt_growth_yoy": g('Growth', 'EBTgrowthYoY')
                                }
                                recs.append(rec)
                        if recs:
                            df_fin = pd.DataFrame(recs)
                            for c in ['roe', 'roa', 'eps', 'book_value_per_share', 'current_ratio', 'debt_to_equity', 'nim', 'ldr', 'bad_debt_ratio',
                                    'loan_loss_reserves_to_npls', 'loans_growth_yoy', 'deposits_growth_yoy', 'interest_income_growth_yoy',
                                    'ebit_margin', 'roic', 'revenue_growth_yoy', 'ebt_growth_yoy']:
                                if c in df_fin.columns: df_fin[c] = pd.to_numeric(df_fin[c], errors='coerce')
                            self._upsert_data(df_fin, "fact_financial_ratios", ['symbol', 'year', 'quarter'])
                    except: pass

                return True, f"Cập nhật thành công {symbol}."
            except Exception as e:
                return False, f"Lỗi: {str(e)}"