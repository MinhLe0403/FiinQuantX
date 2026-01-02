# analysis/signal_engine/scanner.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional
from analysis.core import StockAnalyzer
from analysis.signal_engine.backtester import backtest_signal_history
from analysis.signal_engine.discord_poster import post_to_discord
from analysis.signal_engine.config import SignalConfig

cfg = SignalConfig()

# ----------------------------------------------------------------------
# Helper: Kiểm tra tín hiệu trên phiên hiện tại (realtime hoặc EOD)
# ----------------------------------------------------------------------
def _check_signal_today(
    row_today: pd.Series,
    row_yesterday: pd.Series,
    health: dict,
    use_today_flow: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Trả về (triggered: bool, signal_type: str hoặc None)
    use_today_flow = True → dùng dòng tiền hôm nay (sau 18h)
                    False → dùng dòng tiền hôm qua (realtime 15h30-16h)
    """
    flow_row = row_today if use_today_flow else row_yesterday

    # === LỌC CHUNG ===
    if (row_today['volume'] < cfg.MIN_AVG_VOLUME * 0.9 or
        row_today['close'] < cfg.MIN_PRICE or
        health.get('rs_rating', 0) < cfg.RS_RATING_MIN):
        return False, None

    # Smart Money Net 12 ngày gần nhất (tỷ VND)
    smart_net_12d = (
        flow_row.get('foreign_net_val', 0) +
        flow_row.get('prop_net_val', 0) +
        flow_row.get('local_inst_net_val', 0)
    ) / 1e9  # chuyển sang tỷ

    # ------------------------------------------------------------------
    # NHÓM A: BREAKOUT + VOLUME SPIKE + SMART MONEY + CẢ FOREIGN & LOCAL INST CÙNG MUA
    # ------------------------------------------------------------------
    if (cfg.A_FOREIGN_LOCAL_INST_BOTH_BUY and
        flow_row.get('foreign_net_val', 0) > 0 and
        flow_row.get('local_inst_net_val', 0) > 0 and
        row_today['close'] > row_today['EMA_20'] and
        row_today.get('VOL_SPIKE', False) and
        smart_net_12d > cfg.A_SMART_NET_12D_BILL and
        row_today.get('score_tech', 0) >= cfg.A_TECH_SCORE_MIN):
        return True, "A_BREAKOUT"

    # ------------------------------------------------------------------
    # NHÓM B: PULLBACK TRONG UPTREND
    # ------------------------------------------------------------------
    price_dist = abs((row_today['close'] - row_today['EMA_20']) / row_today['close'])
    if (row_today['EMA_20'] > row_today['EMA_50'] and
        row_today.get('ADX', 0) > cfg.B_ADX_MIN and
        price_dist <= cfg.B_PRICE_DISTANCE_EMA20 and
        row_today.get('score_flow', 0) >= cfg.B_FLOW_SCORE_MIN):
        return True, "B_PULLBACK"

    # ------------------------------------------------------------------
    # NHÓM C: ACCUMULATION PHASE (giá đi ngang + Smart Money gom dài hạn)
    # ------------------------------------------------------------------
    df_hist = health.get('full_df')
    if df_hist is not None and len(df_hist) >= 120:
        recent60 = df_hist.tail(60)
        volatility = (recent60['high'].max() - recent60['low'].min()) / recent60['low'].min()
        smart60_net = (
            recent60['foreign_net_val'].sum() +
            recent60['prop_net_val'].sum() +
            recent60['local_inst_net_val'].sum()
        )
        if (volatility < cfg.C_ACCUMULATION_VOLATILITY_MAX and
            smart60_net > 0 and
            row_today.get('score_val', 0) >= cfg.C_VALUATION_SCORE_MIN):
            return True, "C_ACCUMULATION"

    return False, None


# ----------------------------------------------------------------------
# Tính thống kê từ lịch sử tín hiệu
# ----------------------------------------------------------------------
def _calculate_stats(history_df: pd.DataFrame) -> dict:
    stats = {}
    horizons = cfg.HORIZONS

    # Chỉ lấy các tín hiệu cùng loại (A/B/C) để thống kê chính xác
    for sig_type in history_df['signal_type'].unique():
        sub = history_df[history_df['signal_type'] == sig_type]

        for h in horizons:
            rets = sub[h].dropna()
            if len(rets) == 0:
                continue

            mean_ret = rets.mean()
            std_ret = rets.std()
            skew = rets.skew()
            winrate = (rets > 0).mean()
            sharpe = mean_ret / std_ret * np.sqrt(252 / h) if std_ret > 0 else 0

            stats[f'{sig_type}_return_{h}d'] = mean_ret
            stats[f'{sig_type}_std_{h}d'] = std_ret
            stats[f'{sig_type}_skew_{h}d'] = skew
            stats[f'{sig_type}_sharpe_{h}d'] = sharpe
            stats[f'{sig_type}_winrate_{h}d'] = winrate
            stats[f'{sig_type}_trades'] = len(rets)

    # Tìm horizon tốt nhất (Sharpe × Skew cao nhất → đuôi phải + ổn định)
    best_key = None
    best_score = -999
    for h in horizons:
        key = f'return_{h}d'
        if key not in history_df.columns:
            continue
        mean_ret = history_df[h].mean()
        std_ret = history_df[h].std(ddof=0) or 1
        skew_val = history_df[h].skew()
        composite = (mean_ret * skew_val) / std_ret
        if composite > best_score:
            best_score = composite
            best_key = h

    stats['best_horizon'] = best_key
    stats['best_composite'] = best_score
    stats['total_historical_trades'] = len(history_df)

    return stats


# ----------------------------------------------------------------------
# QUÉT TOÀN THỊ TRƯỜNG (chính thức)
# ----------------------------------------------------------------------
def run_daily_scan(use_today_flow: bool = True, top_n: int = 7):
    """
    use_today_flow = True  → chạy sau 18h (dùng dòng tiền hôm nay)
    use_today_flow = False → chạy realtime 15h30-16h (dùng dòng tiền hôm qua)
    """
    sa = StockAnalyzer()
    symbols = sa.get_all_symbols()
    results = []

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
          f"Bắt đầu quét {len(symbols)} cổ phiếu | use_today_flow = {use_today_flow}")

    for idx, symbol in enumerate(symbols, 1):
        if idx % 50 == 0:
            print(f"   Đã xử lý {idx}/{len(symbols)}...")

        try:
            health = sa.analyze_health(symbol)
            if health.get("error"):
                continue

            df = health['full_df']
            if len(df) < 100:
                continue

            today_row = df.iloc[-1]
            yesterday_row = df.iloc[-2] if len(df) >= 2 else today_row

            triggered, sig_type = _check_signal_today(
                today_row, yesterday_row, health, use_today_flow
            )
            if not triggered:
                continue

            # Backtest lịch sử cho đúng loại tín hiệu
            history_df = backtest_signal_history(symbol, sa)
            if history_df.empty or len(history_df) < 8:  # ít nhất 8 lần trong lịch sử
                continue

            # Lọc chỉ lấy cùng loại tín hiệu
            hist_same_type = history_df[history_df['signal_type'] == sig_type]
            if len(hist_same_type) < 5:
                continue

            stats = _calculate_stats(hist_same_type)

            result = {
                "symbol": symbol,
                "signal_type": sig_type,
                "current_price": today_row['close'],
                "total_score": health.get('total_score', 0),
                "score_tech": today_row.get('score_tech', 0),
                "score_flow": today_row.get('score_flow', 0),
                "score_val": today_row.get('score_val', 0),
                "historical_trades": len(hist_same_type),
                "best_horizon": stats['best_horizon'],
                "best_return": hist_same_type[stats['best_horizon']].mean(),
                "best_sharpe": stats.get(f'{sig_type}_sharpe_{stats["best_horizon"]}d', 0),
                "best_skew": stats.get(f'{sig_type}_skew_{stats["best_horizon"]}d', 0),
                "composite_score": stats['best_composite'],
                "health": health,
            }
            results.append(result)

        except Exception as e:
            print(f"   Lỗi {symbol}: {e}")
            continue

    if not results:
        print("Không tìm thấy tín hiệu nào hôm nay.")
        return

    # XẾP HẠNG THEO COMPOSITE SCORE (Mean × Skew / Std → đuôi phải + ổn định)
    final_df = pd.DataFrame(results)
    final_df = final_df.sort_values("composite_score", ascending=False).reset_index(drop=True)

    print(f"\nTOP {min(top_n, len(final_df))} TÍN HIỆU MẠNH NHẤT HÔM NAY:")
    print(final_df[['symbol', 'signal_type', 'best_horizon',
                    'best_return', 'best_sharpe', 'best_skew', 'historical_trades']].head(top_n))

    # GỬI DISCORD TOP N
    for _, row in final_df.head(top_n).iterrows():
        post_to_discord(row)

    return final_df