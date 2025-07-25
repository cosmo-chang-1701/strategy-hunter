import numpy as np
import httpx
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# --- 數據模型 (與 main.py 中的請求/回應對應) ---
class OptionLeg(BaseModel):
    option_ticker: str
    action: str  # "BUY" or "SELL"
    quantity: int

# --- 主要分析函式 ---
async def analyze_strategy(legs: List[OptionLeg]) -> Dict[str, Any]:
    """
    接收一個策略的組成列表，回傳完整的分析結果。
    """
    if not legs:
        return {}

    # --- 1. 批量獲取所有 leg 的市場快照 ---
    leg_tickers = [leg.option_ticker for leg in legs]
    underlying_ticker = leg_tickers[0].split(':')[1][:6].rstrip('0123456789') # 從 "O:AAPL..." 中提取 "AAPL"
    
    api_key = os.getenv("POLYGON_API_KEY")
    all_tickers_to_query = leg_tickers + [underlying_ticker]
    tickers_string = ",".join(all_tickers_to_query)
    snapshot_url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={tickers_string}&apiKey={api_key}"
    
    async with httpx.AsyncClient() as client:
        snapshot_res = await client.get(snapshot_url)
        snapshot_res.raise_for_status()
        snapshot_map = {snap["ticker"]: snap for snap in snapshot_res.json().get("results", [])}

    # --- 2. 數據提取與初始計算 ---
    stock_snapshot = snapshot_map.get(underlying_ticker)
    if not stock_snapshot:
        raise ValueError(f"Could not fetch snapshot for underlying stock '{underlying_ticker}'")
    
    underlying_price = stock_snapshot.get('session', {}).get('close') or stock_snapshot.get('last_trade', {}).get('price')
    if underlying_price is None:
        raise ValueError(f"Could not parse price from stock snapshot: {stock_snapshot}")

    net_cost = 0
    position_greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    processed_legs = []
    
    for leg in legs:
        snap = snapshot_map.get(leg.option_ticker)
        if not snap or snap.get("error") or not snap.get("greeks"):
             raise ValueError(f"Could not find valid snapshot data for leg: {leg.option_ticker}")
        
        sign = 1 if leg.action.upper() == "BUY" else -1
        mid_price = (snap['last_quote']['bid'] + snap['last_quote']['ask']) / 2
        net_cost += sign * mid_price * leg.quantity * 100 # 1 contract = 100 shares

        # 累加整個策略的希臘值
        for greek_name in position_greeks:
            position_greeks[greek_name] += sign * leg.quantity * snap["greeks"][greek_name]
        
        # 儲存處理過的 Leg 資訊，以供後續計算
        processed_legs.append({
            "strike": snap['details']['strike_price'],
            "type": snap['details']['contract_type'],
            "cost_per_share": mid_price * sign,
            "quantity": leg.quantity,
        })

    # --- 3. 計算到期損益 (P/L) 圖表 ---
    # 建立一個價格範圍 (從現價的75%到125%)，並切成200個點
    price_range = np.linspace(underlying_price * 0.75, underlying_price * 1.25, 200)
    pl_chart_data = []
    
    for price_at_expiration in price_range:
        total_profit_loss = 0
        # 計算在某個到期價格下，每個 leg 的損益
        for leg_info in processed_legs:
            # a. 計算到期時的內在價值
            if leg_info["type"] == "call":
                intrinsic_value = max(0, price_at_expiration - leg_info["strike"])
            else: # put
                intrinsic_value = max(0, leg_info["strike"] - price_at_expiration)
            
            # b. 計算單筆損益 (買入為負成本，賣出為正收入)
            #   P/L per share = (到期價值 - 建倉成本)
            #   (建倉成本 = cost_per_share，已包含方向)
            pl_per_share = intrinsic_value - leg_info["cost_per_share"]
            
            # c. 累加到總損益
            total_profit_loss += pl_per_share * leg_info["quantity"] * 100
        
        pl_chart_data.append({
            "price_at_expiration": price_at_expiration,
            "profit_loss": total_profit_loss
        })

    # --- 4. 計算最大損益與損益兩平點 ---
    profit_losses = [p["profit_loss"] for p in pl_chart_data]
    max_profit = max(profit_losses)
    max_loss = min(profit_losses)

    # 簡單的損益兩平點計算 (尋找P/L從負到正或從正到負的點)
    breakeven_points = []
    for i in range(1, len(pl_chart_data)):
        p1 = pl_chart_data[i-1]
        p2 = pl_chart_data[i]
        # 如果損益的正負號改變，代表中間存在損益兩平點
        if p1['profit_loss'] * p2['profit_loss'] < 0:
            # 使用線性內插法找到更精確的交叉點
            breakeven = p1['price_at_expiration'] - p1['profit_loss'] * \
                (p2['price_at_expiration'] - p1['price_at_expiration']) / (p2['profit_loss'] - p1['profit_loss'])
            breakeven_points.append(round(breakeven, 2))

    # TODO: 偵測無限損益的情況 (例如: 單買 Call/Put)，這裡只是模擬區間內的最大值

    # --- 5. 組合並回傳最終結果 ---
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven_points": breakeven_points,
        "net_cost": net_cost,
        "position_delta": position_greeks["delta"],
        "position_gamma": position_greeks["gamma"],
        "position_theta": position_greeks["theta"],
        "position_vega": position_greeks["vega"],
        "pl_chart_data": pl_chart_data
    }