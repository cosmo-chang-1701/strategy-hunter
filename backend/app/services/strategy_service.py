import os
import numpy as np
import httpx
from typing import List, Dict, Any

from .. import schemas

from ..config import settings

# --- 策略搜尋器邏輯 ---

STRATEGY_DATABASE = {
    "Long Call": {
        "name": "Long Call (買入看漲期權)",
        "description": "最基本的看漲策略，支付權利金，賭標的物價格在到期前會大漲。",
        "risk_profile": "風險有限 (最大虧損為付出的權利金)，獲利無限。",
        "categories": ["大漲", "溫和看漲", "IV上升"],
    },
    "Short Put": {
        "name": "Short Put (賣出看跌期權)",
        "description": "溫和看漲或中性的策略，收取權利金，賭標的物價格在到期前不會大跌。",
        "risk_profile": "獲利有限 (最大獲利為收取的權利金)，風險巨大（若股價跌至零）。",
        "categories": ["溫和看漲", "盤整", "IV下降"],
    },
    "Long Put": {
        "name": "Long Put (買入看跌期權)",
        "description": "最基本的看跌策略，支付權利金，賭標的物價格在到期前會大跌。",
        "risk_profile": "風險有限 (最大虧損為付出的權利金)，獲利巨大。",
        "categories": ["大跌", "溫和看跌", "IV上升"],
    },
    "Short Call": {
        "name": "Short Call (賣出看漲期權)",
        "description": "溫和看跌或中性的策略，收取權利金，賭標的物價格在到期前不會大漲。",
        "risk_profile": "獲利有限 (最大獲利為收取的權利金)，風險無限。",
        "categories": ["溫和看跌", "盤整", "IV下降"],
    },
    "Iron Condor": {
        "name": "Iron Condor (鐵兀鷹)",
        "description": "一種中性策略，透過賣出一組價差合約來收取權利金，賭標的物價格在一個特定區間內盤整。",
        "risk_profile": "風險與獲利都有限。",
        "categories": ["盤整", "IV下降"],
    },
    "Short Strangle": {
        "name": "Short Strangle (賣出勒式)",
        "description": "一種中性、高階的策略，賣出不同履約價的 Call 和 Put 來收取權利金，賭標的物價格在一個大區間內盤整。",
        "risk_profile": "獲利有限，風險無限。",
        "categories": ["盤整", "IV下降"],
    },
    "Long Straddle": {
        "name": "Long Straddle (買入跨式)",
        "description": "買入同履約價的 Call 和 Put，賭市場會出現任一方向的劇烈波動，但不確定是哪個方向。",
        "risk_profile": "風險有限，獲利無限。",
        "categories": ["大漲", "大跌", "IV上升"],
    },
}


def find_strategies_by_criteria(
    request: schemas.StrategyFinderRequest,
) -> List[schemas.RecommendedStrategy]:
    """根據使用者輸入的條件，篩選策略。"""
    recommended_strategies = []
    for properties in STRATEGY_DATABASE.values():
        if (
            request.direction.value in properties["categories"]
            and request.volatility.value in properties["categories"]
        ):
            recommended_strategies.append(schemas.RecommendedStrategy(**properties))
    return recommended_strategies


# --- 策略分析器邏輯  ---
async def analyze_strategy_performance(
    strategy: schemas.StrategyDefinition,
) -> Dict[str, Any]:
    """
    接收一個策略定義，回傳完整的分析結果。
    錯誤將被捕捉並以字典形式回傳。
    """
    legs = strategy.legs
    if not legs:
        return {"error": "Strategy must contain at least one leg.", "status_code": 400}

    try:
        # --- 1. 批量獲取所有 leg 的市場快照 ---
        leg_tickers = [leg.option_ticker for leg in legs]
        # 從第一個 leg ticker 推斷標的物 ticker
        # 注意：這假設策略中的所有 leg 都有相同的標的物
        underlying_ticker = leg_tickers[0].split(":")[1][:6].rstrip("0123456789")

        api_key = settings.POLYGON_API_KEY
        if not api_key:
            return {
                "error": "POLYGON_API_KEY environment variable not set.",
                "status_code": 500,
            }

        all_tickers_to_query = leg_tickers + [underlying_ticker]
        tickers_string = ",".join(all_tickers_to_query)
        snapshot_url = (
            f"https://api.polygon.io/v3/snapshot?ticker.any_of={tickers_string}"
        )
        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient() as client:
            snapshot_res = await client.get(snapshot_url, headers=headers)
            snapshot_res.raise_for_status()
            snapshot_data = snapshot_res.json()
            if not snapshot_data.get("results"):
                return {
                    "error": f"Could not fetch snapshot data for tickers: {tickers_string}",
                    "status_code": 404,
                }
            snapshot_map = {snap["ticker"]: snap for snap in snapshot_data["results"]}

        # --- 2. 數據提取與初始計算 ---
        stock_snapshot = snapshot_map.get(underlying_ticker)
        if not stock_snapshot:
            return {
                "error": f"Could not fetch snapshot for underlying stock '{underlying_ticker}'",
                "status_code": 404,
            }

        underlying_price = stock_snapshot.get("session", {}).get(
            "close"
        ) or stock_snapshot.get("last_trade", {}).get("price")
        if underlying_price is None:
            return {
                "error": f"Could not parse price from stock snapshot: {stock_snapshot}",
                "status_code": 400,
            }

        net_cost = 0
        position_greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        processed_legs = []

        for leg in legs:
            snap = snapshot_map.get(leg.option_ticker)
            if not snap or snap.get("error") or not snap.get("greeks"):
                return {
                    "error": f"Could not find valid snapshot data for leg: {leg.option_ticker}",
                    "status_code": 400,
                }

            sign = 1 if leg.action.upper() == "BUY" else -1
            mid_price = (snap["last_quote"]["bid"] + snap["last_quote"]["ask"]) / 2
            net_cost += sign * mid_price * leg.quantity * 100  # 1 contract = 100 shares

            # 累加整個策略的希臘值
            for greek_name in position_greeks:
                position_greeks[greek_name] += (
                    sign * leg.quantity * snap["greeks"][greek_name]
                )

            # 儲存處理過的 Leg 資訊，以供後續計算
            processed_legs.append(
                {
                    "strike": snap["details"]["strike_price"],
                    "type": snap["details"]["contract_type"],
                    "cost_per_share": mid_price * sign,
                    "quantity": leg.quantity,
                }
            )

        # --- 3. 計算到期損益 (P/L) 圖表 ---
        price_range = np.linspace(underlying_price * 0.75, underlying_price * 1.25, 200)
        pl_chart_data = []

        for price_at_expiration in price_range:
            total_profit_loss = 0
            for leg_info in processed_legs:
                if leg_info["type"] == "call":
                    intrinsic_value = max(0, price_at_expiration - leg_info["strike"])
                else:  # put
                    intrinsic_value = max(0, leg_info["strike"] - price_at_expiration)
                pl_per_share = intrinsic_value - leg_info["cost_per_share"]
                total_profit_loss += pl_per_share * leg_info["quantity"] * 100

            pl_chart_data.append(
                {
                    "price_at_expiration": price_at_expiration,
                    "profit_loss": total_profit_loss,
                }
            )

        # --- 4. 計算最大損益與損益兩平點 ---
        profit_losses = [p["profit_loss"] for p in pl_chart_data]
        max_profit = max(profit_losses)
        max_loss = min(profit_losses)

        breakeven_points = []
        for i in range(1, len(pl_chart_data)):
            p1 = pl_chart_data[i - 1]
            p2 = pl_chart_data[i]
            if p1["profit_loss"] * p2["profit_loss"] < 0:
                breakeven = p1["price_at_expiration"] - p1["profit_loss"] * (
                    p2["price_at_expiration"] - p1["price_at_expiration"]
                ) / (p2["profit_loss"] - p1["profit_loss"])
                breakeven_points.append(round(breakeven, 2))

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
            "pl_chart_data": pl_chart_data,
        }
    except httpx.HTTPStatusError as e:
        return {
            "error": f"HTTP error occurred when calling Polygon API: {e.response.text}",
            "status_code": e.response.status_code,
        }
    except Exception as e:
        # 捕捉所有其他未預期的錯誤
        return {
            "error": f"An unexpected error occurred during analysis: {e}",
            "status_code": 500,
        }
