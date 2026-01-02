# analysis/signal_engine/discord_poster.py
import requests
import plotly.graph_objects as go
from .config import SignalConfig

def post_to_discord(row):
    symbol = row['symbol']
    msg = f"""
    **TÍN HIỆU MẠNH ĐƯỢC PHÁT HIỆN** {symbol}
    **Loại:** {row['signal_type']}
    **Giá hiện tại:** {row['current_price']:,.0f} đ
    **Best Horizon:** T+{row['best_horizon']} ngày (Sharpe + Skew cao nhất)
    """
    for h in SignalConfig.HORIZONS:
        msg += f"T+{h} | +{row.get(f'return_{h}d',0)*100:5.1f}% | Sharpe {row.get(f'sharpe_{h}d','?'):4.2f} | Skew {row.get(f'skew_{h}d','?'):4.2f}\n"
        msg += f"\nChart TradingView"
        payload = {
        "content": msg,
        "username": "Quantum Signal Bot"
        }
        requests.post(SignalConfig.DISCORD_WEBHOOK_URL, json=payload)